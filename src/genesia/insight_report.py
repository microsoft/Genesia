"""Lean staged insight reports over immutable Persona answers."""

from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from threading import RLock, local
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, create_model

from .insight_support import (
    FEEDBACK_ROLES,
    analysis_input,
    normalize_candidate,
    synthesis_schema,
    validate_citations,
)
from .runtime import canonical, digest, model_prompt, write_json
from .schemas import Contract, Finding, Recommendation, Synthesis


class ReportFindingDraft(Contract):
    id: str = Field(min_length=1)
    source_finding_ids: list[str] = Field(min_length=1)
    text: str = Field(min_length=1)
    title: str = Field(default="", max_length=120)
    candidate: str | None = None
    category: Literal["experience", "preference", "opportunity"]
    feedback_type: Literal["positive", "friction", "preference", "suggestion", "mixed", "neutral"]
    journey_stage: Literal[
        "entry", "discovery", "exploration", "comparison", "decision", "overall", "other"
    ] = "overall"
    interpretation: str = ""
    design_implication: str = ""
    uncertainty: str = ""


class ReportRecommendationDraft(Contract):
    action: str = Field(min_length=1)
    kind: Literal["investigate", "design_change", "enhancement"] = "investigate"
    rationale: str = Field(min_length=1)
    finding_ids: list[str] = Field(min_length=1)
    severity: int = Field(ge=1, le=5)
    effort: int = Field(ge=1, le=5)
    confidence: float = Field(ge=0, le=1)


def report_draft_schema(
    max_findings: int, *, recommendations: bool, feedback_types: tuple[str, ...] | None = None
):
    finding = (
        create_model(
            "SourceBoundReportFinding",
            __base__=ReportFindingDraft,
            feedback_type=(Literal.__getitem__(feedback_types), ...),
        )
        if feedback_types
        else ReportFindingDraft
    )
    return create_model(
        "StagedInsightReport",
        __base__=Contract,
        summary=(str, ...),
        summary_points=(list[str], Field(default_factory=list, max_length=5)),
        findings=(list[finding], Field(max_length=max_findings)),
        limitations=(str, ...),
        recommendations=(
            list[ReportRecommendationDraft],
            Field(default_factory=list, max_length=6 if recommendations else 0),
        ),
    )


def _question_definition(task, row):
    question = row["question"]
    return {
        "method_id": row["method_id"],
        "question_id": row["question_id"],
        **{
            key: question.get(key)
            for key in (
                "text",
                "kind",
                "purpose",
                "feedback_role",
                "candidate",
                "options",
                "objective_ids",
                "criterion_ids",
            )
            if question.get(key) not in (None, [], "")
        },
    }


def _question_statistics(source, method_id, question_id):
    for item in source["statistics"]["questions"]:
        if item["method_id"] == method_id and item["question_id"] == question_id:
            return {
                key: item[key]
                for key in (
                    "kind",
                    "n_valid_responses",
                    "n_answered",
                    "n_not_observed",
                    "n_automation",
                    "n_skipped",
                    "n_missing_or_invalid",
                    "counts",
                    "percent_of_answered",
                    "matrix_counts",
                    "segments",
                )
                if key in item and item[key] not in ({}, [])
            }
    return {}


def _study_brief(task):
    return {
        "objectives": [item.model_dump() for item in task.study.objectives],
        "criteria": [item.model_dump() for item in task.study.criteria],
        "report_focus": list(task.insight.focus),
        "configured_dimensions": {
            "segment_fields": list(task.study.segment_fields),
            "segments": {key: value.model_dump() for key, value in task.study.segments.items()},
            "segment_combinations": dict(task.study.segment_combinations),
        },
    }


