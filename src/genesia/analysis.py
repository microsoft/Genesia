"""Deterministic descriptive statistics for synthetic samples, not population inference."""

import json
from collections import Counter, defaultdict

from .schemas import (
    Episode,
    MethodResponse,
    SegmentSpec,
    Synthesis,
    TaskSpec,
)
from .study import segment_labels


def bucket_label(value, segment: SegmentSpec) -> str:
    return segment.label(value)


def descriptive_statistics(task: TaskSpec, responses: list[MethodResponse], episodes: list[Episode]) -> dict:
    questions = {
        (method.id, question.id): question for method in task.methods for question in method.questions
    }
    rows = defaultdict(list)
    for response in responses:
        if response.valid:
            for answer in response.answers:
                rows[(response.method_id, answer.question_id)].append((response.persona_id, answer))
    people = {episode.persona.id: episode.persona for episode in episodes}
    memberships = {person_id: segment_labels(task.study, person) for person_id, person in people.items()}
    summaries = []
    for key, question in questions.items():
        answers = rows[key]
        observed = [
            (person, answer)
            for person, answer in answers
            if answer.value is not None and answer.basis != "automation"
        ]

        def distribution(items):
            counts = Counter()
            matrix = defaultdict(Counter)
            for _, answer in items:
                if question.kind == "single":
                    counts[answer.value] += 1
                elif question.kind == "multiple":
                    counts.update(answer.value)
                elif question.kind == "likert":
                    for row, choice in answer.value.items():
                        matrix[row][choice] += 1
            return {
                "n_answered": len(items),
                "counts": dict(counts),
                "percent_of_answered": {
                    option: round(count / len(items) * 100, 2) for option, count in counts.items()
                },
                "matrix_counts": {row: dict(counts) for row, counts in matrix.items()},
            }

        segments = {}
        for segment_id in [
            *task.study.segment_fields,
            *task.study.segments,
            *task.study.segment_combinations,
        ]:
            spec = task.study.segments.get(segment_id)
            groups = {label: [] for label in spec.buckets} if spec else {}
            for person_id, answer in observed:
                label = memberships[person_id][segment_id]
                groups.setdefault(label, []).append((person_id, answer))
            segments[segment_id] = {
                group: {
                    **distribution(items),
                    "small_sample": len(items) < 5,
                    **(
                        {
                            "dimensions": dict(
                                zip(
                                    task.study.segment_combinations[segment_id],
                                    json.loads(group),
                                    strict=True,
                                )
                            )
                        }
                        if segment_id in task.study.segment_combinations
                        else {}
                    ),
                }
                for group, items in groups.items()
            }
        summaries.append(
            {
                "method_id": key[0],
                "question_id": key[1],
                "kind": question.kind,
                "n_valid_responses": len(answers),
                "n_not_observed": sum(answer.basis == "not_observed" for _, answer in answers),
                "n_automation": sum(answer.basis == "automation" for _, answer in answers),
                "n_skipped": sum(answer.basis == "skipped" for _, answer in answers),
                "n_missing_or_invalid": len(episodes) - len(answers),
                **distribution(observed),
                "segments": segments,
            }
        )
    return {
        "basis": "Synthetic sample descriptive counts only; no statistical significance or population claims",
        "segment_memberships": memberships,
        "questions": summaries,
    }


def validate_and_rank(synthesis: Synthesis, response_owners: dict[str, str]):
    findings = synthesis.findings + synthesis.segment_differences
    for index, finding in enumerate(findings, 1):
        if not finding.id:
            finding.id = f"finding-{index}"
        if not set(finding.evidence_refs).issubset(response_owners):
            raise ValueError("Finding references invalid or missing response evidence")
        supported = {response_owners[ref] for ref in finding.evidence_refs}
        if set(finding.participants) != supported or len(finding.participants) != len(supported):
            raise ValueError("Finding participants must match cited response owners exactly")
    by_id = {finding.id: finding for finding in findings}
    if len(by_id) != len(findings):
        raise ValueError("Finding IDs must be unique")
    for recommendation in synthesis.recommendations:
        if not set(recommendation.finding_ids).issubset(by_id):
            raise ValueError("Recommendation references an unknown finding")
        participants = {
            person for finding_id in recommendation.finding_ids for person in by_id[finding_id].participants
        }
        recommendation.priority_score = round(
            recommendation.severity * len(participants) * recommendation.confidence / recommendation.effort, 3
        )
    if synthesis.recommendation_order == "score":
        synthesis.recommendations.sort(key=lambda item: (-item.priority_score, item.action))
