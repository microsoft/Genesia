from __future__ import annotations

import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .persona_generation import (
    _generation_snapshot_fields,
    _normalize_candidate_for_slot,
    _recover_generation_checkpoint,
    _run_bounded,
    _task_gateway,
    _validate_candidate_for_slot,
    _validate_candidate_response,
    compile_persona_slots,
    generate_personas,
    load_cohort_plan,
    validate_confirmed_plan,
)
from .personas import generation_artifact_issues
from .runtime import (
    BudgetExceeded,
    BudgetLedger,
    EvidenceStore,
    ModelFailure,
    OpenAICompatibleGateway,
    canonical,
    digest,
    write_json,
)
from .schemas import (
    BudgetSpec,
    ModelSpec,
    PersonaCandidateResponse,
    PersonaGenerationManifest,
)


def _recovery_inputs(source: Path, timeout_seconds: int):
    if not 1 <= timeout_seconds <= 600:
        raise ValueError("Recovery timeout_seconds must be between 1 and 600")
    manifest_path = source / "generation-manifest.json"
    manifest = PersonaGenerationManifest.model_validate_json(manifest_path.read_text("utf-8"))
    if (
        manifest.status != "partial"
        or (source / "transport-recovery.json").exists()
        or (source / "personas.json").exists()
        or (source / "cohort-approval.json").exists()
    ):
        raise ValueError("Transport recovery requires an original, unapproved terminal partial generation")
    issues = generation_artifact_issues(source, manifest)
    if issues:
        raise ValueError("; ".join(issues))
    plan = load_cohort_plan(source / "cohort-plan.yaml")
    validate_confirmed_plan(plan)
    if plan.plan_sha256 != manifest.plan_sha256 or plan.candidates_per_slot != 1:
        raise ValueError("Transport recovery requires the unchanged confirmed single-candidate plan")
    store = EvidenceStore(source)
    if not store.verify()["valid"]:
        raise ValueError("Transport recovery source evidence verification failed")
    snapshot_path = source / "execution-snapshot.json"
    snapshot = json.loads(snapshot_path.read_text("utf-8"))
    if digest(snapshot_path.read_bytes()) != manifest.execution_snapshot_sha256:
        raise ValueError("Transport recovery source execution snapshot does not match its manifest")
    for key, expected in _generation_snapshot_fields(plan).items():
        if snapshot.get(key) != expected:
            raise ValueError(f"Transport recovery source policy or schema changed: {key}")
    slots, _ = compile_persona_slots(plan)
    checkpoint = _recover_generation_checkpoint(plan, slots, store, manifest.execution_snapshot_sha256)
    ledger = json.loads((source / "candidate-personas.json").read_text("utf-8"))
    retained = {value["candidate_id"]: value for value in ledger if value["selection_status"] == "selected"}
    if (
        len(retained) != len(manifest.selected_persona_ids)
        or {value["selected_persona_id"] for value in retained.values()} != set(manifest.selected_persona_ids)
        or len(checkpoint.slots) != plan.sample_size
    ):
        raise ValueError("Transport recovery selected profiles do not match the original cohort")
    for candidate_id, candidate in retained.items():
        item = checkpoint.slots[candidate_id]
        if (
            item.stage != "reviewed"
            or item.candidate is None
            or item.candidate["profile"] != candidate["profile"]
            or item.candidate["risk_review"] != candidate["risk_review"]
            or digest(canonical(candidate["profile"], compact=True)) != candidate["profile_sha256"]
        ):
            raise ValueError("Transport recovery retained profile is missing its exact review evidence")
    events = [
        json.loads(line) for line in (source / "events.jsonl").read_text("utf-8").splitlines() if line.strip()
    ]
    source_model = ModelSpec.model_validate(snapshot["model"])
    requests = {}
    for candidate_id, item in checkpoint.slots.items():
        if candidate_id in retained:
            continue
        if (
            item.stage != "failed"
            or item.candidate is not None
            or item.review_attempts != 0
            or item.generation_attempts != 2
        ):
            raise ValueError("Transport recovery cannot regenerate a returned or quality-rejected profile")
        request_ref = item.generation_request_refs[-1]
        payload = json.loads(store.path(request_ref).read_text("utf-8"))
        model_refs = [
            ref.id
            for ref in store.refs.values()
            if ref.kind == "model_request"
            and (request := json.loads(store.path(ref.id).read_text("utf-8")))["purpose"]
            == "persona_candidate_generation"
            and request["payload"] == payload
        ]
        if len(model_refs) != 1:
            raise ValueError("Transport recovery cannot identify the original model request")
        model_ref = model_refs[0]
        attempts = [
            event
            for event in events
            if event["event"] == "model_attempt" and event["request_ref"] == model_ref
        ]
        outcomes = [
            event
            for event in events
            if event["event"] in {"model_invalid", "model_validated"} and event["request_ref"] == model_ref
        ]
        failures = [
            ref.id
            for ref in store.refs.values()
            if ref.kind == "persona_generation_failure"
            and ref.persona_id == candidate_id
            and json.loads(store.path(ref.id).read_text("utf-8"))["request_ref"] == request_ref
        ]
        if (
            not attempts
            or [event["attempt"] for event in attempts] != list(range(1, len(attempts) + 1))
            or len(attempts) >= source_model.attempts
            or max(event["attempt"] for event in attempts) >= source_model.attempts
            or not outcomes
            or outcomes[-1]["event"] != "model_invalid"
            or outcomes[-1].get("error") != "ReadTimeout"
            or len(failures) != 1
            or "ReadTimeout" not in (item.issue or "")
        ):
            raise ValueError("Transport recovery requires a recorded ReadTimeout with provider attempts left")
        requests[candidate_id] = {
            "request_ref": request_ref,
            "failure_ref": failures[0],
            "model_request_ref": model_ref,
            "generation_attempts": item.generation_attempts,
            "previous_provider_attempts": len(attempts),
            "additional_provider_attempts": 1,
        }
    if not requests or len(retained) + len(requests) != plan.sample_size:
        raise ValueError("Transport recovery must account for every immutable cohort slot")
    source_budget = BudgetSpec.model_validate(snapshot["budget"])
    spent = [event for event in events if event["event"] == "model_attempt"]
    used_tokens = sum(event["reserved_tokens"] for event in spent)
    recovery_started = datetime.now(timezone.utc)
    elapsed = (recovery_started - datetime.fromisoformat(snapshot["created_at"])).total_seconds()
    remaining_seconds = source_budget.max_seconds - elapsed
    remaining_calls = source_budget.max_calls - len(spent)
    remaining_tokens = source_budget.max_tokens - used_tokens
    if remaining_seconds < 1 or remaining_calls < 2 * len(requests) + 1 or remaining_tokens <= 0:
        raise ValueError("Original generation budget has no capacity for bounded transport recovery")
    model = ModelSpec.model_validate(
        {**source_model.model_dump(mode="json"), "timeout_seconds": timeout_seconds, "attempts": 1}
    )
    budget = BudgetSpec(
        max_calls=min(remaining_calls, 3 * len(requests) + 1),
        max_tokens=remaining_tokens,
        max_seconds=int(min(remaining_seconds, (3 * len(requests) + 1) * timeout_seconds)),
    )
    authorization = {
        "version": 1,
        "kind": "transport_only_recovery",
        "created_at": recovery_started.isoformat(),
        "source_manifest_sha256": digest(manifest_path.read_bytes()),
        "source_snapshot_sha256": manifest.execution_snapshot_sha256,
        "source_model": source_model.model_dump(mode="json"),
        "source_budget": source_budget.model_dump(mode="json"),
        "source_model_attempts": len(spent),
        "source_reserved_units": used_tokens,
        "source_elapsed_seconds": elapsed,
        "requests": requests,
        "retained_persona_ids": {key: value["selected_persona_id"] for key, value in retained.items()},
        "retained_profile_sha256": {key: value["profile_sha256"] for key, value in retained.items()},
        "new_model": model.model_dump(mode="json"),
        "new_budget": budget.model_dump(mode="json"),
        "remote_cancellation_verified": False,
    }
    return plan, manifest, store, model, budget, authorization


