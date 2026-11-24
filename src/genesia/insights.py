"""Compatibility exports for deterministic insight-report helpers."""

from .insight_support import (
    FEEDBACK_ROLES,
    analysis_input,
    normalize_candidate,
    synthesis_schema,
    validate_citations,
)

__all__ = [
    "FEEDBACK_ROLES",
    "analysis_input",
    "normalize_candidate",
    "synthesis_schema",
    "validate_citations",
]
