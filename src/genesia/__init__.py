"""Genesia synthetic research runtime."""

from .api import analyze, load_task, preflight, prepare, reanswer, run
from .persona_generation import (
    approve_persona_generation,
    confirm_persona_plan,
    generate_personas,
    plan_personas,
)
from .persona_recovery import recover_personas
from .schemas import (
    CohortPlan,
    PersonaCohortApproval,
    PersonaGenerationManifest,
    PersonaGenerationRequest,
    ResearchResult,
    TaskSpec,
)

__all__ = [
    "analyze",
    "approve_persona_generation",
    "confirm_persona_plan",
    "generate_personas",
    "load_task",
    "plan_personas",
    "preflight",
    "prepare",
    "reanswer",
    "recover_personas",
    "run",
    "CohortPlan",
    "PersonaCohortApproval",
    "PersonaGenerationManifest",
    "PersonaGenerationRequest",
    "TaskSpec",
    "ResearchResult",
]
__version__ = "0.2.0"
