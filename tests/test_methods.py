from pathlib import Path

import pytest
from test_workflow import ScriptedModel, task_fixture

from genesia.api import run
from genesia.schemas import MethodSpec, TaskSpec


class InterviewModel(ScriptedModel):
    def complete(self, purpose, payload, schema, **kwargs):
        if purpose == "interview_moderator":
            assert "persona_role_policy" not in payload
            assert "survey_response_policy" not in payload
            return schema.model_validate(
                dict(
                    ask=not payload["followups"],
                    parent_question_id="base",
                    text="What made it clear?",
                    reason="Clarify participant's answer",
                )
            )
        return super().complete(purpose, payload, schema, **kwargs)


def test_choice_explanation_preserves_value_and_requires_reason():
    from genesia.agents import answer_schema, validate_answers

    method = MethodSpec(
        id="choice",
        kind="interview",
        questions=[
            dict(
                id="preference",
                text="Which and why?",
                kind="single",
                options=["A", "B", "No preference"],
                explain=True,
            )
        ],
    )
    schema = answer_schema(method)
    value = schema.model_validate(
        dict(answers=[dict(question_id="preference", value="A", evidence_refs=["e1"])])
    )
    with pytest.raises(ValueError, match="requires a concrete reason"):
        validate_answers(value, method, {"e1"})
    value.answers[0].reason = "I could understand the labels without reopening the menu."
    validate_answers(value, method, {"e1"})
    assert value.answers[0].value == "A"
    value.answers[0].value = None
    value.answers[0].basis = "not_observed"
    value.answers[0].reason = ""
    validate_answers(value, method, {"e1"})


def test_default_interview_explains_personal_meaning_without_forced_variation():
    from genesia.agents import default_interview_instruction, research_instruction

    instruction = default_interview_instruction()
    assert instruction.startswith("INTERVIEW GOAL\n")
    assert research_instruction() in instruction
    assert "why it mattered to your own needs" in instruction
    assert "Same preference, different personal reasons" in instruction
    assert "Return only the answers, not this check or your reasoning." in instruction
    assert "do not copy these facts" in instruction
    assert "Dayline" not in instruction
    assert "INTERVIEW GOAL" not in research_instruction()


def test_interview_batches_keep_complete_identity_context_and_own_prior_answers(tmp_path):
    from copy import deepcopy

    from genesia.agents import default_interview_instruction

    class SnapshotModel(ScriptedModel):
        def complete(self, purpose, payload, schema, **kwargs):
            return super().complete(purpose, deepcopy(payload), schema, **kwargs)

    task = task_fixture(tmp_path)
    task.methods = task.methods[:1]
    task.goal = "Product background: supervise Agent work. Explore naturally."
    task.methods[0].questions = [
        {"id": f"q{index}", "text": f"What mattered at {index}?"} for index in range(20)
    ]
    task.methods[0] = MethodSpec.model_validate(task.methods[0].model_dump())
    task.methods[0].batch_size = 8
    model = SnapshotModel()
    result = run(task, gateway=model, research_only=True)
    assert result.status == "completed", result.errors
    calls = [payload for purpose, payload in model.calls if purpose == "persona_research"]
    for episode in result.episodes:
        own = [
            payload for payload in calls if payload["episode_summary"]["persona"]["id"] == episode.persona.id
        ]
        assert [len(payload["method"]["questions"]) for payload in own] == [8, 8, 4]
        assert [len(payload["prior_batch_answers"]) for payload in own] == [0, 8, 16]
        for payload in own:
            assert payload["instruction"] == default_interview_instruction()
            assert payload["episode_summary"]["persona"] == episode.persona.model_dump()
            assert payload["episode_summary"]["intent"] == episode.intent.model_dump()
            assert payload["episode_summary"]["goal"] == task.goal
            assert payload["prior_own_responses"] == []
            assert payload["experience_timeline"] == own[0]["experience_timeline"]


