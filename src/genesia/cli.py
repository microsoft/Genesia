import json
import os
import webbrowser
from pathlib import Path

import typer
import yaml

from .api import analyze, load_task, preflight, prepare, run
from .cli_personas import personas_app
from .runtime import EvidenceStore
from .schemas import (
    CohortPlan,
    InsightSpec,
    PersonaCohortApproval,
    PersonaGenerationManifest,
    PersonaGenerationRequest,
    ResearchResult,
    TaskSpec,
)

app = typer.Typer(no_args_is_help=True, help="Evidence-grounded synthetic Persona research")
app.add_typer(personas_app, name="personas")


@app.command("preflight")
def preflight_command(task: Path, network: bool = False):
    report = preflight(load_task(task), network=network)
    typer.echo(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["ok"]:
        raise typer.Exit(1)


@app.command("run")
def run_command(
    task: Path,
    open_report: bool = typer.Option(False, "--open"),
    research_only: bool = typer.Option(False, "--research-only"),
):
    if research_only and open_report:
        raise typer.BadParameter("--research-only does not generate a report; omit --open")
    try:
        result = run(load_task(task), research_only=research_only)
    except (ValueError, OSError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from error
    typer.echo(
        json.dumps(
            {
                "run_id": result.run_id,
                "status": result.status,
                "output_dir": result.output_dir,
                "metrics": result.metrics,
            },
            indent=2,
        )
    )
    if open_report:
        webbrowser.open((Path(result.output_dir) / "report.html").resolve().as_uri())
    if result.status != "completed":
        raise typer.Exit(1)


@app.command("report")
def report_command(run_dir: Path, open_report: bool = typer.Option(False, "--open")):
    """Re-render a saved run without model calls or another Persona study."""
    from .api import render_report
    from .reports import write_reports

    store = EvidenceStore(run_dir.resolve())
    verification = store.verify()
    if not verification["valid"]:
        raise typer.BadParameter("Evidence verification failed; do not render altered evidence")
    result = ResearchResult.model_validate_json((store.root / "research_result.json").read_text("utf-8"))
    write_reports(result, store, render_report(result, store))
    typer.echo(str(store.root / "report.html"))
    if open_report:
        webbrowser.open((store.root / "report.html").as_uri())


@app.command("analyze")
def analyze_command(
    run_dir: Path,
    language: str = typer.Option("", help="Report language; defaults to the saved task"),
    focus: list[str] = typer.Option([], "--focus", help="Decision or report focus; repeatable"),
    candidate_labels: list[str] = typer.Option(
        [], "--candidate-label", help="Explicit URL-stage labels for legacy unlabeled comparisons; repeatable"
    ),
    timeout_seconds: int | None = typer.Option(
        None, "--timeout-seconds", min=1, max=600, help="Analysis request timeout; preserves the source task"
    ),
    open_report: bool = typer.Option(False, "--open"),
):
    """Re-analyze saved answers into a new run (model calls, no new participant sessions)."""
    manifest = json.loads((run_dir / "run_manifest.json").read_text("utf-8"))
    settings = dict(manifest["task"].get("insight", {}))
    settings.pop("strategy", None)
    if language:
        settings["language"] = language
    if focus:
        settings["focus"] = focus
    result = analyze(
        run_dir,
        insight=InsightSpec.model_validate(settings),
        candidate_labels=candidate_labels or None,
        timeout_seconds=timeout_seconds,
    )
    typer.echo(
        json.dumps(
            {
                "run_id": result.run_id,
                "status": result.status,
                "report": str(Path(result.output_dir) / "report.html"),
                "errors": result.errors,
            },
            indent=2,
        )
    )
    if open_report:
        webbrowser.open((Path(result.output_dir) / "report.html").as_uri())
    if result.status != "completed":
        raise typer.Exit(1)


@app.command("doctor")
def doctor_command(task: Path, network: bool = False):
    """Check task and browser installation; --network checks the model catalog and live URL."""
    spec = load_task(task)
    checks = preflight(spec, network=network)
    if spec.environment.mode == "live":
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                if not Path(playwright.chromium.executable_path).exists():
                    checks["issues"].append("Chromium missing: python -m playwright install chromium")
                else:
                    browser = playwright.chromium.launch(headless=True)
                    browser.close()
        except ImportError:
            checks["issues"].append("Install genesia[live]")
        except Exception as error:
            checks["issues"].append(f"Chromium health check failed: {type(error).__name__}")
        if network:
            import requests

            try:
                with requests.Session() as http:
                    http.trust_env = False
                    response = http.get(spec.environment.start_url, timeout=10, allow_redirects=False)
                    if response.status_code != 200:
                        checks["issues"].append(f"Prototype HTTP {response.status_code}")
            except requests.RequestException:
                checks["issues"].append("Prototype unavailable; start the isolated prototype first")
    checks["ok"] = checks["ok"] and not checks["issues"]
    typer.echo(json.dumps(checks, ensure_ascii=False, indent=2))
    if not checks["ok"]:
        raise typer.Exit(1)


@app.command("init")
def init_command(
    mode: str,
    directory: Path,
    personas: Path = typer.Option(None),
    model: str = typer.Option(None, envvar="GENESIA_MODEL"),
    base_url: str = typer.Option("https://api.openai.com/v1", envvar="OPENAI_BASE_URL"),
    api_key_env: str = typer.Option("OPENAI_API_KEY", help="Environment variable containing the API key"),
    goal: str = typer.Option(None),
    url: str = typer.Option(None),
    source: Path = typer.Option(None),
    size: int = 5,
):
    """Create a task for live, survey, or recorded input, prompting for missing inputs."""
    if mode not in {"live", "survey", "recorded"}:
        raise typer.BadParameter("Choose live, survey or recorded")
    target = directory.resolve() / "task.yaml"
    if target.exists():
        raise typer.BadParameter("task.yaml already exists; refusing to overwrite")
    personas = personas or Path(typer.prompt("Authorized Persona JSON/TSV path"))
    if not personas.is_file():
        raise typer.BadParameter("Persona file does not exist")
    model = model or typer.prompt("Model ID available from your configured API")
    goal = goal or typer.prompt("Participant task / research goal")
    environment = {"mode": "survey" if mode == "survey" else "live" if mode == "live" else "auto"}
    if mode == "live":
        environment["start_url"] = url or typer.prompt("Isolated prototype URL")
    if mode == "recorded":
        source = source or Path(typer.prompt("Recording MP4/AVI path"))
        if not source.is_file():
            raise typer.BadParameter("Recording does not exist")
        environment["sources"] = [{"kind": "video", "path": os.path.relpath(source.resolve(), target.parent)}]
    task = TaskSpec.model_validate(
        {
            "goal": goal,
            "cohort": {"source": os.path.relpath(personas.resolve(), target.parent), "size": size},
            "environment": environment,
            "methods": [
                {
                    "id": "feedback",
                    "kind": "survey" if mode == "survey" else "interview",
                    "questions": [{"id": "feedback", "text": "What worked for you, and what was unclear?"}],
                }
            ],
            "model": {"model": model, "base_url": base_url, "api_key_env": api_key_env or None},
            "budget": {"max_tokens": 2500000, "protection": {}},
            "permissions": {"send_persona": False, "send_materials": False, "send_screenshots": False},
        }
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(task.model_dump(), sort_keys=False, allow_unicode=True), "utf-8")
    typer.echo(
        f"Created {target}. Review questions, provider, permissions and budgets before doctor/run. No model calls made."
    )


@app.command("verify")
def verify_command(run_dir: Path):
    if not (run_dir / "evidence.json").is_file():
        typer.echo("Evidence index is missing", err=True)
        raise typer.Exit(1)
    report = EvidenceStore(run_dir).verify()
    typer.echo(json.dumps(report, indent=2))
    if not report["valid"]:
        raise typer.Exit(1)


@app.command("schema")
def schema_command(kind: str = typer.Argument("task")):
    schemas = {
        "task": TaskSpec,
        "result": ResearchResult,
        "persona-request": PersonaGenerationRequest,
        "cohort-plan": CohortPlan,
        "persona-manifest": PersonaGenerationManifest,
        "persona-approval": PersonaCohortApproval,
    }
    if kind not in schemas:
        raise typer.BadParameter(
            "Choose task, result, persona-request, cohort-plan, persona-manifest or persona-approval"
        )
    typer.echo(json.dumps(schemas[kind].model_json_schema(), indent=2))


@app.command("prepare")
def prepare_command(task: Path):
    try:
        report = prepare(load_task(task))
    except (ValueError, OSError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from error
    typer.echo(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "ready":
        raise typer.Exit(1)