def recover_personas(
    generation_dir: str | Path,
    output_dir: str | Path,
    *,
    timeout_seconds: int = 300,
    max_workers: int = 2,
    resume: bool = False,
    progress: Callable[[str], None] | None = None,
) -> PersonaGenerationManifest:
    """Derive a bounded transport-only continuation without modifying its terminal source."""
    source, root = Path(generation_dir).resolve(), Path(output_dir).resolve()
    if source.is_relative_to(root) or root.is_relative_to(source):
        raise ValueError("Recovery output must be separate from its source generation")
    if not 1 <= max_workers <= 16:
        raise ValueError("max_workers must be between 1 and 16")
    if (root / "generation-manifest.json").exists():
        raise ValueError("Generation directory is immutable once a manifest exists")
    if root.exists() and any(root.iterdir()) and not resume:
        raise ValueError("Recovery output exists; use resume=True for this same interrupted recovery")
    if resume and not (root / "transport-recovery.json").is_file():
        raise ValueError("Cannot resume an output without a recorded transport recovery")
    plan, manifest, source_store, model, budget_spec, authorization = _recovery_inputs(
        source, timeout_seconds
    )
    if resume:
        saved = json.loads((root / "transport-recovery.json").read_text("utf-8"))
        if (
            saved["source_manifest_sha256"] != authorization["source_manifest_sha256"]
            or saved["new_model"] != model.model_dump(mode="json")
            or saved["requests"] != authorization["requests"]
        ):
            raise ValueError("Transport recovery configuration changed")
        authorization = saved
        budget_spec = BudgetSpec.model_validate(saved["new_budget"])
        snapshot = json.loads((root / "execution-snapshot.json").read_text("utf-8"))
    else:
        root.mkdir(parents=True, exist_ok=True)
        archive = root / "source-generation"
        source_files = {
            *manifest.artifact_hashes,
            "generation-manifest.json",
            "evidence.json",
            "events.jsonl",
            *(ref.path for ref in source_store.refs.values()),
        }
        for name in sorted(source_files):
            path = (source / name).resolve()
            if not path.is_relative_to(source):
                raise ValueError("Recovery source path escapes its generation")
            target = archive / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        copy_names = {
            "cohort-plan.yaml",
            "plan-review.json",
            "slots.json",
            "evidence.json",
            "events.jsonl",
            *(ref.path for ref in source_store.refs.values()),
        }
        for name in copy_names:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / name, target)
        write_json(root / "transport-recovery.json", authorization)
        snapshot = {
            **_generation_snapshot_fields(
                plan,
                {
                    "model": model.model_dump(mode="json"),
                    "budget": budget_spec.model_dump(mode="json"),
                    "transport_recovery": {
                        "source_manifest_sha256": authorization["source_manifest_sha256"],
                        "authorization_sha256": digest(canonical(authorization)),
                        "retained_persona_ids": authorization["retained_persona_ids"],
                    },
                },
            ),
            "created_at": authorization["created_at"],
        }
        write_json(root / "execution-snapshot.json", snapshot)
    store = EvidenceStore(root)
    if not store.verify()["valid"] or not EvidenceStore(root / "source-generation").verify()["valid"]:
        raise ValueError("Transport recovery evidence verification failed")
    authorization_refs = [ref.id for ref in store.refs.values() if ref.kind == "persona_transport_recovery"]
    authorization_ref = (
        authorization_refs[0]
        if authorization_refs
        else store.json(authorization, "persona_transport_recovery")
    )
    ledger = BudgetLedger(budget_spec)
    ledger.started = (
        time.monotonic()
        - (datetime.now(timezone.utc) - datetime.fromisoformat(snapshot["created_at"])).total_seconds()
    )
    events = [
        json.loads(line) for line in (root / "events.jsonl").read_text("utf-8").splitlines() if line.strip()
    ]
    new_attempts = [event for event in events if event["event"] == "model_attempt"][
        authorization["source_model_attempts"] :
    ]
    ledger.calls = len(new_attempts)
    ledger.tokens = sum(event["reserved_tokens"] for event in new_attempts)
    ledger.check()
    slot_by_id = {slot.slot_id: slot for slot in compile_persona_slots(plan)[0]}
    retried = {
        ref.persona_id for ref in store.refs.values() if ref.kind == "persona_generation_transport_retry"
    }
    gateway = OpenAICompatibleGateway(model, store, ledger)

    def retry(candidate_id: str) -> None:
        request = authorization["requests"][candidate_id]
        store.json(
            {
                "authorization_ref": authorization_ref,
                "request_ref": request["request_ref"],
                "failure_ref": request["failure_ref"],
            },
            "persona_generation_transport_retry",
            persona_id=candidate_id,
        )
        worker, owned = _task_gateway(gateway, max_workers)
        try:
            payload = json.loads(store.path(request["request_ref"]).read_text("utf-8"))
            slot_id = payload["slot"]["slot_id"]
            response = worker.complete(
                "persona_candidate_generation",
                payload,
                PersonaCandidateResponse,
                validate=_validate_candidate_response,
            )
            response = _normalize_candidate_for_slot(response, slot_by_id[slot_id])
            _validate_candidate_for_slot(response, slot_by_id[slot_id])
            store.json(response, "persona_generation_response", persona_id=candidate_id)
        except (ModelFailure, BudgetExceeded, ValueError) as error:
            store.json(
                {
                    "request_ref": request["request_ref"],
                    "issue": f"transport_recovery_failed:{type(error).__name__}: {error}",
                },
                "persona_generation_failure",
                persona_id=candidate_id,
            )
            if progress:
                progress(f"{candidate_id} transport recovery failed: {error}")
        finally:
            if owned:
                worker.close()

    try:
        for _ in _run_bounded(
            [key for key in authorization["requests"] if key not in retried], retry, max_workers
        ):
            pass
        return generate_personas(
            plan,
            root,
            gateway=gateway,
            store=store,
            resume=True,
            max_workers=max_workers,
            execution_snapshot={key: snapshot[key] for key in ("model", "budget", "transport_recovery")},
            progress=progress,
        )
    finally:
        gateway.close()
