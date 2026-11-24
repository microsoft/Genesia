from __future__ import annotations

import re
import unicodedata
from typing import Any

from ..runtime import canonical
from ..schemas import (
    PersonaCandidateResponse,
    PersonaSlot,
)


def _candidate_profile(slot: PersonaSlot, response: PersonaCandidateResponse) -> dict[str, Any]:
    return {
        "segment": slot.segment_id,
        **slot.fixed,
        "diversity_anchors": slot.anchors,
        "research_profile": response.profile.model_dump(mode="json"),
    }


PUBLISHED_DIMENSIONS = {
    "core_identity": "Core Identity",
    "personality_and_cognitive_style": "Psychographics & Personality",
    "digital_behavior_and_online_habits": "Digital Behavior & Online Habits",
    "interests_and_preferences": "Interests & Preferences",
    "economic_and_financial_profile": "Economic & Financial Profile",
    "social_and_relational_dynamics": "Social & Relational Dynamics",
    "daily_and_lifestyle_patterns": "Daily & Lifestyle Patterns",
    "balance_and_self_management": "Health & Well-being",
    "decision_making_and_behavioral_insights": "Decision-Making & Behavioral Insights",
    "other_unique_attributes": "Other Unique Attributes & Contextual Information",
}


def _generated_values_only(value: Any) -> Any:
    if isinstance(value, dict) and {"value", "explanation", "basis"}.issubset(value):
        return value["value"]
    if isinstance(value, dict):
        return {key: _generated_values_only(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_generated_values_only(item) for item in value]
    return value


def _published_persona_profile(candidate_profile: dict[str, Any]) -> dict[str, Any]:
    research_profile = candidate_profile["research_profile"]
    published = {
        target: _generated_values_only(research_profile[source])
        for source, target in PUBLISHED_DIMENSIONS.items()
    }
    personality = published["Psychographics & Personality"]
    personality["personality_traits"] = personality.pop("big_five")
    personality["mbti"] = personality.pop("mbti_type")
    personality["beliefs_and_values"] = personality.pop("values_and_priorities")

    balance = published.pop("Health & Well-being")
    published["Health & Well-being"] = {
        "physical_health": balance["activity_level"],
        "mental_health": balance["stress_management"],
        "work_life_balance": balance["work_life_balance"],
        "health_related_digital_behavior": balance["self_management_digital_behavior"],
    }

    core = published["Core Identity"]
    core.setdefault("research_segment", candidate_profile["segment"])
    for key, value in candidate_profile["diversity_anchors"].items():
        core.setdefault(key, value)
    for key, value in candidate_profile.items():
        if key not in {"segment", "diversity_anchors", "research_profile"}:
            core.setdefault(key, value)
    return published


def _validate_candidate_response(response: PersonaCandidateResponse) -> None:
    if not response.profile.core_identity.full_name.value.strip():
        raise ValueError("Generated full_name must not be blank")
    prohibited_phrases = (
        "ignore previous",
        "ignore all previous",
        "system message",
        "developer message",
        "follow these instructions",
        "reveal the prompt",
        "you are chatgpt",
        "<script",
    )
    sensitive_keys = (
        "medical",
        "diagnosis",
        "religion",
        "political",
        "race",
        "ethnicity",
        "sexual",
    )
    profile = response.profile.model_dump(mode="json")
    if len(canonical(profile, compact=True)) > 60000:
        raise ValueError("Generated profile exceeds the allowed total size")

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if {"value", "explanation", "basis"}.issubset(value) and (
                value["basis"] == "unknown" or str(value["value"]).strip().casefold() == "unknown"
            ):
                raise ValueError("Archetype generation requires concrete values; use synthetic_assumption")
            for key, item in value.items():
                normalized_key = str(key).casefold()
                if any(term in normalized_key for term in sensitive_keys):
                    raise ValueError(f"Generated profile key is not allowed: {key}")
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, str):
            normalized = re.sub(
                r"[^a-z0-9]+",
                " ",
                unicodedata.normalize("NFKC", value).casefold(),
            ).strip()
            if any(ord(character) < 32 and character not in "\n\r\t" for character in value):
                raise ValueError("Generated profile contains control characters")
            if re.search(r"https?://|www\.|[\w.+-]+@[\w.-]+\.[a-z]{2,}", value, re.I):
                raise ValueError("Generated profile contains a URL or email address")
            if re.search(r"(?:\+\d{1,3}[ .-]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}", value):
                raise ValueError("Generated profile contains a phone number")
            if re.search(
                r"\b\d{1,6}\s+[a-z][a-z .'-]{2,}\s(?:street|st|road|rd|avenue|ave|boulevard|blvd|lane|ln|drive|dr)\b",
                value,
                re.I,
            ):
                raise ValueError("Generated profile contains a street address")
            if (
                any(
                    re.sub(r"[^a-z0-9]+", " ", phrase.casefold()).strip() in normalized
                    for phrase in prohibited_phrases
                    if not phrase.startswith("<")
                )
                or "<script" in value.casefold()
            ):
                raise ValueError("Generated profile contains prompt-like instructions")

    visit(profile)


