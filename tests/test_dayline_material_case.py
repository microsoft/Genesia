import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from genesia import preflight

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "use_cases" / "Specification & Screenshot Review"


def runner():
    spec = importlib.util.spec_from_file_location("material_case", CASE / "run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def options(tmp_path, **overrides):
    source = tmp_path / "people.json"
    source.write_text(json.dumps([{"id": f"p{i}", "profile": {}} for i in range(20)]), encoding="utf-8")
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
            "output_dir": None,
            "allow_model_data": True,
            **overrides,
        }
    )


def test_material_case_is_auto_compiled_not_a_live_or_handmade_graph(tmp_path):
    task = runner().build_task(options(tmp_path))
    assert task.environment.mode == "auto"
    assert task.environment.start_url is None
    assert not task.environment.candidate_labels
    assert [s.kind for s in task.environment.sources] == ["document"] + ["image"] * 11
    assert all(Path(source.path).is_file() for source in task.environment.sources)
    assert task.cohort.size == task.study.min_personas == 20
    assert not task.cohort.ids
    assert task.methods[0].kind == "interview"
    assert len(task.methods[0].questions) == 10
    assert any(q.kind == "single" and q.explain for q in task.methods[0].questions)
    assert not any(q.candidate for q in task.methods[0].questions)
    assert task.methods[0].max_followups == 0
    assert task.methods[0].max_images >= task.environment.max_steps + 1
    assert task.budget.protection
    assert preflight(task)["ok"]


def test_material_case_needs_explicit_data_permissions(tmp_path):
    task = runner().build_task(options(tmp_path, allow_model_data=False))
    assert not task.permissions.send_screenshots
    report = preflight(task)
    assert not report["ok"]
    assert any("send_screenshots" in issue for issue in report["issues"])


def test_material_case_preserves_explicit_cohort_and_model_overrides(tmp_path):
    module = runner()
    task = module.build_task(
        options(
            tmp_path,
            persona_id=["p1", "p2"],
            count=2,
            model="chosen-model",
            base_url="https://api.example.com/v1",
            api_key_env="CUSTOM_KEY",
            language="zh-CN",
        )
    )
    assert task.cohort.ids == ["p1", "p2"]
    assert task.cohort.size == task.study.min_personas == 2
    assert task.model.model == "chosen-model" and task.model.api_key_env == "CUSTOM_KEY"
    assert task.insight.language == "zh-CN"
    with pytest.raises(ValueError, match="unique"):
        module.build_task(options(tmp_path, persona_id=["p1", "p1"]))
    with pytest.raises(ValueError, match="must match"):
        module.build_task(options(tmp_path, persona_id=["p1"], count=2))


@pytest.mark.parametrize("stage", ["preflight", "prepare", "run"])
def test_material_runner_calls_only_the_selected_public_entry(tmp_path, monkeypatch, capsys, stage):
    module = runner()
    source = options(tmp_path).personas
    called = []

    def checked_preflight(task, *, network=False):
        assert stage == "preflight"
        called.append(("preflight", network))
        return {"ok": True, "issues": []}

    def checked_prepare(task):
        assert stage == "prepare"
        called.append(("prepare", False))
        return {
            "status": "ready",
            "output_dir": str(tmp_path),
            "environment_build": {"level": "cards", "cards": [], "issues": ["No supported graph"]},
            "research_readiness": {"ok": True},
            "budget": {"calls": 1},
        }

    def checked_run(task):
        assert stage == "run"
        called.append(("run", False))
        return SimpleNamespace(
            status="completed",
            run_id="new-run",
            output_dir=str(tmp_path),
            metrics={},
            errors=[],
            episodes=[SimpleNamespace(mode="cards")],
        )

    monkeypatch.setattr(module, "preflight", checked_preflight)
    monkeypatch.setattr(module, "prepare", checked_prepare)
    monkeypatch.setattr(module, "run", checked_run)
    args = ["--personas", str(source), "--allow-model-data"]
    if stage != "run":
        args.append("--" + stage)
    assert module.main(args) == 0
    assert called == [(stage, False)]
    result = json.loads(capsys.readouterr().out)
    if stage == "prepare":
        assert result["environment_level"] == "cards" and result["states"] == 0
    if stage == "run":
        assert result["episode_modes"] == ["cards"]


def test_material_prepare_needs_revision_is_not_success(tmp_path, monkeypatch):
    module = runner()
    monkeypatch.setattr(
        module,
        "prepare",
        lambda task: {
            "status": "needs_revision",
            "output_dir": str(tmp_path),
            "environment_build": {"level": "context"},
            "research_readiness": {"ok": False},
            "budget": {},
        },
    )
    assert (
        module.main(["--personas", str(options(tmp_path).personas), "--prepare", "--allow-model-data"]) == 1
    )


def test_material_provenance_matches_every_supplied_screen():
    materials = CASE / "materials"
    manifest = json.loads((materials / "provenance.json").read_text(encoding="utf-8"))
    assert manifest["public_design"] == "Design A" and manifest["source_design"] == "B"
    assert manifest["synthetic"] and manifest["not_a_recording"]
    assert manifest["verified_navigation_relations"] == 26
    assert len(manifest["screenshots"]) == 11
    assert hashlib.sha256((materials / "spec.md").read_bytes()).hexdigest() == manifest["spec_sha256"]
    assert (materials / "LICENSE.txt").is_file()
    for row in manifest["screenshots"]:
        path = (materials / row["file"]).resolve()
        assert path.is_relative_to(materials.resolve())
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
        with Image.open(path) as image:
            assert list(image.size) == manifest["viewport"]
            image.verify()
