from __future__ import annotations

import re
from collections import Counter
from typing import Any

from ..runtime import canonical
from ..schemas import (
    CohortPlan,
    Persona,
    PersonaSlot,
)


def _research_behavior_projection(profile: dict[str, Any]) -> dict[str, Any]:
    research = profile["research_profile"]

    def attribute(*path: str) -> Any:
        value: Any = research
        for part in path:
            value = value[part]
        return value["value"]

    return {
        "segment": profile["segment"],
        "fixed": {
            key: value
            for key, value in profile.items()
            if key not in {"segment", "diversity_anchors", "research_profile"}
        },
        "diversity_anchors": profile["diversity_anchors"],
        "occupation": attribute("core_identity", "occupation"),
        "education": attribute("core_identity", "education", "degree"),
        "values_and_priorities": attribute("personality_and_cognitive_style", "values_and_priorities"),
        "motivations": attribute("personality_and_cognitive_style", "motivations"),
        "cognitive_style": attribute("personality_and_cognitive_style", "cognitive_style"),
        "search_patterns": attribute("digital_behavior_and_online_habits", "search_patterns"),
        "preferred_content_sources": attribute(
            "digital_behavior_and_online_habits", "preferred_content_sources"
        ),
        "device_usage": attribute("digital_behavior_and_online_habits", "device_usage"),
        "communication_style": attribute("digital_behavior_and_online_habits", "communication_style"),
        "professional_interests": attribute("interests_and_preferences", "professional_interests"),
        "content_consumption": attribute("interests_and_preferences", "content_consumption"),
        "learning_style": attribute("interests_and_preferences", "learning_style"),
        "work_relationships": attribute("social_and_relational_dynamics", "work_relationships"),
        "online_vs_offline_engagement": attribute(
            "social_and_relational_dynamics", "online_vs_offline_engagement"
        ),
        "work_life_balance": attribute("balance_and_self_management", "work_life_balance"),
        "self_management_digital_behavior": attribute(
            "balance_and_self_management", "self_management_digital_behavior"
        ),
        "decision_making": {
            key: item["value"] for key, item in research["decision_making_and_behavioral_insights"].items()
        },
        "unexpected_behavioral_traits": attribute("other_unique_attributes", "unexpected_behavioral_traits"),
    }


def _profile_tokens(profile: dict[str, Any]) -> set[str]:
    text = canonical(_research_behavior_projection(profile), compact=True).decode("utf-8").casefold()
    tokens = set(re.findall(r"\w+", text, re.UNICODE))
    for run in re.findall(r"[\u3400-\u9fff]+", text):
        tokens.update(f"cjk:{run[index : index + 2]}" for index in range(len(run) - 1))
    return tokens


def _similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_tokens = _profile_tokens(left)
    right_tokens = _profile_tokens(right)
    union = left_tokens | right_tokens
    return len(left_tokens & right_tokens) / len(union) if union else 1.0


def _refill_conflict_projection(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": candidate["candidate_id"],
        "profile_sha256": candidate["profile_sha256"],
        "research_behavior": _research_behavior_projection(candidate["profile"]),
    }


def _refill_conflict_context(
    candidate: dict[str, Any] | None,
    retained: list[dict[str, Any]],
    threshold: float,
) -> list[dict[str, Any]]:
    if candidate is None:
        return []
    conflicts = [(value, _similarity(candidate["profile"], value["profile"])) for value in retained]
    conflicts = [(value, score) for value, score in conflicts if score >= threshold]
    if not conflicts:
        return []
    nearest, _ = min(conflicts, key=lambda item: (-item[1], item[0]["candidate_id"]))
    # One real conflict guides the refill; the final gate still checks every
    # retained profile, so compact feedback does not relax duplicate rejection.
    return [_refill_conflict_projection(nearest)]


def _published_profile_similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    def tokens(profile: dict[str, Any]) -> set[str]:
        copy = {
            section: {
                key: value
                for key, value in values.items()
                if not (section == "Core Identity" and key == "full_name")
            }
            if isinstance(values, dict)
            else values
            for section, values in profile.items()
        }
        text = canonical(copy, compact=True).decode("utf-8").casefold()
        result = set(re.findall(r"\w+", text, re.UNICODE))
        for run in re.findall(r"[\u3400-\u9fff]+", text):
            result.update(f"cjk:{run[index : index + 2]}" for index in range(len(run) - 1))
        return result

    left_tokens = tokens(left)
    right_tokens = tokens(right)
    union = left_tokens | right_tokens
    return len(left_tokens & right_tokens) / len(union) if union else 1.0