def test_compact_answer_contract_binds_evidence_by_question_scope():
    from genesia.agents import (
        answer_output_contract,
        answer_schema,
        bind_answer_evidence,
        validate_answers,
    )

    method = MethodSpec(
        id="feedback",
        kind="interview",
        questions=[
            dict(id="context", text="What matters?", purpose="context"),
            dict(
                id="preference",
                text="Which version?",
                kind="single",
                options=["Version A", "Version B"],
                explain=True,
            ),
        ],
    )
    contract = answer_output_contract(method)
    assert "$defs" not in contract
    assert "Version A | Version B" in contract
    assert "supporting_steps" not in contract
    answers = answer_schema(method).model_validate(
        {
            "answers": [
                {"question_id": "context", "value": "Readability"},
                {
                    "question_id": "preference",
                    "value": "Version A",
                    "reason": "It felt clearer.",
                },
            ]
        }
    )
    timeline = [
        {
            "step_id": "step-2",
            "candidate_before": "Version A",
            "candidate_after": "Version A",
            "before": {"evidence_refs": ["before"]},
            "after": {"evidence_refs": ["after"]},
        }
    ]
    bind_answer_evidence(answers, method, timeline)
    validate_answers(answers, method, {"before", "after"})
    assert answers.answers[0].basis == "profile"
    assert answers.answers[0].evidence_refs == []
    assert answers.answers[1].basis == "experience"
    assert answers.answers[1].evidence_refs == ["before", "after"]


@pytest.mark.parametrize("mode", ["live", "walkthrough", "context", "cards", "survey"])
def test_survey_schema_and_binding_follow_session_mode(mode):
    from genesia.agents import answer_schema, bind_answer_evidence, validate_answers

    method = MethodSpec(
        id="survey",
        kind="survey",
        questions=[
            dict(id="context", text="What matters to you?", purpose="context"),
            dict(id="experience", text="How clear was the workflow?", candidate="Version A"),
            dict(id="unknown", text="What remains unknown?"),
        ],
    )
    profile_only = mode == "survey"
    schema = answer_schema(method, profile_only=profile_only)
    answers = schema.model_validate(
        {
            "answers": [
                {"question_id": "context", "value": "Readable content"},
                {"question_id": "experience", "value": "Clear"},
                {"question_id": "unknown", "value": None},
            ],
        }
    )
    timeline = (
        []
        if profile_only
        else [
            {
                "candidate_before": "Version A",
                "candidate_after": "Version A",
                "before": {"evidence_refs": ["before"]},
                "after": {"evidence_refs": ["after"]},
            },
            {
                "candidate_before": "Version B",
                "candidate_after": "Version B",
                "before": {"evidence_refs": ["other-stage"]},
                "after": None,
            },
        ]
    )
    bind_answer_evidence(answers, method, timeline, profile_only=profile_only)
    validate_answers(answers, method, {"before", "after", "other-stage"}, profile_only=profile_only)
    assert answers.answers[0].basis == "profile" and not answers.answers[0].evidence_refs
    assert answers.answers[1].basis == ("profile" if profile_only else "experience")
    assert answers.answers[1].evidence_refs == ([] if profile_only else ["before", "after"])
    assert answers.answers[2].basis == "not_observed" and not answers.answers[2].evidence_refs


def test_post_experience_survey_keeps_owned_evidence_through_public_run(tmp_path):
    from genesia.runtime import EvidenceStore

    task = task_fixture(tmp_path)
    task.methods = [
        MethodSpec(
            id="survey",
            kind="survey",
            batch_size=1,
            questions=[
                dict(id="context", text="What matters to you?", purpose="context"),
                dict(id="experience", text="What happened?"),
            ],
        )
    ]
    result = run(task, gateway=ScriptedModel(), research_only=True)
    assert result.status == "completed", result.errors
    store = EvidenceStore(Path(result.output_dir))
    for response in result.responses:
        context, experience = response.answers
        assert context.basis == "profile" and context.evidence_refs == []
        assert experience.basis == "experience" and experience.evidence_refs
        episode = next(ep for ep in result.episodes if ep.persona.id == response.persona_id)
        assert set(experience.evidence_refs).issubset(set(episode.final_observation.evidence_refs))
        assert all(
            store.refs[ref].persona_id == response.persona_id
            for ref in experience.evidence_refs
            if store.refs[ref].kind == "observation"
        )


