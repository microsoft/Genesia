from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from ..runtime import canonical, model_prompt
from ..schemas import (
    BudgetSpec,
    CohortPlan,
    ModelSpec,
    Persona,
    PersonaCandidateResponse,
    PersonaCohortRiskReview,
    PersonaGenerationManifest,
    PersonaRiskReview,
)
from .plan import compile_persona_slots, persona_plan_sha256, validate_confirmed_plan
from .prompts import NAME_REPAIR_PURPOSE, _candidate_payload, _PersonaNameRepair, _risk_review_payload


def estimate_generation_budget(plan: CohortPlan, model: ModelSpec) -> BudgetSpec:
    if plan.status == "confirmed":
        validate_confirmed_plan(plan)
    else:
        plan = plan.model_copy(update={"plan_sha256": persona_plan_sha256(plan)})
    slots, _ = compile_persona_slots(plan)
    total_tokens = 0
    profile_bounds = [60000 + len(canonical(slot, compact=True)) + 512 for slot in slots]
    blocking_profile_bound = max(profile_bounds)
    for slot in slots:
        candidate_payload = _candidate_payload(plan, slot, plan.candidates_per_slot - 1, slots)
        risk_payload = _risk_review_payload(
            plan,
            slot,
            {
                "segment": slot.segment_id,
                **slot.fixed,
                "diversity_anchors": slot.anchors,
                "research_profile": {"bounded_content": "x" * 60000},
            },
        )
        candidate_prompt = model_prompt(
            "persona_candidate_generation", candidate_payload, PersonaCandidateResponse
        )
        risk_prompt = model_prompt("persona_candidate_risk_review", risk_payload, PersonaRiskReview)
        per_pair = (
            len(candidate_prompt.encode("utf-8"))
            + 4096
            + model.max_tokens
            + len(risk_prompt.encode("utf-8"))
            + 4096
            + model.max_tokens
        )
        total_tokens += per_pair * plan.candidates_per_slot * model.attempts
        if plan.candidates_per_slot == 1:
            # Two generation versions, each with at most two review operations.
            refill_payload = {
                **candidate_payload,
                "refill": {
                    "reason": "x" * 4000,
                    "previous_profile": {"bounded_content": "x" * 60000},
                    "blocking_profiles": [],
                },
            }
            refill_prompt = model_prompt(
                "persona_candidate_generation", refill_payload, PersonaCandidateResponse
            )
            total_tokens += (
                len(refill_prompt.encode("utf-8"))
                + blocking_profile_bound
                + model.max_tokens * 16
                + 4096
                + model.max_tokens
                + 3 * (len(risk_prompt.encode("utf-8")) + 4096 + model.max_tokens)
            ) * model.attempts
    cohort_payload = {
        "research_request": plan.description,
        "assumptions": plan.assumptions,
        "slots": [slot.model_dump(mode="json") for slot in slots],
        "selected_cohort": [
            {
                "candidate_id": f"{slot.slot_id}-candidate-1",
                "segment": slot.segment_id,
                "fixed": slot.fixed,
                "diversity_anchors": slot.anchors,
                "bounded_content": "x" * 20000,
            }
            for slot in slots
        ],
        "deterministic_quality_audit": {},
        "instruction": "Review the selected cohort as a whole.",
    }
    cohort_prompt = model_prompt(
        "persona_cohort_quality_review",
        cohort_payload,
        PersonaCohortRiskReview,
    )
    cohort_input_bound = len(cohort_prompt.encode("utf-8"))
    if plan.candidates_per_slot == 1:
        cohort_input_bound = max(
            cohort_input_bound,
            sum(profile_bounds) + plan.sample_size**2 * 512 + plan.sample_size * 16384 + 16384,
        )
    total_tokens += (cohort_input_bound + 4096 + model.max_tokens) * model.attempts
    logical_calls = plan.sample_size * plan.candidates_per_slot * 2 + 1
    if plan.candidates_per_slot == 1:
        logical_calls += plan.sample_size * 4
    if plan.sample_size > 1:
        logical_calls += 1
        # Every name is sent at most once, with up to 500 characters and JSON escaping.
        repair_overhead = len(model_prompt(NAME_REPAIR_PURPOSE, {}, _PersonaNameRepair).encode("utf-8"))
        total_tokens += (
            plan.sample_size * (500 * 6 + 64) + repair_overhead + 4096 + model.max_tokens
        ) * model.attempts
    max_calls = logical_calls * model.attempts
    return BudgetSpec(
        max_calls=max_calls,
        max_tokens=total_tokens,
        max_seconds=max(1800, plan.sample_size * 120),
    )


