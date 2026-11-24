from typer.testing import CliRunner

from genesia import load_task
from genesia.cli import app
from genesia.schemas import ModelSpec


def test_public_model_defaults_use_standard_api_and_key_name():
    model = ModelSpec(model="chosen-model")
    assert model.provider == "openai_compatible"
    assert model.base_url == "https://api.openai.com/v1"
    assert model.api_key_env == "OPENAI_API_KEY"


def test_local_compatible_service_can_explicitly_omit_authentication():
    model = ModelSpec(model="local-model", base_url="http://127.0.0.1:8000/v1", api_key_env=None)
    assert model.api_key_env is None


def test_init_uses_public_connection_environment_without_persisting_secret(tmp_path, monkeypatch):
    source = tmp_path / "people.json"
    source.write_text('[{"id":"p1","profile":{"synthetic":true}}]', encoding="utf-8")
    monkeypatch.setenv("GENESIA_MODEL", "chosen-model")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.example.com/v1")
    monkeypatch.setenv("CUSTOM_API_KEY", "fixture-secret-not-for-the-task-file")
    directory = tmp_path / "study"
    result = CliRunner().invoke(
        app,
        [
            "init",
            "survey",
            str(directory),
            "--personas",
            str(source),
            "--goal",
            "Review the concept",
            "--size",
            "1",
            "--api-key-env",
            "CUSTOM_API_KEY",
        ],
    )
    assert result.exit_code == 0, result.output
    task = load_task(directory / "task.yaml")
    assert task.model.model == "chosen-model"
    assert task.model.base_url == "https://api.example.com/v1"
    assert task.model.api_key_env == "CUSTOM_API_KEY"
    assert "fixture-secret-not-for-the-task-file" not in (directory / "task.yaml").read_text("utf-8")
