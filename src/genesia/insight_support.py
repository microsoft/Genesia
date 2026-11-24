"""Deterministic input and citation helpers for staged insight reports."""

from collections import Counter, defaultdict
from typing import Literal

from pydantic import Field, create_model

from .agents import execution_trace
from .analysis import descriptive_statistics, validate_and_rank
from .runtime import canonical, digest
from .schemas import Finding, Quote, Recommendation, Synthesis
from .study import attribute, segment_labels

FEEDBACK_ROLES = {
    "positive": {"overall", "journey", "strength", "comparison", "preference", "design", "verdict"},
    "friction": {"overall", "journey", "friction", "comparison", "preference", "design", "verdict"},
    "mixed": {
        "overall",
        "journey",
        "strength",
        "friction",
        "comparison",
        "preference",
        "design",
        "verdict",
    },
    "preference": {"preference"},
    "suggestion": {"suggestion"},
}


def synthesis_schema(rows, *, draft=False, max_findings=8, composition=False):
    purposes = {row["question"].get("purpose", "experience") for row in rows}
    feedback_study = any(row["question"].get("feedback_role") for row in rows)
    categories = (
        ("experience", "preference", "opportunity")
        if draft or "experience" in purposes or not purposes
        else ("opportunity",)
        if purposes == {"reflection"}
        else ("preference", "opportunity")
    )
    answer_ids = tuple(dict.fromkeys(row["answer_id"] for row in rows if row.get("answer_id")))
    persona_ids = tuple(dict.fromkeys(row["persona_id"] for row in rows if row.get("persona_id")))
    response_refs = tuple(dict.fromkeys(row["response_ref"] for row in rows if row.get("response_ref")))
    answer_id_type = Literal.__getitem__(answer_ids) if answer_ids and not composition else str
    persona_id_type = Literal.__getitem__(persona_ids) if persona_ids and not composition else str
    response_ref_type = Literal.__getitem__(response_refs) if response_refs and not composition else str
    candidates = tuple(
        dict.fromkeys(row["question"].get("candidate") for row in rows if row["question"].get("candidate"))
    )
    candidate_type = Literal.__getitem__(candidates) if candidates else type(None)
    quote = create_model("EvidenceQuote", __base__=Quote, answer_id=(answer_id_type, ...))
    finding = create_model(
        "EvidenceFinding",
        __base__=Finding,
        category=(Literal[categories], Field(default=categories[0])),
        candidate=(candidate_type | None, None),
        participants=(
            list[str if draft else persona_id_type],
            Field(default_factory=list, max_length=0 if composition else None),
        ),
        evidence_refs=(
            list[str if draft else response_ref_type],
            Field(default_factory=list, max_length=0 if composition else None),
        ),
        answer_ids=(
            list[str if draft else answer_id_type],
            Field(default_factory=list, max_length=0 if composition else None),
        ),
        counter_answer_ids=(
            list[str if draft else answer_id_type],
            Field(default_factory=list, max_length=0 if composition else None),
        ),
        **(
            {
                "feedback_type": (
                    Literal["positive", "friction", "preference", "suggestion", "mixed"],
                    ...,
                ),
                "journey_stage": (
                    str
                    if draft
                    else Literal[
                        "entry",
                        "discovery",
                        "exploration",
                        "comparison",
                        "decision",
                        "overall",
                        "other",
                    ],
                    ...,
                ),
            }
            if feedback_study
            else {}
        ),
        **({"quotes": (list[quote], Field(default_factory=list, max_length=0))} if draft else {}),
    )
    return create_model(
        "EvidenceSynthesis",
        __base__=Synthesis,
        findings=(list[finding], Field(max_length=max_findings)),
        segment_differences=(list[finding], Field(default_factory=list, max_length=max_findings)),
        **(
            {"recommendations": (list[Recommendation], Field(default_factory=list, max_length=0))}
            if draft
            else {}
        ),
    )


