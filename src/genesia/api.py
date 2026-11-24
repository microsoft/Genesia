from __future__ import annotations

import importlib.util
import json
import os
import shutil
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import BoundedSemaphore

import requests
import yaml

from .agents import PersonaAgent, execution_trace
from .analysis import descriptive_statistics
from .environments import (
    CapturedEnvironment,
    CardReviewEnvironment,
    ContextReviewEnvironment,
    EnvironmentBuilderAgent,
    WalkthroughEnvironment,
    material_files,
)
from .personas import load_cohort, managed_generation_issues
from .runtime import (
    BudgetLedger,
    EvidenceStore,
    ModelGateway,
    OpenAICompatibleGateway,
    canonical,
    digest,
    model_catalog_url,
    model_headers,
    write_json,
)
from .schemas import Episode, MethodResponse, ReportModel, ResearchResult, TaskSpec
from .study import readiness, review_study


def _new_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{uuid.uuid4().hex[:8]}"


def load_task(path: str | Path) -> TaskSpec:
    path = Path(path).resolve()
    task = TaskSpec.model_validate(yaml.safe_load(path.read_text(encoding="utf-8-sig")))
    task.cohort.source = str((path.parent / task.cohort.source).resolve())
    task.output_dir = str((path.parent / task.output_dir).resolve())
    for source in task.environment.sources:
        if source.kind != "figma":
            source.path = str((path.parent / source.path).resolve())
        if source.trace_path:
            source.trace_path = str((path.parent / source.trace_path).resolve())
    return task


def budget_plan(task: TaskSpec, people) -> dict:
    protection = task.budget.protection
    if protection is None or not people:
        return {}
    budget = task.budget
    research_calls = int(budget.max_calls * protection.research_fraction) // len(people)
    research_tokens = int(budget.max_tokens * protection.research_fraction) // len(people)
    batches = sum(
        (len(method.questions) + method.batch_size - 1) // method.batch_size + method.max_followups * 2
        for method in task.methods
    ) + (task.environment.mode == "survey")
    if research_calls < batches * task.model.attempts:
        raise ValueError("Research protection cannot cover each Persona's question batches and retries")
    if research_tokens < batches * task.model.max_tokens * task.model.attempts:
        raise ValueError("Research protection is below the configured answer output allowance")
    analysis_calls = int(budget.max_calls * protection.analysis_fraction)
    analysis_tokens = int(budget.max_tokens * protection.analysis_fraction)
    analysis_requests = sum(len(method.questions) for method in task.methods) + 1
    if (
        analysis_calls < analysis_requests * task.model.attempts
        or analysis_tokens < analysis_requests * task.model.max_tokens * task.model.attempts
    ):
        raise ValueError("Analysis protection cannot cover per-question insight stages and composition")
    research_deadline = budget.max_seconds * (1 - protection.analysis_fraction)
    plan = {
        "experience": {
            "seconds": budget.max_seconds * (1 - protection.analysis_fraction - protection.research_fraction)
        },
        "analysis": {"calls": analysis_calls, "tokens": analysis_tokens, "seconds": budget.max_seconds},
    }
    plan.update(
        {
            f"research:{person.id}": {
                "calls": research_calls,
                "tokens": research_tokens,
                "seconds": research_deadline,
            }
            for person in people
        }
    )
    return plan