def _write_generation_report(
    root: Path,
    plan: CohortPlan,
    manifest: PersonaGenerationManifest,
    quality_report: dict[str, Any],
    selected: list[Persona],
) -> None:
    issue_items = "".join(f"<li>{html.escape(issue)}</li>" for issue in manifest.issues) or "<li>None</li>"
    candidate_review = quality_report.get("candidate_review", {})
    distributions = quality_report.get("profile_distributions", {})
    distribution_rows = "".join(
        f"<tr><th>{html.escape(field)}</th><td><code>{html.escape(str(values))}</code></td></tr>"
        for field, values in distributions.items()
    )
    quality_gates = quality_report.get("quality_gates", {})
    gate_errors = (
        "".join(f"<li>{html.escape(issue)}</li>" for issue in quality_gates.get("errors", []))
        or "<li>None</li>"
    )
    gate_warnings = (
        "".join(f"<li>{html.escape(issue)}</li>" for issue in quality_gates.get("warnings", []))
        or "<li>None</li>"
    )
    profile_sections = (
        "".join(
            f"<details><summary>{html.escape(persona.id)}</summary>"
            f"<pre>{html.escape(json.dumps(persona.profile, ensure_ascii=False, indent=2))}</pre></details>"
            for persona in selected
        )
        or "<p>No profiles selected.</p>"
    )
    cohort_review = html.escape(
        json.dumps(quality_report.get("cohort_semantic_review"), ensure_ascii=False, indent=2)
    )
    name_repair = quality_report.get("name_repair")
    repair_section = (
        "<h2>Display name repair</h2>"
        f"<pre>{html.escape(json.dumps(name_repair, ensure_ascii=False, indent=2))}</pre>"
        if name_repair
        else ""
    )
    root.joinpath("report.html").write_text(
        "<!doctype html><html><head><meta charset='utf-8'><title>Persona Generation</title>"
        "<style>body{font:16px/1.5 sans-serif;max-width:900px;margin:40px auto;padding:0 20px}"
        "code{overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere}"
        "th{text-align:left;vertical-align:top;padding-right:18px}</style>"
        "</head><body>"
        f"<h1>Persona Generation</h1><p><strong>Status:</strong> {manifest.status}</p>"
        f"<p><strong>Plan:</strong> {html.escape(plan.description)}</p>"
        f"<p><strong>Requested:</strong> {plan.sample_size}; "
        f"<strong>Selected:</strong> {len(manifest.selected_persona_ids)}</p>"
        "<h2>Candidate review coverage</h2>"
        f"<pre>{html.escape(str(candidate_review))}</pre>"
        f"<h2>Selected profiles awaiting human approval</h2>{profile_sections}"
        f"{repair_section}"
        f"<h2>Exact-cohort semantic review</h2><pre>{cohort_review}</pre>"
        "<h2>Cohort profile distributions</h2>"
        f"<table>{distribution_rows}</table>"
        f"<h2>Quality gate errors</h2><ul>{gate_errors}</ul>"
        f"<h2>Quality warnings</h2><ul>{gate_warnings}</ul>"
        f"<h2>Issues and limitations</h2><ul>{issue_items}</ul>"
        "<p><strong>Human approval:</strong> required before managed study use.</p>"
        "<p>Synthetic Persona coverage is not population prevalence or human-participant evidence.</p>"
        "</body></html>",
        "utf-8",
    )
