import hashlib
import importlib.util
import re
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).parents[1]
CASE = ROOT / "use_cases" / "Live Prototype Comparison"


def helpers():
    spec = importlib.util.spec_from_file_location("example_report_helpers", CASE / "report_helpers.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exporter():
    spec = importlib.util.spec_from_file_location("example_sample_exporter", CASE / "export_sample.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_markdown_export_keeps_findings_but_removes_private_profile_and_appendix():
    source = (
        "# Feedback\n\nRun: source-run\n\n"
        "- **Relevant context** (profile): private biography\n"
        "## Shared Findings\n\nParticipant original-id preferred focused reading.\n"
        "![Private frame](artifacts/frame.jpg)\n"
        "## Appendix\n\nPrivate trace\n"
    )
    public = helpers()._sanitize_markdown(source, {"original-id": "P01"}, "source-run")
    assert "Source run: source-run" in public
    assert "P01 preferred focused reading" in public
    assert all(
        value not in public for value in ("private biography", "Private trace", "frame.jpg", "original-id")
    )


def test_html_export_removes_private_sections_and_images():
    source = (
        '<main><p>source-run</p><img src="artifacts/frame.jpg">'
        '<dt><strong>Relevant context</strong> <span class="meta">profile</span></dt>'
        "<dd>private biography</dd>"
        '<section id="findings"><h2>Findings</h2><p>original-id preferred reading.</p></section>'
        '<section id="appendix"><h2>Appendix</h2><p>Private trace</p></section></main>'
    )
    public = helpers()._sanitize_html(source, {"original-id": "P01"}, "source-run")
    assert "P01 preferred reading" in public
    assert all(
        value not in public for value in ("private biography", "Private trace", "frame.jpg", "original-id")
    )


def test_standalone_export_removes_private_artifact_links_and_local_origin():
    source = '<a href="artifacts/answer.json">Answer</a> http://127.0.0.1:5173/?design=b'
    public = helpers()._standalone_html(helpers()._replace_common(source, {}))
    assert "Answer" in public and "prototype:/?design=b" in public
    assert "artifacts/" not in public and "127.0.0.1" not in public


def test_new_sample_gallery_uses_english_navigation():
    page = exporter().gallery(
        [{"alias": "P01", "steps": 2, "preference": "Design A", "gif": "journeys/p01-paired.gif"}],
        {"Design A": 12, "Design B": 7, "No meaningful preference": 1, "Insufficient experience": 0},
    )
    assert '<html lang="en">' in page
    assert "Play full journey" in page
    assert "A \u2192 B comparison" in page
    assert "Preference: A 12/20 \u00b7 B 7/20" in page
    assert "<title>Dayline A/B comparison" in page
    assert "<h1>Dayline" in page
    assert "1022" not in page
    assert "independent" not in page.lower()
    assert not re.search(r"[\u3400-\u4dbf\u4e00-\u9fff]", page)


def test_sample_export_cli_requires_only_current_study_inputs(tmp_path, monkeypatch):
    module = exporter()
    inputs = [tmp_path / name for name in ("study", "analysis", "journeys", "output")]
    calls = []

    def export(study_run, analysis_run, journey_dir, output):
        calls.append((study_run, analysis_run, journey_dir, output))
        return {"participants": []}

    monkeypatch.setattr(module, "export_sample", export)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "export_sample.py",
            "--study-run",
            str(inputs[0]),
            "--analysis-run",
            str(inputs[1]),
            "--journey-dir",
            str(inputs[2]),
            "--output",
            str(inputs[3]),
        ],
    )
    module.main()
    assert calls == [tuple(path.resolve() for path in inputs)]


def test_public_exporter_redacts_paths_aliases_ids_and_rejects_session_leaks():
    module = exporter()
    assert module.public_text("https://example.com/report", {}, set()) == "https://example.com/report"
    assert (
        module.public_text(
            r"Source persona-0001 at C:\private\study", {"persona-0001": "P01"}, {"private-session"}
        )
        == "Source P01 at PRIVATE_SOURCE_DIRECTORY"
    )
    with pytest.raises(ValueError, match="session"):
        module.public_text("private-session", {}, {"private-session"})