def validate_task(task: TaskSpec, *, network: bool = False) -> dict:
    issues = []
    uses_images = task.environment.mode == "live"
    if not task.permissions.send_persona or not task.permissions.send_materials:
        issues.append("Explicit send_persona and send_materials permissions are required")
    try:
        people, snapshot = load_cohort(task.cohort)
        issues.extend(managed_generation_issues(task.cohort, people))
    except (ValueError, OSError) as error:
        issues.append(f"Cohort: {error}")
        snapshot = None
        people = []
    plan = {}
    try:
        plan = budget_plan(task, people)
    except ValueError as error:
        issues.append(f"Budget: {error}")
    if task.environment.mode == "live":
        for method in task.methods:
            if method.evidence_mode == "complete" and method.max_images < task.environment.max_steps + 1:
                issues.append(f"{method.id}: complete evidence needs max_images >= max_steps + 1")
    try:
        materials = material_files(task.environment)
        uses_images = (
            task.environment.mode == "live"
            or any(kind in {"image", "video"} for kind, _ in materials)
            or any(source.kind == "figma" for source in task.environment.sources)
        )
        if uses_images and not task.permissions.send_screenshots:
            issues.append("Explicit send_screenshots permission is required")
        if (
            any(source.kind == "figma" for source in task.environment.sources)
            and not task.permissions.fetch_figma
        ):
            issues.append("Figma sources require fetch_figma permission")
        for kind, material in materials:
            dependency = (
                "cv2"
                if kind == "video"
                else "pypdf"
                if material.suffix.lower() == ".pdf"
                else "docx"
                if material.suffix.lower() == ".docx"
                else None
            )
            if dependency and importlib.util.find_spec(dependency) is None:
                issues.append(f"Install genesia[media] for {dependency}")
    except (ValueError, OSError, KeyError, TypeError) as error:
        issues.append(f"Materials: {error}")
    if task.environment.mode == "live" and importlib.util.find_spec("playwright") is None:
        issues.append("Install genesia[live] and run playwright install chromium")
    if network and task.model.api_key_env and not os.environ.get(task.model.api_key_env):
        issues.append(f"Model API key environment variable is not set: {task.model.api_key_env}")
    if network and not issues:
        try:
            with requests.Session() as http:
                http.trust_env = False
                response = http.get(
                    model_catalog_url(task.model),
                    headers=model_headers(task.model),
                    timeout=10,
                    allow_redirects=False,
                )
                if response.status_code != 200:
                    hint = {
                        401: "Check API credentials and that the key belongs to the configured endpoint.",
                        403: "Check resource access, model permissions and endpoint restrictions.",
                        404: "Check the API base URL and support for the OpenAI-compatible /models route.",
                        429: "Check the provider rate limit or quota before retrying.",
                    }.get(
                        response.status_code,
                        "Check provider availability and OpenAI-compatible /models support.",
                    )
                    issues.append(f"Model catalog request failed (HTTP {response.status_code}). {hint}")
                else:
                    models = response.json()
                    if isinstance(models, dict):
                        models = models.get("value", models.get("models", models.get("data", [])))
                    if not isinstance(models, list) or any(not isinstance(model, dict) for model in models):
                        raise ValueError("Invalid model catalog shape")
                    candidates = [model for model in models if model.get("id") == task.model.model]
                    if not candidates:
                        issues.append("Requested model is not available in the configured model catalog")
        except requests.Timeout:
            issues.append(
                "Model catalog request timed out. Check network connectivity and provider availability."
            )
        except requests.ConnectionError:
            issues.append("Cannot connect to model catalog. Check network, TLS and endpoint configuration.")
        except (ValueError, TypeError, AttributeError):
            issues.append(
                "Model catalog response is invalid. Expected JSON with a model list; "
                "check OpenAI-compatible /models support."
            )
        except requests.RequestException:
            issues.append(
                "Model catalog request failed. Check provider availability and endpoint configuration."
            )
    provider_notice = (
        "The configured OpenAI-compatible API receives approved persona, materials and screenshots."
    )
    return {
        "ok": not issues and (readiness(task, people)["ok"] or not task.study.block_on_errors),
        "issues": issues
        + (
            [item["message"] for item in readiness(task, people)["issues"] if item["severity"] == "error"]
            if task.study.block_on_errors
            else []
        ),
        "research_readiness": readiness(task, people),
        "budget_plan": plan,
        "cohort": snapshot,
        "model": task.model.model,
        "provider": task.model.provider,
        "endpoint": task.model.base_url,
        "data_notice": provider_notice,
        "network_checked": network and not issues,
    }


def preflight(task: TaskSpec, *, network: bool = False) -> dict:
    return validate_task(task, network=network)


