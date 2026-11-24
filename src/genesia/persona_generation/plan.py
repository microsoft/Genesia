from __future__ import annotations

import random
import re
from collections import Counter
from pathlib import Path

import yaml

from ..runtime import ModelGateway, canonical, digest
from ..schemas import (
    CohortPlan,
    DiversityAnchor,
    PersonaGenerationRequest,
    PersonaPlanProposal,
    PersonaSegment,
    PersonaSlot,
)


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug[:48] or "persona-cohort"


def _plan_content(plan: CohortPlan) -> dict:
    return plan.model_dump(exclude={"status", "plan_sha256"})


def persona_plan_sha256(plan: CohortPlan) -> str:
    return digest(canonical(_plan_content(plan), compact=True))


def validate_confirmed_plan(plan: CohortPlan) -> None:
    if plan.status != "confirmed" or not plan.plan_sha256:
        raise ValueError("Persona generation requires a confirmed Cohort Plan")
    if persona_plan_sha256(plan) != plan.plan_sha256:
        raise ValueError("Cohort Plan changed after confirmation")


def confirm_persona_plan(plan: CohortPlan) -> CohortPlan:
    draft = plan.model_copy(update={"status": "draft", "plan_sha256": None})
    compile_persona_slots(draft)
    return draft.model_copy(update={"status": "confirmed", "plan_sha256": persona_plan_sha256(draft)})


def _validate_proposal(proposal: PersonaPlanProposal, sample_size: int) -> None:
    if sum(segment.quota for segment in proposal.segments) != sample_size:
        raise ValueError("Planned segment quotas must sum to sample_size")
    if len({segment.id for segment in proposal.segments}) != len(proposal.segments):
        raise ValueError("Planned segment IDs must be unique")
    if len({anchor.field for anchor in proposal.diversity_anchors}) != len(proposal.diversity_anchors):
        raise ValueError("Planned Diversity Anchor fields must be unique")
    if len({quota.field for quota in proposal.quotas}) != len(proposal.quotas):
        raise ValueError("Planned quota fields must be unique")
    for quota in proposal.quotas:
        if sum(quota.counts.values()) != sample_size:
            raise ValueError(f"Planned quota counts for {quota.field} must sum to sample_size")


def plan_personas(
    request: PersonaGenerationRequest,
    *,
    gateway: ModelGateway | None = None,
) -> CohortPlan:
    segments = request.segments
    anchors = request.diversity_anchors
    assumptions = list(request.assumptions)
    eligibility = request.eligibility
    quotas = request.quotas
    limitations = ["Archetype coverage is designed for perspective diversity, not population representation."]

    if not segments:
        if gateway is None:
            segments = [
                PersonaSegment(
                    id="general",
                    description="Eligible participants described by the research request",
                    quota=request.sample_size,
                )
            ]
            assumptions.append(
                "No planning model was supplied; the request uses one general research segment."
            )
        else:
            proposal = gateway.complete(
                "persona_cohort_plan",
                {
                    "research_request": request.model_dump(),
                    "instruction": (
                        "Propose research-relevant segments and at most four Diversity Anchors. "
                        "Convert explicit demographic distributions into integer quota counts that "
                        "sum to sample_size; use largest-remainder rounding only within each individual "
                        "distribution. Preserve sample_size exactly. Anchors describe background or behavior, not "
                        "expected product findings, preferences or problems. Use soft cohort coverage "
                        "unless the request explicitly requires otherwise. Do not infer prevalence."
                    ),
                },
                PersonaPlanProposal,
                validate=lambda value: _validate_proposal(value, request.sample_size),
            )
            _validate_proposal(proposal, request.sample_size)
            segments = proposal.segments
            if not eligibility:
                eligibility = proposal.eligibility
            if not quotas:
                quotas = proposal.quotas
            if not anchors:
                anchors = proposal.diversity_anchors
            assumptions.extend(proposal.assumptions)
            limitations.extend(proposal.limitations)

    request_hash = digest(canonical(request, compact=True))[:10]
    plan = CohortPlan(
        id=f"{_slug(request.description)}-{request_hash}",
        description=request.description,
        sample_size=request.sample_size,
        seed=request.seed,
        candidates_per_slot=request.candidates_per_slot,
        duplicate_similarity_threshold=request.duplicate_similarity_threshold,
        eligibility=eligibility,
        segments=segments,
        quotas=quotas,
        diversity_anchors=anchors,
        assumptions=list(dict.fromkeys(assumptions)),
        limitations=list(dict.fromkeys(limitations)),
    )
    compile_persona_slots(plan)
    return plan


