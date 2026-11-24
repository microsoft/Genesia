import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest
import yaml
from test_methods import SurveyModel
from test_workflow import ScriptedModel

from genesia import load_task, preflight, prepare, run
from genesia.runtime import EvidenceStore

ROOT = Path(__file__).parents[1]
LIVE_SKILL = ROOT / ".github" / "skills" / "genesia-live-prototype"
COMPARISON_SKILL = ROOT / ".github" / "skills" / "genesia-live-comparison"
RECORDED_SKILL = ROOT / ".github" / "skills" / "genesia-recorded-prototype"
SURVEY_SKILL = ROOT / ".github" / "skills" / "genesia-persona-survey"
PERSONA_GENERATION_SKILL = ROOT / ".github" / "skills" / "genesia-persona-generation"
RAW_ANSWER_REPORT_SKILL = ROOT / ".github" / "skills" / "genesia-raw-answer-report"
RAW_ANSWER_RESEARCH_REPORT_SKILL = ROOT / ".github" / "skills" / "genesia-raw-answer-research-report"


def frontmatter(text: str) -> dict:
    match = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, "SKILL.md requires YAML frontmatter"
    return yaml.safe_load(match.group(1))


@pytest.mark.parametrize(
    "skill",
    [
        LIVE_SKILL,
        COMPARISON_SKILL,
        RECORDED_SKILL,
        SURVEY_SKILL,
        PERSONA_GENERATION_SKILL,
        RAW_ANSWER_REPORT_SKILL,
        RAW_ANSWER_RESEARCH_REPORT_SKILL,
    ],
    ids=lambda path: path.name,
)
def test_skill_metadata_and_relative_resources_are_valid(skill):
    text = (skill / "SKILL.md").read_text("utf-8")
    metadata = frontmatter(text)
    assert metadata["name"] == skill.name
    assert metadata.get("user-invocable") is True
    assert isinstance(metadata.get("description"), str) and metadata["description"].strip()
    for target in re.findall(r"\]\(([^)]+)\)", text):
        url = urlsplit(target)
        if not url.scheme and url.path:
            assert (skill / unquote(url.path)).resolve().exists(), target
    assert not (skill / "assets" / "personas.json").exists()


@pytest.mark.browser
def test_genesia_live_template_accepts_user_supplied_personas(tmp_path):
    personas = tmp_path / "personas.json"
    personas.write_text(
        json.dumps([{"id": f"p{index}", "profile": {"source": "test fixture"}} for index in range(5)]),
        "utf-8",
    )
    task = load_task(LIVE_SKILL / "assets" / "live-task.yaml")
    task.cohort.source = str(personas)
    report = preflight(task)

    assert report["ok"], report["issues"]
    assert report["research_readiness"]["sample_size"] == 5
    assert task.environment.mode == "live"
    assert task.permissions.send_screenshots is True
    assert task.model.provider == "openai_compatible"


