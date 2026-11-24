import importlib.util
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from test_methods import SurveyModel

from genesia import preflight, run
from genesia.schemas import TaskSpec

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "use_cases" / "Profile-Grounded Persona Survey"


def runner():
    spec = importlib.util.spec_from_file_location("delegation_survey_case", CASE / "run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def options(tmp_path, **overrides):
    source = tmp_path / "people.json"
    source.write_text(json.dumps([{"id": f"p{i}", "profile": {}} for i in range(20)]), "utf-8")
    return SimpleNamespace(
        **{
            "task": CASE / "task.yaml",
            "personas": source,
            "count": None,
            "persona_id": None,
            "model": None,
            "base_url": None,
            "api_key_env": None,
            "language": None,
            "output_dir": tmp_path / "runs",
            "allow_model_data": True,
            **overrides,
        }
    )


def test_survey_case_has_no_environment_or_experience_questions(tmp_path):
    task = runner().build_task(options(tmp_path))
    assert task.environment.mode == "survey"
    assert not task.environment.sources and task.environment.start_url is None
    assert task.cohort.size == task.study.min_personas == 20
    assert not task.cohort.ids
    method = task.methods[0]
    assert method.kind == "survey" and method.max_images == method.max_followups == 0
    assert len(method.questions) == 12
    assert {q.kind for q in method.questions} == {"text", "single", "multiple", "likert"}
    assert {q.purpose for q in method.questions} == {"context", "reflection"}
    assert sum(bool(q.ask_if) for q in method.questions) == 2
    assert all(not q.candidate for q in method.questions)
    assert not task.study.segments and not task.study.segment_fields
    assert not task.permissions.send_screenshots
    assert preflight(task)["ok"]


def test_survey_case_requires_explicit_permissions_and_preserves_cohort_overrides(tmp_path):
    module = runner()
    denied = module.build_task(options(tmp_path, allow_model_data=False))
    assert not preflight(denied)["ok"]
    task = module.build_task(
        options(
            tmp_path,
            persona_id=["p1", "p2"],
            count=2,
            model="chosen-text-model",
            base_url="https://api.example.com/v1",
            api_key_env="CUSTOM_KEY",
            language="zh-CN",
        )
    )
    assert task.cohort.ids == ["p1", "p2"]
    assert task.cohort.size == task.study.min_personas == 2
    assert task.model.model == "chosen-text-model" and task.model.api_key_env == "CUSTOM_KEY"
    assert task.insight.language == "zh-CN" and not task.permissions.send_screenshots
    with pytest.raises(ValueError, match="unique"):
        module.build_task(options(tmp_path, persona_id=["p1", "p1"]))
    with pytest.raises(ValueError, match="must match"):
        module.build_task(options(tmp_path, persona_id=["p1"], count=2))


@pytest.mark.parametrize("stage", ["preflight", "run"])
@pytest.mark.parametrize("succeeds", [False, True])
def test_survey_runner_uses_only_the_selected_public_entry(tmp_path, monkeypatch, capsys, stage, succeeds):
    module = runner()
    source = options(tmp_path).personas
    called = []

    def checked_preflight(task, *, network=False):
        assert stage == "preflight"
        called.append(("preflight", network))
        return {"ok": succeeds}

    def checked_run(task):
        assert stage == "run"
        called.append(("run", False))
        return SimpleNamespace(
            run_id="fixture",
            status="completed" if succeeds else "partial",
            output_dir=str(tmp_path),
            episodes=[SimpleNamespace(mode="survey")],
            metrics={},
            errors=[] if succeeds else ["Fixture failure"],
        )

    monkeypatch.setattr(module, "preflight", checked_preflight)
    monkeypatch.setattr(module, "run", checked_run)
    args = ["--personas", str(source), "--allow-model-data"]
    if stage == "preflight":
        args += ["--preflight", "--network"]
    assert module.main(args) == (0 if succeeds else 1)
    assert called == [(stage, stage == "preflight")]
    output = json.loads(capsys.readouterr().out)
    if stage == "run":
        assert output["episode_modes"] == ["survey"]


def test_survey_runner_rejects_network_flag_without_preflight(tmp_path):
    with pytest.raises(SystemExit) as error:
        runner().main(["--personas", str(options(tmp_path).personas), "--network"])
    assert error.value.code == 2


@pytest.mark.parametrize("non_survey_input", [False, True])
def test_survey_runner_rejects_product_input_or_non_survey_methods(tmp_path, non_survey_input):
    module = runner()
    args = options(tmp_path)
    data = module.build_task(args).model_dump()
    if non_survey_input:
        data["environment"] = {"mode": "live", "start_url": "http://127.0.0.1:8000/"}
    else:
        data["methods"][0]["kind"] = "interview"
    args.task = tmp_path / "unsupported-task.yaml"
    args.task.write_text(yaml.safe_dump(data), "utf-8")
    with pytest.raises(ValueError, match="survey"):
        module.build_task(args)


class DelegationFixtureModel(SurveyModel):
    def complete(self, purpose, payload, schema, **kwargs):
        if purpose == "persona_research":
            self.calls.append((purpose, deepcopy(payload)))
            assert payload["experience_timeline"] == []
            assert kwargs.get("images") is None
            person = payload["episode_summary"]["persona"]["id"]
            answers = []
            for question in payload["method"]["questions"]:
                if question["id"] == "delegation_position":
                    value = question["options"][int(person[-1])]
                elif question["kind"] == "single":
                    value = question["options"][0]
                elif question["kind"] == "multiple":
                    value = question["options"][:2]
                elif question["kind"] == "likert":
                    value = {row: question["options"][0] for row in question["rows"]}
                else:
                    value = "A hypothetical preference, not product experience."
                if person == "p2" and question["id"] == "next_validation":
                    value = None
                answers.append(
                    dict(
                        question_id=question["id"],
                        value=value,
                        basis="profile",
                        evidence_refs=[],
                        reason="A preference grounded in the supplied context."
                        if question.get("explain")
                        else "",
                    )
                )
            result = schema.model_validate({"answers": answers})
            kwargs["validate"](result)
            return result
        if purpose == "research_synthesis" and payload.get("output_stage") == "question_insights":
            self.calls.append((purpose, deepcopy(payload)))
            rows = payload["rows"]
            suggestion = rows[0]["question"]["feedback_role"] == "suggestion"
            result = schema.model_validate(
                dict(
                    summary="Synthetic preference summary.",
                    findings=[
                        dict(
                            id="fixture",
                            text="A stated hypothetical preference, not an observed result.",
                            category="opportunity" if suggestion else "preference",
                            feedback_type="suggestion" if suggestion else "preference",
                            journey_stage="overall",
                            answer_ids=[row["answer_id"] for row in rows],
                            participants=[],
                            evidence_refs=[],
                        )
                    ],
                    limitations="Synthetic survey fixture, not human data.",
                    recommendations=[],
                )
            )
            kwargs["validate"](result)
            return result
        return super().complete(purpose, payload, schema, **kwargs)


def test_full_survey_preserves_all_branch_outcomes_and_exact_denominators(tmp_path):
    data = runner().build_task(options(tmp_path, count=3, persona_id=["p0", "p1", "p2"])).model_dump()
    data["study"]["review"] = False
    task = TaskSpec.model_validate(data)
    model = DelegationFixtureModel()
    result = run(
        task,
        gateway=model,
        environment_factory=lambda *_: (_ for _ in ()).throw(
            AssertionError("Survey must not open a product")
        ),
    )
    assert result.status == "completed", result.errors or [response.error for response in result.responses]
    assert result.metrics["valid_responses"] == 3
    assert all(
        ep.mode == "survey"
        and ep.phase == "finished"
        and not ep.steps
        and ep.final_observation is None
        and ep.outcome == "survey_ready"
        for ep in result.episodes
    )
    source = json.loads((Path(result.output_dir) / "analysis_input.json").read_text("utf-8"))
    assert len(source["rows"]) == 36
    assert sum(row["status"] == "skipped" for row in source["rows"]) == 4
    assert sum(row["status"] == "not_observed" for row in source["rows"]) == 1
    assert sum(row["status"] == "answered" for row in source["rows"]) == 31
    assert len(result.report.analysis["reviewed_answer_ids"]) == 31
    stats = {q["question_id"]: q for q in result.metrics["descriptive_statistics"]["questions"]}
    assert stats["first_task"]["n_answered"] == stats["refusal_reason"]["n_answered"] == 1
    assert stats["first_task"]["n_skipped"] == stats["refusal_reason"]["n_skipped"] == 2
    assert stats["next_validation"]["n_answered"] == 2 and stats["next_validation"]["n_not_observed"] == 1
    assert stats["relevant_tasks"]["n_answered"] == 3
    assert stats["relevant_tasks"]["counts"] == {
        option: 3 for option in task.methods[0].questions[0].options[:2]
    }
    assert sum(stats["relevant_tasks"]["percent_of_answered"].values()) == 200
    assert all(
        not answer.evidence_refs and answer.basis in {"profile", "not_observed", "skipped"}
        for response in result.responses
        for answer in response.answers
    )
    assert all(finding.category != "experience" for finding in result.synthesis.findings)
    assert all(r.kind != "design_change" for r in result.synthesis.recommendations)
    root = Path(result.output_dir)
    assert (root / "insight_report.md").read_bytes() == (root / "report.md").read_bytes()
    assert not (root / "environment_build.json").exists()
    assert not (root / "state_graph.json").exists()
    assert not (root / "ui_cards.json").exists()
    assert not any(purpose in {"persona_action", "environment_readiness"} for purpose, _ in model.calls)
    asked = {
        person: [
            question["id"]
            for purpose, payload in model.calls
            if purpose == "persona_research" and payload["episode_summary"]["persona"]["id"] == person
            for question in payload["method"]["questions"]
        ]
        for person in ("p0", "p1", "p2")
    }
    assert "first_task" in asked["p0"] and "refusal_reason" not in asked["p0"]
    assert "first_task" not in asked["p1"] and "refusal_reason" in asked["p1"]
    assert "first_task" not in asked["p2"] and "refusal_reason" not in asked["p2"]