def _select_candidate_cohort(
    slots: list[PersonaSlot],
    candidates: dict[str, list[dict[str, Any]]],
    threshold: float,
    *,
    beam_width: int = 256,
) -> list[dict[str, Any]]:
    states: list[tuple[list[dict[str, Any]], float, float]] = [([], 0.0, 0.0)]
    similarity_cache: dict[tuple[str, str], float] = {}

    def similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
        key = tuple(sorted((left["candidate_id"], right["candidate_id"])))
        if key not in similarity_cache:
            similarity_cache[key] = _similarity(left["profile"], right["profile"])
        return similarity_cache[key]

    for slot in slots:
        expanded: list[tuple[list[dict[str, Any]], float, float]] = []
        for selected, maximum, total in states:
            selected_hashes = {candidate["profile_sha256"] for candidate in selected}
            for candidate in candidates[slot.slot_id]:
                if candidate["profile_sha256"] in selected_hashes:
                    continue
                pairwise = [similarity(candidate, existing) for existing in selected]
                candidate_maximum = max(pairwise, default=0.0)
                if candidate_maximum >= threshold:
                    continue
                expanded.append(
                    (
                        [*selected, candidate],
                        max(maximum, candidate_maximum),
                        total + sum(pairwise),
                    )
                )
        if not expanded:
            return states[0][0]
        expanded.sort(
            key=lambda state: (
                state[1],
                state[2],
                tuple(candidate["candidate_id"] for candidate in state[0]),
            )
        )
        states = expanded[:beam_width]
    return states[0][0]


def _surname(name: str) -> str:
    return name.split()[-1]


def _surname_limit(size: int) -> int:
    # Keep the existing >= 80% error threshold for cohorts of at least three.
    return (4 * size - 1) // 5 if size >= 3 else size


def _name_quality_errors(names: list[str]) -> list[str]:
    errors = []
    if len(set(names)) != len(names):
        errors.append("Selected Persona full names must be unique")
    if max(Counter(map(_surname, names)).values(), default=0) > _surname_limit(len(names)):
        errors.append("Synthetic surname concentration is too high for an independently generated cohort")
    return errors


