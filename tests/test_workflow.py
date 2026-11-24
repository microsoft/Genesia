import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from rich.text import Text
from typer.testing import CliRunner

from genesia.agents import (
    PersonaAgent,
    answer_schema,
    representative_images,
    validate_action_choice,
    validate_answers,
)
from genesia.api import _new_run_id, preflight, reanswer, run
from genesia.cli import app
from genesia.runtime import BudgetLedger, EvidenceStore
from genesia.schemas import (
    Action,
    Answers,
    BudgetSpec,
    EnvironmentSpec,
    Episode,
    ExecutionResult,
    MethodSpec,
    ModelSpec,
    Observation,
    Persona,
    Step,
    Target,
    TaskSpec,
)


class ScriptedModel:
    def __init__(self):
        self.calls = []

    def complete(
        self,
        purpose,
        payload,
        schema,
        *,
        images=None,
        interleave_key=None,
        output_contract=None,
        validate=None,
    ):
        self.calls.append((purpose, payload))
        if purpose == "environment_readiness":
            data = dict(summary="Fixture concept without UI states", states=[], transitions=[])
        elif purpose == "persona_intent":
            data = dict(goal="Review", preferences="Simple", completion_standard="Understand it")
        elif purpose == "persona_action":
            assert "questions" not in json.dumps(payload)
            data = dict(action="stop", intent="I have reviewed it", outcome="completed")
        elif purpose == "persona_research":
            assert interleave_key == "experience_timeline"
            assert output_contract and "supporting_steps" not in output_contract
            assert payload[interleave_key]
            data = {
                "answers": [
                    {
                        "question_id": question["id"],
                        "value": "Clear",
                        "evidence_refs": [payload[interleave_key][-1]["after"]["evidence_refs"][-1]],
                    }
                    for question in payload["method"]["questions"]
                ]
            }
        elif purpose == "research_synthesis":
            if payload.get("output_stage") in {"insight_reduce", "insight_report"}:
                sources = payload["source_findings"]
                candidates = {item.get("candidate") for item in sources} - {None}
                finding_id = "f1"
                data = {
                    "summary": "Synthetic feedback",
                    "findings": [
                        {
                            "id": finding_id,
                            "source_finding_ids": [item["id"] for item in sources],
                            "text": sources[0]["text"],
                            "candidate": next(iter(candidates)) if len(candidates) == 1 else None,
                            "category": sources[0]["category"],
                            "feedback_type": sources[0]["feedback_type"],
                            "journey_stage": sources[0]["journey_stage"],
                            "interpretation": sources[0].get("interpretation", ""),
                            "design_implication": sources[0].get("design_implication", ""),
                            "uncertainty": sources[0].get("uncertainty", ""),
                        }
                    ],
                    "limitations": "Simulated only",
                    "recommendations": (
                        [
                            {
                                "action": "Validate the finding",
                                "kind": "investigate",
                                "rationale": "Synthetic evidence requires validation",
                                "finding_ids": [finding_id],
                                "severity": 2,
                                "effort": 1,
                                "confidence": 0.5,
                            }
                        ]
                        if payload["output_stage"] == "insight_report"
                        else []
                    ),
                }
                result = schema.model_validate(data)
                if validate:
                    validate(result)
                return result
            assert all("executed_actions" in outcome for outcome in payload["outcomes"])
            summarized_findings = [
                finding for summary in payload.get("summaries", []) for finding in summary.get("findings", [])
            ]
            data = dict(
                summary="Synthetic feedback",
                findings=[
                    dict(
                        text="Clear",
                        participants=[payload["rows"][0]["persona_id"]],
                        evidence_refs=[payload["rows"][0]["response_ref"]],
                    )
                ]
                if payload["rows"]
                else [dict(summarized_findings[0])]
                if summarized_findings
                else [],
                limitations="Simulated only",
            )
            if "reviewed_findings" in payload:
                data["findings"] = [
                    {
                        **finding,
                        "answer_ids": [],
                        "counter_answer_ids": [],
                        "participants": [],
                        "evidence_refs": [],
                    }
                    for finding in payload["reviewed_findings"]
                ]
        else:
            raise AssertionError(purpose)
        if purpose == "research_synthesis" and data["findings"]:
            if "reviewed_findings" not in payload:
                data["findings"][0]["id"] = data["findings"][0].get("id") or "f1"
                if payload["rows"]:
                    data["findings"][0]["answer_ids"] = [payload["rows"][0]["answer_id"]]
                    purpose_kind = payload["rows"][0]["question"].get("purpose", "experience")
                    data["findings"][0]["category"] = {
                        "experience": "experience",
                        "context": "preference",
                        "reflection": "opportunity",
                    }[purpose_kind]
                if payload["rows"] and any(
                    question.get("feedback_role") for question in payload["question_definitions"]
                ):
                    evidence_row = next(
                        (row for row in payload["rows"] if row["question"].get("purpose") == "experience"),
                        payload["rows"][0],
                    )
                    data["findings"][0].update(
                        category="experience",
                        feedback_type="positive",
                        journey_stage="overall",
                        answer_ids=[evidence_row["answer_id"]],
                        participants=[evidence_row["persona_id"]],
                        evidence_refs=[evidence_row["response_ref"]],
                    )
                if payload.get("output_stage") == "question_insights":
                    evidence_rows = [
                        row
                        for row in payload["rows"]
                        if row["question"].get("purpose", "experience") == "experience"
                    ] or payload["rows"]
                    data["findings"][0].update(
                        answer_ids=[row["answer_id"] for row in evidence_rows],
                        participants=sorted({row["persona_id"] for row in evidence_rows}),
                        evidence_refs=sorted({row["response_ref"] for row in evidence_rows}),
                    )
            data["recommendations"] = (
                []
                if payload.get("output_stage") in {"candidate_themes", "question_insights"}
                else [
                    dict(
                        action="Clarify the selected state",
                        rationale="Supported feedback",
                        finding_ids=[data["findings"][0]["id"]],
                        severity=2,
                        effort=1,
                        confidence=0.5,
                    )
                ]
            )
        result = schema.model_validate(data)
        if validate:
            validate(result)
        return result


