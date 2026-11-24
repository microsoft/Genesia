from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

import typer
import yaml

from .persona_generation import (
    approve_persona_generation,
    compile_persona_slots,
    confirm_persona_plan,
    estimate_generation_budget,
    generate_personas,
    load_cohort_plan,
    load_persona_request,
    plan_personas,
    validate_confirmed_plan,
    write_cohort_plan,
)
from .persona_recovery import recover_personas
from .personas import generation_artifact_issues, load_cohort, managed_generation_issues
from .runtime import BudgetLedger, EvidenceStore, OpenAICompatibleGateway, digest
from .schemas import (
    BudgetSpec,
    CohortSpec,
    ModelSpec,
    PersonaGenerationManifest,
    PersonaGenerationRequest,
)

personas_app = typer.Typer(no_args_is_help=True, help="Plan and generate synthetic Persona cohorts")


def _friendly_errors(function):
    @wraps(function)
    def guarded(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (typer.Exit, typer.BadParameter):
            raise
        except (OSError, ValueError, RuntimeError, yaml.YAMLError) as error:
            detail = str(error).strip() or type(error).__name__
            typer.echo(detail, err=True)
            raise typer.Exit(1) from error

    return guarded


def _model_id(value: str | None) -> str:
    model = value or os.environ.get("GENESIA_MODEL")
    if not model:
        raise typer.BadParameter(
            "Persona planning/generation needs a configured deployment model; set GENESIA_MODEL "
            "or use --model"
        )
    return model


def _summary(plan) -> dict:
    _, issues = compile_persona_slots(plan)
    return {
        "id": plan.id,
        "status": plan.status,
        "sample_size": plan.sample_size,
        "initial_candidate_count": plan.sample_size * plan.candidates_per_slot,
        "candidates_per_slot": plan.candidates_per_slot,
        "max_refill_generations_per_slot": 1 if plan.candidates_per_slot == 1 else 0,
        "segments": [
            {"id": segment.id, "count": segment.quota, "description": segment.description}
            for segment in plan.segments
        ],
        "quotas": [quota.model_dump(mode="json") for quota in plan.quotas],
        "diversity_anchors": [
            {
                "field": anchor.field,
                "values": anchor.values,
                "rationale": anchor.rationale,
            }
            for anchor in plan.diversity_anchors
        ],
        "assumptions": plan.assumptions,
        "limitations": plan.limitations,
        "issues": issues,
    }


def _plan_request(
    request: PersonaGenerationRequest,
    output: Path,
    model: str | None,
    base_url: str = "https://api.openai.com/v1",
    api_key_env: str | None = "OPENAI_API_KEY",
) -> Path:
    target = output.resolve() / "cohort-plan.yaml"
    if target.exists():
        raise typer.BadParameter("cohort-plan.yaml already exists; refusing to overwrite")
    gateway = None
    owned_gateway = None
    if not request.segments:
        model_spec = ModelSpec(model=_model_id(model), base_url=base_url, api_key_env=api_key_env)
        store = EvidenceStore(output.resolve())
        budget = BudgetLedger(BudgetSpec(max_calls=5, max_tokens=500000, max_seconds=600))
        owned_gateway = OpenAICompatibleGateway(model_spec, store, budget)
        gateway = owned_gateway
    try:
        plan = plan_personas(request, gateway=gateway)
    finally:
        if owned_gateway:
            owned_gateway.close()
    write_cohort_plan(target, plan)
    typer.echo(json.dumps(_summary(plan), ensure_ascii=False, indent=2))
    return target


@personas_app.command("recover")
@_friendly_errors
def recover_command(
    generation: Path,
    output: Path = typer.Option(..., "--output"),
    timeout_seconds: int = typer.Option(300, "--timeout-seconds", min=1, max=600),
    workers: int = typer.Option(2, "--workers", min=1, max=16),
    resume: bool = typer.Option(False, "--resume"),
    allow_transport_replay: bool = typer.Option(False, "--allow-transport-replay"),
):
    """Derive a transport-only continuation; keep the terminal source immutable."""
    if not allow_transport_replay:
        raise typer.BadParameter(
            "Use --allow-transport-replay to authorize one additional provider attempt for each "
            "eligible saved ReadTimeout request. Remote cancellation is unknown; charges may duplicate. "
            "No returned profile is regenerated and no cohort is approved."
        )
    manifest = recover_personas(
        generation,
        output,
        timeout_seconds=timeout_seconds,
        max_workers=workers,
        resume=resume,
        progress=typer.echo,
    )
    typer.echo(json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2))
    if manifest.status != "completed":
        raise typer.Exit(2)


@personas_app.command("create")
@_friendly_errors
def create_command(
    output: Path = typer.Option(Path("persona-plan"), "--output"),
    model: str | None = typer.Option(None, "--model", envvar="GENESIA_MODEL"),
    base_url: str = typer.Option("https://api.openai.com/v1", "--base-url", envvar="OPENAI_BASE_URL"),
    api_key_env: str = typer.Option("OPENAI_API_KEY", "--api-key-env"),
):
    """Ask two short questions and produce a one-page draft Cohort Plan."""
    description = typer.prompt("What do you want to research, and which users should be covered?")
    sample_size = typer.prompt("How many Personas?", default=5, type=int)
    request = PersonaGenerationRequest(description=description, sample_size=sample_size)
    output.mkdir(parents=True, exist_ok=True)
    (output / "request.yaml").write_text(
        yaml.safe_dump(request.model_dump(mode="json"), sort_keys=False, allow_unicode=True),
        "utf-8",
    )
    _plan_request(request, output, model, base_url, api_key_env or None)