def normalize_candidate(value, rows):
    categories = {
        "positive": "experience",
        "friction": "experience",
        "mixed": "experience",
        "preference": "preference",
        "suggestion": "opportunity",
    }
    answered = {row["answer_id"]: row for row in rows if row["status"] == "answered"}

    def supported(finding):
        if not set(finding.answer_ids).issubset(answered):
            return True
        selected = [answered[answer_id] for answer_id in finding.answer_ids]
        roles = {row["question"].get("feedback_role") for row in selected}
        if finding.feedback_type in FEEDBACK_ROLES and not roles.intersection(
            FEEDBACK_ROLES[finding.feedback_type]
        ):
            return False
        return finding.category != "experience" or any(
            row["question"].get("purpose", "experience") == "experience" for row in selected
        )

    for finding in value.findings + value.segment_differences:
        finding.participants = []
        finding.evidence_refs = []
        finding.answer_ids = [answer_id for answer_id in finding.answer_ids if answer_id in answered]
        finding.counter_answer_ids = [
            answer_id
            for answer_id in finding.counter_answer_ids
            if answer_id in answered and answer_id not in finding.answer_ids
        ]
        if finding.journey_stage not in {
            "entry",
            "discovery",
            "exploration",
            "comparison",
            "decision",
            "overall",
            "other",
        }:
            finding.journey_stage = "other"
        if finding.feedback_type in categories:
            finding.category = categories[finding.feedback_type]
    value.findings = [
        finding
        for finding in value.findings
        if finding.answer_ids and finding.scope_status != "prototype_limit" and supported(finding)
    ]
    value.segment_differences = [
        finding
        for finding in value.segment_differences
        if finding.answer_ids and finding.scope_status != "prototype_limit" and supported(finding)
    ]


def analysis_input(task, responses, episodes):
    by_person = {(response.persona_id, response.method_id): response for response in responses}
    rows = []
    for episode in episodes:
        for method in task.methods:
            response = by_person.get((episode.persona.id, method.id))
            answers = {answer.question_id: answer for answer in response.answers} if response else {}
            questions = [(question, None) for question in method.questions]
            if response:
                from .schemas import Question

                questions.extend(
                    (Question.model_validate(item["question"]), item) for item in response.followups
                )
            for question, followup in questions:
                from .schemas import Answer

                answer = Answer.model_validate(followup["answer"]) if followup else answers.get(question.id)
                status = (
                    "missing"
                    if response is None
                    else "invalid"
                    if not response.valid
                    else "missing"
                    if answer is None
                    else "skipped"
                    if answer.basis == "skipped"
                    else "not_observed"
                    if answer.basis == "not_observed"
                    else "automation"
                    if answer.basis == "automation"
                    else "unanswered"
                    if answer.value is None
                    else "answered"
                )
                identity = [episode.session_id, method.id, question.id, bool(followup)]
                rows.append(
                    {
                        "answer_id": "a-" + digest(canonical(identity))[:24],
                        "persona_id": episode.persona.id,
                        "session_id": episode.session_id,
                        "method_id": method.id,
                        "question_id": question.id,
                        "question": question.model_dump(),
                        "followup": followup is not None,
                        "parent_question_id": followup["parent_question_id"] if followup else None,
                        "status": status,
                        "basis": answer.basis if answer else None,
                        "value": answer.value if answer else None,
                        "reason": answer.reason if answer else "",
                        "response_ref": response.evidence_ref if response else None,
                        "evidence_refs": answer.evidence_refs if answer else [],
                    }
                )
    counts = defaultdict(Counter)
    for row in rows:
        if not row["followup"]:
            counts[(row["method_id"], row["question_id"])][row["status"]] += 1
    return {
        "goal": task.goal,
        "study": task.study.model_dump(),
        "methods": [method.model_dump() for method in task.methods],
        "input_mode": task.environment.mode,
        "prototype": task.environment.prototype.model_dump() if task.environment.prototype else None,
        "experience_constraints": {
            "max_steps": task.environment.max_steps,
            "min_actions_before_stop": task.environment.min_actions_before_stop,
            "required_url_fragments_before_stop": task.environment.required_url_fragments_before_stop,
        },
        "sources": [source.model_dump(exclude={"token_env"}) for source in task.environment.sources],
        "selected_personas": [episode.persona.id for episode in episodes],
        "participant_context": [
            {
                "persona_id": episode.persona.id,
                "attributes": {
                    field: value
                    for field in (
                        "age",
                        "region",
                        "market",
                        "occupation",
                        "job_category",
                        "industry",
                        "seniority",
                        "company_size",
                        "education.degree_map",
                    )
                    if (value := attribute(episode.persona, f"Core Identity.{field}")) is not None
                    and isinstance(value, (str, int, float, bool))
                },
                "segments": segment_labels(task.study, episode.persona),
            }
            for episode in episodes
        ],
        "rows": rows,
        "question_quality": [
            {
                "method_id": key[0],
                "question_id": key[1],
                "n_selected": len(episodes),
                "counts": dict(value),
                "denominator": "answered only; excluded statuses listed separately",
            }
            for key, value in counts.items()
        ],
        "statistics": descriptive_statistics(task, responses, episodes),
        "outcomes": [
            {
                "persona_id": episode.persona.id,
                "session_intent": episode.intent.model_dump() if episode.intent else None,
                "outcome": episode.outcome,
                "basis": episode.outcome_basis,
                "steps": len(episode.steps),
                "coverage": episode.coverage,
                "executed_actions": execution_trace(episode),
            }
            for episode in episodes
        ],
    }


