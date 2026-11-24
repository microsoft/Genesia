import importlib.util
import json
import socket
import tomllib
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit
from urllib.request import urlopen

import pytest

from genesia import load_task, preflight

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "use_cases" / "Live Prototype Comparison"


def test_package_version_matches_project_metadata():
    from genesia import __version__

    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
    assert metadata["project"]["version"] == __version__


def test_comparison_runner_exposes_public_options(capsys):
    with pytest.raises(SystemExit) as result:
        runner().main(["--help"])
    assert result.value.code == 0
    help_text = capsys.readouterr().out
    for option in (
        "--personas",
        "--model",
        "--base-url",
        "--api-key-env",
        "--preflight",
        "--url-a",
        "--url-b",
        "--local-prototype",
        "--language",
    ):
        assert option in help_text
    assert "--url-d" not in help_text


def runner():
    spec = importlib.util.spec_from_file_location("live_prototype_comparison", CASE / "run.py")
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
            "persona_id": None,
            "count": None,
            "url_a": None,
            "url_b": None,
            "model": None,
            "base_url": None,
            "api_key_env": None,
            "language": None,
            "output_dir": None,
            "allow_model_data": True,
            **overrides,
        }
    )


def test_comparison_example_has_bounded_live_configuration(tmp_path):
    task = runner().build_task(options(tmp_path))
    assert task.cohort.size == 20
    assert task.cohort.ids == []
    assert task.execution.max_concurrent_personas == 5
    assert task.execution.max_concurrent_model_calls == 5
    assert task.environment.candidate_labels == ["Design A", "Design B"]
    assert task.environment.min_actions_before_stop == 0
    assert task.methods[0].evidence_mode == "complete"
    assert task.methods[0].max_images >= task.environment.max_steps + 1
    assert task.methods[0].batch_size == 8
    assert len(task.methods[0].questions) == 20
    questions = task.methods[0].questions
    assert all(
        question.id.startswith("a_") and question.candidate == "Design A" for question in questions[:8]
    )
    assert all(
        question.id.startswith("b_") and question.candidate == "Design B" for question in questions[8:16]
    )
    assert next(question for question in questions if question.id == "x_preference").options == [
        "Design A",
        "Design B",
        "No meaningful preference",
        "Insufficient experience",
    ]
    assert task.environment.start_url.endswith("?design=b&research=1")
    assert task.environment.handoff_urls[0].endswith("?design=d&research=1")
    assert task.model.attempts == 1
    assert task.environment.required_url_fragments_before_stop == []
    assert not load_task(CASE / "task.yaml").permissions.send_persona


def test_comparison_example_updates_both_urls_atomically(tmp_path):
    task = runner().build_task(
        options(
            tmp_path,
            url_a="http://127.0.0.1:9999/?design=b",
            url_b="http://127.0.0.1:9999/?design=d",
        )
    )
    assert task.environment.start_url.startswith("http://127.0.0.1:9999/")
    assert task.environment.handoff_urls == ["http://127.0.0.1:9999/?design=d"]
    with pytest.raises(ValueError, match="start origin"):
        runner().build_task(options(tmp_path, url_a="http://127.0.0.1:9999/"))


def test_comparison_example_accepts_user_api_connection(tmp_path):
    task = runner().build_task(
        options(
            tmp_path,
            model="chosen-model",
            base_url="https://api.example.com/v1",
            api_key_env="CUSTOM_API_KEY",
        )
    )
    assert task.model.provider == "openai_compatible"
    assert task.model.model == "chosen-model"
    assert task.model.base_url == "https://api.example.com/v1"
    assert task.model.api_key_env == "CUSTOM_API_KEY"


def test_report_language_override_preserves_the_research_protocol(tmp_path):
    module = runner()
    original = module.build_task(options(tmp_path))
    assert original.insight.language == "en"
    translated = module.build_task(options(tmp_path, language="zh-CN"))
    assert translated.insight.language == "zh-CN"
    left = original.model_dump()
    right = translated.model_dump()
    right["insight"]["language"] = "en"
    assert left == right


def test_report_language_from_custom_task_is_kept_without_an_override(tmp_path):
    import yaml

    config = load_task(CASE / "task.yaml").model_dump()
    config["insight"]["language"] = "zh-CN"
    path = tmp_path / "custom-task.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    assert runner().build_task(options(tmp_path, task=path)).insight.language == "zh-CN"
    assert runner().build_task(options(tmp_path, task=path, language="en")).insight.language == "en"


def test_language_option_rejects_unsupported_values(tmp_path):
    with pytest.raises(SystemExit) as result:
        runner().main(["--personas", str(options(tmp_path).personas), "--language", "unknown"])
    assert result.value.code == 2