@pytest.mark.parametrize("kind", ["interview", "survey", "design_review", "task_outcome_review"])
def test_explicit_automation_basis_survives_binding_with_candidate_scoped_evidence(kind):
    from genesia.agents import answer_schema, bind_answer_evidence, validate_answers

    method = MethodSpec(
        id="review",
        kind=kind,
        questions=[
            dict(id="limited", text="What prevented further assessment?", candidate="A"),
            dict(id="ordinary", text="What did you understand?", candidate="A"),
            dict(id="unknown", text="What could you not assess?", candidate="A"),
        ],
    )
    answers = answer_schema(method).model_validate(
        dict(
            answers=[
                dict(
                    question_id="limited",
                    value="An automation limit prevented further review.",
                    basis="automation",
                ),
                dict(question_id="ordinary", value="The supplied structure was understandable."),
                dict(question_id="unknown", value=None, basis="automation"),
            ]
        )
    )
    timeline = [
        dict(candidate_before="A", candidate_after="A", before={"evidence_refs": ["owned"]}, after=None),
        dict(candidate_before="B", candidate_after="B", before={"evidence_refs": ["other"]}, after=None),
    ]
    bind_answer_evidence(answers, method, timeline)
    validate_answers(answers, method, {"owned", "other"})
    assert answers.answers[0].basis == "automation"
    assert answers.answers[0].evidence_refs == ["owned"]
    assert answers.answers[1].basis == "experience"
    assert answers.answers[1].evidence_refs == ["owned"]
    assert answers.answers[2].basis == "not_observed" and not answers.answers[2].evidence_refs
    with pytest.raises(ValueError, match="outside this Persona"):
        validate_answers(answers, method, set())
    answers.answers[0].evidence_refs = []
    with pytest.raises(ValueError, match="Automation-limited answers require"):
        validate_answers(answers, method, {"owned", "other"})


def test_automation_classification_reaches_statistics_and_synthesis_through_public_run(tmp_path):
    from genesia.insight_support import analysis_input

    task = task_fixture(tmp_path)
    task.environment.max_steps = 1
    task.methods = [
        MethodSpec(
            id="review",
            kind="survey",
            questions=[
                dict(id="q1", text="How clear was the material?", kind="single", options=["Clear", "Unclear"])
            ],
        )
    ]

    class LimitedModel(ScriptedModel):
        def complete(self, purpose, payload, schema, **kwargs):
            if purpose == "persona_action":
                return schema.model_validate(dict(action="wait", intent="Read the supplied material"))
            if purpose == "persona_research" and payload["episode_summary"]["persona"]["id"] == "p0":
                result = schema.model_validate(
                    dict(
                        answers=[
                            dict(question_id="q1", value="Unclear", basis="automation"),
                        ]
                    )
                )
                kwargs["validate"](result)
                return result
            return super().complete(purpose, payload, schema, **kwargs)

    model = LimitedModel()
    result = run(task, gateway=model)
    assert result.status == "completed", result.errors
    assert all(episode.outcome == "max_steps" for episode in result.episodes)
    source = analysis_input(task, result.responses, result.episodes)
    assert [row["status"] for row in source["rows"]].count("automation") == 1
    assert [row["status"] for row in source["rows"]].count("answered") == 2
    stats = result.metrics["descriptive_statistics"]["questions"][0]
    assert stats["n_automation"] == 1 and stats["n_answered"] == 2
    assert stats["counts"] == {"Clear": 2}
    assert all(
        row["basis"] != "automation"
        for purpose, payload in model.calls
        if purpose == "research_synthesis"
        for row in payload.get("rows", [])
    )
    assert len(result.report.analysis["reviewed_answer_ids"]) == 2
    assert all(answer.evidence_refs for response in result.responses for answer in response.answers)