def render_report(result: ResearchResult, store: EvidenceStore | None = None) -> str:
    def evidence_links(refs):
        return ", ".join(
            f"[{ref}]({store.refs[ref].path})" if store and ref in store.refs else ref for ref in refs
        )

    lines = [
        "# Genesia Research Result [SIMULATED]",
        "",
        f"Run: {result.run_id}",
        f"Status: {result.status}",
        "",
        "## Summary",
        "",
        result.synthesis.summary
        if result.synthesis
        else "Synthesis unavailable; inspect validated responses.",
        "",
        "## Metrics",
        "",
        "```json",
        json.dumps(result.metrics, indent=2),
        "```",
        "",
    ]
    if result.synthesis:
        lines.extend(["## Findings", ""])
        for finding in result.synthesis.findings:
            lines.append(
                f"- {finding.text} Participants: {', '.join(finding.participants)}. "
                f"Evidence: {evidence_links(finding.evidence_refs)}."
            )
        lines.extend(["", "## Segment Differences", ""])
        for finding in result.synthesis.segment_differences:
            lines.append(
                f"- {finding.text} Participants: {', '.join(finding.participants)}; evidence: {evidence_links(finding.evidence_refs)}"
            )
        lines.extend(
            [
                "",
                "## Design Priorities",
                "",
                "Advisory score = severity x cited participant count x confidence / effort. Not measured impact.",
                "",
            ]
        )
        for rank, recommendation in enumerate(result.synthesis.recommendations, 1):
            lines.append(
                f"{rank}. {recommendation.action} (score={recommendation.priority_score}; "
                f"severity={recommendation.severity}, effort={recommendation.effort}, confidence={recommendation.confidence}). "
                f"{recommendation.rationale} Findings: {', '.join(recommendation.finding_ids)}"
            )
        lines.extend(["", "## Limitations", "", result.synthesis.limitations, ""])
    lines.extend(
        ["## Recorded Actions", "", "These are execution records, separate from participant self-report.", ""]
    )
    for episode in result.episodes:
        lines.extend(
            [
                f"### {episode.persona.id}",
                "",
                f"Outcome: {episode.outcome}; basis: {episode.outcome_basis}",
                "",
            ]
        )
        for action in execution_trace(episode):
            lines.append(
                f"- Step {action['step']}: {action['action']} / {action['target'] or '-'} / "
                f"execution success={action['execution_success']}"
            )
        if episode.coverage:
            lines.append(f"- Coverage: {json.dumps(episode.coverage)}")
        if episode.final_observation:
            lines.append(f"- Final observation: {evidence_links(episode.final_observation.evidence_refs)}")
        lines.append("")
    lines.extend(["## Individual Responses", ""])
    for response in result.responses:
        lines.extend(
            [
                f"### {response.persona_id}: {response.method_id}",
                "",
                f"Session: {response.session_id}; valid: {response.valid}; evidence: {evidence_links([response.evidence_ref]) if response.evidence_ref else '-'}",
                "",
            ]
        )
        for answer in response.answers:
            lines.append(
                f"- {answer.question_id}: {json.dumps(answer.value, ensure_ascii=False)} "
                f"({answer.basis}; evidence: {evidence_links(answer.evidence_refs)})"
            )
        for followup in response.followups:
            lines.append(
                f"- Follow-up: {followup['question']['text']} Answer: {followup['answer']['value']} "
                f"Evidence: {evidence_links(followup['answer']['evidence_refs'])}"
            )
        if response.error:
            lines.append(response.error)
        lines.append("")
    if "environment_build" in result.metrics:
        build = result.metrics["environment_build"]
        lines.extend(
            [
                "## Environment Readiness",
                "",
                f"Compiled level: {build['level']}",
                "",
                build["summary"],
                "",
                *[f"- {issue}" for issue in build["issues"]],
                "",
                "See environment_build.json for compilation details and evidence references.",
                "",
            ]
        )
    lines.extend(
        [
            "## Errors",
            "",
            *result.errors,
            "",
            "Generated synthetic feedback is not independent validation with real participants.",
            "",
        ]
    )
    lines.extend(
        ["## Research Readiness", "", "```json", json.dumps(result.study_review, indent=2), "```", ""]
    )
    return "\n".join(lines)


def render_survey_insight_report(result: ResearchResult) -> str:
    lines = [
        "# Genesia Survey Insight Report [SIMULATED]",
        "",
        f"Run: {result.run_id}",
        f"Status: {result.status}",
        "",
        "## Response Quality",
        "",
        f"- Requested Personas: {result.metrics['requested_personas']}",
        f"- Valid responses: {result.metrics['valid_responses']}",
        f"- Invalid responses: {result.metrics['invalid_responses']}",
        f"- Missing responses: {result.metrics['missing_responses']}",
        "",
        "## Executive Summary",
        "",
        result.synthesis.summary if result.synthesis else "Synthesis unavailable.",
        "",
        "## Findings",
        "",
    ]
    if result.synthesis:
        lines.extend(
            f"- {finding.text} Personas: {', '.join(finding.participants)}. "
            f"Evidence: {', '.join(finding.evidence_refs)}."
            for finding in result.synthesis.findings
        )
        lines.extend(["", "## Segment Differences", ""])
        lines.extend(
            f"- {finding.text} Personas: {', '.join(finding.participants)}. "
            f"Evidence: {', '.join(finding.evidence_refs)}."
            for finding in result.synthesis.segment_differences
        )
        lines.extend(["", "## Recommendations", ""])
        lines.extend(
            f"{index}. {item.action} (score={item.priority_score}). {item.rationale} "
            f"Findings: {', '.join(item.finding_ids)}."
            for index, item in enumerate(result.synthesis.recommendations, 1)
        )
        lines.extend(["", "## Limitations", "", result.synthesis.limitations, ""])
    lines.extend(
        [
            "## Descriptive Statistics",
            "",
            "```json",
            json.dumps(result.metrics["descriptive_statistics"], ensure_ascii=False, indent=2),
            "```",
            "",
            "Synthetic Persona responses are not observations of real users or population estimates.",
            "",
        ]
    )
    if result.errors:
        lines.extend(["## Errors", "", *[f"- {error}" for error in result.errors], ""])
    return "\n".join(lines)