def task_fixture(tmp_path):
    people = tmp_path / "people.json"
    people.write_text(
        json.dumps([dict(id=f"p{index}", profile={"name": f"Fixture {index}"}) for index in range(3)]),
        encoding="utf-8",
    )
    material = tmp_path / "screen.md"
    material.write_text("Calendar creation screen: enter title and save.", encoding="utf-8")
    return TaskSpec.model_validate(
        dict(
            goal="Review calendar",
            cohort=dict(source=str(people), size=3),
            environment=dict(mode="scenario", sources=[dict(kind="document", path=str(material))]),
            methods=[
                dict(id=kind, kind=kind, questions=[dict(id="q1", text="How clear was it?")])
                for kind in ["interview", "survey", "design_review", "task_outcome_review"]
            ],
            model=dict(model="fixture"),
            permissions=dict(send_persona=True, send_materials=True),
            output_dir=str(tmp_path / "runs"),
        )
    )


def test_three_personas_all_methods(tmp_path):
    model = ScriptedModel()
    result = run(task_fixture(tmp_path), gateway=model)
    assert result.status == "completed"
    assert result.metrics["valid_responses"] == 12
    assert len({episode.session_id for episode in result.episodes}) == 3
    for episode in result.episodes:
        assert all(
            response.session_id == episode.session_id
            for response in result.responses
            if response.persona_id == episode.persona.id
        )
    persona_calls = [
        (purpose, payload)
        for purpose, payload in model.calls
        if purpose in {"persona_intent", "persona_action", "persona_research"}
    ]
    assert persona_calls and all(
        "You ARE the person" in payload["persona_role_policy"] for _, payload in persona_calls
    )
    for purpose, payload in persona_calls:
        if purpose == "persona_research":
            if payload["method"]["kind"] == "survey":
                assert "Question Type Handling" in payload["survey_response_policy"]
            else:
                assert payload["survey_response_policy"] is None
    assert EvidenceStore(__import__("pathlib").Path(result.output_dir)).verify()["valid"]


def test_research_only_keeps_answers_without_analysis_or_reports(tmp_path):
    from pathlib import Path

    from genesia.runtime import model_prompt
    from genesia.schemas import SessionIntent

    task = task_fixture(tmp_path)
    model = ScriptedModel()
    result = run(task, gateway=model, research_only=True)
    assert result.status == "completed", result.errors
    assert result.metrics["analysis_skipped"] is True
    assert result.metrics["valid_responses"] == 12
    assert result.synthesis is None
    assert not any(purpose == "research_synthesis" for purpose, _ in model.calls)
    root = Path(result.output_dir)
    assert not (root / "report.html").exists()
    assert not (root / "analysis_input.json").exists()
    assert EvidenceStore(root).verify()["valid"]
    assert json.loads((root / "run_manifest.json").read_text("utf-8"))["phase"] == "research_only"
    payload = next(payload for purpose, payload in model.calls if purpose == "persona_intent")
    prompt = model_prompt("persona_intent", payload, SessionIntent)
    assert prompt.startswith("ROLE INSTRUCTIONS")
    assert prompt.count("You ARE the person") == 1
    assert "persona_role_policy" in payload


def test_reanswer_reuses_episodes_without_experience_or_analysis(tmp_path):
    task = task_fixture(tmp_path)
    source_model = ScriptedModel()
    source = run(task, gateway=source_model, research_only=True)
    source_path = Path(source.output_dir)
    source_result_bytes = (source_path / "research_result.json").read_bytes()
    source_events_bytes = (source_path / "events.jsonl").read_bytes()
    replay_model = ScriptedModel()
    updated_task = task.model_copy(deep=True)
    revised_question = (
        updated_task.methods[0].questions[0].model_copy(update={"text": "Answer this revised question."})
    )
    updated_task.methods[0] = updated_task.methods[0].model_copy(
        update={"questions": [revised_question, *updated_task.methods[0].questions[1:]]}
    )
    replay = reanswer(source_path, task=updated_task, gateway=replay_model)
    assert replay.status == "completed", replay.errors
    assert replay.run_id != source.run_id
    assert replay.metrics["experience_reused"] is True
    assert replay.metrics["analysis_skipped"] is True
    assert replay.synthesis is None
    assert [episode.session_id for episode in replay.episodes] == [
        episode.session_id for episode in source.episodes
    ]
    assert all(purpose == "persona_research" for purpose, _ in replay_model.calls)
    assert len(replay_model.calls) == len(source.episodes) * len(task.methods)
    revised_calls = [payload for _, payload in replay_model.calls if payload["method"]["id"] == "interview"]
    assert len(revised_calls) == len(source.episodes)
    assert all(
        any(
            question["text"] == "Answer this revised question." for question in payload["method"]["questions"]
        )
        for payload in revised_calls
    )
    replay_root = Path(replay.output_dir)
    assert not (replay_root / "report.html").exists()
    replay_manifest = json.loads((replay_root / "run_manifest.json").read_text("utf-8"))
    assert replay_manifest["phase"] == "reanswer_only"
    assert replay_manifest["task"]["methods"][0]["questions"][0]["text"] == ("Answer this revised question.")
    assert EvidenceStore(replay_root).verify()["valid"]
    assert (source_path / "research_result.json").read_bytes() == source_result_bytes
    assert (source_path / "events.jsonl").read_bytes() == source_events_bytes


