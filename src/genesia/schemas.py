from __future__ import annotations

import re
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


ProfileText = Annotated[str, Field(min_length=1, max_length=500)]
BehaviorKey = Annotated[str, Field(min_length=1, max_length=80)]
PlanKey = Annotated[str, Field(min_length=1, max_length=80)]
PlanValue = Annotated[str, Field(min_length=1, max_length=300)]


class Persona(Contract):
    id: str = Field(min_length=1)
    profile: dict[str, Any]


class CohortSpec(Contract):
    source: str
    ids: list[str] = Field(default_factory=list)
    size: int = Field(default=2, ge=1, le=1000)
    seed: int = 42
    filters: dict[str, str] = Field(default_factory=dict)


class PersonaSegment(Contract):
    id: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=500)
    quota: int = Field(ge=1, le=1000)
    required: bool = True
    constraints: dict[PlanKey, PlanValue] = Field(default_factory=dict, max_length=16)


class PersonaQuota(Contract):
    field: str = Field(min_length=1, max_length=80)
    policy: Literal["hard", "soft"] = "soft"
    counts: dict[PlanValue, int] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def valid_counts(self):
        if any(not value.strip() for value in self.counts):
            raise ValueError("Quota values must be non-empty")
        if any(count < 0 for count in self.counts.values()) or not any(self.counts.values()):
            raise ValueError("Quota counts must be non-negative with at least one requested Persona")
        return self


class DiversityAnchor(Contract):
    field: str = Field(min_length=1, max_length=80)
    values: list[PlanValue] = Field(min_length=2, max_length=20)
    policy: Literal["hard", "soft"] = "soft"
    scope: Literal["cohort"] = "cohort"
    minimum_per_value: int = Field(default=1, ge=1, le=1000)
    rationale: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def unique_values(self):
        if len(self.values) != len(set(self.values)) or any(not value.strip() for value in self.values):
            raise ValueError("Diversity Anchor values must be unique and non-empty")
        return self


class PersonaGenerationRequest(Contract):
    description: str = Field(min_length=1, max_length=4000)
    sample_size: int = Field(default=5, ge=1, le=1000)
    seed: int = 42
    candidates_per_slot: int = Field(default=1, ge=1, le=5)
    duplicate_similarity_threshold: float = Field(default=0.88, ge=0.5, le=1)
    eligibility: dict[PlanKey, PlanValue] = Field(default_factory=dict, max_length=16)
    segments: list[PersonaSegment] = Field(default_factory=list)
    quotas: list[PersonaQuota] = Field(default_factory=list)
    diversity_anchors: list[DiversityAnchor] = Field(default_factory=list)
    assumptions: list[ProfileText] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def coherent_request(self):
        if self.segments and sum(segment.quota for segment in self.segments) != self.sample_size:
            raise ValueError("Segment quotas must sum to sample_size")
        for items, label, key in (
            (self.segments, "Segment", lambda item: item.id),
            (self.quotas, "Quota", lambda item: item.field),
            (self.diversity_anchors, "Diversity Anchor", lambda item: item.field),
        ):
            values = [key(item) for item in items]
            if len(values) != len(set(values)):
                raise ValueError(f"{label} identifiers must be unique")
        for quota in self.quotas:
            if sum(quota.counts.values()) != self.sample_size:
                raise ValueError(f"Quota counts for {quota.field} must sum to sample_size")
        for anchor in self.diversity_anchors:
            if anchor.policy == "hard" and len(anchor.values) * anchor.minimum_per_value > self.sample_size:
                raise ValueError(f"Hard Diversity Anchor {anchor.field} exceeds sample_size")
        return self


class PersonaPlanProposal(Contract):
    eligibility: dict[PlanKey, PlanValue] = Field(default_factory=dict, max_length=16)
    segments: list[PersonaSegment] = Field(min_length=1)
    quotas: list[PersonaQuota] = Field(default_factory=list)
    diversity_anchors: list[DiversityAnchor] = Field(default_factory=list, max_length=4)
    assumptions: list[ProfileText] = Field(default_factory=list, max_length=16)
    limitations: list[ProfileText] = Field(default_factory=list, max_length=16)


class CohortPlan(PersonaGenerationRequest):
    version: Literal[1] = 1
    id: str = Field(min_length=1, max_length=100)
    status: Literal["draft", "confirmed"] = "draft"
    limitations: list[ProfileText] = Field(default_factory=list, max_length=16)
    plan_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class PersonaSlot(Contract):
    slot_id: str = Field(min_length=1)
    segment_id: str = Field(min_length=1)
    fixed: dict[str, str] = Field(default_factory=dict)
    anchors: dict[str, str] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)


class GeneratedAttribute(Contract):
    value: str = Field(min_length=1, max_length=500)
    explanation: str = Field(min_length=1, max_length=300)
    basis: Literal[
        "fixed",
        "anchor",
        "research_request",
        "synthetic_assumption",
        "unknown",
    ]


class GeneratedTrait(GeneratedAttribute):
    pass


class GeneratedEducation(Contract):
    degree: GeneratedAttribute
    major: GeneratedAttribute
    institution: GeneratedAttribute


