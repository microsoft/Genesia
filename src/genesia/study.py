"""Research readiness and model-assisted source-fidelity review."""

import json
import re

from .runtime import EvidenceStore, ModelGateway, write_json
from .schemas import (
    EnvironmentBuildResult,
    FidelityReviewAssessment,
    Graph,
    Persona,
    ReviewAssessment,
    ReviewIssue,
    StudySpec,
    TaskSpec,
)


def attribute(persona: Persona, field: str):
    value = persona.profile
    for part in field.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    return value


def segment_labels(study: StudySpec, persona: Persona) -> dict[str, str]:
    labels = {field: str(attribute(persona, field)) for field in study.segment_fields}
    labels.update(
        {name: spec.label(attribute(persona, spec.source)) for name, spec in study.segments.items()}
    )
    labels.update(
        {
            name: json.dumps([labels[dimension] for dimension in dimensions], ensure_ascii=False)
            for name, dimensions in study.segment_combinations.items()
        }
    )
    return labels


def readiness(
    task: TaskSpec,
    people: list[Persona],
    graph: Graph | None = None,
    *,
    environment_build: EnvironmentBuildResult | None = None,
) -> dict:
    issues = []

    def issue(category, severity, message, suggestion):
        issues.append(
            ReviewIssue(
                category=category, severity=severity, message=message, suggestion=suggestion
            ).model_dump()
        )

    if not task.study.objectives:
        issue(
            "scope",
            "warning",
            "No explicit research objectives",
            "Declare objectives and map questions to them",
        )
    mapped = {
        objective
        for method in task.methods
        for question in method.questions
        for objective in question.objective_ids
    }
    missing = {objective.id for objective in task.study.objectives} - mapped
    if missing:
        issue(
            "questions",
            "error",
            f"Objectives without questions: {sorted(missing)}",
            "Map at least one question per objective",
        )
    criteria = {
        criterion
        for method in task.methods
        for question in method.questions
        for criterion in question.criterion_ids
    }
    if any(criterion.id not in criteria for criterion in task.study.criteria):
        issue(
            "questions",
            "warning",
            "Evaluation criteria not mapped to questions",
            "Attach criterion_ids to evaluation questions",
        )
    if len(people) < task.study.min_personas:
        issue(
            "sample",
            "error",
            "Selected cohort is below study min_personas",
            "Increase the cohort or revise the study requirement",
        )
    for field, requested in task.study.sample_requirements.items():
        present = {str(attribute(person, field)) for person in people}
        absent = set(requested) - present
        if absent:
            issue(
                "sample",
                "error",
                f"Missing requested segments for {field}: {sorted(absent)}",
                "Adjust Persona filters or provide profiles for these segments",
            )
    for segment_id, segment in task.study.segments.items():
        if not segment.buckets:
            if people and all(attribute(person, segment.source) is None for person in people):
                issue(
                    "sample",
                    "error",
                    f"Segment {segment_id} is missing for the entire cohort",
                    f"Check profile path {segment.source}",
                )
            continue
        invalid = [
            person.id
            for person in people
            if isinstance((value := attribute(person, segment.source)), bool) or not isinstance(value, int)
        ]
        if invalid:
            issue(
                "sample",
                "error",
                f"Integer segment {segment_id} has missing or non-integer values for: {invalid}",
                f"Provide integer {segment.source} values for every selected Persona",
            )
    for name in task.study.segment_combinations:
        groups = {segment_labels(task.study, person)[name] for person in people}
        if len(groups) > 100:
            issue(
                "sample",
                "error",
                f"Segment combination {name} exceeds 100 observed groups",
                "Use fewer dimensions or broader buckets",
            )
    question_text = [task.goal] + [question.text for method in task.methods for question in method.questions]
    for text in question_text:
        if re.search(
            r"\b(obviously|surely|don't you agree|how much do you love|you must like)\b", text, re.I
        ):
            issue(
                "task",
                "warning",
                "Potentially leading task/question language",
                "Use a neutral goal or question; review wording before running",
            )
            break
    coverage = {}
    if graph or environment_build:
        texts = [node.text for node in graph.nodes] if graph else []
        if environment_build:
            texts.extend(item.text for item in environment_build.context)
            texts.extend(card.description for card in environment_build.cards)
        corpus = " ".join(texts).casefold()
        for objective in task.study.objectives:
            hits = [term for term in objective.evidence_terms if term.casefold() in corpus]
            coverage[objective.id] = {
                "terms": objective.evidence_terms,
                "matched": hits,
                "basis": "lexical indicator, not semantic proof",
            }
            if objective.evidence_terms and not hits:
                issue(
                    "evidence",
                    "warning",
                    f"No evidence term matched objective {objective.id}",
                    "Add relevant materials or narrow the objective",
                )
    experience_calls = 1 if task.environment.mode == "survey" else 2
    minimum = len(people) * (experience_calls + sum(1 + method.max_followups for method in task.methods)) + 1
    if task.budget.max_calls < minimum:
        issue(
            "task",
            "warning",
            "Call budget is below the approximate minimum study workload",
            "Increase max_calls or reduce methods/personas",
        )
    return {
        "ok": not any(item["severity"] == "error" for item in issues),
        "issues": issues,
        "evidence_coverage": coverage,
        "sample_size": len(people),
        "limitations": "Rules detect structural gaps; they do not certify study validity or representativeness.",
    }