def test_experience_timeline_binds_actions_to_before_and_after_evidence():
    from genesia.agents import experience_timeline
    from genesia.schemas import Action, Episode, ExecutionResult, Observation, Persona, Step

    before = Observation(
        id="o1",
        mode="live",
        text="Stable shell\nTransparency effects\nOn",
        url="http://localhost/colors",
        image_refs=["frame-before"],
        evidence_refs=["frame-before", "state-before"],
    )
    after = Observation(
        id="o2",
        mode="live",
        text="Stable shell\nTransparency effects\nOff",
        url="http://localhost/colors",
        image_refs=["frame-after"],
        evidence_refs=["frame-after", "state-after"],
    )
    episode = Episode(
        session_id="session",
        persona=Persona(id="person", profile={}),
        goal="Adjust colors",
        mode="live",
        phase="research",
        steps=[
            Step(
                number=1,
                observation=before,
                action=Action(action="click", target_id="toggle", intent="Reduce distraction"),
                result=ExecutionResult(success=True, message="click executed"),
            )
        ],
        final_observation=after,
    )
    timeline = experience_timeline(episode, {"frame-before", "frame-after"}, complete=True)
    assert timeline == [
        {
            "step_id": "step-1",
            "action": {
                "action": "click",
                "target": None,
                "value": None,
                "intent": "Reduce distraction",
                "expected_result": "",
                "execution_success": True,
                "result": "click executed",
            },
            "before": {
                "observation_id": "o1",
                "url": "http://localhost/colors",
                "page": "Colors",
                "image_refs": ["frame-before"],
                "evidence_refs": ["frame-before", "state-before"],
            },
            "after": {
                "observation_id": "o2",
                "url": "http://localhost/colors",
                "page": "Colors",
                "image_refs": ["frame-after"],
                "evidence_refs": ["frame-after", "state-after"],
            },
            "stage_before": 1,
            "stage_after": 1,
            "candidate_before": None,
            "candidate_after": None,
            "attached_images": [
                {"role": "before", "ref": "frame-before"},
                {"role": "after", "ref": "frame-after"},
            ],
        }
    ]

    episode.candidate_labels = ["Design B", "Design A"]
    labeled = experience_timeline(episode, {"frame-before", "frame-after"}, complete=True)
    assert labeled[0]["candidate_before"] == "Design B"
    assert labeled[0]["candidate_after"] == "Design B"

    episode.steps = []
    timeline = experience_timeline(episode, {"frame-after"}, complete=True)
    assert timeline[0]["step_id"] == "initial-state"
    assert timeline[0]["action"] is None
    assert timeline[0]["attached_images"] == [{"role": "after", "ref": "frame-after"}]


@pytest.mark.parametrize("mode", ["context", "cards", "walkthrough", "captured_graph", "scenario"])
def test_material_timeline_retains_text_without_claiming_omitted_images(mode):
    from genesia.agents import experience_timeline
    from genesia.schemas import Action, Episode, ExecutionResult, Observation, Persona, Step

    before = Observation(
        id="o1",
        mode=mode,
        text="First supplied material",
        image_refs=["omitted-image"],
        evidence_refs=["omitted-image", "document", "observation-1"],
    )
    after = Observation(
        id="o2",
        mode=mode,
        text="Second supplied material",
        image_refs=["selected-image"],
        evidence_refs=["selected-image", "observation-2"],
    )
    episode = Episode(
        session_id="s",
        persona=Persona(id="p", profile={}),
        goal="Review materials",
        mode=mode,
        steps=[
            Step(
                number=1,
                observation=before,
                action=Action(action="click", target_id="next", intent="Continue"),
                result=ExecutionResult(success=True, message="Advanced material"),
            )
        ],
        final_observation=after,
    )
    timeline = experience_timeline(episode, {"selected-image"}, complete=False)
    assert timeline[0]["before"]["material_text"] == before.text
    assert timeline[0]["after"]["material_text"] == after.text
    assert timeline[0]["before"]["image_refs"] == []
    assert timeline[0]["before"]["evidence_refs"] == ["document", "observation-1"]
    assert timeline[0]["after"]["evidence_refs"] == after.evidence_refs
    assert timeline[0]["attached_images"] == [{"role": "after", "ref": "selected-image"}]