def _question_payload(task, source, selected):
    first = selected[0]
    context = {item["persona_id"]: item for item in source["participant_context"]}
    definition = _question_definition(task, first)
    rows = [
        {
            "answer_id": row["answer_id"],
            "persona_id": row["persona_id"],
            "question_id": row["question_id"],
            "method_id": row["method_id"],
            "question": {
                key: row["question"].get(key)
                for key in ("purpose", "feedback_role", "candidate")
                if row["question"].get(key) is not None
            },
            "value": row["value"],
            "reason": row["reason"],
            "basis": row["basis"],
            "status": row["status"],
            "response_ref": row["response_ref"],
            "segments": context.get(row["persona_id"], {}).get("segments", {}),
        }
        for row in selected
    ]
    language = (
        "Write the analysis fields in Simplified Chinese."
        if task.insight.language == "zh-CN"
        else "Write the analysis fields in English."
    )
    return {
        "output_stage": "question_insights",
        "goal": source["goal"],
        "study": _study_brief(task),
        "prototype": source["prototype"],
        "question_definitions": [definition],
        "descriptive_statistics": {
            "basis": source["statistics"]["basis"],
            "questions": [
                {
                    "method_id": first["method_id"],
                    "question_id": first["question_id"],
                    **_question_statistics(source, first["method_id"], first["question_id"]),
                }
            ],
        },
        "rows": rows,
        "outcomes": [],
        "summaries": [],
        "instruction": (
            f"{language} Analyze this exact question using every supplied original answer and reason. "
            "Return at most three non-overlapping, decision-relevant findings. Cite all supporting and "
            "counter answer IDs, including meaningful disagreement. Keep candidate-specific feedback "
            "attached to its candidate. Treat profile dimensions as context, not causes. "
            "Use the research objectives and report focus to select findings, not mention frequency "
            "alone. Review supplied segment memberships descriptively; preserve a decision-relevant "
            "minority view without manufacturing group differences. "
            "Distinguish reported experience, preference, and suggestion. "
            "Do not infer an executed action from a stated intention. Do not turn an untried path, prototype "
            "limit, automation issue, or wish into a demonstrated product defect. Known prototype "
            "boundaries are limitations, not product findings or recommendations. Distinguish missing "
            "study evidence from a demonstrated product need. Do not write a final "
            "report, enumerate Personas, or repeat the question. Recommendations must be empty."
        ),
    }


def _source_packet(finding, question_ids):
    return {
        "id": finding.id,
        "text": finding.text,
        "title": finding.title,
        "candidate": finding.candidate,
        "category": finding.category,
        "feedback_type": finding.feedback_type,
        "journey_stage": finding.journey_stage,
        "interpretation": finding.interpretation,
        "design_implication": finding.design_implication,
        "uncertainty": finding.uncertainty,
        "scope_status": finding.scope_status,
        "answer_ids": list(finding.answer_ids),
        "counter_answer_ids": list(finding.counter_answer_ids),
        "question_ids": list(question_ids),
    }


def _exploration_coverage(task, episodes):
    labels = task.environment.candidate_labels or list(
        dict.fromkeys(
            question.candidate
            for method in task.methods
            for question in method.questions
            if question.candidate
        )
    )
    urls = [task.environment.start_url, *task.environment.handoff_urls]
    candidates = [
        {
            "label": labels[index] if index < len(labels) else f"Candidate {index + 1}",
            "base": url.split("#", 1)[0],
        }
        for index, url in enumerate(urls)
        if url
    ]
    route_people = defaultdict(set)
    exposed = defaultdict(set)
    step_counts = []
    for episode in episodes:
        step_counts.append(len(episode.steps))
        observations = [
            *(step.observation for step in episode.steps),
            *([episode.final_observation] if episode.final_observation else []),
        ]
        for observation in observations:
            if observation is None or not observation.url:
                continue
            matches = [candidate for candidate in candidates if observation.url.startswith(candidate["base"])]
            if not matches:
                continue
            candidate = max(matches, key=lambda item: len(item["base"]))
            exposed[candidate["label"]].add(episode.persona.id)
            route = (
                observation.url.split("#", 1)[1].split("?", 1)[0]
                if "#" in observation.url
                else urlsplit(observation.url).path
            )
            route_people[(candidate["label"], route)].add(episode.persona.id)
    return {
        "participants": len(episodes),
        "steps": {
            "minimum": min(step_counts) if step_counts else 0,
            "maximum": max(step_counts) if step_counts else 0,
            "average": round(sum(step_counts) / len(step_counts), 1) if step_counts else 0,
        },
        "candidate_exposure": {label: len(people) for label, people in sorted(exposed.items())},
        "routes": [
            {"candidate": candidate, "route": route, "personas": len(people)}
            for (candidate, route), people in sorted(
                route_people.items(), key=lambda item: (item[0][0], -len(item[1]), item[0][1])
            )
        ],
    }


