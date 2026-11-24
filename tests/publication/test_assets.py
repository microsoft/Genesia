import hashlib
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest
from PIL import Image

from genesia import load_task
from genesia.personas import load_cohort

pytestmark = pytest.mark.publication

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / "use_cases" / "Live Prototype Comparison"
SAMPLE = CASE / "sample"
POOL = ROOT / "data" / "personas" / "global-digital-100"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_global_digital_pool_matches_approved_publication_and_coverage():
    publication = read_json(POOL / "publication-manifest.json")
    quality = read_json(POOL / "quality-summary.json")
    people = read_json(POOL / "personas.json")
    assert len(people) == len({person["id"] for person in people}) == 100
    assert {path.name for path in POOL.iterdir()} == set(publication["published_files"])
    for filename, key in (
        ("personas.json", "personas_sha256"),
        ("quality-summary.json", "quality_summary_sha256"),
    ):
        assert hashlib.sha256((POOL / filename).read_bytes()).hexdigest() == publication[key]
    core = [person["profile"]["Core Identity"] for person in people]
    assert all(person["synthetic_status"] == "fictional_public_example" for person in core)
    assert all(person["research_language"] == "English" for person in core)
    assert all(str(person["age"]).isdecimal() and 18 <= int(person["age"]) <= 74 for person in core)
    assert Counter(person["gender"] for person in core) == {"Woman": 45, "Man": 45, "Nonbinary": 10}
    for field in (
        "age_band",
        "region",
        "technical_confidence",
        "product_familiarity",
        "device_and_access_context",
        "decision_style",
    ):
        assert dict(Counter(person[field] for person in core)) == quality["profile_distributions"][field]
    assert quality["candidate_review"]["selected"] == quality["candidate_review"]["risk_reviewed"] == 100
    assert quality["cohort_semantic_review"]["severity"] == "low"
    assert publication["privacy_review"]["email_hits"] == publication["privacy_review"]["phone_hits"] == 0
    task = load_task(CASE / "task.yaml")
    task.cohort.source = str(POOL / "personas.json")
    selected, _ = load_cohort(task.cohort)
    assert len(selected) == 20