@pytest.mark.parametrize("mode", ["auto", "scenario", "cards", "walkthrough", "captured_graph"])
@pytest.mark.parametrize("evidence_mode", ["sampled", "complete"])
def test_material_sdk_interview_receives_only_reviewed_text(tmp_path, mode, evidence_mode):
    from copy import deepcopy

    from genesia.runtime import EvidenceStore, model_content
    from genesia.schemas import SourceSpec

    task = task_fixture(tmp_path)
    task.cohort.size = 1
    task.methods = task.methods[:2]
    for method in task.methods:
        method.evidence_mode = evidence_mode
    task.environment.mode = "auto" if mode == "cards" else mode
    sources = []
    texts = ["FIRST_MATERIAL_POLICY_17", "SECOND_MATERIAL_POLICY_23", "UNSEEN_MATERIAL_POLICY_41"]
    for index, text in enumerate(texts):
        path = tmp_path / f"material-{index}.md"
        path.write_text(text, encoding="utf-8")
        sources.append(SourceSpec(kind="document", path=str(path)))
    task.environment.sources = sources

    class MaterialModel(ScriptedModel):
        def __init__(self):
            super().__init__()
            self.research_requests = []

        def complete(self, purpose, payload, schema, **kwargs):
            if purpose == "persona_research":
                self.research_requests.append(
                    (deepcopy(payload), schema, kwargs["interleave_key"], kwargs["output_contract"])
                )
            if purpose == "environment_readiness" and mode == "cards":
                data = dict(
                    summary="Unconnected supplied UI states",
                    states=[
                        dict(
                            id=f"s{index}",
                            title=f"Material {index}",
                            description=source["text"],
                            evidence=[dict(source_id=source["id"], quote=source["text"])],
                        )
                        for index, source in enumerate(payload["sources"])
                    ],
                )
            elif purpose == "environment_build":
                sources = payload["sources"]
                data = dict(
                    start="s0",
                    nodes=[
                        dict(id=f"s{index}", text=source["text"], source_ids=[source["id"]])
                        for index, source in enumerate(sources)
                    ],
                    edges=[
                        dict(id=f"next-{index}", source=f"s{index}", target=f"s{index + 1}", label="Next")
                        for index in range(len(sources) - 1)
                    ],
                )
            elif purpose == "ui_card_extract":
                data = dict(title="Supplied material", description=payload["source"]["text"])
            elif purpose == "ui_card_bind":
                data = dict(
                    states=[
                        dict(
                            id="stable",
                            title="Supplied material",
                            card_ids=[c["id"] for c in payload["cards"]],
                        )
                    ]
                )
            elif purpose == "persona_action":
                data = (
                    dict(
                        action="click",
                        target_id=payload["observation"]["targets"][0]["id"],
                        intent="Read another supplied material",
                    )
                    if not payload["history"]
                    else dict(action="stop", intent="I have enough context", outcome="completed")
                )
            else:
                return super().complete(purpose, payload, schema, **kwargs)
            result = schema.model_validate(data)
            if kwargs.get("validate"):
                kwargs["validate"](result)
            return result

    model = MaterialModel()
    result = run(task, gateway=model)
    assert result.status == "completed", result.errors
    assert result.episodes[0].mode == ("context" if mode == "auto" else mode)
    assert len(result.episodes[0].steps) == 2
    assert len(model.research_requests) == 2
    store = EvidenceStore(Path(result.output_dir))
    for payload, schema, interleave_key, output_contract in model.research_requests:
        content, _ = model_content(
            "persona_research",
            payload,
            schema,
            store,
            interleave_key=interleave_key,
            output_contract=output_contract,
        )
        visible = "\n".join(item["text"] for item in content if item["type"] == "text")
        assert visible.count(texts[0]) == visible.count(texts[1]) == 1
        assert texts[2] not in visible
        assert "observation_id" not in visible
        assert "evidence_refs" not in "\n".join(
            item["text"] for item in content if item["type"] == "text" and "TIMELINE ITEM:" in item["text"]
        )
        assert store.verify()["valid"]


