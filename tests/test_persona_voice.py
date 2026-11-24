import copy
import json

import pytest

from genesia.agents import (
    PersonaAgent,
    answer_role_policy,
    answer_voice_instruction,
    default_interview_instruction,
    persona_role_policy,
    profile_survey_instruction,
    research_instruction,
    survey_answer_policy,
    survey_response_policy,
)
from genesia.runtime import (
    BudgetLedger,
    EvidenceStore,
    OpenAICompatibleGateway,
    canonical,
    model_content,
)
from genesia.schemas import (
    BudgetSpec,
    Episode,
    MethodSpec,
    ModelSpec,
    Observation,
    Persona,
    SessionIntent,
)


def test_answer_policy_changes_are_scoped_copies_not_shared_intent_resources():
    role = persona_role_policy()
    survey = survey_response_policy()
    assert answer_role_policy() == role.replace("stable session intent", "stable task orientation").replace(
        "that shaped your use.", "that characterize you in this context."
    )
    assert "stable session intent" in persona_role_policy()
    assert "that shaped your use." in persona_role_policy()
    prefix, rest = survey.split("#### Open Text\n", 1)
    _, suffix = rest.split("### 4. Survey Consistency", 1)
    updated = survey_answer_policy()
    assert updated.startswith(prefix + "#### Open Text\n")
    assert updated.split("### 4. Survey Consistency", 1)[1] == suffix
    assert "normally 2-4 sentences" not in updated
    assert "normally 2-4 sentences" in survey_response_policy()
    assert "There is no common sentence count" in updated
    assert persona_role_policy() == role and survey_response_policy() == survey


def test_interview_keeps_existing_rules_examples_and_adds_exact_shared_voice():
    voice = answer_voice_instruction()
    interview = default_interview_instruction()
    assert interview.endswith("\n\n" + voice)
    assert research_instruction() in interview
    assert "Same preference, different personal reasons" in interview
    assert "do not copy these facts, preferences, phrases or answer structure" in interview
    assert "Supplied material is not proof of live product execution." in interview
    assert "For survey-only input" in research_instruction()
    assert "Grounding and response rules:" not in interview
    assert "questionnaire about a hypothetical idea" not in interview
    assert "questionnaire about a hypothetical idea" in profile_survey_instruction()
    assert voice in profile_survey_instruction()
    assert "not a script or a replacement for the complete profile" in voice
    assert "Do not manufacture differences" in voice


@pytest.mark.parametrize("purpose", ["persona_intent", "persona_action", "environment_readiness"])
@pytest.mark.parametrize("interleaved", [False, True])
def test_non_answer_wire_format_stays_at_baseline(tmp_path, purpose, interleaved):
    payload = {
        "persona_role_policy": "Unchanged role.",
        "instruction": "Unchanged stage instruction.",
        "persona": {"profile": {"goal": "Intrinsic goal", "notes": "Original wording"}},
        "experience_timeline": [],
    }
    original = copy.deepcopy(payload)
    kwargs = {"interleave_key": "experience_timeline"} if interleaved else {}
    parts, _ = model_content(purpose, payload, SessionIntent, EvidenceStore(tmp_path), **kwargs)
    assert payload == original
    assert "SUPPLIED DATA:" not in parts[0]["text"]
    assert "Provide brief participant intent, not hidden chain-of-thought." in parts[0]["text"]
    assert "Provide the requested participant answers" not in parts[0]["text"]
    if interleaved:
        assert (
            "BASE PAYLOAD:\n" + canonical({"persona": payload["persona"]}, compact=True).decode()
            in parts[0]["text"]
        )
    else:
        visible = dict(payload)
        if purpose in {"persona_intent", "persona_action"}:
            del visible["persona_role_policy"]
            del visible["instruction"]
        assert "PAYLOAD:\n" + canonical(visible, compact=True).decode() in parts[0]["text"]


