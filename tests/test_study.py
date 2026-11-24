import pytest
from test_workflow import task_fixture

from genesia.api import preflight, prepare
from genesia.schemas import EnvironmentSpec, Persona, StudySpec
from genesia.study import readiness


def test_unmapped_objective_blocks_preflight(tmp_path):
    task = task_fixture(tmp_path)
    task.study = StudySpec(objectives=[dict(id="discover", description="Assess discoverability")])
    report = preflight(task)
    assert not report["ok"]
    assert any("without questions" in issue for issue in report["issues"])


def test_sample_segments_and_leading_language(tmp_path):
    task = task_fixture(tmp_path)
    task.goal = "Surely this is easy, don't you agree?"
    task.study = StudySpec(min_personas=4, sample_requirements={"role": ["manager"]})
    report = readiness(task, [])
    assert not report["ok"]
    assert {issue["category"] for issue in report["issues"]} >= {"scope", "sample", "task"}


def test_numeric_segments_require_integer_profile_values(tmp_path):
    task = task_fixture(tmp_path)
    task.study = StudySpec.model_validate(
        {
            "segments": {
                "age_group": {
                    "source": "Core Identity.age",
                    "buckets": ["<30", "30-39", "40-49", "50+"],
                }
            }
        }
    )
    people = [
        Persona(id="valid", profile={"Core Identity": {"age": 29}}),
        Persona(id="missing", profile={"Core Identity": {}}),
        Persona(id="float", profile={"Core Identity": {"age": 29.5}}),
    ]

    report = readiness(task, people)

    issue = next(item for item in report["issues"] if "Integer segment age_group" in item["message"])
    assert issue["severity"] == "error"
    assert "missing" in issue["message"] and "float" in issue["message"]


def test_unknown_objective_reference_rejected(tmp_path):
    task = task_fixture(tmp_path).model_dump()
    task["methods"][0]["questions"][0]["objective_ids"] = ["unknown"]
    from genesia.schemas import TaskSpec

    with pytest.raises(ValueError, match="unknown objective"):
        TaskSpec.model_validate(task)


def test_prepare_does_not_run_persona_or_research_answers(tmp_path):
    from test_workflow import ScriptedModel

    from genesia.api import prepare

    model = ScriptedModel()
    report = prepare(task_fixture(tmp_path), gateway=model)
    assert report["status"] == "ready"
    assert model.calls == []


def test_prepare_auto_context_reports_compilation_level(tmp_path):
    from test_workflow import ScriptedModel

    material = tmp_path / "concept.md"
    material.write_text("Product purpose without screens or transitions.", "utf-8")
    task = task_fixture(tmp_path)
    task.environment = EnvironmentSpec(mode="auto", sources=[dict(kind="document", path=str(material))])

    report = prepare(task, gateway=ScriptedModel())

    assert report["status"] == "ready"
    assert report["environment_build"]["level"] == "context"
    assert report["environment_build"]["graph"] is None


@pytest.mark.parametrize("with_ui", [False, True])
def test_auto_reviews_context_and_cards_against_sources(tmp_path, with_ui):
    from test_workflow import ScriptedModel

    class Reviewer(ScriptedModel):
        def complete(self, purpose, payload, schema, **kwargs):
            if purpose == "environment_readiness" and with_ui:
                source = payload["sources"][0]
                result = schema.model_validate(
                    dict(
                        summary="One described UI state",
                        states=[
                            dict(
                                id="home",
                                title="Home",
                                description=source["text"],
                                evidence=[dict(source_id=source["id"], quote=source["text"])],
                            )
                        ],
                    )
                )
                kwargs["validate"](result)
                return result
            if purpose in {"study_review", "fidelity_review"}:
                self.calls.append((purpose, payload))
                assert payload["graph"] is None
                assert payload["environment_build"]["level"] == ("cards" if with_ui else "context")
                assert "calendar" in payload["sources"][0]["text"]
                result = schema.model_validate(dict(summary="Review completed", issues=[]))
                kwargs["validate"](result)
                return result
            return super().complete(purpose, payload, schema, **kwargs)

    task = task_fixture(tmp_path)
    task.study = StudySpec(
        review=True,
        objectives=[dict(id="calendar", description="Review calendar", evidence_terms=["calendar"])],
    )
    task.methods[0].questions[0].objective_ids = ["calendar"]
    source = tmp_path / "spec.md"
    source.write_text("Home screen shows a calendar." if with_ui else "A shared calendar concept.", "utf-8")
    task.environment = EnvironmentSpec(
        mode="auto", sources=[dict(kind="document", path=str(source))], fidelity_review=True
    )
    model = Reviewer()
    report = prepare(task, gateway=model)
    review = report["research_readiness"]
    assert report["status"] == "ready" and "fidelity_assessment" in review
    assert review["evidence_coverage"]["calendar"]["matched"] == ["calendar"]
    assert {purpose for purpose, _ in model.calls} >= {"study_review", "fidelity_review"}