@pytest.mark.parametrize("image_limit", [0, 1])
def test_sampled_material_research_binds_text_but_not_omitted_images(tmp_path, image_limit):
    from genesia.agents import PersonaAgent
    from genesia.runtime import BudgetLedger, EvidenceStore
    from genesia.schemas import Action, BudgetSpec, Episode, ExecutionResult, Observation, Persona, Step

    store = EvidenceStore(tmp_path)
    episode = Episode(
        session_id="s", persona=Persona(id="p", profile={}), goal="Review materials", mode="cards"
    )
    images, documents = [], []
    for index in range(2):
        image = store.put(f"image-{index}".encode(), "source_image", ".png")
        document = store.put(f"Material text {index}".encode(), "source", ".txt")
        observation = Observation(
            id=f"o{index}",
            mode="cards",
            text=f"Material text {index}",
            image_refs=[image],
            evidence_refs=[image, document],
        )
        observation.evidence_refs.append(
            store.json(observation, "observation", persona_id="p", session_id="s")
        )
        episode.steps.append(
            Step(
                number=index + 1,
                observation=observation,
                action=Action(action="wait", intent="Read"),
                result=ExecutionResult(success=True, message="Reviewed"),
            )
        )
        images.append(image)
        documents.append(document)
    episode.final_observation = episode.steps[-1].observation
    episode.phase = "research"
    model = ScriptedModel()
    agent = PersonaAgent(episode, model, store, BudgetLedger(BudgetSpec()))
    response = agent.research(
        MethodSpec(
            id="review",
            kind="interview",
            evidence_mode="sampled",
            max_images=image_limit,
            questions=[dict(id="q1", text="What did you review?")],
        )
    )
    assert response.valid, response.errors
    selected = set(images[-image_limit:]) if image_limit else set()
    answer_refs = set(response.answers[0].evidence_refs)
    assert answer_refs.intersection(images) == selected
    assert set(documents).issubset(answer_refs)
    payload = model.calls[-1][1]
    assert payload["evidence_selection"]["omitted_images"] == len(images) - image_limit
    assert [item["before"]["material_text"] for item in payload["experience_timeline"]] == [
        "Material text 0",
        "Material text 1",
    ]


@pytest.mark.parametrize("frame_count", [4, 48])
def test_complete_interview_preserves_sequence_without_researcher_goals(tmp_path, frame_count):
    from genesia.agents import PersonaAgent, execution_trace
    from genesia.runtime import BudgetLedger, EvidenceStore
    from genesia.schemas import Action, Episode, ExecutionResult, Observation, Persona, Step, StudySpec

    store = EvidenceStore(tmp_path)
    episode = Episode(
        session_id="session",
        persona=Persona(id="person", profile={}),
        goal="Work comfortably",
        mode="live",
        phase="research",
    )
    for number in range(1, frame_count + 1):
        image = store.put(
            f"frame-{number}".encode(), "frame", ".jpg", persona_id="person", session_id="session"
        )
        observation = Observation(
            id=f"o{number}",
            text=f"State {number}",
            mode="live",
            url=f"http://localhost/{number}",
            image_refs=[image],
            evidence_refs=[image],
        )
        episode.steps.append(
            Step(
                number=number,
                observation=observation,
                action=Action(action="wait", intent="Inspect", expected_result="See the result"),
                result=ExecutionResult(success=True, message="Executed"),
            )
        )
    episode.final_observation = episode.steps[-1].observation
    model = ScriptedModel()
    agent = PersonaAgent(
        episode,
        model,
        store,
        BudgetLedger(task_fixture(tmp_path).budget),
        StudySpec(objectives=[{"id": "secret", "description": "Researcher hypothesis"}]),
    )
    method = MethodSpec(
        id="review",
        kind="interview",
        evidence_mode="complete",
        max_images=frame_count,
        questions=[{"id": "q1", "text": "What happened?", "objective_ids": ["secret"]}],
    )
    assert agent.research(method).valid
    payload = model.calls[-1][1]
    assert "study" not in payload
    assert "objective_ids" not in payload["method"]["questions"][0]
    assert payload["evidence_selection"]["omitted_images"] == 0
    assert len(payload["experience_timeline"]) == frame_count
    assert "representative_states" not in payload["episode_summary"]
    assert "executed_actions" not in payload
    assert "allowed_evidence_refs" not in payload
    assert "relevant_visible_text" not in payload["experience_timeline"][0]["before"]
    assert "relevant_visible_text" not in payload["experience_timeline"][0]["after"]
    assert execution_trace(episode)[0]["after_observation_id"] == "o2"
    assert execution_trace(episode)[0]["expected_result"] == "See the result"
    method.max_images = frame_count - 1
    import pytest

    with pytest.raises(ValueError, match="exceeds max_images"):
        agent.research(method)