def run(
    task: TaskSpec,
    *,
    gateway: ModelGateway | None = None,
    environment_factory=None,
    research_only: bool = False,
) -> ResearchResult:
    checks = validate_task(task, network=gateway is None)
    if not checks["ok"]:
        from .reports import write_reports

        failed_id = _new_run_id()
        failed_store = EvidenceStore(Path(task.output_dir).resolve() / failed_id)
        result = ResearchResult(
            run_id=failed_id,
            status="failed",
            episodes=[],
            responses=[],
            metrics={
                "requested_personas": task.cohort.size,
                "valid_responses": 0,
                "invalid_responses": 0,
                "missing_responses": task.cohort.size * len(task.methods),
            },
            errors=checks["issues"],
            output_dir=str(failed_store.root),
            report=ReportModel(goal=task.goal, input_mode=task.environment.mode),
        )
        write_json(failed_store.root / "research_result.json", result)
        write_json(
            failed_store.root / "run_manifest.json",
            {"run_id": failed_id, "status": "failed", "stage": "validation"},
        )
        write_json(failed_store.root / "evidence.json", [])
        write_reports(result, failed_store, render_report(result, failed_store))
        raise ValueError(
            "Task validation failed: "
            + "; ".join(checks["issues"])
            + f"; report: {failed_store.root / 'report.html'}"
        )
    people, snapshot = load_cohort(task.cohort)
    run_id = _new_run_id()
    root = Path(task.output_dir).resolve() / run_id
    store = EvidenceStore(root)
    budget = BudgetLedger(task.budget)
    plan = budget_plan(task, people)
    if research_only:
        plan.pop("analysis", None)
    scopes = {name: budget.scope(name, **allocation) for name, allocation in plan.items()}
    experience_budget = scopes.get("experience", budget)
    manifest = {
        "schema_version": "0.2",
        "run_id": run_id,
        "status": "running",
        "phase": "research_only" if research_only else "full_study",
        "simulated": True,
        "config_sha256": digest(canonical(task)),
        "cohort": snapshot,
        "task": task.model_dump(),
        "budget_plan": plan,
        "engine_version": "0.2.0",
        "skill_version": "0.2.0",
        "data_notice": checks["data_notice"],
    }
    write_json(root / "run_manifest.json", manifest)
    own_gateway = gateway is None
    gateway = gateway or OpenAICompatibleGateway(task.model, store, experience_budget)
    episodes, responses, errors = [], [], []
    synthesis = None
    analysis_provenance = {}
    call_slots = BoundedSemaphore(task.execution.max_concurrent_model_calls)

    class LimitedGateway:
        def __init__(self, delegate, stage_budget):
            self.delegate = delegate
            self.stage_budget = stage_budget

        def complete(self, *args, **kwargs):
            with call_slots:
                self.stage_budget.check()
                return self.delegate.complete(*args, **kwargs)

    study_report = {}
    try:
        graph = None
        environment_build = None
        if task.environment.mode == "auto":
            environment_build = EnvironmentBuilderAgent(gateway, store, task.permissions).compile(
                task.environment, task.goal
            )
            graph = environment_build.graph
        elif task.environment.mode not in {"live", "survey"}:
            graph = EnvironmentBuilderAgent(gateway, store, task.permissions).build(
                task.environment, task.goal
            )
        study_report = review_study(task, people, graph, gateway, store, environment_build=environment_build)
        if not study_report["ok"] and task.study.block_on_errors:
            raise ValueError(
                "Research readiness/fidelity review blocked the study; inspect study_review.json"
            )

        def run_person(person):
            local_responses, local_errors = [], []
            research_budget = scopes.get(f"research:{person.id}", budget)
            active_budget = research_budget if task.environment.mode == "survey" else experience_budget
            person_gateway = (
                OpenAICompatibleGateway(task.model, store, active_budget) if own_gateway else gateway
            )
            episode_mode = task.environment.mode
            if environment_build is not None:
                episode_mode = environment_build.level
                if environment_build.graph is not None:
                    episode_mode = (
                        "walkthrough"
                        if environment_build.graph.observed_path and environment_build.graph.cards
                        else "captured_graph"
                    )
            episode = Episode(
                session_id=uuid.uuid4().hex,
                persona=person,
                goal=task.goal,
                mode=episode_mode,
                prototype=task.environment.prototype,
                candidate_labels=task.environment.candidate_labels,
            )
            agent = PersonaAgent(
                episode, LimitedGateway(person_gateway, active_budget), store, active_budget, task.study
            )
            try:
                budget.check()
                if task.environment.mode == "survey":
                    agent.begin_survey()
                elif environment_factory:
                    environment = environment_factory(task.environment, store, agent.owner)
                elif task.environment.mode == "live":
                    from .live import LiveEnvironment

                    environment = LiveEnvironment(task.environment, store, agent.owner)
                elif task.environment.mode == "auto":
                    if environment_build.level == "context":
                        environment = ContextReviewEnvironment(environment_build.context, store, agent.owner)
                    elif environment_build.level == "cards":
                        environment = CardReviewEnvironment(
                            environment_build.cards, store, agent.owner, context=environment_build.context
                        )
                    elif environment_build.graph.observed_path and environment_build.graph.cards:
                        environment = WalkthroughEnvironment(
                            environment_build.graph,
                            store,
                            "walkthrough",
                            agent.owner,
                            context=environment_build.context,
                        )
                    else:
                        environment = CapturedEnvironment(
                            environment_build.graph,
                            store,
                            "captured_graph",
                            agent.owner,
                            context=environment_build.context,
                        )
                else:
                    environment = (
                        WalkthroughEnvironment(
                            graph, store, task.environment.mode, agent.owner, task.environment.curated_path
                        )
                        if task.environment.mode == "walkthrough"
                        else CapturedEnvironment(graph, store, task.environment.mode, agent.owner)
                    )
                if task.environment.mode != "survey":
                    agent.experience(
                        environment,
                        task.environment.max_steps,
                        task.environment.min_actions_before_stop,
                        task.environment.required_url_fragments_before_stop,
                    )
                agent.budget = research_budget
                agent.gateway = LimitedGateway(person_gateway, research_budget)
                if own_gateway:
                    person_gateway.budget = research_budget
                for method in task.methods:
                    research_budget.check()
                    local_responses.append(agent.research(method))
                episode.phase = "finished"
                agent.save()
            except Exception as error:
                episode.phase = "failed"
                if episode.outcome == "running":
                    episode.outcome, episode.outcome_basis = "failed", "runtime_error"
                local_errors.append(f"{person.id}: {type(error).__name__}: {str(error)[:160]}")
                agent.save()
                store.event("persona_failed", **agent.owner, error=type(error).__name__)
            finally:
                if plan:
                    research_budget.release()
                if own_gateway:
                    person_gateway.close()
            return episode, local_responses, local_errors

        with ThreadPoolExecutor(max_workers=task.execution.max_concurrent_personas) as executor:
            for episode, person_responses, person_errors in executor.map(run_person, people):
                episodes.append(episode)
                responses.extend(person_responses)
                errors.extend(person_errors)
        if not research_only and any(response.valid for response in responses):
            from .insight_report import synthesize_insight_report

            if own_gateway:
                gateway.budget = scopes.get("analysis", budget)
            synthesis, analysis_provenance = synthesize_insight_report(
                task, responses, episodes, gateway, store
            )
    except Exception as error:
        errors.append(f"Run stage: {type(error).__name__}: {str(error)[:160]}")
        store.event("stage_failed", error=type(error).__name__)
    finally:
        if own_gateway:
            gateway.close()
    valid = sum(response.valid for response in responses)
    expected = len(people) * len(task.methods)
    metrics = {
        "requested_personas": len(people),
        "episodes": len(episodes),
        "outcomes": dict(Counter(episode.outcome for episode in episodes)),
        "valid_responses": valid,
        "invalid_responses": sum(not response.valid for response in responses),
        "missing_responses": expected - len(responses),
        "failed_actions": sum(not step.result.success for episode in episodes for step in episode.steps),
        "budget": budget.summary(),
        "analysis_skipped": research_only,
        "descriptive_statistics": descriptive_statistics(task, responses, episodes),
    }
    if environment_build is not None:
        metrics["environment_build"] = {
            "level": environment_build.level,
            "summary": environment_build.assessment.summary
            if environment_build.assessment
            else "Prepared graph",
            "issues": environment_build.issues,
        }
    status = (
        "completed"
        if valid == expected and (research_only or synthesis) and not errors
        else "partial"
        if valid
        else "failed"
    )
    if (root / "analysis_provenance.json").exists():
        analysis_provenance = json.loads((root / "analysis_provenance.json").read_text("utf-8"))
    result = ResearchResult(
        run_id=run_id,
        status=status,
        episodes=episodes,
        responses=responses,
        metrics=metrics,
        synthesis=synthesis,
        errors=errors,
        output_dir=str(root),
        study_review=study_report,
        report=ReportModel(
            goal=task.goal,
            input_mode=task.environment.mode,
            methods=[method.model_dump() for method in task.methods],
            objectives=[objective.model_dump() for objective in task.study.objectives],
            analysis=analysis_provenance,
        ),
    )
    write_json(root / "research_result.json", result)
    from .reports import write_reports

    if not research_only:
        write_reports(result, store, render_report(result, store))
    if not research_only and task.environment.mode == "survey":
        (root / "insight_report.md").write_text((root / "report.md").read_text("utf-8"), encoding="utf-8")
    manifest.update(status=status, budget=budget.summary())
    write_json(root / "run_manifest.json", manifest)
    write_json(root / "evidence_verification.json", store.verify())
    store.event("run_finished", status=status)
    return result