@pytest.mark.parametrize("expected_level", ["context", "cards", "graph"])
def test_genesia_recorded_template_accepts_user_sources(tmp_path, expected_level):
    class RecordedModel(ScriptedModel):
        def complete(self, purpose, payload, schema, **kwargs):
            if purpose == "environment_readiness":
                self.calls.append((purpose, payload))
                assert "questions" not in json.dumps(payload)
                state_count = {"context": 0, "cards": 1, "graph": 2}[expected_level]
                result = schema.model_validate(
                    dict(
                        summary="Synthetic recording assessment",
                        states=[
                            dict(
                                id=f"state-{index}",
                                title=source["name"],
                                description="Visible fixture state",
                                evidence=[dict(source_id=source["id"])],
                            )
                            for index, source in enumerate(payload["sources"][:state_count])
                        ],
                    )
                )
            elif purpose in {"study_review", "fidelity_review"}:
                self.calls.append((purpose, payload))
                assert payload["environment_build"]["level"] == expected_level
                result = schema.model_validate(dict(summary="Fixture review", issues=[]))
            else:
                return super().complete(purpose, payload, schema, **kwargs)
            kwargs["validate"](result)
            return result

    personas = tmp_path / "personas.json"
    personas.write_text(
        json.dumps([{"id": f"p{index}", "profile": {"source": "test fixture"}} for index in range(5)]),
        "utf-8",
    )
    frames = tmp_path / "frames"
    frames.mkdir()
    for name in ("001.png", "002.png"):
        (frames / name).write_bytes(b"test frame")
    manifest = tmp_path / "frames.json"
    manifest.write_text(
        json.dumps(
            {
                "frames": [
                    {"path": "frames/001.png", "timestamp_seconds": 0.0},
                    {"path": "frames/002.png", "timestamp_seconds": 2.0},
                ]
            }
        ),
        "utf-8",
    )

    task = load_task(RECORDED_SKILL / "assets" / "recorded-task.yaml")
    assert task.environment.sources[0].kind == "video"
    task.cohort.source = str(personas)
    task.environment.sources[0] = task.environment.sources[0].model_copy(
        update={"kind": "recording", "path": str(manifest)}
    )
    report = preflight(task)

    assert report["ok"], report["issues"]
    assert report["research_readiness"]["sample_size"] == 5
    assert task.environment.mode == "auto"
    assert task.environment.fidelity_review is True
    assert task.permissions.send_screenshots is True

    task.output_dir = str(tmp_path / "runs")
    model = RecordedModel()
    preparation = prepare(task, gateway=model)
    root = Path(preparation["output_dir"])

    assert preparation["status"] == "ready"
    assert preparation["environment_build"]["level"] == expected_level
    for name in (
        "preparation.json",
        "study_review.json",
        "environment_readiness.json",
        "environment_build.json",
    ):
        assert (root / name).is_file()
    assert (root / "ui_cards.json").is_file() == (expected_level != "context")
    assert (root / "state_graph.json").is_file() == (expected_level == "graph")
    assert {purpose for purpose, _ in model.calls} == {
        "environment_readiness",
        "study_review",
        "fidelity_review",
    }
    assert EvidenceStore(root).verify()["valid"]


def test_genesia_survey_template_accepts_user_personas(tmp_path):
    personas = tmp_path / "personas.json"
    personas.write_text(
        json.dumps([{"id": f"p{index}", "profile": {"source": "test fixture"}} for index in range(5)]),
        "utf-8",
    )
    task = load_task(SURVEY_SKILL / "assets" / "survey-task.yaml")
    task.cohort.source = str(personas)
    report = preflight(task)

    assert report["ok"], report["issues"]
    assert report["research_readiness"]["sample_size"] == 5
    assert task.environment.mode == "survey"
    assert task.environment.sources == [] and task.environment.start_url is None
    assert {method.kind for method in task.methods} == {"survey"}
    assert task.permissions.send_screenshots is False


def test_genesia_survey_template_runs_and_writes_insight_report(tmp_path):
    personas = tmp_path / "personas.json"
    personas.write_text(
        json.dumps([{"id": f"p{index}", "profile": {"source": "test fixture"}} for index in range(5)]),
        "utf-8",
    )
    task = load_task(SURVEY_SKILL / "assets" / "survey-task.yaml")
    task.cohort.source = str(personas)
    task.output_dir = str(tmp_path / "runs")

    result = run(task, gateway=SurveyModel())

    root = Path(result.output_dir)
    assert result.status == "completed"
    assert result.metrics["valid_responses"] == 5
    assert all(episode.mode == "survey" and not episode.steps for episode in result.episodes)
    assert not (root / "environment_readiness.json").exists()
    assert not (root / "environment_build.json").exists()
    assert (root / "report.md").is_file()
    assert "Responses: 5 valid; 0 invalid; 0 missing" in (root / "insight_report.md").read_text("utf-8")
    assert (root / "report.html").is_file()
    assert (root / "insight_report.md").read_bytes() == (root / "report.md").read_bytes()
    assert EvidenceStore(root).verify()["valid"]