def test_reflections_bind_previous_action_to_current_evidence(tmp_path):
    from genesia.agents import PersonaAgent, execution_trace
    from genesia.runtime import BudgetLedger, EvidenceStore
    from genesia.schemas import BudgetSpec, Episode, ExecutionResult, Observation, Persona, PrototypeScope

    store = EvidenceStore(tmp_path)

    class Environment:
        number = 0
        closed = False

        def observe(self):
            self.number += 1
            ref = store.put(str(self.number).encode(), "frame", ".jpg", persona_id="p1", session_id="s1")
            return Observation(
                id=f"o{self.number}",
                text=f"State {self.number}",
                mode="live",
                image_refs=[ref],
                evidence_refs=[ref],
            )

        def act(self, action):
            return ExecutionResult(success=True, message="Waited")

        def close(self):
            self.closed = True

    class ReflectingModel(ScriptedModel):
        def complete(self, purpose, payload, schema, **kwargs):
            if purpose == "persona_action":
                self.calls.append((purpose, payload))
                data = {"action": "wait", "intent": "Inspect visible options"}
                if payload["history"]:
                    assert payload["history"][-1]["after_observation_id"] == payload["observation"]["id"]
                    assert len(kwargs["images"]) == 2
                    data.update(
                        action="stop",
                        outcome="completed",
                        reflection={
                            "interest": "Readability",
                            "observed_effect": "A visible change",
                            "judgment": "Enough to form my view",
                            "effect_status": "visible_change",
                        },
                    )
                return schema.model_validate(data)
            return super().complete(purpose, payload, schema, **kwargs)

    episode = Episode(
        session_id="s1",
        persona=Persona(id="p1", profile={}),
        goal="Explore",
        mode="live",
        prototype=PrototypeScope(scope="Appearance", known_limitations=["Other areas are placeholders"]),
    )
    model, environment = ReflectingModel(), Environment()
    agent = PersonaAgent(episode, model, store, BudgetLedger(BudgetSpec()))
    agent.experience(environment, 4)
    assert environment.closed
    assert len(episode.experience_notes) == 1
    note = episode.experience_notes[0]
    assert (note.step, note.before_observation_id, note.after_observation_id) == (1, "o1", "o2")
    assert note.after_evidence_refs == episode.steps[1].observation.evidence_refs
    assert execution_trace(episode)[0]["participant_reflection"]["judgment"] == "Enough to form my view"
    method = MethodSpec(
        id="interview",
        kind="interview",
        evidence_mode="complete",
        max_images=5,
        questions=[dict(id="q1", text="Which choice did you keep, and why?")],
    )
    assert agent.research(method).valid
    payload = model.calls[-1][1]
    assert "experience_notes" not in payload["episode_summary"]
    assert all("participant_reflection" not in item["action"] for item in payload["experience_timeline"])
    assert episode.experience_notes[0].step == 1
    assert payload["episode_summary"]["prototype"]["scope"] == "Appearance"
    assert store.verify()["valid"]


def test_followups_keep_identity_and_evidence(tmp_path):
    task = task_fixture(tmp_path)
    task.methods = [
        MethodSpec(
            id="interview",
            kind="interview",
            max_followups=2,
            questions=[dict(id="base", text="Was it clear?")],
        )
    ]
    result = run(task, gateway=InterviewModel())
    assert result.status == "completed"
    for response in result.responses:
        assert len(response.followups) == 1
        assert response.followups[0]["parent_question_id"] == "base"
        assert response.followups[0]["answer"]["evidence_refs"]


def test_answer_schema_distinguishes_question_purpose_from_answer_basis():
    from pydantic import ValidationError

    method = MethodSpec(
        id="feedback",
        kind="interview",
        questions=[
            dict(id="context", text="What matters?", purpose="context", feedback_role="context"),
            dict(
                id="suggestion",
                text="What would improve it?",
                purpose="reflection",
                feedback_role="suggestion",
            ),
        ],
    )
    schema = __import__("genesia.agents", fromlist=["answer_schema"]).answer_schema(method)
    value = schema.model_validate(
        dict(
            answers=[
                dict(question_id="context", value="Readability", basis="profile"),
                dict(question_id="suggestion", value="Keep immediate feedback", basis="experience"),
            ]
        )
    )
    assert [answer.basis for answer in value.answers] == ["profile", "experience"]
    with pytest.raises(ValidationError):
        schema.model_validate(
            dict(
                answers=[
                    dict(question_id="context", value="Readability", basis="profile"),
                    dict(question_id="suggestion", value="Preview", basis="reflection"),
                ]
            )
        )


