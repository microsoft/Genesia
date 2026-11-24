import json

import pytest

from genesia.runtime import (
    BudgetLedger,
    EvidenceStore,
    ModelFailure,
    OpenAICompatibleGateway,
    model_prompt,
)
from genesia.schemas import BudgetSpec, ModelSpec, SessionIntent


class Response:
    status_code = 200

    def __init__(self, text):
        self.text = text

    def json(self):
        return {"choices": [{"message": {"content": self.text}}], "usage": {"total_tokens": 12}}


@pytest.mark.parametrize("temperature", [None, 0.85])
def test_request_estimate_matches_gateway_reservation(tmp_path, monkeypatch, temperature):
    config = ModelSpec(
        base_url="http://127.0.0.1:8000/v1", api_key_env=None, model="fixture", temperature=temperature
    )
    ledger = BudgetLedger(BudgetSpec())
    gateway = OpenAICompatibleGateway(config, EvidenceStore(tmp_path), ledger)
    payload = {"rows": [{"value": "Original answer", "ref": "a1"}]}
    expected_prompt = model_prompt("intent", payload, SessionIntent)

    def post(*args, **kwargs):
        assert kwargs["json"]["messages"][0]["content"][0]["text"] == expected_prompt
        assert ("temperature" in kwargs["json"]) == (temperature is not None)
        if temperature is not None:
            assert kwargs["json"]["temperature"] == temperature
        return Response(json.dumps(dict(goal="Test", preferences="Simple", completion_standard="Done")))

    monkeypatch.setattr(gateway.http, "post", post)
    gateway.complete("intent", payload, SessionIntent)
    assert ledger.tokens == len(expected_prompt.encode("utf-8")) + config.max_tokens
    gateway.close()


def test_interleaved_timeline_places_each_image_beside_its_step(tmp_path, monkeypatch):
    config = ModelSpec(base_url="http://127.0.0.1:8000/v1", api_key_env=None, model="fixture")
    ledger = BudgetLedger(BudgetSpec())
    store = EvidenceStore(tmp_path)
    image_ref = store.put(b"image-bytes", "frame", ".jpg")
    gateway = OpenAICompatibleGateway(config, store, ledger)
    request = {}
    payload = {
        "persona_role_policy": "Stay in character.",
        "instruction": "Answer from the recorded experience.",
        "participant": {"id": "p1"},
        "evidence_selection": {"attached_images": 1},
        "prior_batch_answers": [],
        "experience_timeline": [
            {
                "step_id": "step-1",
                "stage_before": 1,
                "stage_after": 1,
                "candidate_before": "Version A",
                "candidate_after": "Version A",
                "before": {"page": "Overview"},
                "after": {"page": "Colors"},
                "attached_images": [{"role": "after", "ref": image_ref}],
                "action": {"action": "click"},
            },
            {
                "step_id": "step-2",
                "stage_before": 1,
                "stage_after": 1,
                "candidate_before": "Version A",
                "candidate_after": "Version A",
                "before": {"page": "Colors"},
                "after": {"page": "Colors"},
                "attached_images": [{"role": "before", "ref": image_ref}],
                "action": {"action": "stop"},
            },
        ],
    }

    def post(*args, **kwargs):
        request.update(kwargs["json"])
        return Response(json.dumps(dict(goal="Done", preferences="Simple", completion_standard="Done")))

    monkeypatch.setattr(gateway.http, "post", post)
    gateway.complete(
        "persona_research",
        payload,
        SessionIntent,
        interleave_key="experience_timeline",
        output_contract='Return {"goal":"...","preferences":"...","completion_standard":"..."}',
    )
    content = request["messages"][0]["content"]
    assert [item["type"] for item in content] == ["text", "text", "image_url", "text", "text"]
    assert "experience_timeline" not in content[0]["text"]
    assert "evidence_selection" not in content[0]["text"]
    assert "prior_batch_answers" not in content[0]["text"]
    assert "step-1" in content[1]["text"]
    assert "images_following" in content[1]["text"]
    assert image_ref not in content[1]["text"]
    assert "observation_id" not in content[1]["text"]
    assert "http://" not in content[1]["text"]
    assert '"candidate":"Version A"' in content[1]["text"]
    assert '"page_transition":{"from":"Overview","to":"Colors"}' in content[1]["text"]
    assert "stage_before" not in content[1]["text"]
    assert "page_before" not in content[1]["text"]
    assert content[2]["type"] == "image_url"
    assert "step-2" in content[3]["text"]
    assert content[4]["text"].startswith("OUTPUT FORMAT:")
    assert "$defs" not in content[4]["text"]
    assert sum(item["type"] == "image_url" for item in content) == 1
    expected = (
        sum(len(item["text"].encode("utf-8")) for item in content if item["type"] == "text")
        + len(b"image-bytes") // 64
        + config.max_tokens
    )
    assert ledger.tokens == expected
    gateway.close()