def test_exploration_guidance_does_not_gate_stopping(tmp_path):
    task = task_fixture(tmp_path)
    task.goal = "Explore and try this feature according to your preferences."
    model = ScriptedModel()
    result = run(task, gateway=model)
    assert result.status == "completed", result.errors
    intents = [payload for purpose, payload in model.calls if purpose == "persona_intent"]
    actions = [payload for purpose, payload in model.calls if purpose == "persona_action"]
    research = [payload for purpose, payload in model.calls if purpose == "persona_research"]
    synthesis = [payload for purpose, payload in model.calls if purpose == "research_synthesis"]
    assert all("This is not a UX critique" in payload["instruction"] for payload in intents)
    assert all("not a generic usability checklist" in payload["instruction"] for payload in intents)
    assert all(
        "The questionnaire does not change who you are" in payload["instruction"] for payload in research
    )
    assert all("candidate's own merits" in payload["instruction"] for payload in research)
    assert all("untried counterpart" in payload["instruction"] for payload in research)
    assert all("Do not append formulaic labels" in payload["instruction"] for payload in research)
    assert all("Receiving a questionnaire" in payload["persona_role_policy"] for payload in research)
    assert all("Leave reflection null" in payload["instruction"] for payload in actions)
    assert all("what prevented exploration" in payload["instruction"] for payload in actions)
    assert all("do not keep probing it" in payload["instruction"] for payload in actions)
    assert all("No visible change alone does not establish" in payload["instruction"] for payload in actions)
    assert research and all(
        "do not assume it is a product defect" in payload["instruction"] for payload in research
    )
    assert all("experience_notes" not in payload["episode_summary"] for payload in research)
    assert all("representative_states" not in payload["episode_summary"] for payload in research)
    assert all("executed_actions" not in payload for payload in research)
    assert all("allowed_evidence_refs" not in payload for payload in research)
    assert all(
        "participant_reflection" not in item["action"]
        for payload in research
        for item in payload["experience_timeline"]
    )
    assert all(
        "feedback_role" not in question and "purpose" not in question
        for payload in research
        for question in payload["method"]["questions"]
    )
    assert synthesis and all(
        "not product findings or recommendations" in json.dumps(payload) for payload in synthesis
    )
    assert all("Distinguish missing study evidence" in json.dumps(payload) for payload in synthesis)
    assert all("stop" in payload["allowed_actions"] for payload in actions)
    assert all("questions" not in json.dumps(payload) for payload in intents + actions)
    assert all(len(episode.steps) == 1 for episode in result.episodes)


def test_parallel_personas_preserve_identity_and_artifacts(tmp_path):
    from threading import Barrier, Lock

    class ParallelModel(ScriptedModel):
        def __init__(self):
            super().__init__()
            self.barrier = Barrier(3)
            self.lock = Lock()
            self.active = 0
            self.peak = 0

        def complete(self, purpose, payload, schema, **kwargs):
            if purpose == "persona_intent":
                with self.lock:
                    self.active += 1
                    self.peak = max(self.peak, self.active)
                self.barrier.wait(timeout=10)
                with self.lock:
                    self.active -= 1
            return super().complete(purpose, payload, schema, **kwargs)

    task = task_fixture(tmp_path)
    task.execution.max_concurrent_personas = 3
    task.execution.max_concurrent_model_calls = 3
    model = ParallelModel()
    result = run(task, gateway=model)
    assert result.status == "completed", result.errors
    assert model.peak == 3
    assert len(result.responses) == 12
    for episode in result.episodes:
        assert (
            len([response for response in result.responses if response.session_id == episode.session_id]) == 4
        )
    root = __import__("pathlib").Path(result.output_dir)
    assert EvidenceStore(root).verify()["valid"]
    events = [json.loads(line) for line in (root / "events.jsonl").read_text("utf-8").splitlines()]
    assert sum(event["event"] == "method_finished" for event in events) == 12


def test_unified_report_escapes_untrusted_text_and_handles_failure(tmp_path):
    from genesia.reports import render

    result = run(task_fixture(tmp_path), gateway=FailingResearchModel())
    root = __import__("pathlib").Path(result.output_dir)
    assert all(
        (root / name).is_file() for name in ["report.html", "report.md", "appendix.html", "appendix.md"]
    )
    result.synthesis.summary = '<script>alert("private")</script>'
    html = render(result, EvidenceStore(root), html_output=True)
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "Content-Security-Policy" in html
    result.synthesis = None
    result.status = "failed"
    assert "no conclusions were invented" in render(result, EvidenceStore(root))


def test_cli_init_doctor_and_render(tmp_path):
    from pathlib import Path

    task = task_fixture(tmp_path)
    runner = CliRunner()
    directory = tmp_path / "study"
    created = runner.invoke(
        app,
        [
            "init",
            "survey",
            str(directory),
            "--personas",
            task.cohort.source,
            "--model",
            "fixture",
            "--goal",
            "Review",
            "--size",
            "3",
        ],
    )
    assert created.exit_code == 0, created.output
    assert runner.invoke(app, ["doctor", str(directory / "task.yaml")]).exit_code == 1
    assert runner.invoke(app, ["init", "survey", str(directory)]).exit_code != 0
    result = run(task, gateway=ScriptedModel())
    regenerated = runner.invoke(app, ["report", result.output_dir])
    assert regenerated.exit_code == 0, regenerated.output
    assert (Path(result.output_dir) / "report.html").is_file()