def test_batches_and_branching_preserve_question_order(tmp_path):
    task = task_fixture(tmp_path)
    task.methods = [
        MethodSpec(
            id="survey",
            kind="survey",
            batch_size=1,
            questions=[
                dict(id="first", text="Clarity?"),
                dict(id="conditional", text="Explain confusion", ask_if={"first": "Confusing"}),
                dict(id="last", text="What worked?"),
            ],
        )
    ]
    result = run(task, gateway=ScriptedModel())
    assert result.status == "completed"
    for response in result.responses:
        assert [answer.question_id for answer in response.answers] == ["first", "conditional", "last"]
        assert response.answers[1].basis == "skipped"
        assert len(response.batches) == 2


class SurveyModel(ScriptedModel):
    def complete(self, purpose, payload, schema, **kwargs):
        if purpose == "persona_intent":
            role_policy = payload["persona_role_policy"]
            assert "You ARE the person" in role_policy
            assert "ten dimensions" in role_policy
            assert "Role Consistency" in role_policy
            policy = payload["survey_response_policy"]
            assert "Answer every question" in policy
        if purpose == "persona_research":
            role_policy = payload["persona_role_policy"]
            assert "You ARE the person" in role_policy
            assert "ten dimensions" in role_policy
            policy = payload["survey_response_policy"]
            assert "exact offered option text" in policy
            assert "Vary the number of selected options naturally" in policy
            assert "basis: not_observed" in policy
            answers = []
            for question in payload["method"]["questions"]:
                value = (
                    question["options"][0]
                    if question["kind"] == "single"
                    else [question["options"][0]]
                    if question["kind"] == "multiple"
                    else {row: question["options"][0] for row in question["rows"]}
                    if question["kind"] == "likert"
                    else "Profile-grounded response"
                )
                answers.append(
                    {
                        "question_id": question["id"],
                        "value": value,
                        "basis": "profile",
                        "evidence_refs": [],
                    }
                )
            result = schema.model_validate({"answers": answers})
            if validate := kwargs.get("validate"):
                validate(result)
            return result
        return super().complete(purpose, payload, schema, **kwargs)


def test_survey_only_run_skips_environment_and_writes_insight_report(tmp_path):
    data = task_fixture(tmp_path).model_dump()
    data["environment"] = {"mode": "survey"}
    data["methods"] = [
        {
            "id": "product_survey",
            "kind": "survey",
            "batch_size": 2,
            "questions": [
                {
                    "id": "frequency",
                    "text": "How often would this fit your work?",
                    "kind": "single",
                    "options": ["Often", "Sometimes", "Never"],
                },
                {"id": "reason", "text": "Why?"},
            ],
        }
    ]
    task = TaskSpec.model_validate(data)

    result = run(
        task,
        gateway=SurveyModel(),
        environment_factory=lambda *_: (_ for _ in ()).throw(AssertionError("No environment")),
    )

    assert result.status == "completed"
    assert result.metrics["valid_responses"] == 3
    assert result.metrics["failed_actions"] == 0
    assert all(not episode.steps and episode.outcome == "survey_ready" for episode in result.episodes)
    assert all(
        answer.basis == "profile" and not answer.evidence_refs
        for response in result.responses
        for answer in response.answers
    )
    frequency = next(
        item
        for item in result.metrics["descriptive_statistics"]["questions"]
        if item["question_id"] == "frequency"
    )
    assert frequency["counts"] == {"Often": 3}
    insight = (tmp_path / "runs" / result.run_id / "insight_report.md").read_text("utf-8")
    assert "Genesia Research Report" in insight and "## Summary" in insight
    assert "Responses: 3 valid; 0 invalid; 0 missing" in insight
    assert insight == (tmp_path / "runs" / result.run_id / "report.md").read_text("utf-8")