class GeneratedPhysicalAttributes(Contract):
    height: GeneratedAttribute
    body_shape: GeneratedAttribute
    hairstyle: GeneratedAttribute
    skin_color: GeneratedAttribute
    facial_features: GeneratedAttribute
    dress_style: GeneratedAttribute


class GeneratedCoreIdentity(Contract):
    full_name: GeneratedAttribute
    age: GeneratedAttribute
    gender: GeneratedAttribute
    nationality: GeneratedAttribute
    current_residence: GeneratedAttribute
    education: GeneratedEducation
    occupation: GeneratedAttribute
    company: GeneratedAttribute
    physical_attributes: GeneratedPhysicalAttributes


class GeneratedBigFive(Contract):
    openness: GeneratedTrait
    conscientiousness: GeneratedTrait
    extraversion: GeneratedTrait
    agreeableness: GeneratedTrait
    neuroticism: GeneratedTrait


class GeneratedPersonalityAndCognitiveStyle(Contract):
    big_five: GeneratedBigFive
    mbti_type: GeneratedAttribute
    values_and_priorities: GeneratedAttribute
    motivations: GeneratedAttribute
    cognitive_style: GeneratedAttribute


class GeneratedDigitalBehaviorAndOnlineHabits(Contract):
    search_patterns: GeneratedAttribute
    ad_interactions: GeneratedAttribute
    preferred_content_sources: GeneratedAttribute
    social_media_usage: GeneratedAttribute
    ecommerce_behavior: GeneratedAttribute
    device_usage: GeneratedAttribute
    subscriptions: GeneratedAttribute
    communication_style: GeneratedAttribute


class GeneratedInterestsAndPreferences(Contract):
    professional_interests: GeneratedAttribute
    hobbies: GeneratedAttribute
    entertainment_preferences: GeneratedAttribute
    content_consumption: GeneratedAttribute
    learning_style: GeneratedAttribute


class GeneratedEconomicAndFinancialProfile(Contract):
    spending_patterns: GeneratedAttribute
    income_level: GeneratedAttribute
    investment_habits: GeneratedAttribute
    financial_tools: GeneratedAttribute


class GeneratedSocialAndRelationalDynamics(Contract):
    work_relationships: GeneratedAttribute
    family_structure: GeneratedAttribute
    friendship_circle: GeneratedAttribute
    community_involvement: GeneratedAttribute
    online_vs_offline_engagement: GeneratedAttribute


class GeneratedDailyAndLifestylePatterns(Contract):
    morning_routine: GeneratedAttribute
    workday_habits: GeneratedAttribute
    evening_and_leisure: GeneratedAttribute
    weekend_activities: GeneratedAttribute
    sleep_schedule: GeneratedAttribute


class GeneratedBalanceAndSelfManagement(Contract):
    activity_level: GeneratedAttribute
    stress_management: GeneratedAttribute
    work_life_balance: GeneratedAttribute
    self_management_digital_behavior: GeneratedAttribute


class GeneratedDecisionMakingAndBehavioralInsights(Contract):
    decision_making_style: GeneratedAttribute
    brand_loyalty: GeneratedAttribute
    influence_factors: GeneratedAttribute
    tech_adoption: GeneratedAttribute
    privacy_and_security_concerns: GeneratedAttribute


class GeneratedOtherUniqueAttributes(Contract):
    cultural_and_linguistic_background: GeneratedAttribute
    travel_habits: GeneratedAttribute
    personal_projects: GeneratedAttribute
    unexpected_behavioral_traits: GeneratedAttribute


class GeneratedResearchProfile(Contract):
    core_identity: GeneratedCoreIdentity
    personality_and_cognitive_style: GeneratedPersonalityAndCognitiveStyle
    digital_behavior_and_online_habits: GeneratedDigitalBehaviorAndOnlineHabits
    interests_and_preferences: GeneratedInterestsAndPreferences
    economic_and_financial_profile: GeneratedEconomicAndFinancialProfile
    social_and_relational_dynamics: GeneratedSocialAndRelationalDynamics
    daily_and_lifestyle_patterns: GeneratedDailyAndLifestylePatterns
    balance_and_self_management: GeneratedBalanceAndSelfManagement
    decision_making_and_behavioral_insights: GeneratedDecisionMakingAndBehavioralInsights
    other_unique_attributes: GeneratedOtherUniqueAttributes


class PersonaCandidateResponse(Contract):
    profile: GeneratedResearchProfile


class PersonaRiskReview(Contract):
    severity: Literal["none", "low", "medium", "high"] = "none"
    risks: list[
        Literal[
            "contradiction",
            "sensitive_inference",
            "stereotype",
            "prompt_like_content",
            "unsupported_detail",
        ]
    ] = Field(default_factory=list)
    explanation: str = ""


class PersonaCohortRiskReview(Contract):
    severity: Literal["none", "low", "medium", "high"] = "none"
    risks: list[
        Literal[
            "anchor_conflict",
            "template_repetition",
            "insufficient_behavioral_diversity",
            "demographic_behavior_coupling",
            "cohort_realism",
        ]
    ] = Field(default_factory=list)
    explanation: str = ""