def test_dayline_sample_is_complete_anonymized_and_hash_indexed():
    manifest = read_json(SAMPLE / "manifest.json")
    assert manifest["source_study_run_id"] == "20261103T032218Z-4ac45e6b"
    assert manifest["source_study_status"] == "completed"
    assert manifest["source_analysis_run_id"] == "20261103T033653Z-4427957c"
    assert manifest["source_analysis_status"] == "completed"
    assert manifest["source_experience"]["run_id"] == "20261021T163805Z-89710f3f"
    assert manifest["source_experience"]["status"] == "partial"
    assert manifest["source_experience"]["new_interaction"] is False
    assert manifest["model_configuration"]["upstream_model_id"] == "gpt-6.1-sol"
    assert manifest["model_configuration"]["inference_parameters"]["temperature"] == 1
    assert manifest["study_date"] == "2026-10-22"
    assert manifest["same_episodes_and_responses"] and manifest["source_files_unchanged"]
    assert manifest["answers"] == 400 and manifest["analysis_answer_coverage"] == "400/400"
    assert manifest["valid_responses"] == 20
    assert manifest["invalid_responses"] == manifest["missing_responses"] == manifest["failed_actions"] == 0
    assert manifest["publication"]["model_calls"] == manifest["publication"]["new_browser_sessions"] == 0
    indexed = {row["path"]: row for row in manifest["files"]}
    actual = {
        path.relative_to(SAMPLE).as_posix()
        for path in SAMPLE.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    assert set(indexed) == actual
    for relative, row in indexed.items():
        path = SAMPLE / relative
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
        assert path.stat().st_size == row["bytes"]
    text = "\n".join(
        path.read_text("utf-8") for path in SAMPLE.rglob("*") if path.suffix in {".md", ".html", ".json"}
    )
    assert not re.search(r"persona-\d+|[A-Z]:\\|\"session_id\"|\"profile\"", text)
    assert all(not line.endswith((" ", "\t")) for line in text.splitlines())
    for internal in (
        "PRIVATE_SOURCE_DIRECTORY",
        "PYTHONPATH",
        "ReadTimeout",
        "ModelFailure",
        "research-work",
        "research.audit.json",
        "0.2.1rc1",
    ):
        assert internal not in text
    assert not {"provider", "model", "study_package"} & manifest.keys()
    assert manifest["publication"]["internal_operational_details_removed"]
    assert all(row["valid"] and not row["errors"] for row in manifest["evidence_verification"])
    assert "independent_reports" not in manifest
    assert not list(CASE.glob("independent_raw_answer_*.md"))
    assert not list(SAMPLE.glob("independent_raw_answer_*.md"))
    assert manifest["version_labels"] == [
        {"public": "Design A", "source": "Design B"},
        {"public": "Design B", "source": "Design D"},
    ]
    assert manifest["publication"]["overlays_regenerated_from_verified_source_frames"]
    prototype = read_json(SAMPLE / "prototype.json")
    assert [(version["label"], version["route"]) for version in prototype["versions"]] == [
        ("Design A", "/?design=b&research=1"),
        ("Design B", "/?design=d&research=1"),
    ]
    notice = manifest["version_label_notice"]
    for filename in ("report.md", "report.html", "standalone-report.html", "index.html"):
        text = (SAMPLE / filename).read_text("utf-8")
        assert notice in text
        without_notice = text.replace(notice, "")
        assert "Design D" not in without_notice
        assert not re.search(r"\bB(?:\s*(?:to|\u2192|-to-)\s*)D\b", without_notice)


def test_dayline_preference_counts_and_every_journey_frame():
    manifest = read_json(SAMPLE / "manifest.json")
    feedback = read_json(SAMPLE / "preferences.json")
    assert (
        feedback["counts"]
        == manifest["preference_counts"]
        == {
            "Design A": 14,
            "Design B": 4,
            "No meaningful preference": 2,
            "Insufficient experience": 0,
        }
    )
    assert len(feedback["answers"]) == len({row["participant"] for row in feedback["answers"]}) == 20
    assert Counter(row["value"] for row in feedback["answers"]) == Counter(
        {key: value for key, value in feedback["counts"].items() if value}
    )
    assert len(list((SAMPLE / "journeys").glob("*.gif"))) == 20
    assert sum(row["steps"] for row in manifest["participants"]) == manifest["recorded_steps"] == 340
    for index, participant in enumerate(manifest["participants"], 1):
        assert participant["alias"] == f"P{index:02d}"
        assert len(participant["source_frames"]) == participant["steps"] == participant["frames"]
        assert {row["candidate"] for row in participant["source_frames"]} == {"A", "B"}
        for index, row in enumerate(participant["source_frames"], 1):
            assert row["candidate"] == {"B": "A", "D": "B"}[row["source_candidate"]]
            assert row["step"] == index
            assert f"Design {row['candidate']}" in row["annotations"]["title"]
            assert row["annotations"]["title"].startswith("Dayline | ")
            assert "1022" not in row["annotations"]["title"]
            assert "Design D" not in row["annotations"]["title"]
        handoffs = [
            row for row in participant["source_frames"] if row["annotations"]["action"].startswith("ADVANCE")
        ]
        assert len(handoffs) == 1
        assert handoffs[0]["annotations"]["action"].startswith("ADVANCE to B")
        with Image.open(SAMPLE / participant["gif"]) as image:
            assert image.n_frames == participant["frames"]
            assert list(image.size) == participant["size"] == [960, 693]
            assert image.info["loop"] == 0
            durations = []
            for frame in range(image.n_frames):
                image.seek(frame)
                image.load()
                durations.append(image.info["duration"])
            assert durations == [2000] * (image.n_frames - 1) + [4000]
            assert sum(durations) == participant["duration_ms"]
    standalone = (SAMPLE / "standalone-report.html").read_text("utf-8")
    assert standalone.count("data:image/gif;base64,") == 1
    assert not re.search(r'<img[^>]+src="(?!data:)', standalone)


def test_public_case_names_are_descriptive_not_internal_date_labels():
    guides = [
        ROOT / "README.md",
        ROOT / "use_cases" / "README.md",
        CASE / "README.md",
        *SAMPLE.glob("*.md"),
    ]
    for path in guides:
        text = path.read_text("utf-8")
        assert not re.search(r"(?<!\d)(?:case|release)?10(?:19|22)(?!\d)", text), path
        if path.parent != SAMPLE:
            assert not re.search(r"\b20\d{6}T\d{6}Z-[a-f0-9]+\b", text), path
    gallery = (SAMPLE / "index.html").read_text("utf-8")
    assert "<title>Dayline A/B comparison" in gallery
    assert "<h1>Dayline" in gallery
    assert "1022" not in gallery


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        self.links.extend(value for key, value in attrs if key in {"href", "src"} and value)


def test_public_sample_html_links_and_readme_images_resolve():
    for filename in ("index.html", "report.html", "standalone-report.html"):
        page = SAMPLE / filename
        parser = Links()
        parser.feed(page.read_text("utf-8"))
        for link in parser.links:
            url = urlsplit(link)
            if not url.scheme and url.path:
                assert (page.parent / unquote(url.path)).resolve().is_file(), (filename, link)
    guides = [
        ROOT / "README.md",
        ROOT / "use_cases" / "README.md",
    ]
    for case_name in (
        "Live Prototype Comparison",
        "Profile-Grounded Persona Survey",
        "Specification & Screenshot Review",
    ):
        case = ROOT / "use_cases" / case_name
        assert not (case / "README_CN.md").exists()
        guides.extend([case / "README.md", *(case / "sample").glob("*.md")])
    for guide in guides:
        text = guide.read_text("utf-8")
        for target in re.findall(r"!?\[[^\]]*\]\(([^\s)]+)\)", text):
            url = urlsplit(target)
            if not url.scheme and url.path:
                assert (guide.parent / unquote(url.path)).resolve().is_file(), (guide, target)
        if guide.parent == ROOT:
            images = re.findall(r"!\[[^\]]*\]\(([^\s)]+)\)", text)
            assert images
            for target in images:
                path = guide.parent / unquote(urlsplit(target).path)
                if path.suffix.lower() == ".svg":
                    svg = ET.parse(path).getroot()
                    assert svg.tag == "{http://www.w3.org/2000/svg}svg"
                    _, _, width, height = map(float, svg.attrib["viewBox"].split())
                    assert width > 0 and height > 0
                else:
                    with Image.open(path) as image:
                        image.verify()


def test_current_report_labels_merged_evidence_without_changing_research_counts():
    manifest = read_json(SAMPLE / "manifest.json")
    report = (SAMPLE / "report.md").read_text("utf-8")
    labels = re.findall(
        r"(?m)^Evidence contributors: (\d+) from cited supporting answers; "
        r"(\d+) from cited counter answers\.",
        report,
    )
    assert len(labels) == 10
    assert "not votes on every claim" in report
    assert "Evidence: 3 supporting Personas" not in report
    assert "Evidence contributors: 3 from cited supporting answers; 4 from cited counter answers" in report
    assert manifest["publication"]["evidence_labels"]["numbers_and_saved_memberships_unchanged"]