def test_cli_run_research_only_forwards_flag_and_rejects_open(tmp_path, monkeypatch):
    import genesia.cli as cli

    task = task_fixture(tmp_path)
    captured = {}

    def fake_run(spec, *, research_only=False):
        captured["task"] = spec
        captured["research_only"] = research_only
        return SimpleNamespace(
            run_id="research-only-run",
            status="completed",
            output_dir=str(tmp_path / "runs" / "research-only-run"),
            metrics={"analysis_skipped": True},
        )

    monkeypatch.setattr(cli, "load_task", lambda _: task)
    monkeypatch.setattr(cli, "run", fake_run)
    runner = CliRunner()

    result = runner.invoke(app, ["run", "task.yaml", "--research-only"])

    assert result.exit_code == 0, result.output
    assert captured == {"task": task, "research_only": True}
    assert '"run_id": "research-only-run"' in result.output
    rejected = runner.invoke(app, ["run", "task.yaml", "--research-only", "--open"], env={"FORCE_COLOR": "1"})
    assert rejected.exit_code != 0
    assert "--research-only does not generate a report" in Text.from_ansi(rejected.output).plain


def test_cli_analyze_accepts_repeatable_focus(tmp_path, monkeypatch):
    import genesia.cli as cli

    task = task_fixture(tmp_path)
    run_dir = tmp_path / "source-run"
    run_dir.mkdir()
    (run_dir / "run_manifest.json").write_text(
        json.dumps({"task": task.model_dump(mode="json")}),
        "utf-8",
    )
    captured = {}

    def fake_analyze(source, *, insight, candidate_labels=None, timeout_seconds=None):
        captured["source"] = source
        captured["insight"] = insight
        captured["candidate_labels"] = candidate_labels
        captured["timeout_seconds"] = timeout_seconds
        output = tmp_path / "analysis-run"
        output.mkdir()
        return SimpleNamespace(
            run_id="analysis-run",
            status="completed",
            output_dir=str(output),
            errors=[],
        )

    monkeypatch.setattr(cli, "analyze", fake_analyze)
    result = CliRunner().invoke(
        app,
        [
            "analyze",
            str(run_dir),
            "--language",
            "zh-CN",
            "--timeout-seconds",
            "300",
            "--focus",
            "Version choice",
            "--focus",
            "Critical uncertainty",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["source"] == run_dir
    assert captured["timeout_seconds"] == 300
    assert captured["insight"].language == "zh-CN"
    assert captured["insight"].focus == ["Version choice", "Critical uncertainty"]


def test_auto_context_runs_without_graph(tmp_path):
    task = task_fixture(tmp_path)
    material = tmp_path / "concept.md"
    material.write_text("A product concept with goals, but no defined interface states.", "utf-8")
    task.environment = EnvironmentSpec(mode="auto", sources=[dict(kind="document", path=str(material))])

    result = run(task, gateway=ScriptedModel())

    build = json.loads((__import__("pathlib").Path(result.output_dir) / "environment_build.json").read_text())
    assert result.status == "completed" and build["level"] == "context"
    assert all(episode.mode == "context" for episode in result.episodes)
    assert result.metrics["environment_build"]["summary"] == "Fixture concept without UI states"
    assert "Environment readiness: context; Fixture concept without UI states" in (
        __import__("pathlib").Path(result.output_dir) / "report.md"
    ).read_text("utf-8")
    assert not (__import__("pathlib").Path(result.output_dir) / "state_graph.json").exists()


def test_auto_image_runs_as_cards_without_graph(tmp_path):
    class AutoCardModel(ScriptedModel):
        def complete(self, purpose, payload, schema, **kwargs):
            if purpose == "environment_readiness":
                result = schema.model_validate(
                    dict(
                        summary="Fixture UI state",
                        states=[
                            dict(
                                id="calendar",
                                title="Calendar screen",
                                description="Visible calendar",
                                evidence=[dict(source_id=payload["sources"][0]["id"])],
                            )
                        ],
                    )
                )
                kwargs["validate"](result)
                return result
            return super().complete(purpose, payload, schema, **kwargs)

    task = task_fixture(tmp_path)
    image = tmp_path / "screen.png"
    image.write_bytes(b"fixture image")
    task.environment = EnvironmentSpec(mode="auto", sources=[dict(kind="image", path=str(image))])
    task.permissions.send_screenshots = True

    result = run(task, gateway=AutoCardModel())

    root = __import__("pathlib").Path(result.output_dir)
    build = json.loads((root / "environment_build.json").read_text())
    assert result.status == "completed" and build["level"] == "cards"
    assert all(episode.mode == "cards" for episode in result.episodes)
    assert (root / "ui_cards.json").is_file() and not (root / "state_graph.json").exists()


@pytest.mark.parametrize("connected", [False, True])
def test_auto_spec_background_and_joint_cards_reach_only_the_reviewed_interview(tmp_path, connected):
    from copy import deepcopy

    from genesia.runtime import model_content

    task = task_fixture(tmp_path)
    task.cohort.size = 1
    task.methods = task.methods[:2]
    for method in task.methods:
        method.evidence_mode = "complete"
    background = "Shared limitation: all data is synthetic."
    pages = [f"PAGE_{index}_ONLY" for index in range(5)]
    transitions = [f"Open goes from PAGE_{index} to PAGE_{index + 1}." for index in range(4)]
    spec = tmp_path / "spec.md"
    spec.write_text("\n".join([background, *pages, *transitions]), "utf-8")
    sources = [dict(kind="document", path=str(spec))]
    for index in range(5):
        image = tmp_path / f"page-{index}.png"
        image.write_bytes(f"page-image-{index}".encode())
        sources.append(dict(kind="image", path=str(image)))
    task.environment = EnvironmentSpec(mode="auto", sources=sources, max_steps=6)
    task.permissions.send_screenshots = True

    class MixedMaterialModel(ScriptedModel):
        def __init__(self):
            super().__init__()
            self.research_requests = []
            self.readiness_calls = 0

        def complete(self, purpose, payload, schema, **kwargs):
            if purpose == "environment_readiness":
                self.readiness_calls += 1
                spec_id = payload["sources"][0]["id"]
                result = schema.model_validate(
                    dict(
                        summary="Five supplied UI states with shared background",
                        background=[dict(source_id=spec_id, quote=background)],
                        states=[
                            dict(
                                id=f"s{index}",
                                title=f"Page {index}",
                                description=pages[index],
                                evidence=[
                                    dict(source_id=spec_id, quote=pages[index]),
                                    dict(source_id=source["id"]),
                                ],
                            )
                            for index, source in enumerate(payload["sources"][1:])
                        ],
                        transitions=[
                            dict(
                                source=f"s{index}",
                                target=f"s{index + 1}",
                                label="Next page",
                                evidence=[dict(source_id=spec_id, quote=quote)],
                            )
                            for index, quote in enumerate(transitions)
                        ]
                        if connected
                        else [],
                    )
                )
                kwargs["validate"](result)
                return result
            if purpose == "persona_action":
                assert len(payload["observation"]["image_refs"]) == 1
                result = schema.model_validate(
                    dict(
                        action="click",
                        target_id=payload["observation"]["targets"][0]["id"],
                        intent="Read the next supplied page",
                    )
                    if len(payload["history"]) < 3
                    else dict(action="stop", intent="I have enough context", outcome="completed")
                )
                kwargs["validate"](result)
                return result
            if purpose == "persona_research":
                self.research_requests.append(
                    (deepcopy(payload), schema, kwargs["interleave_key"], kwargs["output_contract"])
                )
            return super().complete(purpose, payload, schema, **kwargs)

    model = MixedMaterialModel()
    result = run(task, gateway=model)
    assert result.status == "completed", result.errors
    assert model.readiness_calls == 1
    episode = result.episodes[0]
    assert episode.mode == ("captured_graph" if connected else "cards")
    assert len(episode.coverage["visited_cards"]) == 4
    assert len(episode.coverage["unseen_cards"]) == 1
    assert len(episode.steps) == 4
    store = EvidenceStore(Path(result.output_dir))
    for payload, schema, key, contract in model.research_requests:
        content, _ = model_content(
            "persona_research",
            payload,
            schema,
            store,
            interleave_key=key,
            output_contract=contract,
        )
        text = "\n".join(item["text"] for item in content if item["type"] == "text")
        assert text.count(background) == 1
        assert all(text.count(page) == 1 for page in pages[:4])
        assert pages[4] not in text
        assert not any(transition in text for transition in transitions)
        assert sum(item["type"] == "image_url" for item in content) == 4
    assert len(model.research_requests) == 2
    assert store.verify()["valid"]


def test_auto_declared_graph_allows_persona_branch_choice(tmp_path):
    class BranchModel(ScriptedModel):
        def complete(self, purpose, payload, schema, **kwargs):
            if purpose == "environment_readiness":
                source = payload["sources"][0]
                result = schema.model_validate(
                    dict(
                        summary="Explicit branches",
                        states=[
                            dict(
                                id=name,
                                title=name,
                                description=f"{name} screen",
                                evidence=[dict(source_id=source["id"], quote=f"{name} screen.")],
                            )
                            for name in ("Home", "Settings", "Help")
                        ],
                        transitions=[
                            dict(
                                source="Home",
                                target=name,
                                label=f"Open {name}",
                                evidence=[dict(source_id=source["id"], quote=f"Home opens {name}.")],
                            )
                            for name in ("Settings", "Help")
                        ],
                    )
                )
                kwargs["validate"](result)
                return result
            if purpose == "persona_action" and not payload["history"]:
                targets = payload["observation"]["targets"]
                assert {target["name"] for target in targets} == {"Open Settings", "Open Help"}
                action = schema.model_validate(
                    dict(action="click", target_id=targets[1]["id"], intent="Get help")
                )
                kwargs["validate"](action)
                return action
            return super().complete(purpose, payload, schema, **kwargs)

    task = task_fixture(tmp_path)
    source = tmp_path / "spec.md"
    source.write_text(
        "Home screen. Settings screen. Help screen. Home opens Settings. Home opens Help.", "utf-8"
    )
    task.environment = EnvironmentSpec(mode="auto", sources=[dict(kind="document", path=str(source))])
    result = run(task, gateway=BranchModel())
    assert result.status == "completed"
    assert all(episode.mode == "captured_graph" for episode in result.episodes)
    assert all(episode.final_observation.state_id == "Help" for episode in result.episodes)
    assert result.metrics["environment_build"]["level"] == "graph"


def test_stop_is_unavailable_until_minimum_actions(tmp_path):
    class MinimumActionModel(ScriptedModel):
        def complete(self, purpose, payload, schema, **kwargs):
            if purpose == "persona_action" and "stop" not in payload["allowed_actions"]:
                result = schema.model_validate(dict(action="wait", intent="Continue observing"))
                if validate := kwargs.get("validate"):
                    validate(result)
                return result
            return super().complete(purpose, payload, schema, **kwargs)

    task = task_fixture(tmp_path)
    task.environment.max_steps = 3
    task.environment.min_actions_before_stop = 2
    result = run(task, gateway=MinimumActionModel())

    assert result.status == "completed"
    assert all(
        [step.action.action for step in episode.steps] == ["wait", "wait", "stop"]
        for episode in result.episodes
    )


def test_experience_budget_stop_preserves_final_state_and_interview(tmp_path):
    from genesia.runtime import StageBudgetExceeded

    class ExhaustedExploration(ScriptedModel):
        def complete(self, purpose, payload, schema, **kwargs):
            if purpose == "persona_action":
                if not payload["history"]:
                    return schema.model_validate(dict(action="wait", intent="Inspect this view"))
                raise StageBudgetExceeded("experience protected interview budget")
            return super().complete(purpose, payload, schema, **kwargs)

    result = run(task_fixture(tmp_path), gateway=ExhaustedExploration())
    assert result.status == "completed", result.errors
    assert len(result.responses) == 12
    assert all(episode.outcome == "exploration_budget" for episode in result.episodes)
    assert all(episode.outcome_basis == "automation_budget_limit" for episode in result.episodes)
    assert all(episode.final_observation is not None for episode in result.episodes)
    assert all(len(episode.steps) == 1 for episode in result.episodes)


def test_builtin_budget_path_preserves_interviews_and_analysis(tmp_path, monkeypatch):
    from genesia import api
    from genesia.schemas import BudgetProtection

    original_validate = api.validate_task
    monkeypatch.setattr(
        api, "validate_task", lambda task, network=False: original_validate(task, network=False)
    )

    class ChargingGateway(ScriptedModel):
        def __init__(self, config, store, budget):
            super().__init__()
            self.budget = budget

        def close(self):
            pass

        def complete(self, purpose, payload, schema, **kwargs):
            self.budget.reserve(850000 if purpose == "persona_action" else 100)
            if purpose == "persona_action":
                return schema.model_validate(dict(action="wait", intent="Inspect"))
            return super().complete(purpose, payload, schema, **kwargs)

    monkeypatch.setattr(api, "OpenAICompatibleGateway", ChargingGateway)
    task = task_fixture(tmp_path)
    task.budget.protection = BudgetProtection()
    task.budget.max_calls = 200
    task.budget.max_tokens = 2000000
    task.model.max_tokens = 1000
    task.execution.max_concurrent_personas = 3
    result = run(task)
    assert result.status == "completed", result.errors
    assert result.metrics["valid_responses"] == 12
    assert any(episode.outcome == "exploration_budget" for episode in result.episodes)
    assert result.metrics["budget"]["reserved_tokens"] <= task.budget.max_tokens
    stages = result.metrics["budget"]["stages"]
    assert stages["analysis"]["calls"] >= 3
    assert all(stages[f"research:p{index}"]["calls"] == 4 for index in range(3))


def test_preflight_checks_protected_question_capacity(tmp_path):
    from genesia.schemas import BudgetProtection

    task = task_fixture(tmp_path)
    task.budget.protection = BudgetProtection()
    task.budget.max_calls = 12
    task.model.max_tokens = 1000
    checks = preflight(task)
    assert not checks["ok"]
    assert any("question batches and retries" in issue for issue in checks["issues"])
    task.budget.max_calls = 200
    checks = preflight(task)
    assert checks["ok"], checks["issues"]
    assert checks["budget_plan"]["research:p0"]["calls"] == 20
    assert run(task, gateway=ScriptedModel()).status == "completed"


def test_phase_gate(tmp_path):
    model = ScriptedModel()
    episode = Episode(session_id="s", persona=Persona(id="p", profile={}), goal="Test", mode="scenario")
    agent = PersonaAgent(episode, model, EvidenceStore(tmp_path), BudgetLedger(BudgetSpec()))
    with pytest.raises(ValueError, match="until experience"):
        agent.research(MethodSpec(id="m", kind="interview", questions=[dict(id="q", text="Why?")]))
    assert model.calls == []


def test_representative_images_keep_first_middle_and_last():
    assert representative_images(["a", "b", "c", "d", "e", "e"], 3) == ["a", "c", "e"]
    assert representative_images(["a", "b"], 3) == ["a", "b"]
    assert representative_images(["a", "b"], 1) == ["b"]
    assert representative_images(["a"], 0) == []


@pytest.mark.parametrize("mode", ["live", "context", "cards", "walkthrough", "captured_graph"])
def test_action_choice_rejects_incompatible_and_repeated_targets(mode):
    observation = Observation(
        id="o3",
        mode=mode,
        url="http://localhost",
        text="Accent color",
        state_id="state",
        card_ids=["card"],
        targets=[Target(id="p1", name="Accent color", actions=["click"])],
    )
    click = Action(action="click", target_id="p1", intent="Open accent color")
    steps = [
        Step(
            number=number,
            observation=observation.model_copy(update={"id": f"o{number}"}),
            action=click,
            result=ExecutionResult(success=True, message="clicked"),
        )
        for number in (1, 2)
    ]

    with pytest.raises(ValueError, match="incompatible"):
        validate_action_choice(
            Action(action="select", target_id="p1", value="Manual", intent="Wrong action"),
            ["click", "select"],
            observation,
            [],
        )
    with pytest.raises(ValueError, match="repeat"):
        validate_action_choice(click, ["click", "stop"], observation, steps)


def test_stop_requires_all_configured_live_url_areas():
    colors = Observation(
        id="colors",
        mode="live",
        url="http://localhost/#/settings/personalization/colors",
        text="Colors",
    )
    background = Observation(
        id="background",
        mode="live",
        url="http://localhost/#/settings/personalization/background",
        text="Background",
    )
    step = Step(
        number=1,
        observation=background,
        action=Action(action="wait", intent="Review background"),
        result=ExecutionResult(success=True, message="reviewed"),
    )
    stop = Action(action="stop", intent="Done", outcome="completed")
    required = ["/settings/personalization/background", "/settings/personalization/themes"]

    with pytest.raises(ValueError, match="themes"):
        validate_action_choice(stop, ["stop"], colors, [step], required)

    themes = colors.model_copy(update={"url": "http://localhost/#/settings/personalization/themes"})
    validate_action_choice(stop, ["stop"], themes, [step], required)


@pytest.mark.parametrize(
    "kind,value,options,rows",
    [
        ("single", "invented", ["A", "B"], []),
        ("multiple", ["A", "A"], ["A", "B"], []),
        ("likert", {"wrong": "A"}, ["A", "B"], ["speed"]),
    ],
)
def test_survey_strict_validation(kind, value, options, rows):
    method = MethodSpec(
        id="survey",
        kind="survey",
        questions=[dict(id="q", text="Rate", kind=kind, options=options, rows=rows)],
    )
    answers = Answers(answers=[dict(question_id="q", value=value, evidence_refs=["e1"])])
    with pytest.raises(ValueError):
        validate_answers(answers, method, {"e1"})


def test_cross_persona_evidence_rejected():
    method = MethodSpec(id="m", kind="interview", questions=[dict(id="q", text="Why?")])
    answers = Answers(answers=[dict(question_id="q", value="Clear", evidence_refs=["other-persona"])])
    with pytest.raises(ValueError, match="outside"):
        validate_answers(answers, method, {"own"})


def test_survey_only_rejects_fabricated_experience_basis():
    method = MethodSpec(id="survey", kind="survey", questions=[dict(id="q", text="Why?")])
    answers = Answers(answers=[dict(question_id="q", value="Invented experience")])
    with pytest.raises(ValueError, match="Persona profile"):
        validate_answers(answers, method, set(), profile_only=True)


def test_cli_schema():
    result = CliRunner().invoke(app, ["schema"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["title"] == "TaskSpec"


def test_method_schema_rejects_wrong_value_shape_and_duplicate_answers():
    method = MethodSpec(
        id="review", kind="task_outcome_review", questions=[dict(id="q", text="What happened?")]
    )
    schema = answer_schema(method)
    with pytest.raises(ValueError):
        schema.model_validate(dict(answers=[dict(question_id="q", value={"achieved": "something"})]))
    with pytest.raises(ValueError):
        schema.model_validate(
            dict(answers=[dict(question_id="q", value="Done"), dict(question_id="q", value=None)])
        )


class FailingResearchModel(ScriptedModel):
    def complete(self, purpose, payload, schema, **kwargs):
        if purpose == "persona_research" and payload["method"]["kind"] == "survey":
            raise ValueError("Fixture invalid response")
        if purpose == "research_synthesis" and payload.get("output_stage") == "question_insights":
            assert all(row["status"] == "answered" for row in payload["rows"])
            assert all(row["method_id"] != "survey" for row in payload["rows"])
        return super().complete(purpose, payload, schema, **kwargs)


def test_invalid_responses_excluded_and_partial_recorded(tmp_path):
    result = run(task_fixture(tmp_path), gateway=FailingResearchModel())
    assert result.status == "partial"
    assert result.metrics["valid_responses"] == 9
    assert result.metrics["invalid_responses"] == 3
    assert result.synthesis


def test_permission_denied_before_any_model_call(tmp_path):
    task = task_fixture(tmp_path)
    task.permissions.send_persona = False
    model = ScriptedModel()
    with pytest.raises(ValueError, match="permissions"):
        run(task, gateway=model)
    assert model.calls == []


def test_captured_graph_three_personas_choose_transitions(tmp_path):
    task = task_fixture(tmp_path)
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(
        json.dumps(
            dict(
                start="home",
                nodes=[
                    dict(id="home", text="Home screen", source_ids=["local"]),
                    dict(id="review", text="Review screen", source_ids=["local"]),
                ],
                edges=[dict(id="open", source="home", target="review", label="Open review")],
            )
        ),
        encoding="utf-8",
    )
    task.environment = EnvironmentSpec(
        mode="captured_graph", sources=[dict(kind="graph", path=str(graph_path))]
    )

    class GraphModel(ScriptedModel):
        def complete(self, purpose, payload, schema, **kwargs):
            if purpose == "persona_action" and not payload["history"]:
                return schema.model_validate(dict(action="click", target_id="open", intent="Review"))
            if purpose == "persona_action":
                assert payload["observation"]["text"] == "Review screen"
            return super().complete(purpose, payload, schema, **kwargs)

    result = run(task, gateway=GraphModel())
    assert result.status == "completed"
    assert all(len(episode.steps) == 2 for episode in result.episodes)


def test_run_id_contains_sortable_utc_timestamp_and_unique_suffix():
    first = _new_run_id()
    second = _new_run_id()

    assert re.fullmatch(r"\d{8}T\d{6}Z-[0-9a-f]{8}", first)
    assert first != second


def test_network_preflight_rejects_unavailable_model(tmp_path, monkeypatch):
    import requests

    monkeypatch.setenv("OPENAI_API_KEY", "offline-fixture-key")

    class Catalog:
        status_code = 200

        def json(self):
            return [{"id": "another-model", "capabilities": {"supportsImageToText": True}}]

    monkeypatch.setattr(requests.Session, "get", lambda *args, **kwargs: Catalog())
    report = preflight(task_fixture(tmp_path), network=True)
    assert not report["ok"]
    assert any("not available" in issue for issue in report["issues"])


@pytest.mark.parametrize(
    ("status", "hint"),
    [(401, "credentials"), (403, "access"), (404, "base URL"), (429, "rate limit"), (503, "provider")],
)
def test_catalog_http_failure_is_actionable_without_exposing_provider_content(
    tmp_path, monkeypatch, status, hint
):
    import requests

    secret = "review-fixture-do-not-disclose"
    monkeypatch.setenv("OPENAI_API_KEY", secret)

    class Catalog:
        status_code = status
        text = f"Authorization: {secret}; private upstream diagnostics"

        def json(self):
            pytest.fail("Do not read provider bodies for rejected requests")

    monkeypatch.setattr(requests.Session, "get", lambda *args, **kwargs: Catalog())
    report = preflight(task_fixture(tmp_path), network=True)
    assert not report["ok"] and not report["network_checked"]
    assert any(f"HTTP {status}" in issue and hint in issue for issue in report["issues"])
    assert secret not in json.dumps(report)
    assert "private upstream" not in json.dumps(report)


@pytest.mark.parametrize("kind", ["timeout", "connection", "invalid_json", "invalid_shape"])
def test_catalog_errors_are_safe_and_specific(tmp_path, monkeypatch, kind):
    import requests

    secret = "unsafe-error-detail"
    monkeypatch.setenv("OPENAI_API_KEY", secret)

    class Catalog:
        status_code = 200

        def json(self):
            if kind == "invalid_json":
                raise requests.exceptions.JSONDecodeError("Invalid JSON", secret, 0)
            return {"data": [secret]}

    def get(*args, **kwargs):
        if kind == "timeout":
            raise requests.Timeout(secret)
        if kind == "connection":
            raise requests.ConnectionError(secret)
        return Catalog()

    monkeypatch.setattr(requests.Session, "get", get)
    report = preflight(task_fixture(tmp_path), network=True)
    assert not report["ok"] and not report["network_checked"]
    hint = {"timeout": "timed out", "connection": "connect"}.get(kind, "invalid")
    assert any(hint in issue for issue in report["issues"])
    assert secret not in json.dumps(report)


def test_live_preflight_reports_missing_optional_dependency(tmp_path, monkeypatch):
    from genesia import api

    original = api.importlib.util.find_spec
    monkeypatch.setattr(
        api.importlib.util,
        "find_spec",
        lambda name: None if name == "playwright" else original(name),
    )
    task = task_fixture(tmp_path)
    task.environment = EnvironmentSpec(mode="live", start_url="http://127.0.0.1:5173/")
    task.permissions.send_screenshots = True
    report = preflight(task)
    assert not report["ok"]
    assert any("genesia[live]" in issue for issue in report["issues"])


def test_preflight_is_public_facade_for_task_validation(monkeypatch):
    import genesia.api as api

    expected = {"ok": True, "network_checked": True}
    monkeypatch.setattr(api, "validate_task", lambda task, network: expected)
    assert api.preflight(object(), network=True) is expected


def test_run_uses_task_validation_not_preflight(tmp_path, monkeypatch):
    import genesia.api as api

    monkeypatch.setattr(api, "preflight", lambda *args, **kwargs: pytest.fail("public facade called"))
    monkeypatch.setattr(
        api,
        "validate_task",
        lambda *args, **kwargs: {"ok": False, "issues": ["fixture validation failure"]},
    )
    with pytest.raises(ValueError, match="Task validation failed: fixture validation failure"):
        api.run(task_fixture(tmp_path), gateway=ScriptedModel())


def test_prepare_uses_task_validation_not_preflight(tmp_path, monkeypatch):
    import genesia.api as api

    monkeypatch.setattr(api, "preflight", lambda *args, **kwargs: pytest.fail("public facade called"))
    monkeypatch.setattr(
        api,
        "validate_task",
        lambda *args, **kwargs: {"ok": False, "issues": ["fixture validation failure"]},
    )
    with pytest.raises(ValueError, match="Task validation failed: fixture validation failure"):
        api.prepare(task_fixture(tmp_path), gateway=ScriptedModel())


def test_openai_compatible_network_preflight_uses_standard_catalog(tmp_path, monkeypatch):
    import requests

    task = task_fixture(tmp_path)
    task.model = ModelSpec(
        provider="openai_compatible",
        base_url="https://api.example.com/v1",
        model="vision-model",
        api_key_env="EXAMPLE_API_KEY",
    )
    monkeypatch.setenv("EXAMPLE_API_KEY", "fixture-secret")
    request = {}

    class Catalog:
        status_code = 200

        def json(self):
            return {"data": [{"id": "vision-model"}]}

    def get(_self, url, **kwargs):
        request.update(url=url, **kwargs)
        return Catalog()

    monkeypatch.setattr(requests.Session, "get", get)
    report = preflight(task, network=True)
    assert report["ok"]
    assert report["provider"] == "openai_compatible"
    assert request["url"] == "https://api.example.com/v1/models"
    assert request["headers"] == {"Authorization": "Bearer fixture-secret"}


def test_openai_compatible_network_preflight_requires_configured_key(tmp_path):
    task = task_fixture(tmp_path)
    task.model = ModelSpec(
        provider="openai_compatible",
        base_url="https://api.example.com/v1",
        model="vision-model",
        api_key_env="MISSING_EXAMPLE_API_KEY",
    )
    report = preflight(task, network=True)
    assert not report["ok"]
    assert any("environment variable" in issue for issue in report["issues"])