def analyze(
    run_dir: str | Path,
    *,
    insight=None,
    candidate_labels: list[str] | None = None,
    timeout_seconds: int | None = None,
    gateway: ModelGateway | None = None,
) -> ResearchResult:
    """Analyze an intact saved study into a new directory without repeating participant sessions."""
    from .insight_report import synthesize_insight_report
    from .reports import write_reports

    source = Path(run_dir).resolve()
    if not (source / "evidence.json").is_file():
        raise ValueError("Source evidence index is missing")
    source_store = EvidenceStore(source)
    if not source_store.verify()["valid"]:
        raise ValueError("Source evidence integrity check failed")
    result = ResearchResult.model_validate_json((source / "research_result.json").read_text("utf-8"))
    for response in result.responses:
        if not response.evidence_ref or response.evidence_ref not in source_store.refs:
            raise ValueError("Source response evidence is missing")
        recorded = MethodResponse.model_validate_json(
            source_store.path(response.evidence_ref).read_text("utf-8")
        )
        if recorded.model_dump(exclude={"evidence_ref"}) != response.model_dump(exclude={"evidence_ref"}):
            raise ValueError("Saved response differs from immutable source evidence")
    manifest = json.loads((source / "run_manifest.json").read_text("utf-8"))
    task_data = dict(manifest["task"])
    task_data["insight"] = dict(task_data.get("insight", {}))
    task_data["insight"].pop("strategy", None)
    if candidate_labels is not None:
        environment = dict(task_data["environment"])
        if environment.get("candidate_labels"):
            raise ValueError("Analysis cannot override saved candidate_labels")
        if not environment.get("handoff_urls"):
            raise ValueError("Analysis candidate_labels require a saved staged comparison")
        configured = {
            question.get("candidate")
            for method in task_data["methods"]
            for question in method["questions"]
            if question.get("candidate")
        }
        if set(candidate_labels) != configured:
            raise ValueError("Analysis candidate_labels must match the saved question candidates")
        environment["candidate_labels"] = list(candidate_labels)
        task_data["environment"] = environment
    task = TaskSpec.model_validate(task_data)
    source_timeout_seconds = task.model.timeout_seconds
    if timeout_seconds is not None:
        task.model.timeout_seconds = timeout_seconds
    if not task.permissions.send_persona or not task.permissions.send_materials:
        raise ValueError("Analysis requires explicit persona and material sending permissions")
    if insight is not None:
        task.insight = insight
    run_id = _new_run_id()
    root = source.parent / run_id
    root.mkdir()
    for name in ("artifacts", "episodes", "research"):
        if (source / name).is_dir():
            shutil.copytree(source / name, root / name)
    shutil.copy2(source / "evidence.json", root / "evidence.json")
    store = EvidenceStore(root)
    budget = BudgetLedger(task.budget)
    own_gateway = gateway is None
    gateway = gateway or OpenAICompatibleGateway(task.model, store, budget)
    manifest.update(
        run_id=run_id,
        status="running",
        task=task.model_dump(),
        config_sha256=digest(canonical(task)),
        phase="analysis_only",
        analysis_mode="staged",
        source_run_id=result.run_id,
        source_status=result.status,
        source_errors=list(result.errors),
        source_result_sha256=digest((source / "research_result.json").read_bytes()),
    )
    if candidate_labels is not None:
        manifest["analysis_candidate_label_resolution"] = {
            "basis": "Explicit URL-stage labels supplied for a legacy saved task; no answers or episodes relabeled.",
            "candidate_labels": list(candidate_labels),
        }
    if timeout_seconds is not None:
        manifest["analysis_timeout_override"] = {
            "source_timeout_seconds": source_timeout_seconds,
            "timeout_seconds": task.model.timeout_seconds,
        }
    write_json(root / "run_manifest.json", manifest)
    result.run_id, result.output_dir, result.synthesis = run_id, str(root), None
    result.errors = []
    provenance = {}
    try:
        result.synthesis, provenance = synthesize_insight_report(
            task, result.responses, result.episodes, gateway, store
        )
    except Exception as error:
        result.errors.append(f"Analysis: {type(error).__name__}: {error}")
        if (root / "analysis_provenance.json").exists():
            provenance = json.loads((root / "analysis_provenance.json").read_text("utf-8"))
    finally:
        if own_gateway:
            gateway.close()
    result.status = (
        "completed"
        if result.synthesis
        and not result.errors
        and not result.metrics.get("invalid_responses")
        and not result.metrics.get("missing_responses")
        and not any(episode.phase == "failed" for episode in result.episodes)
        else "partial"
        if result.metrics.get("valid_responses")
        else "failed"
    )
    result.report = ReportModel(
        goal=task.goal,
        input_mode=task.environment.mode,
        methods=[method.model_dump() for method in task.methods],
        objectives=[objective.model_dump() for objective in task.study.objectives],
        analysis=provenance,
    )
    result.metrics["source_budget"] = result.metrics.get("budget", {})
    result.metrics["budget"] = budget.summary()
    result.metrics["descriptive_statistics"] = descriptive_statistics(task, result.responses, result.episodes)
    write_json(root / "research_result.json", result)
    write_reports(result, store, render_report(result, store))
    if task.environment.mode == "survey":
        (root / "insight_report.md").write_bytes((root / "report.md").read_bytes())
    manifest.update(status=result.status, budget=budget.summary())
    write_json(root / "run_manifest.json", manifest)
    write_json(root / "evidence_verification.json", store.verify())
    store.event("analysis_finished", status=result.status, source_run_id=manifest["source_run_id"])
    return result