def test_model_cannot_confuse_recording_count_with_cohort(tmp_path):
    from genesia.personas import load_cohort
    from genesia.runtime import EvidenceStore
    from genesia.study import model_review

    task = task_fixture(tmp_path)
    people, _ = load_cohort(task.cohort)

    class BadReviewer:
        def complete(self, purpose, payload, schema, **kwargs):
            assert payload["sample"]["selected_count"] == 3
            result = schema.model_validate(
                dict(
                    summary="Incorrect",
                    issues=[
                        dict(
                            category="sample",
                            severity="error",
                            message="Only one recording",
                            suggestion="Add participants",
                            evidence_refs=[],
                        )
                    ],
                )
            )
            kwargs["validate"](result)
            return result

    with pytest.raises(ValueError, match="single recording"):
        model_review(task, people, None, BadReviewer(), EvidenceStore(tmp_path))


def test_live_study_review_requires_empty_refs_without_sources(tmp_path):
    from genesia.personas import load_cohort
    from genesia.runtime import EvidenceStore
    from genesia.study import model_review

    task = task_fixture(tmp_path)
    people, _ = load_cohort(task.cohort)

    class Reviewer:
        def complete(self, purpose, payload, schema, **kwargs):
            assert purpose == "study_review"
            assert payload["available_evidence_ids"] == []
            assert "every evidence_refs list must be empty" in payload["instruction"]
            result = schema.model_validate(
                {
                    "summary": "Live readiness is unknown until interaction.",
                    "issues": [
                        {
                            "category": "evidence",
                            "severity": "warning",
                            "message": "Live UI evidence is not observed yet.",
                            "suggestion": "Review the completed episodes.",
                            "evidence_refs": [],
                        }
                    ],
                }
            )
            kwargs["validate"](result)
            return result

    result = model_review(task, people, None, Reviewer(), EvidenceStore(tmp_path))

    assert result.issues[0].evidence_refs == []


def test_fidelity_schema_exposes_its_category_constraint_and_source_ids(tmp_path):
    from genesia.personas import load_cohort
    from genesia.runtime import EvidenceStore
    from genesia.schemas import ReviewAssessment
    from genesia.study import model_review

    task = task_fixture(tmp_path)
    people, _ = load_cohort(task.cohort)

    class Reviewer:
        def complete(self, purpose, payload, schema, **kwargs):
            assert purpose == "fidelity_review"
            assert payload["available_evidence_ids"] == []
            definition = schema.model_json_schema()["$defs"]["FidelityReviewIssue"]
            assert definition["properties"]["category"]["const"] == "fidelity"
            with pytest.raises(ValueError, match="fidelity"):
                schema.model_validate(
                    {
                        "summary": "Invalid category",
                        "issues": [
                            {
                                "category": "evidence",
                                "severity": "warning",
                                "message": "Source gap",
                                "suggestion": "Review sources",
                            }
                        ],
                    }
                )
            value = schema.model_validate(
                {
                    "summary": "No source content",
                    "issues": [
                        {
                            "category": "fidelity",
                            "severity": "warning",
                            "message": "Cannot assess fidelity without sources",
                            "suggestion": "Supply material",
                            "evidence_refs": [],
                        }
                    ],
                }
            )
            kwargs["validate"](value)
            return value

    result = model_review(task, people, None, Reviewer(), EvidenceStore(tmp_path), fidelity=True)
    assert isinstance(result, ReviewAssessment)
    assert result.issues[0].category == "fidelity"