def test_public_variant_aliases_are_simultaneous_and_preserve_generic_ab_terms():
    module = exporter()
    assert module.public_variant_text("Design B then Design D; B-to-D, B/D, B\u2192D") == (
        "Design A then Design B; A-to-B, A/B, A\u2192B"
    )
    assert module.public_variant_text("P01:b_information P02:d_control A/B A\uff0fB") == (
        "P01:a_information P02:b_control A/B A\uff0fB"
    )
    assert module.public_variant_text("B12 D7 B's board; B\u7684 D\u7248") == (
        "A12 B7 A's board; A\u7684 B\u7248"
    )
    assert module.public_variant_text("README SDK 8+8+4 P01 20/20 17.0") == "README SDK 8+8+4 P01 20/20 17.0"


def test_public_report_names_preserve_source_provenance_and_findings():
    module = exporter()
    provenance = (
        "20261021T163805Z-89710f3f partial 2026-10-22 "
        "f2cec90c7bbae7b2bf6e1af078b0bfb91d325ab9 10191234 "
        "P01 prefers Design A because the content is easier to read."
    )
    assert module.public_case_text(provenance) == provenance
    assert module.public_case_text("# case1022") == "# Dayline A/B"
    assert module.public_case_text("# Dayline release1022") == "# Dayline"
    assert module.public_case_text("fresh RELEASE case1022") == "Dayline A/B"
    assert module.public_case_text("fresh release1022") == "\u672c\u6b21\u51bb\u7ed3\u7248\u672c"
    assert module.public_case_text("release1022 \u7684 `PYTHONPATH`") == (
        "\u7814\u7a76\u51bb\u7ed3\u7248\u672c \u7684 `PYTHONPATH`"
    )
    assert module.public_case_text("\u4e0e 1019 \u7684\u6d4f\u89c8\u5668") == (
        "\u4e0e \u5148\u524d\u7814\u7a76 \u7684\u6d4f\u89c8\u5668"
    )
    assert module.public_case_text("run-1019 2026-10-19 1019 observations") == (
        "run-1019 2026-10-19 1019 observations"
    )
    public = module.public_case_text("# Dayline release1022\n" + provenance)
    assert module.public_case_text(public) == public


@pytest.mark.parametrize("html_format", [False, True])
def test_native_public_edition_removes_internal_logs_not_findings(html_format):
    module = exporter()
    if html_format:
        source = (
            "<main><h2>Findings</h2><p>P01 preferred focused reading.</p>"
            "<p>Source run: 20261021T163805Z-89710f3f</p><ul>"
            "<li>Analysis-only rerun of private-source</li>"
            "<li>Run stage: ModelFailure: private-provider transport failed: ReadTimeout</li>"
            "<li>Fixed order limits causal claims.</li></ul></main>"
        )
    else:
        source = (
            "# Findings\n\nP01 preferred focused reading.\n"
            "Source run: 20261021T163805Z-89710f3f\n"
            "- Analysis-only rerun of private-source\n"
            "- Run stage: ModelFailure: private-provider transport failed: ReadTimeout\n"
            "- Fixed order limits causal claims.\n"
        )
    result = module.public_native_report(source, html_format=html_format)
    assert "P01 preferred focused reading." in result
    assert "Fixed order limits causal claims." in result
    assert "private-source" not in result and "20261021" not in result
    module.check_publication_text(result)


@pytest.mark.parametrize(
    "text", ["PRIVATE_SOURCE_DIRECTORY", "PYTHONPATH", "private-provider", "unpublished-model"]
)
def test_publication_refuses_unreviewed_operational_content(text):
    with pytest.raises(ValueError, match="internal operational"):
        exporter().check_publication_text(text, private_values=("private-provider", "unpublished-model"))