class PersonaSlotGenerationCheckpoint(Contract):
    candidate_id: str = Field(min_length=1)
    slot_id: str = Field(min_length=1)
    candidate_index: int = Field(ge=0)
    stage: Literal["generated", "reviewed", "failed"]
    candidate: dict[str, Any] | None = None
    issue: str | None = None
    generation_attempts: int = Field(default=0, ge=0)
    review_attempts: int = Field(default=0, ge=0)
    generation_request_refs: list[str] = Field(default_factory=list)
    review_request_refs: list[str] = Field(default_factory=list)
    refill_reason: str | None = None

    @model_validator(mode="after")
    def checkpoint_stage_is_coherent(self):
        if self.stage in {"generated", "reviewed"} and self.candidate is None:
            raise ValueError(f"{self.stage} checkpoint requires candidate data")
        if self.stage == "failed" and not self.issue:
            raise ValueError("Failed checkpoint requires an issue")
        return self


class PersonaGenerationCheckpoint(Contract):
    version: Literal[1] = 1
    plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    slots: dict[str, PersonaSlotGenerationCheckpoint] = Field(default_factory=dict)


class PersonaGenerationManifest(Contract):
    version: Literal[1] = 1
    generation_id: str = Field(min_length=1)
    status: Literal["completed", "partial", "failed"]
    plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    personas_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    selected_persona_ids: list[str] = Field(default_factory=list)
    required_full_cohort: bool = True
    requires_human_approval: bool = False
    attempted_candidate_count: int = Field(default=0, ge=0)
    candidate_count: int = Field(default=0, ge=0)
    reviewed_candidate_count: int = Field(default=0, ge=0)
    rejected_candidate_count: int = Field(default=0, ge=0)
    unselected_candidate_count: int = Field(default=0, ge=0)
    artifact_hashes: dict[str, str] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)


class PersonaCohortApproval(Contract):
    version: Literal[1] = 1
    status: Literal["approved"] = "approved"
    generation_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    personas_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    approved_persona_ids: list[str] = Field(min_length=1)
    approved_at: str = Field(min_length=1)


class SourceSpec(Contract):
    kind: Literal["document", "image", "recording", "graph", "video", "figma", "cards"]
    path: str
    trace_path: str | None = None
    sample_seconds: float = Field(default=3.0, gt=0)
    max_frames: int = Field(default=24, ge=2, le=120)
    figma_nodes: list[str] = Field(default_factory=list)
    token_env: str = "FIGMA_ACCESS_TOKEN"

    @model_validator(mode="after")
    def source_options(self):
        if self.kind == "figma" and not self.figma_nodes:
            raise ValueError("Figma requires explicit node IDs to bound exports")
        if self.trace_path and self.kind not in {"video", "recording"}:
            raise ValueError("Trace alignment requires video or recording input")
        return self


class PrototypeScope(Contract):
    scope: str = Field(min_length=1)
    known_limitations: list[str] = Field(default_factory=list)


class EnvironmentSpec(Contract):
    mode: Literal["auto", "survey", "scenario", "image_direct", "captured_graph", "walkthrough", "live"]
    sources: list[SourceSpec] = Field(default_factory=list)
    start_url: str | None = None
    max_steps: int = Field(default=12, ge=1, le=100)
    min_actions_before_stop: int = Field(default=0, ge=0, le=99)
    required_url_fragments_before_stop: list[str] = Field(default_factory=list)
    headless: bool = True
    width: int = Field(default=1440, ge=640, le=3840)
    height: int = Field(default=900, ge=480, le=2160)
    screenshot_width: int | None = Field(default=None, ge=320, le=3840)
    screenshot_quality: int = Field(default=85, ge=1, le=100)
    handoff_urls: list[str] = Field(default_factory=list)
    candidate_labels: list[str] = Field(default_factory=list)
    fidelity_review: bool = False
    curated_path: list[str] = Field(default_factory=list)
    prototype: PrototypeScope | None = None

    @model_validator(mode="after")
    def check_input(self):
        if self.min_actions_before_stop >= self.max_steps:
            raise ValueError("min_actions_before_stop must leave one step available for stop")
        if self.mode == "survey":
            if (
                self.sources
                or self.start_url
                or self.min_actions_before_stop
                or self.required_url_fragments_before_stop
            ):
                raise ValueError("Survey mode does not use environment sources, URLs or action floors")
        elif self.mode == "live":
            url = urlsplit(self.start_url or "")
            if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password:
                raise ValueError("Live requires an HTTP(S) start_url without credentials")
            if self.screenshot_width and self.screenshot_width > self.width:
                raise ValueError("screenshot_width cannot exceed the live viewport width")
            start_origin = (url.scheme, url.hostname, url.port or (443 if url.scheme == "https" else 80))
            handoffs = [urlsplit(item) for item in self.handoff_urls]
            if len(self.handoff_urls) != len(set(self.handoff_urls)) or any(
                item.scheme not in {"http", "https"}
                or not item.hostname
                or item.username
                or item.password
                or (item.scheme, item.hostname, item.port or (443 if item.scheme == "https" else 80))
                != start_origin
                for item in handoffs
            ):
                raise ValueError("Live handoff URLs must be unique HTTP(S) URLs on the start origin")
            if self.handoff_urls and not self.candidate_labels:
                raise ValueError("Live handoff_urls require explicit candidate_labels in URL order")
            if self.candidate_labels and (
                len(self.candidate_labels) != len(self.handoff_urls) + 1
                or len(self.candidate_labels) != len(set(self.candidate_labels))
            ):
                raise ValueError(
                    "Live candidate_labels must be unique and align with start_url plus handoff_urls"
                )
            fragments = self.required_url_fragments_before_stop
            if len(fragments) != len(set(fragments)) or any(
                not fragment.startswith("/") or "://" in fragment or fragment.strip() != fragment
                for fragment in fragments
            ):
                raise ValueError("Required URL fragments must be unique relative path fragments")
        elif not self.sources:
            raise ValueError("Non-live environments require sources")
        elif self.candidate_labels:
            raise ValueError("candidate_labels are limited to live environments")
        elif self.required_url_fragments_before_stop:
            raise ValueError("Required URL fragments are limited to live environments")
        return self


