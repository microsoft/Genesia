import json
from pathlib import Path

import pytest
from test_workflow import ScriptedModel, task_fixture

from genesia import analyze, run
from genesia.analysis import validate_and_rank
from genesia.insight_report import _composition_payload, _execution_summary, _question_payload
from genesia.reports import render
from genesia.runtime import EvidenceStore
from genesia.schemas import Synthesis


def test_decision_priority_survives_score_calculation_and_legacy_still_sorts():
    synthesis = Synthesis(
        summary="Inspect the content first",
        limitations="Synthetic",
        recommendation_order="decision",
        findings=[dict(id="f", text="Content", participants=["p"], evidence_refs=["r"])],
        recommendations=[
            dict(
                action="Inspect content",
                rationale="Consequential decision",
                finding_ids=["f"],
                severity=5,
                effort=5,
                confidence=1,
            ),
            dict(
                action="Preserve labels",
                rationale="Common strength",
                finding_ids=["f"],
                severity=2,
                effort=1,
                confidence=1,
            ),
        ],
    )
    validate_and_rank(synthesis, {"r": "p"})
    assert [item.action for item in synthesis.recommendations] == ["Inspect content", "Preserve labels"]
    assert [item.priority_score for item in synthesis.recommendations] == [1, 2]
    synthesis.recommendation_order = "score"
    validate_and_rank(synthesis, {"r": "p"})
    assert synthesis.recommendations[0].action == "Preserve labels"
    legacy = synthesis.model_dump(exclude={"recommendation_order", "summary_points"})
    assert Synthesis.model_validate(legacy).recommendation_order == "score"


class DecisionModel(ScriptedModel):
    summary_text = "Keep the foundation; improve evidence recovery."

    def complete(self, purpose, payload, schema, **kwargs):
        value = super().complete(purpose, payload, schema, **kwargs)
        if payload.get("output_stage") == "insight_report":
            value.summary = self.summary_text
            value.summary_points = ["One consequential minority view changes the next step."]
            value.findings[0].title = "Evidence recovery"
            value.findings[0].text = "The evidence can be understood but is difficult to recover."
            value.findings[0].uncertainty = "Real-world correctness has not been measured."
            value.recommendations[0].action = "Show the exact content"
            value.recommendations[0].severity = 5
            value.recommendations[0].effort = 5
            value.recommendations[0].confidence = 1
            second = value.recommendations[0].model_copy(deep=True)
            second.action = "Preserve clear labels"
            second.severity = 2
            second.effort = 1
            value.recommendations.append(second)
            if validate := kwargs.get("validate"):
                validate(value)
        return value


@pytest.mark.parametrize("language", ["en", "zh-CN"])
@pytest.mark.parametrize("feedback", [False, True])
def test_coherent_report_uses_one_story_and_preserves_evidence(tmp_path, language, feedback):
    task = task_fixture(tmp_path)
    task.insight.language = language
    if feedback:
        task.methods[0].questions[0].feedback_role = "overall"
    source = run(task, gateway=ScriptedModel(), research_only=True)
    source_path = Path(source.output_dir) / "research_result.json"
    original = source_path.read_bytes()
    model = DecisionModel()
    if language == "zh-CN":
        model.summary_text = "\u4fdd\u7559\u57fa\u7840\uff0c\u6539\u5584\u8bc1\u636e\u67e5\u627e\u3002"
    result = analyze(source.output_dir, gateway=model)
    assert result.status == "completed", result.errors
    assert source_path.read_bytes() == original
    assert result.synthesis.recommendation_order == "decision"
    assert [item.action for item in result.synthesis.recommendations] == [
        "Show the exact content",
        "Preserve clear labels",
    ]
    assert all(purpose == "research_synthesis" for purpose, _ in model.calls)
    store = EvidenceStore(Path(result.output_dir))
    markdown = render(result, store)
    html = render(result, store, html_output=True)
    headings = ["Summary", "Next actions", "Findings", "Limitations", "Appendix / Evidence"]
    assert [line[3:] for line in markdown.splitlines() if line.startswith("## ")] == headings
    for prose in (
        result.synthesis.summary,
        result.synthesis.summary_points[0],
        result.synthesis.findings[0].title,
        result.synthesis.findings[0].text,
        result.synthesis.findings[0].uncertainty,
    ):
        assert prose in markdown and prose in html
    assert markdown.index("Show the exact content") < markdown.index("Preserve clear labels")
    assert html.index("Show the exact content") < html.index("Preserve clear labels")
    assert 'lang="zh-CN"' in html if language == "zh-CN" else 'lang="en"' in html
    assert "Cross-version" not in markdown
    assert "# Genesia Research Report [SIMULATED]" in markdown
    assert "<title>Genesia Research Report</title>" in html
    assert "Source status: completed" in markdown
    assert html.count("<section") == 5
    assert "#finding-f1" in markdown and 'href="#finding-f1"' in html
    assert 'id="finding-f1"' in markdown and 'id="finding-f1"' in html
    assert "<strong>To validate" not in html and "**To validate" not in markdown
    assert store.verify()["valid"]
    provenance = json.loads((Path(result.output_dir) / "analysis_provenance.json").read_text("utf-8"))
    assert len(set(provenance["reviewed_answer_ids"])) == provenance["n_eligible_answers"] == 12