def test_historical_exporter_rejects_new_run_without_creating_media(tmp_path):
    module = exporter()
    episode, evidence = source_episode(tmp_path)
    episode["candidate_labels"] = ["Design A", "Design B"]
    output = tmp_path / "new-run.gif"
    with pytest.raises(ValueError, match="For new A/B runs"):
        module.write_journey_gif(tmp_path, episode, evidence, output, "P01")
    assert not output.exists()


def source_episode(tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGB", (1200, 750), "white").save(source)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    steps = [
        {
            "number": index,
            "observation": {
                "url": "http://127.0.0.1:5173/?design=" + design,
                "image_refs": [f"e{index}"],
                "targets": [{"id": "target", "name": "Open task", "x": 120, "y": 180}],
            },
            "action": {"action": action, "target_id": "target"},
            "result": {"success": True},
        }
        for index, (design, action) in enumerate((("b", "click"), ("b", "advance"), ("d", "stop")), 1)
    ]
    episode = {
        "persona": {"id": "fixture"},
        "session_id": "fixture-session",
        "mode": "live",
        "candidate_labels": ["Design B", "Design D"],
        "steps": steps,
        "final_observation": {"image_refs": ["e3"]},
    }
    evidence = {
        f"e{index}": {
            "kind": "frame",
            "path": source.name,
            "persona_id": "fixture",
            "session_id": "fixture-session",
            "sha256": digest,
        }
        for index in range(1, 4)
    }
    return episode, evidence


def test_exported_gif_uses_public_headers_handoff_and_complete_source_frames(tmp_path):
    module = exporter()
    episode, evidence = source_episode(tmp_path)
    result = module.write_journey_gif(tmp_path, episode, evidence, tmp_path / "journey.gif", "P01")
    assert result["frames"] == 3 and result["duration_ms"] == 8000
    assert [frame["candidate"] for frame in result["source_frames"]] == ["A", "A", "B"]
    assert [frame["source_candidate"] for frame in result["source_frames"]] == ["B", "B", "D"]
    assert result["source_frames"][0]["annotations"]["title"] == "Dayline | P01 | Design A | Step 1/3"
    assert result["source_frames"][1]["annotations"]["action"].startswith("ADVANCE to B")
    assert result["source_frames"][2]["annotations"]["title"] == "Dayline | P01 | Design B | Step 3/3"
    with Image.open(tmp_path / "journey.gif") as image:
        assert image.n_frames == 3 and image.size == (960, 693)
        for index, duration in enumerate((2000, 2000, 4000)):
            image.seek(index)
            assert image.info["duration"] == duration
    assert episode["candidate_labels"] == ["Design B", "Design D"]


@pytest.mark.parametrize(
    "fault", ["hash", "owner", "path", "stage", "origin", "missing_step", "failed", "final"]
)
def test_journey_export_rejects_invalid_source_evidence(tmp_path, fault):
    module = exporter()
    episode, evidence = source_episode(tmp_path)
    if fault == "hash":
        evidence["e1"]["sha256"] = "0" * 64
    elif fault == "owner":
        evidence["e1"]["persona_id"] = "someone-else"
    elif fault == "path":
        evidence["e1"]["path"] = "..\\outside.png"
    elif fault == "stage":
        episode["steps"][2]["observation"]["url"] = "http://127.0.0.1:5173/?design=b"
    elif fault == "origin":
        episode["steps"][2]["observation"]["url"] = "https://example.com/?design=d"
    elif fault == "missing_step":
        episode["steps"][1]["number"] = 3
    elif fault == "failed":
        episode["steps"][0]["result"]["success"] = False
    elif fault == "final":
        episode["final_observation"]["image_refs"] = ["unknown"]
    with pytest.raises(ValueError):
        module.write_journey_gif(tmp_path, episode, evidence, tmp_path / "invalid.gif", "P01")