def reanswer(
    run_dir: str | Path,
    *,
    task: TaskSpec | None = None,
    gateway: ModelGateway | None = None,
) -> ResearchResult:
    """Repeat only the questionnaire from intact saved episodes into a new run."""
    source = Path(run_dir).resolve()
    source_result_path = source / "research_result.json"
    source_manifest_path = source / "run_manifest.json"
    if not (source / "evidence.json").is_file() or not source_result_path.is_file():
        raise ValueError("Source run is missing evidence or research_result.json")
    source_store = EvidenceStore(source)
    if not source_store.verify()["valid"]:
        raise ValueError("Source evidence integrity check failed")
    source_result = ResearchResult.model_validate_json(source_result_path.read_text("utf-8"))
    manifest = json.loads(source_manifest_path.read_text("utf-8"))
    task_data = dict(manifest["task"])
    task_data["insight"] = dict(task_data.get("insight", {}))
    task_data["insight"].pop("strategy", None)
    source_task = TaskSpec.model_validate(task_data)
    task = task or source_task
    source_persona_ids = {episode.persona.id for episode in source_result.episodes}
    if task.cohort.ids and not source_persona_ids.issubset(task.cohort.ids):
        missing = sorted(source_persona_ids.difference(task.cohort.ids))
        raise ValueError(f"Re-answer task does not include source personas: {missing}")
    if not task.permissions.send_persona or not task.permissions.send_materials:
        raise ValueError("Re-answering requires explicit persona and material sending permissions")
    has_images = any(
        observation.image_refs
        for episode in source_result.episodes
        for observation in [
            *(step.observation for step in episode.steps),
            *([episode.final_observation] if episode.final_observation else []),
        ]
    )
    if has_images and not task.permissions.send_screenshots:
        raise ValueError("Prototype re-answering requires screenshot sending permission")
    if not source_result.episodes:
        raise ValueError("Source run has no saved episodes")

    run_id = _new_run_id()
    root = source.parent / run_id
    root.mkdir()
    shutil.copytree(source / "artifacts", root / "artifacts")
    shutil.copy2(source / "evidence.json", root / "evidence.json")
    store = EvidenceStore(root)
    budget = BudgetLedger(task.budget)
    people = [episode.persona for episode in source_result.episodes]
    plan = {
        name: allocation
        for name, allocation in budget_plan(task, people).items()
        if name.startswith("research:")
    }
    scopes = {name: budget.scope(name, **allocation) for name, allocation in plan.items()}
    own_gateway = gateway is None
    gateway = gateway or OpenAICompatibleGateway(task.model, store, budget)
    responses, episodes, errors = [], [], []
    manifest.update(
        run_id=run_id,
        status="running",
        phase="reanswer_only",
        task=task.model_dump(),
        config_sha256=digest(canonical(task)),
        source_run_id=source_result.run_id,
        source_status=source_result.status,
        source_config_sha256=manifest.get("config_sha256"),
        source_result_sha256=digest(source_result_path.read_bytes()),
        source_episodes_sha256=digest(canonical(source_result.episodes)),
        budget_plan=plan,
    )
    write_json(root / "run_manifest.json", manifest)
    store.event("reanswer_started", source_run_id=source_result.run_id)
    try:
        for source_episode in source_result.episodes:
            episode = source_episode.model_copy(deep=True)
            episode.phase = "research"
            research_budget = scopes.get(f"research:{episode.persona.id}", budget)
            person_gateway = (
                OpenAICompatibleGateway(task.model, store, research_budget) if own_gateway else gateway
            )
            agent = PersonaAgent(episode, person_gateway, store, research_budget, task.study)
            try:
                for method in task.methods:
                    research_budget.check()
                    responses.append(agent.research(method))
                episode.phase = "finished"
                agent.save()
            except Exception as error:
                episode.phase = "failed"
                errors.append(f"{episode.persona.id}: {type(error).__name__}: {str(error)[:160]}")
                agent.save()
            finally:
                if f"research:{episode.persona.id}" in scopes:
                    research_budget.release()
                if own_gateway:
                    person_gateway.close()
            episodes.append(episode)
    finally:
        if own_gateway:
            gateway.close()

    valid = sum(response.valid for response in responses)
    expected = len(episodes) * len(task.methods)
    status = "completed" if valid == expected and not errors else "partial" if valid else "failed"
    metrics = {
        "requested_personas": len(episodes),
        "episodes": len(episodes),
        "outcomes": dict(Counter(episode.outcome for episode in episodes)),
        "valid_responses": valid,
        "invalid_responses": sum(not response.valid for response in responses),
        "missing_responses": expected - len(responses),
        "failed_actions": sum(not step.result.success for episode in episodes for step in episode.steps),
        "experience_reused": True,
        "analysis_skipped": True,
        "source_budget": source_result.metrics.get("budget", {}),
        "budget": budget.summary(),
        "descriptive_statistics": descriptive_statistics(task, responses, episodes),
    }
    result = ResearchResult(
        run_id=run_id,
        status=status,
        episodes=episodes,
        responses=responses,
        metrics=metrics,
        synthesis=None,
        errors=errors,
        output_dir=str(root),
        study_review=source_result.study_review,
        report=ReportModel(
            goal=task.goal,
            input_mode=task.environment.mode,
            methods=[method.model_dump() for method in task.methods],
            objectives=[objective.model_dump() for objective in task.study.objectives],
        ),
    )
    write_json(root / "research_result.json", result)
    manifest.update(status=status, budget=budget.summary())
    write_json(root / "run_manifest.json", manifest)
    write_json(root / "evidence_verification.json", store.verify())
    store.event("reanswer_finished", status=status, source_run_id=source_result.run_id)
    return result