class Question(Contract):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    candidate: str | None = Field(default=None, min_length=1)
    explain: bool = False
    purpose: Literal["experience", "context", "reflection"] = "experience"
    feedback_role: (
        Literal[
            "context",
            "overall",
            "journey",
            "strength",
            "friction",
            "comparison",
            "preference",
            "design",
            "suggestion",
            "verdict",
        ]
        | None
    ) = None
    kind: Literal["text", "single", "multiple", "likert"] = "text"
    options: list[str] = Field(default_factory=list)
    rows: list[str] = Field(default_factory=list)
    required: bool = True
    objective_ids: list[str] = Field(default_factory=list)
    criterion_ids: list[str] = Field(default_factory=list)
    ask_if: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_options(self):
        if len(self.options) != len(set(self.options)) or len(self.rows) != len(set(self.rows)):
            raise ValueError("Question options and rows must be unique")
        if self.kind != "text" and not self.options:
            raise ValueError("Choice and Likert questions require options")
        if self.kind == "likert" and not self.rows:
            raise ValueError("Likert questions require rows")
        return self


class MethodSpec(Contract):
    id: str = Field(min_length=1)
    kind: Literal["interview", "survey", "design_review", "task_outcome_review"]
    questions: list[Question] = Field(min_length=1)
    batch_size: int = Field(default=20, ge=1, le=100)
    max_images: int = Field(default=8, ge=0, le=64)
    evidence_mode: Literal["sampled", "complete"] = "sampled"
    max_followups: int = Field(default=0, ge=0, le=8)

    @model_validator(mode="after")
    def check_ids(self):
        if len({question.id for question in self.questions}) != len(self.questions):
            raise ValueError("Question IDs must be unique within a method")
        previous = set()
        for question in self.questions:
            if not set(question.ask_if).issubset(previous):
                raise ValueError("Conditional questions can reference only earlier question IDs")
            previous.add(question.id)
        if self.max_followups and self.kind != "interview":
            raise ValueError("Dynamic follow-ups are limited to interviews")
        return self


class ResearchObjective(Contract):
    id: str
    description: str = Field(min_length=1)
    evidence_terms: list[str] = Field(default_factory=list)


class EvaluationCriterion(Contract):
    id: str
    description: str = Field(min_length=1)
    anchors: list[str] = Field(min_length=2)


def numeric_bucket_bounds(label: str) -> tuple[int | None, int | None]:
    if match := re.fullmatch(r"<\s*(-?\d+)", label):
        return None, int(match.group(1)) - 1
    if match := re.fullmatch(r"(-?\d+)\s*-\s*(-?\d+)", label):
        return int(match.group(1)), int(match.group(2))
    if match := re.fullmatch(r"(-?\d+)\s*\+", label):
        return int(match.group(1)), None
    raise ValueError(f"Invalid numeric segment bucket: {label}")


class SegmentSpec(Contract):
    source: str = Field(min_length=1)
    buckets: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("buckets", mode="before")
    @classmethod
    def strip_buckets(cls, value: Any) -> Any:
        if not isinstance(value, list):
            return value
        return [item.strip() if isinstance(item, str) else item for item in value]

    @model_validator(mode="after")
    def valid_buckets(self):
        if not self.source.strip() or any(not part.strip() for part in self.source.split(".")):
            raise ValueError("Segment source must be a non-empty profile path")
        if not self.buckets:
            return self
        if len(self.buckets) != len(set(self.buckets)):
            raise ValueError("Segment buckets must be unique")
        bounds = [numeric_bucket_bounds(label) for label in self.buckets]
        if bounds[0][0] is not None or bounds[-1][1] is not None:
            raise ValueError("Segment buckets must start with <N and end with N+")
        for index, (lower, upper) in enumerate(bounds):
            if lower is not None and upper is not None and lower > upper:
                raise ValueError("Segment bucket lower bound must not exceed its upper bound")
            if index:
                previous_upper = bounds[index - 1][1]
                if previous_upper is None or lower is None or lower != previous_upper + 1:
                    raise ValueError("Segment buckets must be ordered, contiguous and non-overlapping")
        return self

    def label(self, value: Any) -> str:
        if not self.buckets:
            return (
                str(value) if isinstance(value, (str, int, float, bool)) and str(value).strip() else "Unknown"
            )
        if isinstance(value, bool) or not isinstance(value, int):
            return "Unassigned"
        for label in self.buckets:
            lower, upper = numeric_bucket_bounds(label)
            if (lower is None or value >= lower) and (upper is None or value <= upper):
                return label
        return "Unassigned"