@personas_app.command("plan")
@_friendly_errors
def plan_command(
    request: Path,
    output: Path = typer.Option(Path("persona-plan"), "--output"),
    model: str | None = typer.Option(None, "--model", envvar="GENESIA_MODEL"),
    base_url: str = typer.Option("https://api.openai.com/v1", "--base-url", envvar="OPENAI_BASE_URL"),
    api_key_env: str = typer.Option("OPENAI_API_KEY", "--api-key-env"),
):
    """Create a draft Cohort Plan from a structured request."""
    _plan_request(load_persona_request(request), output, model, base_url, api_key_env or None)


@personas_app.command("review")
@_friendly_errors
def review_command(plan: Path):
    """Show the concise research plan that needs user confirmation."""
    typer.echo(json.dumps(_summary(load_cohort_plan(plan)), ensure_ascii=False, indent=2))


@personas_app.command("confirm")
@_friendly_errors
def confirm_command(plan: Path):
    """Confirm the user-facing plan without exposing routine technical settings."""
    confirmed = confirm_persona_plan(load_cohort_plan(plan))
    write_cohort_plan(plan, confirmed)
    typer.echo(json.dumps(_summary(confirmed), ensure_ascii=False, indent=2))


@personas_app.command("generate")
@_friendly_errors
def generate_command(
    plan: Path,
    output: Path | None = typer.Option(None, "--output"),
    model: str | None = typer.Option(None, "--model", envvar="GENESIA_MODEL"),
    base_url: str = typer.Option("https://api.openai.com/v1", "--base-url", envvar="OPENAI_BASE_URL"),
    api_key_env: str = typer.Option("OPENAI_API_KEY", "--api-key-env"),
    open_report: bool = typer.Option(False, "--open"),
    resume: bool = typer.Option(False, "--resume"),
    workers: int = typer.Option(5, "--workers", min=1, max=16),
):
    """Generate and validate a confirmed Persona cohort."""
    import webbrowser

    cohort_plan = load_cohort_plan(plan)
    validate_confirmed_plan(cohort_plan)
    if resume and output is None:
        raise typer.BadParameter("--resume requires the existing --output directory")
    generation_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    root = (output or plan.parent / "persona-generations" / generation_id).resolve()
    model_spec = ModelSpec(
        model=_model_id(model),
        base_url=base_url,
        api_key_env=api_key_env or None,
        max_tokens=16384,
        attempts=3,
    )
    budget_spec = estimate_generation_budget(cohort_plan, model_spec)
    if resume and (root / "execution-snapshot.json").is_file():
        saved_snapshot = json.loads((root / "execution-snapshot.json").read_text("utf-8"))
        budget_spec = BudgetSpec.model_validate(saved_snapshot["budget"])
    store = EvidenceStore(root)
    budget = BudgetLedger(budget_spec)
    gateway = OpenAICompatibleGateway(model_spec, store, budget)
    try:
        manifest = generate_personas(
            cohort_plan,
            root,
            gateway=gateway,
            store=store,
            execution_snapshot={
                "model": model_spec.model_dump(mode="json"),
                "budget": budget_spec.model_dump(mode="json"),
            },
            resume=resume,
            max_workers=workers,
            progress=typer.echo,
        )
    finally:
        gateway.close()
    review_counts = json.loads((root / "quality-report.json").read_text("utf-8"))["candidate_review"]
    typer.echo(
        json.dumps(
            {
                **manifest.model_dump(mode="json"),
                "initial_candidate_count": review_counts["initial_candidate_count"],
                "selected_cohort_count": len(manifest.selected_persona_ids),
                "generation_attempts": review_counts["generation_attempts"],
                "refill_generation_attempts": review_counts["refill_generation_attempts"],
                "generated_profile_versions": review_counts["generated_profile_versions"],
                "risk_review_attempts": review_counts["risk_review_attempts"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if open_report:
        webbrowser.open((root / "report.html").as_uri())
    if manifest.status != "completed":
        raise typer.Exit(1)


@personas_app.command("validate")
@_friendly_errors
def validate_command(generation_dir: Path):
    """Verify a generated cohort and its evidence before research use."""
    root = generation_dir.resolve()
    errors = []
    try:
        manifest = PersonaGenerationManifest.model_validate_json(
            (root / "generation-manifest.json").read_text("utf-8")
        )
        errors.extend(generation_artifact_issues(root, manifest))
        snapshot = root / "execution-snapshot.json"
        if not snapshot.is_file() or digest(snapshot.read_bytes()) != manifest.execution_snapshot_sha256:
            errors.append("Execution snapshot hash mismatch")
        if manifest.status != "completed":
            errors.append(f"Persona generation is not completed: {manifest.status}")
        else:
            spec = CohortSpec(source=str(root / "personas.json"), size=len(manifest.selected_persona_ids))
            people, _ = load_cohort(spec)
            errors.extend(managed_generation_issues(spec, people))
    except (OSError, ValueError) as error:
        errors.append(f"Generation manifest could not be validated: {type(error).__name__}")
    evidence = EvidenceStore(root).verify() if (root / "evidence.json").is_file() else {"valid": False}
    if not evidence["valid"]:
        errors.append("Generation evidence verification failed")
    errors = list(dict.fromkeys(errors))
    result = {"valid": not errors, "errors": errors}
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    if errors:
        raise typer.Exit(1)


@personas_app.command("approve")
@_friendly_errors
def approve_command(generation_dir: Path):
    """Approve an exact generated cohort after reviewing its report and profiles."""
    approval = approve_persona_generation(generation_dir)
    typer.echo(json.dumps(approval.model_dump(mode="json"), ensure_ascii=False, indent=2))