def _assign_quota(
    slots: list[dict], field: str, counts: dict[str, int], policy: str, seed: int
) -> str | None:
    used = Counter(slot["fixed"].get(field) for slot in slots if field in slot["fixed"])
    excess = {value: used[value] - count for value, count in counts.items() if used[value] > count}
    unknown = sorted(value for value in used if value not in counts)
    if policy == "hard" and (excess or unknown):
        raise ValueError(f"Hard quota {field} conflicts with fixed segment constraints")

    open_slots = [slot for slot in slots if field not in slot["fixed"]]
    assignments = [value for value, count in counts.items() for _ in range(max(0, count - used[value]))]
    issue = None
    if len(assignments) != len(open_slots):
        if policy == "hard":
            raise ValueError(f"Hard quota {field} cannot be allocated")
        issue = f"Soft quota {field} deviates because fixed segment constraints consume its target"
        ordered = sorted(counts, key=lambda value: (used[value], value))
        while len(assignments) < len(open_slots):
            assignments.append(ordered[len(assignments) % len(ordered)])
        assignments = assignments[: len(open_slots)]

    rng = random.Random(f"{seed}:quota:{field}")
    rng.shuffle(open_slots)
    rng.shuffle(assignments)
    for slot, value in zip(open_slots, assignments):
        slot["fixed"][field] = value

    actual = Counter(slot["fixed"].get(field) for slot in slots)
    if policy == "hard" and actual != Counter(counts):
        raise ValueError(f"Hard quota {field} allocation did not preserve requested counts")
    if policy == "soft" and actual != Counter(counts):
        issue = issue or f"Soft quota {field} could not be matched exactly"
    return issue


def _assign_anchor(slots: list[dict], anchor: DiversityAnchor, seed: int) -> str | None:
    required = len(anchor.values) * anchor.minimum_per_value
    if required > len(slots) and anchor.policy == "hard":
        raise ValueError(f"Hard Diversity Anchor {anchor.field} cannot fit in the cohort")

    assignments = [value for value in anchor.values for _ in range(anchor.minimum_per_value)][: len(slots)]
    while len(assignments) < len(slots):
        counts = Counter(assignments)
        assignments.append(min(anchor.values, key=lambda value: (counts[value], value)))

    ordered_slots = list(slots)
    rng = random.Random(f"{seed}:anchor:{anchor.field}")
    rng.shuffle(ordered_slots)
    rng.shuffle(assignments)
    for slot, value in zip(ordered_slots, assignments):
        slot["anchors"][anchor.field] = value

    actual = Counter(slot["anchors"].get(anchor.field) for slot in slots)
    missing = [value for value in anchor.values if actual[value] < anchor.minimum_per_value]
    if missing:
        return f"Soft Diversity Anchor {anchor.field} cannot cover: {', '.join(missing)}"
    return None


def compile_persona_slots(plan: CohortPlan) -> tuple[list[PersonaSlot], list[str]]:
    slots: list[dict] = []
    for segment in plan.segments:
        for index in range(segment.quota):
            fixed = dict(plan.eligibility)
            for field, value in segment.constraints.items():
                if field in fixed and fixed[field] != value:
                    raise ValueError(f"Segment {segment.id} conflicts with eligibility for {field}")
                fixed[field] = value
            slots.append(
                {
                    "slot_id": f"slot-{len(slots) + 1:04d}",
                    "segment_id": segment.id,
                    "fixed": fixed,
                    "anchors": {},
                    "assumptions": [
                        "Diversity Anchors were allocated for coverage, not inferred from demographics."
                    ],
                }
            )
    if len(slots) != plan.sample_size:
        raise ValueError("Compiled Persona slots do not match sample_size")

    issues = []
    for quota in plan.quotas:
        issue = _assign_quota(slots, quota.field, quota.counts, quota.policy, plan.seed)
        if issue:
            issues.append(issue)
    for anchor in plan.diversity_anchors:
        issue = _assign_anchor(slots, anchor, plan.seed)
        if issue:
            issues.append(issue)
    return [PersonaSlot.model_validate(slot) for slot in slots], issues


def load_persona_request(path: str | Path) -> PersonaGenerationRequest:
    source = Path(path)
    return PersonaGenerationRequest.model_validate(yaml.safe_load(source.read_text("utf-8")))


def load_cohort_plan(path: str | Path) -> CohortPlan:
    source = Path(path)
    return CohortPlan.model_validate(yaml.safe_load(source.read_text("utf-8")))


def write_cohort_plan(path: str | Path, plan: CohortPlan) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump(plan.model_dump(mode="json"), sort_keys=False, allow_unicode=True),
        "utf-8",
    )