@pytest.mark.parametrize("initial_only", [False, True])
def test_material_text_reaches_http_request_with_images_and_without_internal_ids(
    tmp_path, monkeypatch, initial_only
):
    from genesia.agents import experience_timeline
    from genesia.schemas import Action, Episode, ExecutionResult, Observation, Persona, Step

    store = EvidenceStore(tmp_path)
    images = [store.put(f"image-{index}".encode(), "source_image", ".png") for index in range(2)]
    observations = [
        Observation(
            id=f"private-observation-{index}",
            mode="cards",
            text=f"MATERIAL_TEXT_{index}",
            card_ids=[f"private-card-{index}"],
            image_refs=[ref],
            evidence_refs=[ref],
        )
        for index, ref in enumerate(images)
    ]
    episode = Episode(
        session_id="private-session",
        persona=Persona(id="private-persona", profile={}),
        goal="Read the supplied materials",
        mode="cards",
        final_observation=observations[0] if initial_only else observations[1],
    )
    if not initial_only:
        episode.steps = [
            Step(
                number=1,
                observation=observations[0],
                action=Action(action="click", target_id="next", intent="Continue"),
                result=ExecutionResult(success=True, message="Advanced supplied material"),
            ),
            Step(
                number=2,
                observation=observations[1],
                action=Action(action="stop", intent="Enough context", outcome="completed"),
                result=ExecutionResult(success=True, message="Stopped"),
            ),
        ]
    payload = {"experience_timeline": experience_timeline(episode, set(images), complete=True)}
    config = ModelSpec(base_url="http://127.0.0.1:8000/v1", api_key_env=None, model="fixture")
    ledger = BudgetLedger(BudgetSpec())
    gateway = OpenAICompatibleGateway(config, store, ledger)
    request = {}

    def post(*args, **kwargs):
        request.update(kwargs["json"])
        return Response(json.dumps(dict(goal="Done", preferences="Simple", completion_standard="Done")))

    monkeypatch.setattr(gateway.http, "post", post)
    try:
        gateway.complete("persona_research", payload, SessionIntent, interleave_key="experience_timeline")
    finally:
        gateway.close()
    content = request["messages"][0]["content"]
    text = "\n".join(item["text"] for item in content if item["type"] == "text")
    assert text.count(observations[0].text) == 1
    assert text.count(observations[1].text) == (0 if initial_only else 1)
    assert "private-observation" not in text and "private-card" not in text
    assert all(ref not in text for ref in images)
    timeline_items = [
        json.loads(item["text"].split("\n", 1)[1])
        for item in content
        if item["type"] == "text" and item["text"].startswith("EXPERIENCE TIMELINE ITEM:")
    ]
    assert [entry["role"] for entry in timeline_items[0]["materials"]] == (
        ["after"] if initial_only else ["before", "after"]
    )
    if not initial_only:
        assert "materials" not in timeline_items[1]
    attached = images[:1] if initial_only else images
    assert sum(item["type"] == "image_url" for item in content) == len(attached)
    assert ledger.tokens == (
        sum(len(item["text"].encode("utf-8")) for item in content if item["type"] == "text")
        + sum(len(store.path(ref).read_bytes()) for ref in attached) // 64
        + config.max_tokens
    )