def test_composition_keeps_segment_and_decision_rules_without_quota(tmp_path):
    task = task_fixture(tmp_path)
    source = {
        "goal": "Review",
        "prototype": {},
        "statistics": {
            "basis": "Synthetic",
            "questions": [
                {
                    "method_id": "m",
                    "question_id": "q",
                    "segments": {"region": {"Europe": {"n_answered": 2, "small_sample": True}}},
                }
            ],
        },
        "participant_context": [
            {"persona_id": "p1", "segments": {"region": "Europe"}},
            {"persona_id": "p2", "segments": {"region": "Europe"}},
        ],
    }
    payload = _composition_payload(task, source, [], final=True)
    assert payload["segment_counts"] == {"region": {"Europe": 2}}
    assert (
        payload["descriptive_statistics"]["questions"][0]["segments"]["region"]["Europe"]["n_answered"] == 2
    )
    assert "Then derive and prioritize actions" in payload["instruction"]
    assert "Only then distill the summary" in payload["instruction"]
    assert "fewer or none" in payload["instruction"]
    assert "minority or segment finding can lead" in payload["instruction"]
    assert "number of people reporting each individual issue" in payload["instruction"]


def test_composition_trace_is_execution_evidence_not_intent(tmp_path):
    task = task_fixture(tmp_path)
    source = {
        "goal": "Review",
        "prototype": {},
        "statistics": {"basis": "Synthetic", "questions": []},
        "participant_context": [],
        "outcomes": [
            {
                "persona_id": "p",
                "basis": "self report",
                "executed_actions": [
                    dict(
                        step=1,
                        action="click",
                        target="Review",
                        execution_success=True,
                        result="Executed",
                        intent="Sent successfully",
                        expected_result="Delivered",
                    )
                ],
            }
        ],
    }
    row = dict(
        answer_id="a",
        persona_id="p",
        question_id="q",
        method_id="m",
        question={"text": "What happened?", "purpose": "experience"},
        value="Reviewed",
        reason="",
        basis="experience",
        status="answered",
        response_ref="r",
    )
    payload = _question_payload(task, source, [row])
    assert payload["outcomes"] == []
    source["rows"] = [row]
    payload = _composition_payload(task, source, [], final=True)
    summary = payload["execution_summary"]
    assert summary["controls"] == [{"target": "Review", "attempted_personas": 1, "successful_personas": 1}]
    assert "Sent successfully" not in json.dumps(summary)
    assert summary["first_click_order"] == []
    assert payload["answer_owners"] == {"a": "p"}
    assert "chunk count is not a whole-cohort count" in payload["instruction"]


def test_candidate_targets_and_findings_remain_explicit(tmp_path):
    task = task_fixture(tmp_path)
    for index, method in enumerate(task.methods):
        method.questions[0].candidate = "Version A" if index < 2 else "Version B"
        method.questions[0].feedback_role = "journey" if index % 2 == 0 else "suggestion"
    result = run(task, gateway=ScriptedModel())
    assert result.status == "completed", result.errors
    store = EvidenceStore(Path(result.output_dir))
    markdown = render(result, store)
    assert "Version A -" in markdown and "Version B -" in markdown
    assert "Cross-version" in markdown


def test_execution_counts_deduplicate_people_and_do_not_count_failed_clicks_as_success():
    summary = _execution_summary(
        {
            "outcomes": [
                {
                    "persona_id": "p1",
                    "executed_actions": [
                        dict(step=1, action="click", target="Authorize", execution_success=True),
                        dict(step=2, action="click", target="Authorize", execution_success=True),
                        dict(step=3, action="click", target="Accept", execution_success=True),
                    ],
                },
                {
                    "persona_id": "p2",
                    "executed_actions": [
                        dict(step=1, action="click", target="Authorize", execution_success=False),
                        dict(step=2, action="click", target="Accept", execution_success=True),
                        dict(step=3, action="click", target="Authorize", execution_success=True),
                    ],
                },
                {
                    "persona_id": "p3",
                    "executed_actions": [
                        dict(step=1, action="click", target="Authorize", execution_success=False),
                        dict(step=2, action="stop", target=None, execution_success=True),
                    ],
                },
            ]
        }
    )
    authorization = next(item for item in summary["controls"] if item["target"] == "Authorize")
    assert authorization == dict(target="Authorize", attempted_personas=3, successful_personas=2)
    assert summary["first_click_order"] == [
        dict(before="Accept", after="Authorize", personas=1),
        dict(before="Authorize", after="Accept", personas=1),
    ]
    assert summary["omitted_controls"] == summary["omitted_order_pairs"] == 0


def test_execution_summary_bounds_are_explicit():
    summary = _execution_summary(
        {
            "outcomes": [
                {
                    "persona_id": "p",
                    "executed_actions": [
                        dict(step=index, action="click", target=f"Control {index}", execution_success=True)
                        for index in range(70)
                    ],
                }
            ]
        }
    )
    assert len(summary["controls"]) == len(summary["first_click_order"]) == 64
    assert summary["omitted_controls"] == 6
    assert summary["omitted_order_pairs"] == 70 * 69 // 2 - 64