def _segment_counts(source):
    counts = defaultdict(lambda: defaultdict(int))
    for participant in source["participant_context"]:
        for dimension, label in participant.get("segments", {}).items():
            counts[dimension][label] += 1
    return {dimension: dict(sorted(labels.items())) for dimension, labels in sorted(counts.items())}


def _execution_summary(source):
    controls = defaultdict(set)
    successful = defaultdict(set)
    orders = defaultdict(set)
    for outcome in source.get("outcomes", []):
        person = outcome["persona_id"]
        first_steps = {}
        for action in outcome["executed_actions"]:
            if action["action"] != "click" or not action.get("target"):
                continue
            target = action["target"]
            controls[target].add(person)
            if action.get("execution_success"):
                successful[target].add(person)
                first_steps.setdefault(target, action["step"])
        for before, step in first_steps.items():
            for after, later in first_steps.items():
                if step < later:
                    orders[(before, after)].add(person)
    ranked_controls = sorted(controls, key=lambda target: (-len(controls[target]), target))
    ranked_orders = sorted(orders, key=lambda pair: (-len(orders[pair]), pair))
    return {
        "basis": "First successful control clicks, not backend success, satisfaction or complete task validation.",
        "n_personas": len(source.get("outcomes", [])),
        "controls": [
            {
                "target": target,
                "attempted_personas": len(controls[target]),
                "successful_personas": len(successful[target]),
            }
            for target in ranked_controls[:64]
        ],
        "first_click_order": [
            {"before": before, "after": after, "personas": len(orders[(before, after)])}
            for before, after in ranked_orders[:64]
        ],
        "omitted_controls": max(0, len(ranked_controls) - 64),
        "omitted_order_pairs": max(0, len(ranked_orders) - 64),
    }