class StudySpec(Contract):
    objectives: list[ResearchObjective] = Field(default_factory=list)
    criteria: list[EvaluationCriterion] = Field(default_factory=list)
    min_personas: int = Field(default=1, ge=1)
    sample_requirements: dict[str, list[str]] = Field(default_factory=dict)
    segment_fields: list[str] = Field(default_factory=list)
    segments: dict[str, SegmentSpec] = Field(default_factory=dict)
    segment_combinations: dict[str, list[str]] = Field(default_factory=dict, max_length=8)
    review: bool = False
    block_on_errors: bool = True

    @model_validator(mode="after")
    def unique_ids(self):
        for items in (self.objectives, self.criteria):
            if len(items) != len({item.id for item in items}):
                raise ValueError("Study IDs must be unique within each category")
        if any(not segment_id.strip() or segment_id != segment_id.strip() for segment_id in self.segments):
            raise ValueError("Segment IDs must be non-empty")
        if set(self.segment_fields).intersection(self.segments):
            raise ValueError("Segment IDs must not duplicate segment_fields")
        for name, dimensions in self.segment_combinations.items():
            if not name.strip() or name in self.segments or name in self.segment_fields:
                raise ValueError("Combination IDs must be non-empty and distinct from segment IDs")
            if not 2 <= len(dimensions) <= 3 or len(set(dimensions)) != len(dimensions):
                raise ValueError("A segment combination requires two or three distinct dimensions")
            if not set(dimensions).issubset(self.segments):
                raise ValueError("Segment combinations must reference configured segments")
        return self


class ReviewIssue(Contract):
    category: Literal["scope", "evidence", "sample", "task", "questions", "fidelity"]
    severity: Literal["info", "warning", "error"]
    message: str = Field(min_length=1)
    suggestion: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)


class ReviewAssessment(Contract):
    summary: str
    issues: list[ReviewIssue]


class FidelityReviewIssue(ReviewIssue):
    category: Literal["fidelity"] = "fidelity"


class FidelityReviewAssessment(Contract):
    summary: str
    issues: list[FidelityReviewIssue]


class FollowupDecision(Contract):
    ask: bool
    parent_question_id: str | None = None
    text: str = ""
    reason: str


class ModelSpec(Contract):
    provider: Literal["openai_compatible"] = "openai_compatible"
    base_url: str = "https://api.openai.com/v1"
    model: str = Field(min_length=1)
    api_key_env: str | None = Field(default="OPENAI_API_KEY", pattern=r"^[A-Z][A-Z0-9_]*$")
    timeout_seconds: int = Field(default=120, ge=1, le=600)
    max_tokens: int = Field(default=4096, ge=128, le=16384)
    temperature: float | None = Field(default=None, ge=0, le=2)
    token_limit_field: Literal["max_completion_tokens", "max_tokens"] = "max_completion_tokens"
    attempts: int = Field(default=2, ge=1, le=3)

    @model_validator(mode="after")
    def provider_endpoint(self):
        url = urlsplit(self.base_url)
        local = url.hostname in {"localhost", "127.0.0.1", "::1"}
        if not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("Model base_url must be an HTTP(S) endpoint without credentials or query data")
        if url.scheme != "https" and not (url.scheme == "http" and local):
            raise ValueError("Remote OpenAI-compatible APIs require HTTPS")
        if not local and not self.api_key_env:
            raise ValueError("Remote OpenAI-compatible APIs require api_key_env")
        return self


class Permissions(Contract):
    send_persona: bool = False
    send_materials: bool = False
    send_screenshots: bool = False
    fetch_figma: bool = False


class BudgetProtection(Contract):
    research_fraction: float = Field(default=0.3, gt=0, lt=1)
    analysis_fraction: float = Field(default=0.25, gt=0, lt=1)

    @model_validator(mode="after")
    def leave_experience_budget(self):
        if self.research_fraction + self.analysis_fraction >= 1:
            raise ValueError("Protected fractions must leave budget for experience")
        return self


class BudgetSpec(Contract):
    max_calls: int = Field(default=80, ge=1)
    max_tokens: int = Field(default=250000, ge=1)
    max_seconds: int = Field(default=1800, ge=1)
    protection: BudgetProtection | None = None


class ExecutionSpec(Contract):
    max_concurrent_personas: int = Field(default=1, ge=1, le=32)
    max_concurrent_model_calls: int = Field(default=4, ge=1, le=32)


