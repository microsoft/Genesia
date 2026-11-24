import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote

import pytest

pytestmark = pytest.mark.publication
CASE = Path(__file__).resolve().parents[2] / "use_cases" / "Specification & Screenshot Review"
SAMPLE = CASE / "sample"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_material_sample_is_one_completed_full_study_with_matching_hashes():
    manifest = json.loads((SAMPLE / "manifest.json").read_text("utf-8"))
    assert manifest["source"]["status"] == "completed"
    assert manifest["source"]["phase"] == "full_study"
    assert manifest["source"]["analysis_recovery_used"] is False
    assert manifest["source"]["upstream_model_id"] == "gpt-6.1-sol"
    assert manifest["source"]["inference_parameters"]["temperature"] == 1
    protocol = manifest["protocol"]
    assert protocol["personas"] * protocol["questions_per_persona"] == protocol["eligible_answers"] == 200
    assert protocol["reviewed_answers"] == 200
    assert protocol["states"] == protocol["cards"] == 11
    assert protocol["declared_transitions"] == 26 and protocol["background_passages"] == 13
    assert protocol["steps"] == 110
    assert protocol["findings"] == 6 and protocol["recommendations"] == 4
    assert len(protocol["fidelity_warnings"]) == 2
    assert all(issue["severity"] == "warning" for issue in protocol["fidelity_warnings"])
    assert protocol["live_product_execution"] is False
    assert sum(protocol["usefulness_counts"].values()) == 20
    assert protocol["usefulness_counts"] == {"Useful": 17, "Mixed": 3}
    assert manifest["inputs"]["task_sha256"] == sha(CASE / "task.yaml")
    assert manifest["inputs"]["spec_sha256"] == sha(CASE / "materials" / "spec.md")
    assert manifest["inputs"]["material_provenance_sha256"] == sha(CASE / "materials" / "provenance.json")
    for name, metadata in manifest["files"].items():
        assert sha(SAMPLE / name) == metadata["sha256"]


def test_material_sample_excludes_private_run_assets_and_paths():
    assert {path.name for path in SAMPLE.iterdir()} == {
        "README.md",
        "README_CN.md",
        "report.md",
        "manifest.json",
    }
    report = (SAMPLE / "report.md").read_text("utf-8")
    assert "[SIMULATED]" in report
    assert "## Summary" in report and "## Findings" in report and "## Limitations" in report
    assert "## Appendix / Evidence" not in report
    assert not re.search(r"persona-\d+|[A-Za-z]:[\\/]|pre-test|bearer_token|api_key", report, re.I)
    assert "appendix.html" not in report and "research_result.json" not in report
    assert "Evidence contributors:" in report and "not votes on every claim" in report
    assert "\u672c\u8f6e\u65e0\u4eba\u8bbf\u95eeActivity\u6750\u6599" in report
    for guide in (CASE / "README.md", *SAMPLE.glob("*.md")):
        text = guide.read_text("utf-8")
        for target in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", text):
            if not target.startswith(("http:", "https:")):
                assert (guide.parent / unquote(target)).exists(), (guide, target)