def _composition_payload(task, source, packets, *, final):
    language = (
        "Write the report fields in Simplified Chinese."
        if task.insight.language == "zh-CN"
        else "Write the report fields in English."
    )
    answer_index = {row["answer_id"]: row for row in source.get("rows", []) if row["status"] == "answered"}
    enriched_packets = []
    cited_ids = set()
    for packet in packets:
        support = packet.get("answer_ids", [])
        cited_ids.update(support)
        cited_ids.update(packet.get("counter_answer_ids", []))
        roles = {answer_index[ref]["question"].get("feedback_role") for ref in support}
        allowed = ["neutral"] + [
            kind for kind, required_roles in FEEDBACK_ROLES.items() if roles.intersection(required_roles)
        ]
        enriched_packets.append({**packet, "allowed_feedback_types": allowed})
    relevant_questions = {
        (answer_index[ref]["method_id"], answer_index[ref]["question_id"]) for ref in cited_ids
    }
    return {
        "output_stage": "insight_report" if final else "insight_reduce",
        "goal": source["goal"],
        "study": _study_brief(task),
        "prototype": source["prototype"],
        "source_findings": enriched_packets,
        "answer_owners": {
            row["answer_id"]: row["persona_id"]
            for row in source.get("rows", [])
            if row["status"] == "answered" and (final or row["answer_id"] in cited_ids)
        },
        "execution_summary": _execution_summary(source) if final else {},
        "segment_counts": _segment_counts(source) if "participant_context" in source else {},
        "descriptive_statistics": {
            "basis": source["statistics"]["basis"],
            "questions": [
                {
                    key: item[key]
                    for key in (
                        "method_id",
                        "question_id",
                        "kind",
                        "n_valid_responses",
                        "n_answered",
                        "n_not_observed",
                        "n_automation",
                        "n_skipped",
                        "n_missing_or_invalid",
                        "counts",
                        "percent_of_answered",
                        "matrix_counts",
                        "segments",
                    )
                    if key in item and item[key] not in ({}, [])
                }
                for item in source["statistics"]["questions"]
                if final or (item["method_id"], item["question_id"]) in relevant_questions
            ],
        },
        "instruction": (
            f"{language} Build one coherent research report, not separate executive and detailed reports. "
            "First derive findings across questions in relation to the research objectives and report "
            "focus, including configured segments. Then derive and prioritize actions from those same "
            "findings. Only then distill the summary. Do not rank solely by mention frequency. "
            "A consequential minority or segment finding can lead the report; do not invent demographic "
            "differences or causal explanations. Keep significant segment names and actual group sizes "
            "in the relevant finding. Merge only genuinely overlapping findings. Preserve a distinctive "
            "view when it changes the decision, design implication, recommendation, or critical "
            "uncertainty. Every output finding must cite one or more source_finding_ids; do not cite "
            "raw answer IDs and do not introduce factual clauses absent from those source findings "
            "or supplied execution_summary. A finding's feedback_type must be allowed by at least one "
            "of its cited source findings, using allowed_feedback_types. Words such as preference or "
            "suggestion in prose do not authorize those feedback types without a matching source question. "
            "Use neutral for descriptive findings when appropriate. Never invent supporting source IDs. "
            "Execution records can verify control attempts and their "
            "sequence, not backend success or satisfaction. Never infer execution from intention. "
            "Do not turn a merged finding's union of supporting answer IDs into the number of people "
            "reporting each individual issue. Preserve the source claim's denominator and counterevidence. "
            "When one question was split, reconcile all its chunks using answer_owners to count "
            "distinct Personas. A chunk count is not a whole-cohort count. Do not narrate chunk "
            "sizes or processing mechanics in findings. If a combined thematic count cannot be "
            "established, omit the number rather than copying one chunk's count. Check behavioral "
            "counts and order claims against execution_summary, including participants missing "
            "from a chunk's source finding. Execution counts refer to first successful clicks, "
            "not substantive review, priority or external completion. Omitted controls or order "
            "pairs are unreported, not evidence of absence. "
            "Keep strengths, friction, tradeoffs, counterevidence, and prototype or order limitations. "
            "Known prototype boundaries are limitations, not product findings or recommendations. "
            "Distinguish missing study evidence from a demonstrated product need. "
            "For each named candidate with source findings, retain at least one candidate-specific "
            "finding using only that candidate's source IDs. Keep controls requiring different design "
            "actions separate: do not collapse Auto behavior, pointer labeling, color identification, "
            "background/2.5D meaning, taskbar discoverability, or dashboard density into one generic issue. "
            "Use a short concrete title for each finding and natural paragraphs in text explaining "
            "what happened and why it matters. Keep interpretation and design_implication empty when "
            "already covered by text; do not repeat the same advice in every field. "
            "Order findings so headline conclusions are expanded first, followed by other important "
            "strengths, tradeoffs and observations. Not every finding needs an action. "
            "Lead the detailed findings with the evidence behind the highest-priority action, "
            "including any minority view that changes that action, rather than a generic common strength. "
            "The summary is a short plain-language overall judgment. summary_points contains a few "
            "most important findings, not a duplicate action list or a fixed quota. Both must be "
            "derived only from the final findings and agree with the recommendation priority. "
            "Do not put routine uncertainty in the summary. Keep limitations to a few sentences "
            "at the end; preserve any caveat necessary to avoid a misleading finding or action "
            "in that finding's text or the action rationale. "
            + (
                "Return at most six recommendations linked to final finding IDs; fewer or none is "
                "valid. Return them in decision-priority order, considering objective relevance, "
                "consequence, experienced friction, coverage, confidence and effort rather than "
                "frequency alone. State the concrete surface and change in action; explain the "
                "supported consequence and what existing strength to preserve in rationale. "
                "Merge actions only when they require the same product change; keep different controls "
                "and decision stages separate. Distinguish product changes from optional enhancements "
                "and research follow-up. Do not present a known working capability as a missing feature. "
                "Use kind=design_change only when at least one linked final finding has "
                "category=experience. Recommendations linked only to preference or reflection wishes "
                "must use kind=enhancement or kind=investigate."
                if final
                else "This is an intermediate reduction. Recommendations must be empty."
            )
        ),
    }