def test_model_retry_audited(tmp_path, monkeypatch):
    store = EvidenceStore(tmp_path)
    gateway = OpenAICompatibleGateway(
        ModelSpec(base_url="http://127.0.0.1:8000/v1", api_key_env=None, model="fixture"),
        store,
        BudgetLedger(BudgetSpec()),
    )
    replies = iter(
        [
            Response("not JSON"),
            Response(json.dumps(dict(goal="Test", preferences="Simple", completion_standard="Done"))),
        ]
    )
    monkeypatch.setattr(gateway.http, "post", lambda *args, **kwargs: next(replies))
    assert gateway.complete("intent", {}, SessionIntent).goal == "Test"
    events = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert sum(event["event"] == "model_attempt" for event in events) == 2
    assert gateway.budget.calls == 2


def test_transport_no_blind_retries(tmp_path, monkeypatch):
    gateway = OpenAICompatibleGateway(
        ModelSpec(base_url="http://127.0.0.1:8000/v1", api_key_env=None, model="fixture"),
        EvidenceStore(tmp_path),
        BudgetLedger(BudgetSpec()),
    )
    response = Response("")
    response.status_code = 503
    monkeypatch.setattr(gateway.http, "post", lambda *args, **kwargs: response)
    with pytest.raises(ModelFailure):
        gateway.complete("intent", {}, SessionIntent)
    assert gateway.budget.calls == 1


@pytest.mark.parametrize("status", [401, 402, 429, 503])
def test_inference_http_status_is_preserved_without_response_body(tmp_path, monkeypatch, status):
    gateway = OpenAICompatibleGateway(
        ModelSpec(base_url="http://127.0.0.1:8000/v1", api_key_env=None, model="fixture"),
        EvidenceStore(tmp_path),
        BudgetLedger(BudgetSpec()),
    )
    response = Response("private response credentials must not be logged")
    response.status_code = status
    monkeypatch.setattr(gateway.http, "post", lambda *args, **kwargs: response)
    with pytest.raises(ModelFailure, match=f"HTTP {status}"):
        gateway.complete("intent", {}, SessionIntent)
    events = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert f"HTTP {status}" in events and response.text not in events
    assert gateway.budget.calls == 1
    gateway.close()


def test_exploration_request_timeout_respects_protected_time(tmp_path, monkeypatch):
    import requests

    from genesia import runtime

    clock = [0.0]
    monkeypatch.setattr(runtime.time, "monotonic", lambda: clock[0])
    ledger = BudgetLedger(BudgetSpec(max_seconds=20))
    exploration = ledger.scope("experience", seconds=5)
    research = ledger.scope("research:p1", calls=1, tokens=10, seconds=15)
    gateway = OpenAICompatibleGateway(
        ModelSpec(base_url="http://127.0.0.1:8000/v1", api_key_env=None, model="fixture"),
        EvidenceStore(tmp_path),
        exploration,
    )

    def timeout(*args, **kwargs):
        assert kwargs["timeout"] == 5
        clock[0] = 5.0
        raise requests.Timeout("Stage window ended")

    monkeypatch.setattr(gateway.http, "post", timeout)
    with pytest.raises(runtime.StageBudgetExceeded, match="experience"):
        gateway.complete("persona_action", {}, SessionIntent)
    research.reserve(10)
    gateway.close()


def test_openai_compatible_endpoint_uses_environment_key_without_storing_it(tmp_path, monkeypatch):
    secret = "fixture-secret-that-must-not-be-written"
    monkeypatch.setenv("EXAMPLE_API_KEY", secret)
    config = ModelSpec(
        provider="openai_compatible",
        base_url="https://api.example.com/v1",
        model="vision-model",
        api_key_env="EXAMPLE_API_KEY",
        token_limit_field="max_tokens",
    )
    store = EvidenceStore(tmp_path)
    gateway = OpenAICompatibleGateway(config, store, BudgetLedger(BudgetSpec()))
    request = {}

    def post(url, **kwargs):
        request.update(url=url, **kwargs)
        return Response(json.dumps(dict(goal="Test", preferences="Simple", completion_standard="Done")))

    monkeypatch.setattr(gateway.http, "post", post)
    assert gateway.complete("intent", {}, SessionIntent).goal == "Test"
    assert request["url"] == "https://api.example.com/v1/chat/completions"
    assert request["headers"] == {"Authorization": f"Bearer {secret}"}
    assert request["json"]["max_tokens"] == config.max_tokens
    assert "max_completion_tokens" not in request["json"]
    assert secret not in "".join(path.read_text("utf-8") for path in tmp_path.rglob("*.json"))