def model_review(
    task: TaskSpec,
    people: list[Persona],
    graph: Graph | None,
    gateway: ModelGateway,
    store: EvidenceStore,
    *,
    fidelity=False,
    environment_build: EnvironmentBuildResult | None = None,
) -> ReviewAssessment:
    refs = {ref for node in graph.nodes for ref in node.source_ids} if graph else set()
    if environment_build:
        refs.update(ref for item in environment_build.context for ref in item.source_ids)
        refs.update(ref for card in environment_build.cards for ref in card.source_ids)
    images = [ref for ref in sorted(refs) if store.refs[ref].kind == "source_image"]

    def validate(value):
        if any(not set(issue.evidence_refs).issubset(refs) for issue in value.issues):
            raise ValueError("Review references nonexistent source evidence")
        if fidelity and any(issue.category != "fidelity" for issue in value.issues):
            raise ValueError("Fidelity review issues must use category=fidelity")
        sample_errors = [
            issue
            for issue in readiness(task, people)["issues"]
            if issue["category"] == "sample" and issue["severity"] == "error"
        ]
        if (
            not fidelity
            and not sample_errors
            and any(issue.category == "sample" and issue.severity == "error" for issue in value.issues)
        ):
            raise ValueError(
                "Deterministic cohort requirements passed. A single recording is shared evidence, not a single participant. Sample suitability uncertainty is warning, not a contradictory count error."
            )

    if fidelity:
        payload = {
            "graph": graph.model_dump() if graph else None,
            "instruction": "Compare the compiled Context, Cards or Graph to supplied sources. Identify invented transitions, "
            "over-merged errors/success, unsupported claims or omissions. Cite source IDs. "
            "Every issue must use category=fidelity. Cite only source IDs listed in available_evidence_ids; "
            "when the list is empty, every evidence_refs list must be empty. "
            "This is a model-assisted fidelity review, not an independent oracle.",
        }
    else:
        payload = {
            "goal": task.goal,
            "study": task.study.model_dump(),
            "methods": [method.model_dump() for method in task.methods],
            "sample": {
                "selected_count": len(people),
                "minimum": task.study.min_personas,
                "requested": task.study.sample_requirements,
                "participants": [
                    {
                        "id": person.id,
                        "segments": {
                            **{field: attribute(person, field) for field in task.study.segment_fields},
                            **{
                                segment_id: attribute(person, segment.source)
                                for segment_id, segment in task.study.segments.items()
                            },
                        },
                    }
                    for person in people
                ],
                "rule_check": readiness(task, people),
            },
            "graph": graph.model_dump() if graph else None,
            "available_evidence_ids": sorted(refs),
            "instruction": "Review research readiness, not persona feedback. Check scope, neutral questions, "
            "whether supplied evidence can answer objectives, rubric and sample coverage. "
            "Report actionable opportunities/gaps. No population-validity claims. "
            "Selected Personas are separate from recorded actors. Multiple Personas independently review "
            "the same recording; do not demand separate source recordings for each participant. "
            "Use deterministic cohort counts as authoritative. Sample suitability uncertainty is warning. "
            "Live UI is not yet observed: mark evidence readiness unknown, do not invent it. "
            "Error only for clear contradictions; uncertainty should be warning. Cite only IDs listed "
            "in available_evidence_ids. When available_evidence_ids is empty, every evidence_refs list "
            "must be empty.",
        }
    payload["environment_build"] = (
        environment_build.model_dump(exclude={"graph"}) if environment_build else None
    )
    payload["available_evidence_ids"] = sorted(refs)
    payload["sources"] = [
        {"id": ref, "text": store.path(ref).read_text("utf-8")}
        for ref in sorted(refs)
        if store.refs[ref].kind != "source_image"
    ]
    result = gateway.complete(
        "fidelity_review" if fidelity else "study_review",
        payload,
        FidelityReviewAssessment if fidelity else ReviewAssessment,
        images=images,
        validate=validate,
    )
    return ReviewAssessment.model_validate(result.model_dump())


def review_study(task, people, graph, gateway, store, *, environment_build=None):
    report = readiness(task, people, graph, environment_build=environment_build)
    if task.study.review:
        report["model_assessment"] = model_review(
            task, people, graph, gateway, store, environment_build=environment_build
        ).model_dump()
    if task.environment.fidelity_review and (graph or environment_build):
        report["fidelity_assessment"] = model_review(
            task, people, graph, gateway, store, fidelity=True, environment_build=environment_build
        ).model_dump()
    assessments = [report.get(key, {}) for key in ("model_assessment", "fidelity_assessment")]
    report["ok"] = report["ok"] and not any(
        issue["severity"] == "error" for item in assessments for issue in item.get("issues", [])
    )
    write_json(store.root / "study_review.json", report)
    store.json(report, "study_review")
    return report