def _cohort_quality_audit(
    plan: CohortPlan,
    slots: list[PersonaSlot],
    selected_candidates: list[dict[str, Any]],
    selected_personas: list[Persona],
    *,
    attempted: int,
    generated: int,
    reviewed: int,
    rejected: int,
    unselected: int,
    generation_attempts: int,
    review_attempts: int,
) -> dict[str, Any]:
    errors = []
    warnings = []
    profiles = [persona.profile for persona in selected_personas]
    core = [profile["Core Identity"] for profile in profiles]
    if len(selected_personas) != plan.sample_size:
        errors.append(f"Selected cohort is incomplete: {len(selected_personas)}/{plan.sample_size}")

    distribution_fields = [
        "age",
        "age_band",
        "gender",
        "nationality",
        "region",
        "current_residence",
        "occupation",
        "research_segment",
    ]
    distribution_fields.extend(
        sorted(
            {
                *(key for slot in slots for key in slot.fixed if key not in distribution_fields),
                *(anchor.field for anchor in plan.diversity_anchors),
            }
        )
    )
    distributions = {}
    for field in distribution_fields:
        if not any(field in item for item in core):
            continue
        distributions[field] = dict(sorted(Counter(str(item.get(field, "")) for item in core).items()))
    names = [item["full_name"] for item in core]
    surnames = [_surname(name) for name in names]
    distributions["surname"] = dict(sorted(Counter(surnames).items()))
    errors.extend(_name_quality_errors(names))

    for field in ("age", "gender", "nationality", "current_residence", "occupation"):
        counts = Counter(str(item.get(field, "")) for item in core)
        if len(core) >= 5 and max(counts.values(), default=0) / len(core) >= 0.8:
            warnings.append(f"Selected cohort has high {field} concentration: {dict(counts)}")
    if len(core) >= 5 and len(distributions["age"]) < 3:
        warnings.append("Selected cohort uses fewer than three distinct exact ages")

    anchor_coverage = {}
    planned_anchor_coverage = {}
    for anchor in plan.diversity_anchors:
        planned_counts = Counter(slot.anchors.get(anchor.field) for slot in slots)
        planned_anchor_coverage[anchor.field] = dict(
            sorted((str(key), value) for key, value in planned_counts.items())
        )
        counts = Counter(item[anchor.field] for item in core if anchor.field in item)
        anchor_coverage[anchor.field] = dict(sorted((str(key), value) for key, value in counts.items()))
        missing = [value for value in anchor.values if counts[value] < anchor.minimum_per_value]
        if missing:
            errors.append(f"Diversity Anchor {anchor.field} is missing required values: {missing}")

    pairwise = []
    for left_index, left in enumerate(selected_candidates):
        for right_index in range(left_index + 1, len(selected_candidates)):
            right = selected_candidates[right_index]
            pairwise.append(
                {
                    "left": f"persona-{left_index + 1:04d}",
                    "right": f"persona-{right_index + 1:04d}",
                    "research_behavior_similarity": round(
                        _similarity(left["profile"], right["profile"]),
                        6,
                    ),
                    "published_profile_similarity": round(
                        _published_profile_similarity(
                            selected_personas[left_index].profile,
                            selected_personas[right_index].profile,
                        ),
                        6,
                    ),
                }
            )

    def similarity_summary(field: str) -> dict[str, float | int]:
        values = sorted(float(item[field]) for item in pairwise)
        if not values:
            return {"pairs": 0, "minimum": 0.0, "mean": 0.0, "p95": 0.0, "maximum": 0.0}
        p95_index = min(len(values) - 1, int((len(values) - 1) * 0.95))
        return {
            "pairs": len(values),
            "minimum": round(values[0], 6),
            "mean": round(sum(values) / len(values), 6),
            "p95": round(values[p95_index], 6),
            "maximum": round(values[-1], 6),
        }

    behavioral_fields = {
        "decision_making_style": (
            "Decision-Making & Behavioral Insights",
            "decision_making_style",
        ),
        "privacy_and_security_concerns": (
            "Decision-Making & Behavioral Insights",
            "privacy_and_security_concerns",
        ),
        "learning_style": ("Interests & Preferences", "learning_style"),
        "workday_habits": ("Daily & Lifestyle Patterns", "workday_habits"),
        "device_usage": ("Digital Behavior & Online Habits", "device_usage"),
    }
    behavioral_repetition = {}
    for field, (section, attribute) in behavioral_fields.items():
        counts = Counter(str(profile[section][attribute]) for profile in profiles)
        repeated_value, repeated_count = counts.most_common(1)[0] if counts else ("", 0)
        behavioral_repetition[field] = {
            "unique_values": len(counts),
            "max_repeat_count": repeated_count,
            "max_repeat_share": round(
                repeated_count / len(profiles) if profiles else 0.0,
                6,
            ),
            "most_repeated_value": repeated_value,
        }

    if reviewed != generated:
        errors.append(f"Every generated candidate must be risk reviewed: {reviewed}/{generated}")

    return {
        "candidate_review": {
            "attempted": attempted,
            "generated": generated,
            "generation_attempts": generation_attempts,
            "risk_reviewed": reviewed,
            "risk_review_attempts": review_attempts,
            "rejected": rejected,
            "eligible_unselected": unselected,
            "selected": len(selected_personas),
        },
        "selection": {
            "algorithm": (
                "single_candidate_retained_slots_with_bounded_refill"
                if plan.candidates_per_slot == 1
                else "bounded_global_beam_search"
            ),
            "beam_width": None if plan.candidates_per_slot == 1 else 256,
            "duplicate_similarity_threshold": plan.duplicate_similarity_threshold,
        },
        "anchor_coverage": anchor_coverage,
        "planned_anchor_coverage": planned_anchor_coverage,
        "profile_distributions": distributions,
        "pairwise_similarity": pairwise,
        "similarity_summary": {
            "research_behavior": similarity_summary("research_behavior_similarity"),
            "published_profile": similarity_summary("published_profile_similarity"),
        },
        "behavioral_repetition": behavioral_repetition,
        "quality_gates": {
            "errors": errors,
            "warnings": warnings,
        },
    }