def test_comparison_example_explicit_cohort_and_permissions(tmp_path):
    module = runner()
    with pytest.raises(ValueError, match="unique"):
        module.build_task(options(tmp_path, persona_id=["p1", "p1"]))
    with pytest.raises(ValueError, match="must match"):
        module.build_task(options(tmp_path, persona_id=["p1"], count=2))
    with pytest.raises(ValueError):
        module.build_task(options(tmp_path, count=0))
    task = module.build_task(options(tmp_path, persona_id=["p1", "p2"]))
    assert task.cohort.ids == ["p1", "p2"]
    assert task.cohort.size == task.study.min_personas == 2
    task = module.build_task(options(tmp_path, allow_model_data=False))
    assert not task.permissions.send_persona
    assert not task.permissions.send_materials
    assert not task.permissions.send_screenshots


@pytest.mark.browser
def test_comparison_example_preflight_with_live_dependencies(tmp_path):
    task = runner().build_task(options(tmp_path))
    report = preflight(task)
    assert report["ok"], report["issues"]


def test_comparison_example_offline_preflight_never_runs(tmp_path, monkeypatch):
    module = runner()
    source = options(tmp_path).personas
    monkeypatch.setattr(module, "run", lambda *_: pytest.fail("Preflight must not run research"))
    checks = []

    def fake_preflight(task, *, network=False):
        checks.append((task, network))
        return {"ok": True, "issues": []}

    monkeypatch.setattr(module, "preflight", fake_preflight)
    assert module.main(["--personas", str(source), "--allow-model-data", "--preflight"]) == 0
    assert len(checks) == 1 and checks[0][1] is False
    assert checks[0][0].cohort.source == str(source)


def test_local_prototype_requires_a_build(tmp_path, monkeypatch):
    module = runner()
    monkeypatch.setattr(module, "PROTOTYPE_DIST", tmp_path)
    with pytest.raises(ValueError, match="npm run build"):
        with module.local_prototype():
            pytest.fail("An unbuilt prototype must not start")


def test_local_prototype_uses_owned_ports_and_cleans_up(tmp_path, monkeypatch):
    module = runner()
    (tmp_path / "index.html").write_text("frozen prototype", encoding="utf-8")
    monkeypatch.setattr(module, "PROTOTYPE_DIST", tmp_path)
    with module.local_prototype() as first:
        with module.local_prototype() as second:
            assert first != second
            with urlopen(second, timeout=2) as response:
                assert response.read() == b"frozen prototype"
        with urlopen(first, timeout=2) as response:
            assert response.status == 200
    for origin in (first, second):
        with pytest.raises(OSError):
            socket.create_connection(("127.0.0.1", urlsplit(origin).port), timeout=1)


@pytest.mark.parametrize("outcome", ["completed", "partial", "exception", "interrupt", "readiness"])
def test_local_comparison_lifecycle(tmp_path, monkeypatch, outcome):
    module = runner()
    (tmp_path / "index.html").write_text("prototype", encoding="utf-8")
    monkeypatch.setattr(module, "PROTOTYPE_DIST", tmp_path)
    monkeypatch.setattr(module, "preflight", lambda *_args, **_kwargs: {"ok": True, "issues": []})
    origins = []
    runs = []

    def readiness(task):
        start = urlsplit(task.environment.start_url)
        handoff = urlsplit(task.environment.handoff_urls[0])
        assert start.netloc == handoff.netloc
        assert start.query == "design=b&research=1"
        assert handoff.query == "design=d&research=1"
        origins.append(start)
        with urlopen(task.environment.start_url, timeout=2) as response:
            assert response.status == 200
        if outcome == "readiness":
            raise ValueError("Not ready")

    def research(task):
        runs.append(task)
        if outcome == "exception":
            raise ValueError("Model rejected request")
        if outcome == "interrupt":
            raise KeyboardInterrupt
        return SimpleNamespace(
            run_id="local-run",
            status=outcome,
            output_dir=str(tmp_path / "runs"),
            metrics={"valid_responses": 1, "invalid_responses": 0, "missing_responses": 0},
            errors=[] if outcome == "completed" else ["Analysis failed"],
        )

    monkeypatch.setattr(module, "check_local_prototype", readiness)
    monkeypatch.setattr(module, "run", research)
    argv = ["--personas", str(options(tmp_path).personas), "--allow-model-data", "--local-prototype"]
    if outcome == "interrupt":
        with pytest.raises(KeyboardInterrupt):
            module.main(argv)
    else:
        assert module.main(argv) == (0 if outcome == "completed" else 1)
    assert len(runs) == (0 if outcome == "readiness" else 1)
    assert len(origins) == 1
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", origins[0].port), timeout=1)


def test_local_preflight_checks_browser_without_research(tmp_path, monkeypatch):
    module = runner()
    (tmp_path / "index.html").write_text("prototype", encoding="utf-8")
    monkeypatch.setattr(module, "PROTOTYPE_DIST", tmp_path)
    calls = []
    monkeypatch.setattr(
        module,
        "preflight",
        lambda task, *, network=False: calls.append(network) or {"ok": True, "issues": []},
    )
    ready = []
    monkeypatch.setattr(module, "check_local_prototype", lambda task: ready.append(task))
    monkeypatch.setattr(module, "run", lambda *_: pytest.fail("Preflight must not start research"))
    assert (
        module.main(
            [
                "--personas",
                str(options(tmp_path).personas),
                "--allow-model-data",
                "--local-prototype",
                "--preflight",
                "--network",
            ]
        )
        == 0
    )
    assert calls == [False, True]
    assert len(ready) == 1