class InsightSpec(Contract):
    language: Literal["en", "zh-CN"] = "en"
    context_window: int = Field(default=128000, ge=8192)
    input_budget_ratio: float = Field(default=0.6, gt=0, le=0.8)
    chunk_target_tokens: int = Field(default=30000, ge=1024)
    max_findings: int = Field(default=8, ge=1, le=32)
    focus: list[str] = Field(default_factory=list, max_length=16)


class TaskSpec(Contract):
    schema_version: Literal["0.1", "0.2"] = "0.2"
    goal: str = Field(min_length=1)
    cohort: CohortSpec
    environment: EnvironmentSpec
    methods: list[MethodSpec] = Field(min_length=1)
    model: ModelSpec
    permissions: Permissions = Field(default_factory=Permissions)
    budget: BudgetSpec = Field(default_factory=BudgetSpec)
    output_dir: str = "runs"
    study: StudySpec = Field(default_factory=StudySpec)
    execution: ExecutionSpec = Field(default_factory=ExecutionSpec)
    insight: InsightSpec = Field(default_factory=InsightSpec)

    @model_validator(mode="after")
    def unique_methods(self):
        if len({method.id for method in self.methods}) != len(self.methods):
            raise ValueError("Method IDs must be unique")
        if self.environment.mode == "survey" and any(method.kind != "survey" for method in self.methods):
            raise ValueError("Survey mode accepts only survey methods")
        objectives = {objective.id for objective in self.study.objectives}
        criteria = {criterion.id for criterion in self.study.criteria}
        for method in self.methods:
            for question in method.questions:
                if not set(question.objective_ids).issubset(objectives) or not set(
                    question.criterion_ids
                ).issubset(criteria):
                    raise ValueError("Question references an unknown objective or criterion")
        return self


class EvidenceRef(Contract):
    id: str
    sha256: str
    path: str
    kind: str
    persona_id: str | None = None
    session_id: str | None = None


class Target(Contract):
    id: str
    name: str
    description: str = ""
    disabled: bool = False
    x: float | None = None
    y: float | None = None
    fingerprint: dict[str, str] = Field(default_factory=dict)
    actions: list[Literal["click", "right_click", "type", "select"]] = Field(
        default_factory=lambda: ["click"]
    )


class Observation(Contract):
    id: str
    text: str
    targets: list[Target] = Field(default_factory=list)
    image_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    url: str = ""
    mode: str
    state_id: str = ""
    card_ids: list[str] = Field(default_factory=list)
    scroll: dict[str, int | bool] = Field(default_factory=dict)


class ActionReflection(Contract):
    interest: str = Field(min_length=1, max_length=400)
    observed_effect: str = Field(min_length=1, max_length=600)
    judgment: str = Field(max_length=600, default="")
    remaining_interest: str = Field(max_length=400, default="")
    effect_status: Literal["visible_change", "no_visible_change", "known_unavailable", "uncertain"] = (
        "uncertain"
    )


class Action(Contract):
    action: Literal[
        "click", "right_click", "type", "select", "press", "back", "scroll", "advance", "wait", "stop"
    ]
    target_id: str | None = None
    value: str | None = None
    intent: str = Field(min_length=1)
    expected_result: str = ""
    outcome: Literal["completed", "abandoned"] | None = None
    reflection: ActionReflection | None = None

    @model_validator(mode="after")
    def check_action(self):
        if self.action in {"click", "right_click", "type", "select"} and not self.target_id:
            raise ValueError("Targeted actions require target_id")
        if self.action in {"type", "select", "press", "scroll"} and self.value is None:
            raise ValueError("This action requires value")
        if self.action == "scroll" and self.value not in {"up", "down"}:
            raise ValueError("Scroll value must be up or down")
        if self.action in {"press", "back", "scroll", "advance", "wait", "stop"} and self.target_id:
            raise ValueError("Untargeted actions cannot include target_id")
        if self.action == "stop" and not self.outcome:
            raise ValueError("Stop requires completed or abandoned outcome")
        return self


class ExecutionResult(Contract):
    success: bool
    message: str


class Step(Contract):
    number: int
    observation: Observation
    action: Action
    result: ExecutionResult


class SessionIntent(Contract):
    goal: str = Field(min_length=1)
    preferences: str = Field(min_length=1)
    completion_standard: str = Field(min_length=1)
    likely_approach: str = ""
    patience_and_help_seeking: str = ""


class ExperienceNote(Contract):
    step: int
    before_observation_id: str
    after_observation_id: str
    before_evidence_refs: list[str]
    after_evidence_refs: list[str]
    reflection: ActionReflection


class Episode(Contract):
    session_id: str
    persona: Persona
    goal: str
    mode: str
    phase: Literal["experience", "research", "finished", "failed"] = "experience"
    intent: SessionIntent | None = None
    steps: list[Step] = Field(default_factory=list)
    final_observation: Observation | None = None
    outcome: str = "running"
    outcome_basis: str = ""
    coverage: dict[str, Any] = Field(default_factory=dict)
    prototype: PrototypeScope | None = None
    candidate_labels: list[str] = Field(default_factory=list)
    experience_notes: list[ExperienceNote] = Field(default_factory=list)


class UIControl(Contract):
    label: str
    status: Literal["verified", "disabled", "visible-unverified", "visual-only"] = "visible-unverified"