def prepare(task: TaskSpec, *, gateway: ModelGateway | None = None) -> dict:
    checks = validate_task(task, network=gateway is None)
    if not checks["ok"]:
        raise ValueError("Task validation failed: " + "; ".join(checks["issues"]))
    people, snapshot = load_cohort(task.cohort)
    root = Path(task.output_dir).resolve() / ("prepare-" + _new_run_id())
    store = EvidenceStore(root)
    budget = BudgetLedger(task.budget)
    own_gateway = gateway is None
    gateway = gateway or OpenAICompatibleGateway(task.model, store, budget)
    report = {
        "status": "running",
        "output_dir": str(root),
        "cohort": snapshot,
        "task_sha256": digest(canonical(task)),
    }
    try:
        environment_build = None
        if task.environment.mode == "auto":
            environment_build = EnvironmentBuilderAgent(gateway, store, task.permissions).compile(
                task.environment, task.goal
            )
            graph = environment_build.graph
            report["environment_build"] = environment_build.model_dump()
        else:
            graph = (
                EnvironmentBuilderAgent(gateway, store, task.permissions).build(task.environment, task.goal)
                if task.environment.mode not in {"live", "survey"}
                else None
            )
        if graph:
            write_json(root / "state_graph.json", graph)
        report["research_readiness"] = review_study(
            task, people, graph, gateway, store, environment_build=environment_build
        )
        report["status"] = "ready" if report["research_readiness"]["ok"] else "needs_revision"
    except Exception as error:
        report.update(status="failed", error=type(error).__name__)
        raise
    finally:
        report["budget"] = budget.summary()
        write_json(root / "preparation.json", report)
        if own_gateway:
            gateway.close()
    return report