@pytest.mark.parametrize(
    ("mode", "kind"),
    [
        ("survey", "survey"),
        ("live", "interview"),
        ("cards", "interview"),
        ("captured_graph", "interview"),
        ("cards", "survey"),
    ],
)
def test_native_answer_wire_keeps_context_history_contract_and_retry(tmp_path, monkeypatch, mode, kind):
    store = EvidenceStore(tmp_path)
    image = store.put(b"fixture-image-content", "frame", ".png")
    observation = Observation(
        id="owned-observation",
        mode=mode,
        text="Original material passage",
        image_refs=[] if mode == "survey" else [image],
        evidence_refs=[] if mode == "survey" else [image],
    )
    intent = SessionIntent(goal="Personal orientation", preferences="Careful", completion_standard="Checked")
    person = Persona(
        id="p1",
        profile={
            "communication_style": "Brief and direct",
            "motivations": "Intrinsic motivation",
            "personal_goal": "Keep this full-profile goal",
            "notes": "A literal\nmultiline profile field",
        },
    )
    episode = Episode(
        session_id="owned-session",
        persona=person,
        goal="Original study background",
        mode=mode,
        phase="research",
        intent=intent,
        final_observation=None if mode == "survey" else observation,
    )
    method = MethodSpec(
        id="questions",
        kind=kind,
        batch_size=1,
        max_followups=0,
        questions=[
            {"id": "choice", "text": "Which?", "kind": "single", "options": ["A", "B"], "explain": True},
            {"id": "conditional", "text": "Why?", "ask_if": {"choice": "B"}},
            {"id": "detail", "text": "What matters?"},
        ],
    )
    budget = BudgetLedger(BudgetSpec())
    gateway = OpenAICompatibleGateway(
        ModelSpec(base_url="http://127.0.0.1:8000/v1", api_key_env=None, model="fixture"), store, budget
    )
    sent = []

    class Response:
        status_code = 200

        def __init__(self, value):
            self.value = value

        def json(self):
            return {"choices": [{"message": {"content": self.value}}]}

    def post(*args, **kwargs):
        content = kwargs["json"]["messages"][0]["content"]
        sent.append(content)
        if len(sent) == 1:
            return Response("invalid JSON")
        contract = content[-1]["text"]
        example = json.loads(next(line for line in contract.splitlines() if line.startswith('{"answers"')))
        values = [
            {
                "question_id": row["question_id"],
                "value": "A" if row["question_id"] == "choice" else "My answer",
            }
            for row in example["answers"]
        ]
        if values[0]["question_id"] == "choice":
            values[0]["reason"] = "My stated reason."
        return Response(json.dumps({"answers": values}))

    monkeypatch.setattr(gateway.http, "post", post)
    try:
        response = PersonaAgent(episode, gateway, store, budget).research(method)
    finally:
        gateway.close()
    assert response.valid, response.error
    assert len(sent) == 3 and budget.calls == 3
    assert response.answers[1].basis == "skipped"
    assert response.answers[0].reason == "My stated reason."
    for content in sent:
        text = content[0]["text"]
        assert "Original study background" in text and "Personal orientation" in text
        assert all(value in text for value in person.profile.values())
        assert "## Role Consistency" in text and "## Continuity During Research" in text
        assert "not a script or a replacement for the complete profile" in text
        assert "Provide the requested participant answers" in text
        assert (
            "<this person's answer>" in content[-1]["text"]
            or "<exactly one option: A | B>" in content[-1]["text"]
        )
        if kind == "survey":
            assert text.index("Survey Response Policy") < text.index("Approved synthetic research.")
            assert "### 4. Survey Consistency" in text and "normally 2-4 sentences" not in text
        if mode == "survey":
            assert "questionnaire about a hypothetical idea" in text
            assert "You have finished trying the product" not in text
            assert not any(part["type"] == "image_url" for part in content)
        else:
            if mode != "live":
                assert "Original material passage" in "\n".join(
                    p["text"] for p in content if p["type"] == "text"
                )
            assert sum(p["type"] == "image_url" for p in content) == 1
            assert "You have finished trying the product" in text
    assert "Return one corrected JSON object." in sent[1][-1]["text"]
    assert "prior batch answers" in sent[-1][0]["text"]
    assert "My stated reason." in sent[-1][0]["text"]
    assert store.verify()["valid"]


def test_survey_intent_still_uses_original_role_and_survey_policy(tmp_path):
    from test_workflow import ScriptedModel

    episode = Episode(
        session_id="survey-session",
        persona=Persona(id="p1", profile={"communication": "Concise"}),
        goal="Original study goal",
        mode="survey",
    )
    model = ScriptedModel()
    agent = PersonaAgent(episode, model, EvidenceStore(tmp_path), BudgetLedger(BudgetSpec()))
    agent.begin_survey()
    [(purpose, payload)] = model.calls
    assert purpose == "persona_intent"
    assert payload["persona_role_policy"] == persona_role_policy()
    assert payload["survey_response_policy"] == survey_response_policy()
    assert "normally 2-4 sentences" in payload["survey_response_policy"]
    assert answer_voice_instruction() not in payload["instruction"]
