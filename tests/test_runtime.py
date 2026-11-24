import random

import pytest

from genesia.personas import load_cohort
from genesia.runtime import BudgetExceeded, BudgetLedger, EvidenceStore, write_json
from genesia.schemas import BudgetSpec, CohortSpec


def test_compact_model_json_preserves_all_evidence_values():
    import json

    from genesia.runtime import canonical

    payload = {"rows": [{"id": "a1", "value": "Original answer", "refs": ["r1"]}], "missing": None}
    assert json.loads(canonical(payload)) == json.loads(canonical(payload, compact=True)) == payload
    assert len(canonical(payload, compact=True)) < len(canonical(payload))
    assert b"\n" in canonical(payload)


def test_parallel_budget_reservations_are_atomic():
    from concurrent.futures import ThreadPoolExecutor

    from genesia.runtime import BudgetExceeded, BudgetLedger
    from genesia.schemas import BudgetSpec

    ledger = BudgetLedger(BudgetSpec(max_calls=7, max_tokens=700))

    def reserve(_):
        try:
            ledger.reserve(100)
            return True
        except BudgetExceeded:
            return False

    with ThreadPoolExecutor(max_workers=12) as pool:
        assert sum(pool.map(reserve, range(100))) == 7
    assert ledger.summary()["reserved_tokens"] == 700


def test_protected_interviews_survive_parallel_exploration():
    from concurrent.futures import ThreadPoolExecutor

    from genesia.runtime import StageBudgetExceeded

    ledger = BudgetLedger(BudgetSpec(max_calls=10, max_tokens=1000))
    interviews = [ledger.scope(f"research:p{index}", calls=1, tokens=100) for index in range(3)]
    analysis = ledger.scope("analysis", calls=2, tokens=200)
    exploration = ledger.scope("experience")
    with pytest.raises(StageBudgetExceeded):
        exploration.reserve(1001)
    assert ledger.calls == 0

    def explore(_):
        try:
            exploration.reserve(100)
            return True
        except StageBudgetExceeded:
            return False

    with ThreadPoolExecutor(max_workers=12) as pool:
        assert sum(pool.map(explore, range(20))) == 5
    for interview in interviews:
        interview.reserve(100)
        interview.release()
    analysis.reserve(100)
    analysis.reserve(100)
    assert ledger.calls == 10
    assert ledger.summary()["reserved_tokens"] == 1000


def test_stage_deadline_leaves_time_for_research(monkeypatch):
    from genesia import runtime

    clock = [100.0]
    monkeypatch.setattr(runtime.time, "monotonic", lambda: clock[0])
    ledger = BudgetLedger(BudgetSpec(max_seconds=100))
    exploration = ledger.scope("experience", seconds=50)
    research = ledger.scope("research:p1", calls=1, tokens=10, seconds=80)
    clock[0] = 150.0
    with pytest.raises(runtime.StageBudgetExceeded, match="experience"):
        exploration.reserve(1)
    research.reserve(10)
    assert research.remaining_seconds == 30
    assert ledger.remaining_seconds == 50


def test_scope_cannot_take_another_participants_reservation():
    from genesia.runtime import StageBudgetExceeded

    ledger = BudgetLedger(BudgetSpec(max_calls=2, max_tokens=200))
    first = ledger.scope("research:p1", calls=1, tokens=100)
    second = ledger.scope("research:p2", calls=1, tokens=100)
    with pytest.raises(StageBudgetExceeded):
        first.reserve(101)
    first.reserve(50)
    first.release()
    second.reserve(150)
    assert ledger.tokens == 200
    with pytest.raises(ValueError, match="exceed"):
        ledger.scope("analysis", calls=1)


def test_evidence_integrity_and_ownership(tmp_path):
    store = EvidenceStore(tmp_path)
    first = store.put(b"screen", "frame", ".png", persona_id="p1", session_id="s1")
    second = store.put(b"screen", "frame", ".png", persona_id="p2", session_id="s2")
    assert first != second
    assert store.path(first) == store.path(second)
    assert store.verify()["valid"]
    store.path(first).write_bytes(b"changed")
    assert not EvidenceStore(tmp_path).verify()["valid"]


def test_available_capacity_excludes_other_protected_stages():
    ledger = BudgetLedger(BudgetSpec(max_calls=10, max_tokens=1000))
    research = ledger.scope("research", calls=2, tokens=200)
    analysis = ledger.scope("analysis", calls=3, tokens=300)
    ledger.reserve(100)
    assert ledger.available()["calls"] == 4
    assert analysis.available()["tokens"] == 700
    research.reserve(100)
    assert analysis.available()["tokens"] == 700
    research.release()
    assert analysis.available()["tokens"] == 800


def test_budget_checks_before_call():
    ledger = BudgetLedger(BudgetSpec(max_calls=1, max_tokens=10))
    ledger.reserve(5)
    with pytest.raises(BudgetExceeded):
        ledger.reserve(1)
    assert ledger.calls == 1


def test_sampling_is_stable_and_local(tmp_path):
    source = tmp_path / "people.json"
    source.write_text('[{"id":"a","profile":{}},{"id":"b","profile":{}}]', encoding="utf-8")
    state = random.getstate()
    spec = CohortSpec(source=str(source), size=1)
    assert load_cohort(spec) == load_cohort(spec)
    assert random.getstate() == state


def test_missing_persona_fails(tmp_path):
    source = tmp_path / "people.json"
    source.write_text('[{"id":"a","profile":{}}]', encoding="utf-8")
    with pytest.raises(ValueError):
        load_cohort(CohortSpec(source=str(source), ids=["unknown"]))


def test_atomic_replace_retries_only_windows_file_locks(tmp_path, monkeypatch):
    from pathlib import Path

    original = Path.replace
    calls = []

    def locked_once(source, destination):
        calls.append(destination)
        if len(calls) == 1:
            error = PermissionError("Transient sharing violation")
            error.winerror = 32
            raise error
        return original(source, destination)

    monkeypatch.setattr(Path, "replace", locked_once)
    write_json(tmp_path / "state.json", {"persisted": True})
    assert len(calls) == 2
    assert (tmp_path / "state.json").exists()