def validate_citations(value, rows):
    answered = {row["answer_id"]: row for row in rows if row["status"] == "answered"}
    owners = {row["response_ref"]: row["persona_id"] for row in answered.values()}
    candidates = {row["question"].get("candidate") for row in rows} - {None}
    for finding in value.findings + value.segment_differences:
        if finding.candidate is not None and finding.candidate not in candidates:
            raise ValueError("Finding candidate must match a configured question candidate")
        if not finding.answer_ids:
            matching = [row for row in answered.values() if row["response_ref"] in finding.evidence_refs]
            if len(matching) != len(set(finding.evidence_refs)):
                raise ValueError("Cite precise answer_ids, not only a multi-answer response")
            finding.answer_ids = [row["answer_id"] for row in matching]
        if not set(finding.answer_ids).issubset(answered):
            raise ValueError("Finding cites an unknown, excluded or out-of-batch answer")
        if finding.candidate is not None and any(
            answered[ref]["question"].get("candidate") not in {None, finding.candidate}
            for ref in finding.answer_ids
        ):
            raise ValueError("Candidate finding cannot use another candidate's answers as support")
        if not finding.answer_ids:
            raise ValueError("A finding requires at least one supporting answer")
        if not set(finding.counter_answer_ids).issubset(answered):
            raise ValueError("Counterevidence cites an unknown, excluded or out-of-batch answer")
        if set(finding.counter_answer_ids).intersection(finding.answer_ids):
            raise ValueError("The same answer cannot be both support and counterevidence")
        if finding.scope_status == "prototype_limit":
            raise ValueError("Known prototype limits belong in limitations, not product findings")
        selected = [answered[ref] for ref in finding.answer_ids]
        if finding.feedback_type == "preference" and finding.category != "preference":
            raise ValueError("Preference feedback must use category=preference")
        if finding.feedback_type == "suggestion" and finding.category != "opportunity":
            raise ValueError("Suggestion feedback must use category=opportunity")
        if finding.feedback_type in {"positive", "friction", "mixed"} and finding.category != "experience":
            raise ValueError("Evaluative design feedback must use category=experience")
        roles = {row["question"].get("feedback_role") for row in selected}
        if finding.feedback_type in FEEDBACK_ROLES and not roles.intersection(
            FEEDBACK_ROLES[finding.feedback_type]
        ):
            raise ValueError(
                f"{finding.feedback_type} feedback requires a matching participant feedback question"
            )
        if finding.category == "experience" and not any(
            row["question"].get("purpose", "experience") == "experience" for row in selected
        ):
            raise ValueError("Experience findings require experience answers, not only context or wishes")
        expected_refs = {row["response_ref"] for row in selected}
        if not finding.evidence_refs:
            finding.evidence_refs = sorted(expected_refs)
        if set(finding.evidence_refs) != expected_refs:
            raise ValueError(
                f"Finding {finding.id} response refs must match its cited answers: "
                f"expected {sorted(expected_refs)}, got {sorted(set(finding.evidence_refs))}. "
                "Use only response_ref values, not screenshot/observation evidence_refs."
            )
        expected_participants = {row["persona_id"] for row in selected}
        if not finding.participants:
            finding.participants = sorted(expected_participants)
        if set(finding.participants) != expected_participants:
            raise ValueError("Finding participants must match cited answers")
        if finding.claim_type == "observed":
            raise ValueError(
                "Answer synthesis cannot certify observed claims; use persona_report or interpretation"
            )
        for quote in finding.quotes:
            row = answered.get(quote.answer_id)
            if (
                quote.answer_id not in finding.answer_ids + finding.counter_answer_ids
                or not row
                or not any(isinstance(part, str) and part for part in (row["value"], row.get("reason")))
            ):
                raise ValueError("Quote must cite a string answer used by its finding")
            if not any(
                quote.text in part for part in (row["value"], row.get("reason")) if isinstance(part, str)
            ):
                raise ValueError("Quote must match the original answer exactly")
    validate_and_rank(value, owners)
    by_id = {finding.id: finding for finding in value.findings + value.segment_differences}
    for recommendation in value.recommendations:
        if recommendation.kind == "design_change" and not any(
            by_id[ref].category == "experience" for ref in recommendation.finding_ids
        ):
            raise ValueError(
                "Design changes require experience support; wishes are enhancements or investigations"
            )