def _normalized(value: Any) -> str:
    if isinstance(value, list):
        value = " ".join(str(item) for item in value)
    return re.sub(
        r"[^a-z0-9]+",
        " ",
        unicodedata.normalize("NFKC", str(value)).casefold(),
    ).strip()


def _generated_attribute(profile: dict[str, Any], path: tuple[str, ...]) -> dict[str, Any]:
    value: Any = profile
    for part in path:
        value = value[part]
    return value


DIRECT_SLOT_FIELDS = {
    "age": ("core_identity", "age"),
    "gender": ("core_identity", "gender"),
    "nationality": ("core_identity", "nationality"),
    "current_residence": ("core_identity", "current_residence"),
    "education": ("core_identity", "education", "degree"),
    "degree": ("core_identity", "education", "degree"),
    "role": ("core_identity", "occupation"),
    "occupation": ("core_identity", "occupation"),
    "company": ("core_identity", "company"),
    "skin_color": ("core_identity", "physical_attributes", "skin_color"),
}


DIRECT_ANCHOR_FIELDS: dict[str, tuple[str, ...]] = {}


def _age_in_band(age: str, band: str) -> bool:
    try:
        value = int(age)
    except (TypeError, ValueError):
        return False
    if match := re.fullmatch(r"(\d+)\s*-\s*(\d+)", band):
        return int(match.group(1)) <= value <= int(match.group(2))
    if match := re.fullmatch(r"<\s*(\d+)", band):
        return value < int(match.group(1))
    if match := re.fullmatch(r"(\d+)\s*\+", band):
        return value >= int(match.group(1))
    raise ValueError(f"Invalid age_band constraint: {band}")