class UICard(Contract):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    source_ids: list[str] = Field(min_length=1)
    image_refs: list[str] = Field(default_factory=list)
    controls: list[UIControl] = Field(default_factory=list)
    sequence: int = Field(ge=0)
    timestamp_seconds: float | None = Field(default=None, ge=0)
    provenance: Literal["design", "recorded", "supplied"] = "supplied"
    trace_events: list[dict[str, Any]] = Field(default_factory=list)


class VisualControl(UIControl):
    status: Literal["disabled", "visible-unverified", "visual-only"] = "visible-unverified"


class CardDescription(Contract):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    controls: list[VisualControl] = Field(default_factory=list)


class StateBinding(Contract):
    id: str
    title: str
    card_ids: list[str] = Field(min_length=1)


class CardBindings(Contract):
    states: list[StateBinding] = Field(min_length=1)

    def validate_cards(self, cards: list[UICard]):
        ids = [card_id for state in self.states for card_id in state.card_ids]
        if len(ids) != len(set(ids)) or set(ids) != {card.id for card in cards}:
            raise ValueError("Every UI card must be bound exactly once")
        if len({state.id for state in self.states}) != len(self.states):
            raise ValueError("State IDs must be unique")


class GraphNode(Contract):
    id: str
    text: str = Field(min_length=1)
    source_ids: list[str] = Field(min_length=1)
    card_ids: list[str] = Field(default_factory=list)


class GraphEdge(Contract):
    id: str
    source: str
    target: str
    label: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)
    basis: Literal["unspecified", "declared", "recorded_order"] = "unspecified"


class Graph(Contract):
    start: str
    nodes: list[GraphNode] = Field(min_length=1)
    edges: list[GraphEdge] = Field(default_factory=list)
    cards: list[UICard] = Field(default_factory=list)
    observed_path: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_graph(self):
        ids = {node.id for node in self.nodes}
        if len(ids) != len(self.nodes) or self.start not in ids:
            raise ValueError("Graph start and node IDs must be valid and unique")
        if len({edge.id for edge in self.edges}) != len(self.edges):
            raise ValueError("Graph edge IDs must be unique")
        if any(edge.source not in ids or edge.target not in ids for edge in self.edges):
            raise ValueError("Graph edge references an unknown node")
        if self.cards:
            card_ids = [card.id for card in self.cards]
            bound = [card_id for node in self.nodes for card_id in node.card_ids]
            if len(card_ids) != len(set(card_ids)) or sorted(bound) != sorted(card_ids):
                raise ValueError("Graph cards must have unique IDs and exactly-once bindings")
            if any(not node.card_ids for node in self.nodes):
                raise ValueError("Every card-backed state needs evidence")
        if self.observed_path:
            if self.observed_path[0] != self.start or any(state not in ids for state in self.observed_path):
                raise ValueError("Observed path must start at graph entry and reference known nodes")
            edges = {(edge.source, edge.target) for edge in self.edges}
            if any(pair not in edges for pair in zip(self.observed_path, self.observed_path[1:])):
                raise ValueError("Observed path contains unsupported transitions")
        return self


class ContextItem(Contract):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    source_ids: list[str] = Field(min_length=1)
    image_refs: list[str] = Field(default_factory=list)
    sequence: int = Field(ge=0)


class MaterialCitation(Contract):
    source_id: str = Field(min_length=1)
    quote: str = ""


class AssessedUIState(Contract):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    evidence: list[MaterialCitation] = Field(
        min_length=1,
        description="Use each source_id at most once in this state's evidence list. "
        "For a text source, select one contiguous verbatim supporting quote.",
    )
    controls: list[VisualControl] = Field(default_factory=list)


class AssessedTransition(Contract):
    source: str
    target: str
    label: str = Field(min_length=1)
    evidence: list[MaterialCitation] = Field(
        min_length=1,
        description="Use each source_id at most once in this transition's evidence list. "
        "Each citation must quote one contiguous verbatim text passage supporting the transition.",
    )


class EnvironmentAssessment(Contract):
    summary: str = Field(min_length=1)
    states: list[AssessedUIState] = Field(default_factory=list, max_length=120)
    transitions: list[AssessedTransition] = Field(default_factory=list, max_length=240)
    background: list[MaterialCitation] = Field(
        default_factory=list,
        max_length=120,
        description="Verbatim text passages describing shared product context, assumptions or material "
        "limitations, including passages from documents also cited by states or transitions. "
        "Exclude page-specific content and navigation. Use separate contiguous quotes when needed; "
        "a source_id may recur with different quotes, but identical citations must not repeat.",
    )
    issues: list[str] = Field(default_factory=list)

    def validate_sources(self, sources: list[dict]):
        by_id = {source["id"]: source for source in sources}
        state_ids = {state.id for state in self.states}
        if len(state_ids) != len(self.states):
            raise ValueError("Readiness state IDs must be unique")

        def validate_citations(citations, *, text_only=False, unique_sources=True):
            keys = [
                citation.source_id if unique_sources else (citation.source_id, citation.quote)
                for citation in citations
            ]
            if len(set(keys)) != len(keys):
                raise ValueError("Duplicate source citations")
            for citation in citations:
                source = by_id.get(citation.source_id)
                if source is None:
                    raise ValueError("Readiness cites unknown source evidence")
                if source["kind"] == "image":
                    if text_only:
                        raise ValueError(
                            "Background and declared transitions need explicit text evidence, not image order"
                        )
                elif not citation.quote.strip() or citation.quote not in source["text"]:
                    raise ValueError("Readiness quote must match source text exactly")

        image_states = set()
        for state in self.states:
            validate_citations(state.evidence)
            for citation in state.evidence:
                if by_id[citation.source_id]["kind"] == "image":
                    if citation.source_id in image_states:
                        raise ValueError("An image observation must belong to only one stable state")
                    image_states.add(citation.source_id)
        for transition in self.transitions:
            if transition.source not in state_ids or transition.target not in state_ids:
                raise ValueError("Transition references unknown readiness state")
            validate_citations(transition.evidence, text_only=True)
        validate_citations(self.background, text_only=True, unique_sources=False)