def test_local_preflight_failure_does_not_start_a_server(tmp_path, monkeypatch):
    module = runner()
    monkeypatch.setattr(module, "preflight", lambda *_: {"ok": False, "issues": ["Permission missing"]})
    monkeypatch.setattr(module, "local_prototype", lambda: pytest.fail("Must fail before serving"))
    assert (
        module.main(
            [
                "--personas",
                str(options(tmp_path).personas),
                "--local-prototype",
                "--preflight",
            ]
        )
        == 1
    )


@pytest.mark.parametrize("flag", ["--url-a", "--url-b"])
def test_local_prototype_rejects_external_url_overrides(tmp_path, flag):
    with pytest.raises(SystemExit) as result:
        runner().main(
            [
                "--personas",
                str(options(tmp_path).personas),
                "--local-prototype",
                flag,
                "http://127.0.0.1:9999/",
            ]
        )
    assert result.value.code == 2


@pytest.mark.browser
def test_bundled_prototype_renders_both_research_designs(tmp_path):
    module = runner()
    if not (module.PROTOTYPE_DIST / "index.html").is_file():
        pytest.skip("Repository prototype must be built; covered by the dedicated prototype CI job")
    with module.local_prototype() as origin:
        task = module.build_task(
            options(tmp_path, url_a=f"{origin}/?design=b&research=1", url_b=f"{origin}/?design=d&research=1")
        )
        module.check_local_prototype(task)


def test_comparison_example_keeps_saved_explicit_ids_unless_sampling_is_requested(tmp_path):
    import yaml

    config = load_task(CASE / "task.yaml").model_dump()
    config["cohort"]["ids"] = ["p1", "p2"]
    config["cohort"]["size"] = 2
    config["study"]["min_personas"] = 2
    path = tmp_path / "fixed.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    task = runner().build_task(options(tmp_path, task=path))
    assert task.cohort.ids == ["p1", "p2"]
    sampled = runner().build_task(options(tmp_path, task=path, count=3))
    assert sampled.cohort.ids == []
    assert sampled.cohort.size == 3


def test_analysis_failure_recovers_without_repeating_participants(tmp_path):
    from test_workflow import ScriptedModel, task_fixture

    from genesia import analyze, run
    from genesia.runtime import EvidenceStore, ModelFailure

    class TimeoutModel(ScriptedModel):
        def complete(self, purpose, payload, schema, **kwargs):
            assert purpose == "research_synthesis"
            raise ModelFailure("Model API transport failed: ReadTimeout")

    task = task_fixture(tmp_path)
    source = run(task, gateway=ScriptedModel(), research_only=True)
    source_root = Path(source.output_dir)
    before = {
        name: (source_root / name).read_bytes()
        for name in ["research_result.json", "run_manifest.json", "evidence.json", "events.jsonl"]
    }
    failed = analyze(source_root, gateway=TimeoutModel())
    assert failed.status == "partial"
    assert "ReadTimeout" in failed.errors[0]
    assert (Path(failed.output_dir) / "report.html").is_file()
    model = ScriptedModel()
    recovered = analyze(source_root, gateway=model, timeout_seconds=300)
    assert recovered.status == "completed", recovered.errors
    assert all(purpose == "research_synthesis" for purpose, _ in model.calls)
    assert recovered.responses == source.responses
    assert recovered.episodes == source.episodes
    assert EvidenceStore(Path(recovered.output_dir)).verify()["valid"]
    for name, contents in before.items():
        assert (source_root / name).read_bytes() == contents
    manifest = json.loads((Path(recovered.output_dir) / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["phase"] == "analysis_only"
    assert manifest["source_run_id"] == source.run_id
    assert manifest["task"]["model"]["timeout_seconds"] == 300
    assert manifest["analysis_timeout_override"] == {
        "source_timeout_seconds": task.model.timeout_seconds,
        "timeout_seconds": 300,
    }


@pytest.mark.parametrize("timeout", [0, 601])
def test_analysis_rejects_invalid_timeout_before_new_run(tmp_path, timeout):
    from test_workflow import ScriptedModel, task_fixture

    from genesia import analyze, run

    source = run(task_fixture(tmp_path), gateway=ScriptedModel(), research_only=True)
    root = Path(source.output_dir)
    before = set(root.parent.iterdir())
    model = ScriptedModel()
    with pytest.raises(ValueError):
        analyze(root, gateway=model, timeout_seconds=timeout)
    assert set(root.parent.iterdir()) == before
    assert model.calls == []