def _composition_schema(task, payload, *, final):
    types = tuple(
        sorted({kind for packet in payload["source_findings"] for kind in packet["allowed_feedback_types"]})
    )
    return report_draft_schema(task.insight.max_findings, recommendations=final, feedback_types=types)


def _reduction_batches(packets, target, ceiling, size):
    def partition(limit):
        batches, pending = [], []
        for packet in packets:
            candidate = pending + [packet]
            if pending and size(candidate) > limit:
                batches.append(pending)
                pending = []
            pending.append(packet)
            if size(pending) > ceiling:
                raise ValueError("A source finding exceeds the configured context budget")
        if pending:
            batches.append(pending)
        return batches

    batches = partition(target)
    if len(packets) > 1 and all(len(batch) == 1 for batch in batches):
        batches = partition(ceiling)
    if len(packets) > 1 and all(len(batch) == 1 for batch in batches):
        raise ValueError("Insight reduction cannot fit two source findings; increase context budget")
    return batches


def synthesize_insight_report(task, responses, episodes, gateway, store):
    """Analyze every question once, then compose a report from evidence-bound question findings."""
    source = analysis_input(task, responses, episodes)
    input_ref = store.json(source, "analysis_input")
    write_json(store.root / "analysis_input.json", source)
    rows = [row for row in source["rows"] if row["status"] == "answered"]
    if not rows:
        raise ValueError("No answered responses available for insight report")
    ceiling = min(
        int(task.insight.context_window * task.insight.input_budget_ratio),
        task.insight.context_window - task.model.max_tokens - 2048,
    )
    target = min(ceiling, task.insight.chunk_target_tokens)
    state_lock = RLock()
    worker_state = local()
    concurrency = task.execution.max_concurrent_model_calls if callable(getattr(gateway, "fork", None)) else 1
    provenance = {
        "pipeline": "staged_insight_report",
        "strategy": "staged_question_composition",
        "language": task.insight.language,
        "input_ref": input_ref,
        "input_sha256": digest(canonical(source)),
        "input_budget": ceiling,
        "n_total_answers": len(source["rows"]),
        "n_eligible_answers": len(rows),
        "covered_answer_ids": [],
        "reviewed_answer_ids": [],
        "max_concurrent_model_calls": concurrency,
        "exploration_coverage": _exploration_coverage(task, episodes),
        "segment_counts": _segment_counts(source),
        "excluded_statuses": {
            status: sum(1 for row in source["rows"] if row["status"] == status)
            for status in sorted({row["status"] for row in source["rows"] if row["status"] != "answered"})
        },
        "stages": [],
        "status": "running",
        "limitations": [
            "Question stages read every eligible original answer; final composition uses only "
            "evidence-bound question findings and code-derived statistics.",
            "Model interpretation remains subject to researcher review.",
        ],
    }

    def save():
        with state_lock:
            write_json(store.root / "analysis_provenance.json", provenance)

    def parallel_requests(items, operation):
        if concurrency == 1 or len(items) < 2:
            return [operation(item) for item in items]

        def execute(item):
            delegate = gateway.fork()
            worker_state.gateway = delegate
            try:
                return operation(item)
            finally:
                delegate.close()
                del worker_state.gateway

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            return list(executor.map(execute, items))

    def prompt_size(purpose, payload, schema):
        return len(model_prompt(purpose, payload, schema).encode("utf-8")) + 4096

    def question_request(selected, stage_name):
        schema = synthesis_schema(
            selected,
            draft=True,
            max_findings=min(3, task.insight.max_findings),
        )
        payload = _question_payload(task, source, selected)
        estimate = prompt_size("research_synthesis", payload, schema)
        if estimate > ceiling:
            raise ValueError(
                f"{stage_name} input exceeds the configured context budget; reduce answer size "
                "or increase insight.context_window"
            )
        stage = {
            "stage": stage_name,
            "input_ref": store.json(payload, "analysis_request"),
            "estimated_tokens": estimate,
            "answer_ids": [row["answer_id"] for row in selected],
            "status": "running",
        }
        with state_lock:
            provenance["stages"].append(stage)
        save()

        def validate(value):
            normalize_candidate(value, selected)
            candidate = selected[0]["question"].get("candidate")
            for finding in value.findings + value.segment_differences:
                if candidate and finding.candidate is None:
                    finding.candidate = candidate
                if candidate and finding.candidate != candidate:
                    raise ValueError("Question finding must retain its configured candidate")
            validate_citations(value, selected)

        value = getattr(worker_state, "gateway", gateway).complete(
            "research_synthesis", payload, schema, validate=validate
        )
        findings = value.findings + value.segment_differences
        for index, finding in enumerate(findings, 1):
            finding.id = f"{stage_name}-f{index}"
        with state_lock:
            stage.update(status="completed", output_ref=store.json(value, "analysis_question_summary"))
            provenance["covered_answer_ids"].extend(stage["answer_ids"])
            provenance["reviewed_answer_ids"].extend(stage["answer_ids"])
        save()
        question_ids = [f"{selected[0]['method_id']}/{selected[0]['question_id']}"]
        return [_source_packet(finding, question_ids) for finding in findings]

    def split_question(group):
        schema = synthesis_schema(
            group,
            draft=True,
            max_findings=min(3, task.insight.max_findings),
        )
        if prompt_size("research_synthesis", _question_payload(task, source, group), schema) <= target:
            return [group]
        chunks, pending = [], []
        for row in group:
            candidate = pending + [row]
            candidate_schema = synthesis_schema(
                candidate,
                draft=True,
                max_findings=min(3, task.insight.max_findings),
            )
            if (
                pending
                and prompt_size(
                    "research_synthesis",
                    _question_payload(task, source, candidate),
                    candidate_schema,
                )
                > target
            ):
                chunks.append(pending)
                pending = []
            single_schema = synthesis_schema(
                [row],
                draft=True,
                max_findings=min(3, task.insight.max_findings),
            )
            if (
                prompt_size(
                    "research_synthesis",
                    _question_payload(task, source, [row]),
                    single_schema,
                )
                > ceiling
            ):
                raise ValueError("A single answer exceeds the configured context budget")
            pending.append(row)
        if pending:
            chunks.append(pending)
        return chunks

    answer_index = {row["answer_id"]: row for row in rows}

    def bind_report(draft, packets):
        by_id = {item["id"]: item for item in packets}
        if len(by_id) != len(packets):
            raise ValueError("Source finding IDs must be unique")
        final_ids = [item.id for item in draft.findings]
        if len(final_ids) != len(set(final_ids)):
            raise ValueError("Final finding IDs must be unique")
        draft_findings = list(draft.findings)
        covered_candidates = set()
        for item in draft_findings:
            selected_candidates = {
                by_id[ref]["candidate"] for ref in item.source_finding_ids if by_id[ref].get("candidate")
            }
            if len(selected_candidates) == 1:
                covered_candidates.update(selected_candidates)
        available_candidates = {item["candidate"] for item in packets if item.get("candidate")}
        for candidate in sorted(available_candidates - covered_candidates):
            if len(draft_findings) >= task.insight.max_findings:
                break
            source = max(
                (item for item in packets if item.get("candidate") == candidate),
                key=lambda item: len(item.get("answer_ids", [])),
            )
            draft_findings.append(
                ReportFindingDraft(
                    id=f"candidate-{len(draft_findings) + 1}",
                    source_finding_ids=[source["id"]],
                    text=source["text"],
                    title=source.get("title", ""),
                    candidate=candidate,
                    category=source["category"],
                    feedback_type=source["feedback_type"],
                    journey_stage=source["journey_stage"],
                    interpretation=source.get("interpretation", ""),
                    design_implication=source.get("design_implication", ""),
                    uncertainty=source.get("uncertainty", ""),
                )
            )
        findings = []
        source_membership = {}
        for item in draft_findings:
            if len(item.source_finding_ids) != len(set(item.source_finding_ids)):
                raise ValueError("A final finding cannot cite a source finding twice")
            if not set(item.source_finding_ids).issubset(by_id):
                raise ValueError("Final finding cites an unknown source finding")
            selected = [by_id[ref] for ref in item.source_finding_ids]
            candidates = {source["candidate"] for source in selected if source.get("candidate")}
            candidate = next(iter(candidates)) if len(candidates) == 1 else None
            category = {
                "positive": "experience",
                "friction": "experience",
                "mixed": "experience",
                "preference": "preference",
                "suggestion": "opportunity",
            }.get(item.feedback_type, item.category)
            support = sorted({answer_id for source in selected for answer_id in source.get("answer_ids", [])})
            counter = sorted(
                {
                    answer_id
                    for source in selected
                    for answer_id in source.get("counter_answer_ids", [])
                    if answer_id not in support
                }
            )
            participants = sorted({answer_index[ref]["persona_id"] for ref in support})
            evidence_refs = sorted(
                {
                    answer_index[ref]["response_ref"]
                    for ref in support
                    if answer_index[ref].get("response_ref")
                }
            )
            finding = Finding(
                id=item.id,
                text=item.text,
                title=item.title,
                candidate=candidate,
                participants=participants,
                evidence_refs=evidence_refs,
                answer_ids=support,
                counter_answer_ids=counter,
                category=category,
                feedback_type=item.feedback_type,
                journey_stage=item.journey_stage,
                interpretation=item.interpretation,
                design_implication=item.design_implication,
                uncertainty=item.uncertainty,
                evidence_details=list(
                    dict.fromkeys(
                        f"{source['text']} "
                        f"(supporting answers: {len(source.get('answer_ids', []))}; "
                        f"counter answers: {len(source.get('counter_answer_ids', []))})"
                        for source in selected
                    )
                ),
                scope_status=(
                    "uncertain"
                    if any(source.get("scope_status") == "uncertain" for source in selected)
                    else "in_scope"
                ),
            )
            findings.append(finding)
            source_membership[item.id] = list(item.source_finding_ids)
        recommendations = [
            Recommendation(**item.model_dump(), priority_score=0) for item in draft.recommendations
        ]
        result = Synthesis(
            summary=draft.summary,
            summary_points=draft.summary_points,
            recommendation_order="decision",
            findings=findings,
            limitations=draft.limitations,
            recommendations=recommendations,
        )
        validate_citations(result, rows)
        return result, source_membership

    def compose(packets, stage_name, *, final):
        payload = _composition_payload(task, source, packets, final=final)
        schema = _composition_schema(task, payload, final=final)
        estimate = prompt_size("research_synthesis", payload, schema)
        if estimate > ceiling:
            raise ValueError(f"{stage_name} input exceeds the configured context budget")
        stage = {
            "stage": stage_name,
            "input_ref": store.json(payload, "analysis_request"),
            "estimated_tokens": estimate,
            "source_finding_ids": [item["id"] for item in packets],
            "status": "running",
        }
        with state_lock:
            provenance["stages"].append(stage)
        save()

        def validate(value):
            bind_report(value, packets)

        draft = gateway.complete("research_synthesis", payload, schema, validate=validate)
        result, membership = bind_report(draft, packets)
        if not final:
            renamed = {}
            for index, finding in enumerate(result.findings, 1):
                identifier = f"{stage_name}-f{index}"
                renamed[identifier] = membership[finding.id]
                finding.id = identifier
            membership = renamed
        with state_lock:
            stage.update(
                status="completed",
                output_ref=store.json(result, "analysis_summary"),
                finding_sources=membership,
            )
        save()
        return result, [_source_packet(finding, []) for finding in result.findings]

    save()
    try:
        groups = defaultdict(list)
        for row in rows:
            groups[(row["method_id"], row["question_id"])].append(row)
        question_jobs = []
        for question_index, group in enumerate(groups.values(), 1):
            chunks = split_question(group)
            for chunk_index, chunk in enumerate(chunks, 1):
                suffix = f"-chunk-{chunk_index}" if len(chunks) > 1 else ""
                question_jobs.append((chunk, f"question-{question_index}{suffix}"))
        packets = [
            packet
            for result in parallel_requests(
                question_jobs,
                lambda item: question_request(item[0], item[1]),
            )
            for packet in result
        ]

        if not packets:
            result = Synthesis(
                summary="The eligible answers did not support a decision-relevant finding.",
                recommendation_order="decision",
                findings=[],
                limitations=(
                    "This is synthetic Persona feedback. Review the original answers and study "
                    "coverage before drawing a product conclusion."
                ),
            )
            provenance.update(
                status="completed",
                covered_answer_ids=sorted(set(provenance["covered_answer_ids"])),
                reviewed_answer_ids=sorted(set(provenance["reviewed_answer_ids"])),
                final_finding_sources={},
            )
            save()
            return result, provenance

        reduction_depth = 0
        while True:
            final_payload = _composition_payload(task, source, packets, final=True)
            schema = _composition_schema(task, final_payload, final=True)
            if prompt_size("research_synthesis", final_payload, schema) <= ceiling:
                result, _ = compose(packets, "insight-report-composition", final=True)
                break
            reduction_depth += 1
            if reduction_depth > 8:
                raise ValueError("Maximum insight reduction depth reached")

            def reduction_size(candidate):
                payload = _composition_payload(task, source, candidate, final=False)
                return prompt_size(
                    "research_synthesis", payload, _composition_schema(task, payload, final=False)
                )

            batches = _reduction_batches(packets, target, ceiling, reduction_size)
            reduced = []
            for index, batch in enumerate(batches, 1):
                if len(batch) == 1:
                    reduced.extend(batch)
                    continue
                _, merged = compose(
                    batch,
                    f"insight-reduce-{reduction_depth}-{index}",
                    final=False,
                )
                reduced.extend(merged)
            if len(reduced) >= len(packets):
                raise ValueError(
                    "Insight reduction cannot fit without dropping evidence; increase context budget"
                )
            packets = reduced
        provenance.update(
            status="completed",
            covered_answer_ids=sorted(set(provenance["covered_answer_ids"])),
            reviewed_answer_ids=sorted(set(provenance["reviewed_answer_ids"])),
            final_finding_sources=provenance["stages"][-1].get("finding_sources", {}),
        )
        save()
        return result, provenance
    except Exception as error:
        provenance.update(status="failed", error=f"{type(error).__name__}: {error}")
        for stage in provenance["stages"]:
            if stage["status"] == "running":
                stage["status"] = "failed"
        save()
        raise