class EnvironmentBuildResult(Contract):
    level: Literal["context", "cards", "graph"]
    context: list[ContextItem] = Field(default_factory=list)
    cards: list[UICard] = Field(default_factory=list)
    graph: Graph | None = None
    issues: list[str] = Field(default_factory=list)
    assessment: EnvironmentAssessment | None = None

    @model_validator(mode="after")
    def level_matches_artifacts(self):
        if self.level == "context" and (not self.context or self.cards or self.graph):
            raise ValueError("Context build requires context items only")
        if self.level == "cards" and (not self.cards or self.graph):
            raise ValueError("Cards build requires cards without a graph")
        if self.level == "graph" and (self.graph is None or self.cards):
            raise ValueError("Graph build requires a graph without top-level cards")
        return self


class Answer(Contract):
    question_id: str
    value: str | list[str] | dict[str, str] | None
    reason: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    basis: Literal["experience", "profile", "automation", "not_observed", "skipped"] = "experience"


class Answers(Contract):
    answers: list[Answer]


class MethodResponse(Contract):
    session_id: str
    persona_id: str
    method_id: str
    kind: str
    valid: bool
    answers: list[Answer] = Field(default_factory=list)
    error: str | None = None
    evidence_ref: str | None = None
    followups: list[dict[str, Any]] = Field(default_factory=list)
    batches: list[dict[str, Any]] = Field(default_factory=list)


class Quote(Contract):
    answer_id: str
    text: str = Field(min_length=1)


class Finding(Contract):
    text: str = Field(min_length=1)
    title: str = ""
    candidate: str | None = Field(default=None, min_length=1)
    participants: list[str] = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)
    id: str = ""
    answer_ids: list[str] = Field(default_factory=list)
    quotes: list[Quote] = Field(default_factory=list)
    claim_type: Literal["persona_report", "observed", "interpretation"] = "persona_report"
    category: Literal["experience", "preference", "opportunity"] = "experience"
    feedback_type: Literal["positive", "friction", "preference", "suggestion", "mixed", "neutral"] = "neutral"
    journey_stage: Literal[
        "entry", "discovery", "exploration", "comparison", "decision", "overall", "other"
    ] = "overall"
    interpretation: str = ""
    design_implication: str = ""
    uncertainty: str = ""
    evidence_details: list[str] = Field(default_factory=list)
    counter_answer_ids: list[str] = Field(default_factory=list)
    scope_status: Literal["in_scope", "uncertain", "prototype_limit"] = "in_scope"


class Recommendation(Contract):
    action: str = Field(min_length=1)
    kind: Literal["investigate", "design_change", "enhancement"] = "investigate"
    rationale: str = Field(min_length=1)
    finding_ids: list[str] = Field(min_length=1)
    severity: int = Field(ge=1, le=5)
    effort: int = Field(ge=1, le=5)
    confidence: float = Field(ge=0, le=1)
    priority_score: float = 0


class Synthesis(Contract):
    summary: str
    findings: list[Finding]
    limitations: str
    recommendations: list[Recommendation] = Field(default_factory=list)
    segment_differences: list[Finding] = Field(default_factory=list)
    summary_points: list[str] = Field(default_factory=list, max_length=5)
    recommendation_order: Literal["score", "decision"] = "score"


class ReportModel(Contract):
    title: str = "Genesia Research Report"
    goal: str = ""
    input_mode: str = ""
    methods: list[dict[str, Any]] = Field(default_factory=list)
    objectives: list[dict[str, Any]] = Field(default_factory=list)
    analysis: dict[str, Any] = Field(default_factory=dict)


class ResearchResult(Contract):
    schema_version: Literal["0.1", "0.2"] = "0.2"
    simulated: Literal[True] = True
    run_id: str
    status: Literal["completed", "partial", "failed"]
    episodes: list[Episode]
    responses: list[MethodResponse]
    metrics: dict[str, Any]
    synthesis: Synthesis | None = None
    errors: list[str] = Field(default_factory=list)
    output_dir: str
    study_review: dict[str, Any] = Field(default_factory=dict)
    report: ReportModel | None = None