def _representative_age_for_band(band: str) -> str:
    if match := re.fullmatch(r"(\d+)\s*-\s*(\d+)", band):
        lower = int(match.group(1))
        upper = int(match.group(2))
        return str((lower + upper) // 2)
    if match := re.fullmatch(r"<\s*(\d+)", band):
        return str(int(match.group(1)) - 1)
    if match := re.fullmatch(r"(\d+)\s*\+", band):
        return match.group(1)
    raise ValueError(f"Invalid age_band constraint: {band}")


def _normalize_candidate_for_slot(
    response: PersonaCandidateResponse,
    slot: PersonaSlot,
) -> PersonaCandidateResponse:
    profile = response.profile.model_dump(mode="json")
    for fixed_key, path in DIRECT_SLOT_FIELDS.items():
        if fixed_key not in slot.fixed:
            continue
        attribute = _generated_attribute(profile, path)
        attribute.update(
            value=slot.fixed[fixed_key],
            explanation=f"Fixed by cohort slot: {fixed_key}={slot.fixed[fixed_key]}.",
            basis="fixed",
        )
    if "age_band" in slot.fixed:
        age = _generated_attribute(profile, ("core_identity", "age"))
        if _normalized(age["value"]) == _normalized(slot.fixed["age_band"]):
            age["value"] = _representative_age_for_band(slot.fixed["age_band"])
        if not _age_in_band(age["value"], slot.fixed["age_band"]):
            raise ValueError(
                f"Generated age {age['value']} is outside fixed age_band {slot.fixed['age_band']}"
            )
        if "age" not in slot.fixed:
            age.update(
                explanation=(f"Synthetic exact age constrained by fixed age_band={slot.fixed['age_band']}."),
                basis="synthetic_assumption",
            )
    direct_fixed_paths = {path for fixed_key, path in DIRECT_SLOT_FIELDS.items() if fixed_key in slot.fixed}
    anchor_evidence = [
        (_normalized(key), _normalized(value), DIRECT_ANCHOR_FIELDS.get(key))
        for key, value in slot.anchors.items()
    ]

    def contains_phrase(text: str, phrase: str) -> bool:
        return bool(phrase) and f" {phrase} " in f" {text} "

    def normalize_basis(value: Any, path: tuple[str, ...] = ()) -> None:
        if isinstance(value, dict) and {"value", "explanation", "basis"}.issubset(value):
            evidence = _normalized([value["value"], value["explanation"]])
            fixed_supported = path in direct_fixed_paths
            supported_anchors = [
                (key, anchor_value)
                for key, anchor_value, supported_path in anchor_evidence
                if path == supported_path
                if contains_phrase(evidence, key) and contains_phrase(evidence, anchor_value)
            ]
            if value["basis"] == "fixed" and not fixed_supported:
                value.update(
                    explanation="Synthetic assumption; no slot constraint fixes this attribute.",
                    basis="synthetic_assumption",
                )
            elif value["basis"] == "anchor":
                if supported_anchors:
                    key, anchor_value = supported_anchors[0]
                    value["explanation"] = f"Supported by Diversity Anchor: {key}={anchor_value}."
                else:
                    value.update(
                        explanation=("Independent synthetic assumption; not derived from another attribute."),
                        basis="synthetic_assumption",
                    )
            elif value["basis"] == "synthetic_assumption":
                value["explanation"] = "Independent synthetic assumption; not derived from another attribute."
            elif value["basis"] == "research_request":
                value.update(
                    explanation="Independent synthetic assumption; not derived from another attribute.",
                    basis="synthetic_assumption",
                )
            return
        if isinstance(value, dict):
            for key, item in value.items():
                normalize_basis(item, (*path, key))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                normalize_basis(item, (*path, str(index)))

    normalize_basis(profile)
    return PersonaCandidateResponse.model_validate({"profile": profile})


def _validate_candidate_for_slot(
    response: PersonaCandidateResponse,
    slot: PersonaSlot,
) -> None:
    _validate_candidate_response(response)
    profile = response.profile.model_dump(mode="json")
    for fixed_key, path in DIRECT_SLOT_FIELDS.items():
        if fixed_key not in slot.fixed:
            continue
        attribute = _generated_attribute(profile, path)
        if attribute["basis"] != "fixed" or _normalized(attribute["value"]) != _normalized(
            slot.fixed[fixed_key]
        ):
            raise ValueError(f"Generated {'.'.join(path)} contradicts fixed {fixed_key}")
    if "age_band" in slot.fixed:
        age = _generated_attribute(profile, ("core_identity", "age"))
        expected_basis = "fixed" if "age" in slot.fixed else "synthetic_assumption"
        if age["basis"] != expected_basis or not _age_in_band(age["value"], slot.fixed["age_band"]):
            raise ValueError("Generated age contradicts fixed age_band")

    anchor_evidence = [
        (_normalized(key), _normalized(value), DIRECT_ANCHOR_FIELDS.get(key))
        for key, value in slot.anchors.items()
    ]
    direct_fixed_paths = {path for fixed_key, path in DIRECT_SLOT_FIELDS.items() if fixed_key in slot.fixed}

    def contains_phrase(text: str, phrase: str) -> bool:
        return bool(phrase) and f" {phrase} " in f" {text} "

    def validate_basis(value: Any, path: tuple[str, ...] = ()) -> None:
        if isinstance(value, dict) and {"value", "explanation", "basis"}.issubset(value):
            evidence = _normalized([value["value"], value["explanation"]])
            if value["basis"] == "fixed" and path not in direct_fixed_paths:
                raise ValueError("Generated fixed basis is not an exact fixed slot field")
            if value["basis"] == "anchor" and not any(
                contains_phrase(evidence, key)
                and contains_phrase(evidence, anchor_value)
                and path == supported_path
                for key, anchor_value, supported_path in anchor_evidence
            ):
                raise ValueError("Generated anchor basis is not the anchor's direct schema field")
            if value["basis"] == "unknown" or _normalized(value["value"]) == "unknown":
                raise ValueError("Archetype generation requires a concrete value for every attribute")
            return
        if isinstance(value, dict):
            for key, item in value.items():
                validate_basis(item, (*path, key))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                validate_basis(item, (*path, str(index)))

    validate_basis(profile)
