import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote

import pytest

pytestmark = pytest.mark.publication
CASE = Path(__file__).resolve().parents[2] / "use_cases" / "Profile-Grounded Persona Survey"
SAMPLE = CASE / "sample"


def test_survey_publication_records_one_intact_profile_only_run():
    manifest = json.loads((SAMPLE / "manifest.json").read_text("utf-8"))
    assert manifest["source"]["phase"] == "full_study"
    assert manifest["source"]["status"] == "completed"
    assert manifest["source"]["analysis_recovery_used"] is False
    assert manifest["source"]["upstream_model_id"] == "openai/gpt-6.1-terra"
    assert manifest["source"]["inference_parameters"]["temperature"] == 1
    protocol = manifest["protocol"]
    assert protocol["question_slots"] == protocol["personas"] * protocol["question_definitions"] == 240
    assert protocol["answered"] + protocol["skipped"] + protocol["not_observed"] == 240
    assert protocol["reviewed_answers"] == protocol["answered"] == 220
    assert protocol["product_observations"] == protocol["product_actions"] == 0
    assert protocol["model_validation_corrections"] == 0
    assert protocol["findings"] == 8 and protocol["recommendations"] == 6
    assert hashlib.sha256((CASE / "task.yaml").read_bytes()).hexdigest() == manifest["questionnaire_sha256"]
    for name, metadata in manifest["files"].items():
        assert hashlib.sha256((SAMPLE / name).read_bytes()).hexdigest() == metadata["sha256"]


def test_survey_distributions_preserve_skips_matrices_and_denominators():
    source = json.loads((SAMPLE / "distributions.json").read_text("utf-8"))
    assert len(source["questions"]) == 12
    assert sum(q["n_answered"] for q in source["questions"]) == 220
    assert sum(q["n_skipped"] for q in source["questions"]) == 20
    for question in source["questions"]:
        assert question["n_answered"] + question["n_skipped"] + question["n_not_observed"] == 20
        if question["kind"] in {"single", "multiple"}:
            assert question["percent_of_answered"] == {
                choice: round(count / question["n_answered"] * 100, 2)
                for choice, count in question["counts"].items()
            }
        for counts in question["matrix_counts"].values():
            assert sum(counts.values()) == question["n_answered"]
    refusal = next(q for q in source["questions"] if q["question_id"] == "refusal_reason")
    assert refusal["n_answered"] == 0 and refusal["n_skipped"] == 20
    boundaries = next(q for q in source["questions"] if q["question_id"] == "approval_boundaries")
    assert boundaries["matrix_counts"]["Delete a digital file"] == {
        "Confirm every execution": 19,
        "Would not delegate": 1,
    }
    uncertainty = next(q for q in source["questions"] if q["question_id"] == "uncertain_output")
    assert uncertainty["counts"] == {
        "Provide an uncertain draft for me to review": 17,
        "Stop and ask me before continuing": 3,
    }
    assert "segment_memberships" not in source


def test_survey_sample_excludes_private_data_and_has_valid_case_links():
    assert {p.name for p in SAMPLE.iterdir()} == {
        "README.md",
        "README_CN.md",
        "report.md",
        "distributions.json",
        "manifest.json",
    }
    for path in SAMPLE.iterdir():
        text = path.read_text("utf-8")
        assert not re.search(r"persona-\d+|[A-Za-z]:[\\/]|pre-test|api_key|bearer_token", text, re.I)
        assert not any(model in text for model in ("gpt-5.4", "claude-sonnet", "deepseek"))
    report = (SAMPLE / "report.md").read_text("utf-8")
    assert "[SIMULATED]" in report and "## Limitations" in report
    assert "## Appendix / Evidence" not in report
    assert "Evidence contributors:" in report and "not votes on every claim" in report
    assert "3/20" in report and "4/20" in report
    assert "\u4e0d\u80fd\u53ea\u636e\u6b64\u51b3\u5b9a\u9ed8\u8ba4\u6743\u9650" in report
    assert "\u6761\u4ef6\u8df3\u8fc7\u4e0d\u662f\u7f3a\u5931\u6216\u62d2\u7edd" in report
    assert "\u591a\u9009\u4e0d\u662f\u6392\u5e8f" in report
    assert "(distributions.json)" in report
    for guide in (CASE / "README.md", *SAMPLE.glob("*.md")):
        for target in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", guide.read_text("utf-8")):
            if not target.startswith(("http:", "https:")):
                assert (guide.parent / unquote(target)).exists(), (guide, target)
