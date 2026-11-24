import pytest
from test_workflow import ScriptedModel, task_fixture

from genesia.analysis import validate_and_rank
from genesia.api import run
from genesia.schemas import Synthesis


def test_legacy_comparison_analysis_requires_explicit_stage_labels(tmp_path):
    import json
    from pathlib import Path

    from genesia import analyze

    task = task_fixture(tmp_path)
    source = run(task, gateway=ScriptedModel(), research_only=True)
    root = Path(source.output_dir)
    manifest = json.loads((root / "run_manifest.json").read_text("utf-8"))
    manifest["task"]["environment"] = {
        "mode": "live",
        "start_url": "http://localhost:4175/?design=a",
        "handoff_urls": ["http://localhost:4175/?design=b"],
    }
    for index, method in enumerate(manifest["task"]["methods"]):
        method["questions"][0]["candidate"] = "Design A" if index < 2 else "Design B"
    (root / "run_manifest.json").write_text(json.dumps(manifest), "utf-8")
    original = (root / "run_manifest.json").read_bytes()
    with pytest.raises(ValueError, match="explicit candidate_labels"):
        analyze(root, gateway=ScriptedModel())
    with pytest.raises(ValueError, match="match the saved question"):
        analyze(root, candidate_labels=["Wrong", "Design B"], gateway=ScriptedModel())
    result = analyze(root, candidate_labels=["Design A", "Design B"], gateway=ScriptedModel())
    assert result.status == "completed", result.errors
    new = json.loads((Path(result.output_dir) / "run_manifest.json").read_text("utf-8"))
    assert new["task"]["environment"]["candidate_labels"] == ["Design A", "Design B"]
    assert new["analysis_candidate_label_resolution"]["candidate_labels"] == ["Design A", "Design B"]
    assert new["source_run_id"] == source.run_id
    assert result.episodes == source.episodes
    assert result.responses == source.responses
    assert (root / "run_manifest.json").read_bytes() == original
    with pytest.raises(ValueError, match="cannot override saved"):
        analyze(result.output_dir, candidate_labels=["Design B", "Design A"], gateway=ScriptedModel())


def test_reanalysis_preserves_source_and_never_repeats_personas(tmp_path):
    from pathlib import Path

    from genesia import analyze

    task = task_fixture(tmp_path)
    source = run(task, gateway=ScriptedModel())
    original = (Path(source.output_dir) / "research_result.json").read_bytes()
    model = ScriptedModel()
    result = analyze(source.output_dir, gateway=model)
    assert result.status == "completed", result.errors
    assert result.run_id != source.run_id
    assert [item.model_dump() for item in result.responses] == [
        item.model_dump() for item in source.responses
    ]
    assert all(purpose == "research_synthesis" for purpose, _ in model.calls)
    assert (Path(source.output_dir) / "research_result.json").read_bytes() == original
    assert (Path(result.output_dir) / "report.html").is_file()


def test_staged_reanalysis_reads_each_question_then_composes_once(tmp_path):
    import json
    from pathlib import Path

    from genesia import analyze

    task = task_fixture(tmp_path)
    task.insight.focus = ["Primary decision"]
    source = run(task, gateway=ScriptedModel(), research_only=True)
    model = ScriptedModel()
    result = analyze(source.output_dir, gateway=model)

    assert result.status == "completed", result.errors
    question_calls = [
        payload
        for purpose, payload in model.calls
        if purpose == "research_synthesis" and payload.get("output_stage") == "question_insights"
    ]
    final_calls = [
        payload
        for purpose, payload in model.calls
        if purpose == "research_synthesis" and payload.get("output_stage") == "insight_report"
    ]
    assert len(question_calls) == 4
    assert len(final_calls) == 1
    assert all(purpose == "research_synthesis" for purpose, _ in model.calls)
    assert all(len(payload["question_definitions"]) == 1 for payload in question_calls)
    assert sum(len(payload["rows"]) for payload in question_calls) == 12
    assert final_calls[0]["study"]["report_focus"] == ["Primary decision"]
    provenance = json.loads((Path(result.output_dir) / "analysis_provenance.json").read_text("utf-8"))
    assert provenance["pipeline"] == "staged_insight_report"
    assert provenance["strategy"] == "staged_question_composition"
    assert len(set(provenance["reviewed_answer_ids"])) == 12
    assert provenance["n_eligible_answers"] == 12
    assert provenance["stages"][-1]["stage"] == "insight-report-composition"


def test_staged_analysis_chunks_only_oversized_questions(tmp_path):
    from genesia.insight_report import synthesize_insight_report
    from genesia.runtime import EvidenceStore

    task = task_fixture(tmp_path)
    task.insight.context_window = 30000
    task.insight.input_budget_ratio = 0.8
    task.insight.chunk_target_tokens = 12000
    task.model.max_tokens = 1000
    source = run(task, gateway=ScriptedModel(), research_only=True)
    for response in source.responses:
        for answer in response.answers:
            answer.value = "x" * 6000

    model = ScriptedModel()
    _, provenance = synthesize_insight_report(
        task,
        source.responses,
        source.episodes,
        model,
        EvidenceStore(tmp_path / "chunked-analysis"),
    )

    question_stages = [stage for stage in provenance["stages"] if stage["stage"].startswith("question-")]
    assert len(question_stages) == 12
    assert all("-chunk-" in stage["stage"] for stage in question_stages)
    assert len(set(provenance["reviewed_answer_ids"])) == 12
    assert provenance["stages"][-1]["stage"] == "insight-report-composition"


def test_reanalysis_records_prior_failure_without_repeating_it(tmp_path):
    import json
    from pathlib import Path

    from genesia import analyze

    class FailedSynthesis(ScriptedModel):
        def complete(self, purpose, payload, schema, **kwargs):
            if purpose == "research_synthesis":
                raise ValueError("Fixture synthesis failure")
            return super().complete(purpose, payload, schema, **kwargs)

    original = run(task_fixture(tmp_path), gateway=FailedSynthesis())
    assert original.status == "partial"
    result = analyze(original.output_dir, gateway=ScriptedModel())
    assert result.status == "completed", result.errors
    manifest = json.loads((Path(result.output_dir) / "run_manifest.json").read_text("utf-8"))
    assert manifest["source_status"] == "partial"
    assert manifest["source_errors"] == original.errors
    report = (Path(result.output_dir) / "report.md").read_text("utf-8")
    assert "Source status: partial" in report and "Fixture synthesis failure" in report


def test_priority_uses_distinct_participants_and_overwrites_model_score():
    synthesis = Synthesis(
        summary="Study",
        limitations="Synthetic",
        findings=[dict(id="f1", text="Issue", participants=["a", "b"], evidence_refs=["r1", "r2"])],
        recommendations=[
            dict(
                action="Fix",
                rationale="Evidence",
                finding_ids=["f1"],
                severity=4,
                effort=2,
                confidence=0.5,
                priority_score=1000,
            )
        ],
    )
    validate_and_rank(synthesis, {"r1": "a", "r2": "b"})
    assert synthesis.recommendations[0].priority_score == 2
    synthesis.recommendations[0].finding_ids = ["invented"]
    with pytest.raises(ValueError, match="unknown finding"):
        validate_and_rank(synthesis, {"r1": "a", "r2": "b"})
    synthesis.recommendations = []
    validate_and_rank(synthesis, {"r1": "a", "r2": "b"})


def test_wishes_cannot_become_experience_findings(tmp_path):
    from pathlib import Path

    from genesia.insights import analysis_input, validate_citations
    from genesia.reports import render
    from genesia.runtime import EvidenceStore

    task = task_fixture(tmp_path)
    result = run(task, gateway=ScriptedModel())
    rows = analysis_input(task, result.responses, result.episodes)["rows"]
    finding = result.synthesis.findings[0]
    for row in rows:
        if row["answer_id"] in finding.answer_ids:
            row["question"]["purpose"] = "reflection"
    with pytest.raises(ValueError, match="not only context or wishes"):
        validate_citations(result.synthesis, rows)
    finding.category = "opportunity"
    validate_citations(result.synthesis, rows)
    result.synthesis.recommendations[0].kind = "design_change"
    with pytest.raises(ValueError, match="enhancements or investigations"):
        validate_citations(result.synthesis, rows)
    result.synthesis.recommendations[0].kind = "enhancement"
    validate_citations(result.synthesis, rows)
    store = EvidenceStore(Path(result.output_dir))
    finding.feedback_type = "suggestion"
    result.synthesis.recommendation_order = "score"
    assert "## User Suggestions" in render(result, store)
    assert "Source questions" in render(result, store, html_output=True)


def test_final_composition_explains_recommendation_kind_evidence(tmp_path):
    from genesia.insight_report import _composition_payload

    payload = _composition_payload(
        task_fixture(tmp_path),
        {
            "goal": "Review a prototype",
            "prototype": {},
            "statistics": {"basis": "descriptive", "questions": []},
        },
        [],
        final=True,
    )

    assert "Use kind=design_change only" in payload["instruction"]
    assert "kind=enhancement or kind=investigate" in payload["instruction"]


def test_composition_feedback_types_follow_actual_source_questions(tmp_path):
    from genesia.insight_report import _composition_payload, _composition_schema

    task = task_fixture(tmp_path)
    source = {
        "goal": "Review",
        "prototype": {},
        "statistics": {"basis": "Synthetic", "questions": []},
        "rows": [
            {
                "answer_id": "useful",
                "persona_id": "p1",
                "method_id": "m",
                "question_id": "q1",
                "status": "answered",
                "question": {"purpose": "experience", "feedback_role": "verdict"},
            },
            {
                "answer_id": "suggest",
                "persona_id": "p2",
                "method_id": "m",
                "question_id": "q2",
                "status": "answered",
                "question": {"purpose": "reflection", "feedback_role": "suggestion"},
            },
        ],
    }
    packets = [{"id": "useful-f1", "answer_ids": ["useful"], "counter_answer_ids": []}]
    payload = _composition_payload(task, source, packets, final=False)
    assert payload["answer_owners"] == {"useful": "p1"}
    assert payload["source_findings"][0]["allowed_feedback_types"] == [
        "neutral",
        "positive",
        "friction",
        "mixed",
    ]
    assert "allowed_feedback_types" not in packets[0]
    schema = _composition_schema(task, payload, final=False)
    draft = {
        "summary": "Mixed usefulness",
        "limitations": "Static material",
        "recommendations": [],
        "findings": [
            {
                "id": "f1",
                "source_finding_ids": ["useful-f1"],
                "text": "A qualified judgment",
                "category": "experience",
                "feedback_type": "mixed",
            }
        ],
    }
    schema.model_validate(draft)
    for unsupported in ("preference", "suggestion"):
        draft["findings"][0]["feedback_type"] = unsupported
        with pytest.raises(ValueError):
            schema.model_validate(draft)
    final = _composition_payload(task, source, packets, final=True)
    assert final["answer_owners"] == {"useful": "p1", "suggest": "p2"}


def test_reduction_groups_over_soft_target_without_singleton_model_calls():
    from genesia.insight_report import _reduction_batches

    packets = list(range(5))
    batches = _reduction_batches(packets, 10, 30, lambda items: 12 + len(items) * 8)
    assert batches == [[0, 1], [2, 3], [4]]
    assert [item for batch in batches for item in batch] == packets
    with pytest.raises(ValueError, match="two source findings"):
        _reduction_batches(packets, 10, 25, lambda items: 12 + len(items) * 8)


def test_reduction_namespaces_findings_and_preserves_all_answer_owners(tmp_path, monkeypatch):
    import genesia.insight_report as reports
    from genesia.runtime import EvidenceStore

    task = task_fixture(tmp_path)
    task.insight.context_window = 20000
    task.insight.input_budget_ratio = 0.8
    task.insight.chunk_target_tokens = 12000
    task.model.max_tokens = 1000
    source = run(task, gateway=ScriptedModel(), research_only=True)

    def prompt(_purpose, payload, _schema):
        stage = payload.get("output_stage")
        count = len(payload.get("source_findings", []))
        if stage == "insight_report":
            return "x" * (14000 if count > 2 else 4000)
        if stage == "insight_reduce":
            return "x" * (8000 + 1800 * count)
        return "x" * 1000

    monkeypatch.setattr(reports, "model_prompt", prompt)
    model = ScriptedModel()
    result, provenance = reports.synthesize_insight_report(
        task, source.responses, source.episodes, model, EvidenceStore(tmp_path / "reduction")
    )
    reductions = [p for _, p in model.calls if p.get("output_stage") == "insight_reduce"]
    assert len(reductions) == 2 and all(len(p["source_findings"]) == 2 for p in reductions)
    final = next(p for _, p in model.calls if p.get("output_stage") == "insight_report")
    identifiers = [p["id"] for p in final["source_findings"]]
    assert len(set(identifiers)) == len(identifiers) == 2
    assert all(value.startswith("insight-reduce-1-") for value in identifiers)
    assert len(result.findings[0].answer_ids) == 12
    assert provenance["status"] == "completed"
    assert all(s["estimated_tokens"] <= provenance["input_budget"] for s in provenance["stages"])


def test_reflection_batch_schema_constrains_categories():
    from pydantic import ValidationError

    from genesia.insights import synthesis_schema

    schema = synthesis_schema([{"question": {"purpose": "reflection"}}])
    data = {
        "summary": "No change needed",
        "limitations": "Synthetic",
        "findings": [
            {
                "text": "No change needed",
                "participants": ["p1"],
                "evidence_refs": ["r1"],
                "category": "experience",
            }
        ],
    }
    with pytest.raises(ValidationError):
        schema.model_validate(data)
    data["findings"][0]["category"] = "opportunity"
    assert schema.model_validate(data).findings[0].category == "opportunity"


def test_candidate_schema_omits_quotations_and_recommendations():
    from genesia.insights import synthesis_schema

    schema = synthesis_schema([{"question": {"purpose": "experience"}}], draft=True, max_findings=2)
    data = dict(
        summary="Draft",
        limitations="Synthetic",
        findings=[
            dict(
                id="f1",
                text="Visible feedback",
                answer_ids=["a1"],
                quotes=[dict(answer_id="a1", text="Quote")],
            )
        ],
    )
    with pytest.raises(ValueError):
        schema.model_validate(data)
    data["findings"][0]["quotes"] = []
    assert schema.model_validate(data).findings


def test_schema_derives_response_ownership_and_preserves_counterevidence():
    from genesia.insights import synthesis_schema, validate_citations

    rows = [
        dict(
            answer_id=f"a{index}",
            response_ref=f"r{index}",
            persona_id=f"p{index}",
            status="answered",
            question={"purpose": "experience"},
            value="Clear",
        )
        for index in range(2)
    ]
    value = synthesis_schema(rows).model_validate(
        dict(
            summary="Visible feedback",
            limitations="Synthetic",
            findings=[dict(id="f1", text="Clear", answer_ids=["a0"], counter_answer_ids=["a1"])],
        )
    )
    validate_citations(value, rows)
    assert value.findings[0].participants == ["p0"]
    assert value.findings[0].evidence_refs == ["r0"]
    assert value.findings[0].counter_answer_ids == ["a1"]
    value.findings[0].scope_status = "prototype_limit"
    with pytest.raises(ValueError, match="belong in limitations"):
        validate_citations(value, rows)


def test_candidate_validation_derives_ownership_from_answer_ids():
    from genesia.insights import normalize_candidate, synthesis_schema, validate_citations

    rows = [
        dict(
            answer_id="a0",
            response_ref="r0",
            persona_id="p0",
            status="answered",
            question={"purpose": "experience", "feedback_role": "preference"},
            value="Clear",
        )
    ]
    schema = synthesis_schema(rows, draft=True)
    value = schema.model_validate(
        dict(
            summary="Clear",
            limitations="Synthetic",
            findings=[
                dict(
                    id="f1",
                    text="Clear",
                    answer_ids=["a0", "foreign-answer"],
                    counter_answer_ids=["a0", "foreign-counter"],
                    participants=["invented"],
                    evidence_refs=["invented"],
                    feedback_type="friction",
                    category="preference",
                    journey_stage="decision",
                )
            ],
        )
    )
    normalize_candidate(value, rows)
    validate_citations(value, rows)
    assert value.findings[0].participants == ["p0"]
    assert value.findings[0].evidence_refs == ["r0"]
    assert value.findings[0].answer_ids == ["a0"]
    assert value.findings[0].counter_answer_ids == []
    assert value.findings[0].category == "experience"

    reflection_rows = [
        {
            **rows[0],
            "question": {"purpose": "reflection", "feedback_role": "suggestion"},
        }
    ]
    reflection = synthesis_schema(reflection_rows, draft=True).model_validate(
        dict(
            summary="Optional change",
            limitations="Synthetic",
            findings=[
                dict(
                    id="drop-positive",
                    text="No change needed",
                    answer_ids=["a0"],
                    participants=["invented"],
                    evidence_refs=["invented"],
                    feedback_type="positive",
                    category="experience",
                    journey_stage="overall",
                ),
                dict(
                    id="drop-prototype-limit",
                    text="Complete the prototype",
                    answer_ids=["a0"],
                    counter_answer_ids=["a0"],
                    participants=["invented"],
                    evidence_refs=["invented"],
                    feedback_type="suggestion",
                    category="experience",
                    journey_stage="unrecognized-stage",
                    scope_status="prototype_limit",
                ),
                dict(
                    id="f2",
                    text="Optional change",
                    answer_ids=["a0"],
                    participants=["invented"],
                    evidence_refs=["invented"],
                    feedback_type="suggestion",
                    category="experience",
                    journey_stage="overall",
                ),
            ],
        )
    )
    normalize_candidate(reflection, reflection_rows)
    validate_citations(reflection, reflection_rows)
    assert [finding.id for finding in reflection.findings] == ["f2"]
    assert reflection.findings[0].category == "opportunity"


@pytest.mark.parametrize("recommendation_order", ["score", "decision"])
def test_report_shares_explanations_counterexamples_and_counts(tmp_path, recommendation_order):
    from pathlib import Path

    from genesia.insights import analysis_input
    from genesia.reports import render
    from genesia.runtime import EvidenceStore

    task = task_fixture(tmp_path)
    result = run(task, gateway=ScriptedModel())
    finding = result.synthesis.findings[0]
    finding.interpretation = "A tentative <explanation>"
    finding.design_implication = "Preserve visible feedback"
    finding.uncertainty = "Not a claim about every user"
    rows = analysis_input(task, result.responses, result.episodes)["rows"]
    finding.counter_answer_ids = [rows[-1]["answer_id"]]
    result.synthesis.recommendation_order = recommendation_order
    saved_synthesis = result.synthesis.model_dump()
    store = EvidenceStore(Path(result.output_dir))
    markdown = render(result, store)
    html = render(result, store, html_output=True)
    label = (
        "Evidence contributors: 3 from cited supporting answers; 1 from cited counter answers. "
        "These sets may overlap and are not votes on every claim."
    )
    assert label in markdown
    assert label in html
    assert "3 supporting Personas" not in markdown
    assert "from cited counter answers: p" not in markdown
    assert "A tentative &lt;explanation&gt;" in html
    assert "Preserve visible feedback" in markdown
    if recommendation_order == "score":
        assert "Eligible answers: 12" in markdown
    else:
        assert "Analysis coverage: 12/12 eligible answers" in markdown
    assert result.synthesis.model_dump() == saved_synthesis


def test_numeric_bucket_segments_remain_structured_without_main_report_tables(tmp_path):
    import json
    from pathlib import Path

    from genesia.reports import render
    from genesia.runtime import EvidenceStore
    from genesia.schemas import Question, StudySpec

    task = task_fixture(tmp_path)
    Path(task.cohort.source).write_text(
        json.dumps(
            [
                {"id": f"p{index}", "profile": {"Core Identity": {"age": age, "region": "Europe"}}}
                for index, age in enumerate((25, 35, 45))
            ]
        ),
        "utf-8",
    )
    task.cohort.size = 3
    task.methods[0].questions[0] = Question(
        id="q1", text="How clear was it?", kind="single", options=["Clear", "Unclear"]
    )
    task.study = StudySpec.model_validate(
        {
            "segments": {
                "age_group": {
                    "source": "Core Identity.age",
                    "buckets": ["<30", "30-39", "40-49", "50+"],
                },
                "region": {"source": "Core Identity.region"},
            },
            "segment_combinations": {"region_age": ["region", "age_group"]},
        }
    )

    result = run(task, gateway=ScriptedModel())
    statistics = result.metrics["descriptive_statistics"]["questions"][0]
    groups = statistics["segments"]["age_group"]
    assert list(groups) == ["<30", "30-39", "40-49", "50+"]
    assert all(groups[label]["counts"] == {"Clear": 1} for label in ("<30", "30-39", "40-49"))
    assert groups["50+"]["counts"] == {} and groups["50+"]["n_answered"] == 0
    assert all(group["small_sample"] is True for group in groups.values())
    assert statistics["segments"]["region"]["Europe"]["counts"] == {"Clear": 3}
    joint = statistics["segments"]["region_age"][json.dumps(["Europe", "<30"])]
    assert joint["counts"] == {"Clear": 1}
    assert joint["dimensions"] == {"region": "Europe", "age_group": "<30"}

    store = EvidenceStore(Path(result.output_dir))
    markdown = render(result, store)
    html = render(result, store, html_output=True)
    assert "## Segment Analysis" not in markdown
    assert "Segment Analysis" not in html
    assert "Segment Feedback" not in html
    assert '"age_group"' in result.model_dump_json()


def test_candidate_report_keeps_conclusions_not_persona_lists(tmp_path):
    from pathlib import Path

    from genesia.reports import render
    from genesia.runtime import EvidenceStore

    task = task_fixture(tmp_path)
    for index, method in enumerate(task.methods):
        method.questions[0].candidate = "Version A" if index < 2 else "Version B"
        method.questions[0].feedback_role = "journey" if index % 2 == 0 else "suggestion"
    result = run(task, gateway=ScriptedModel())
    assert result.status == "completed", result.errors
    result.synthesis.recommendation_order = "score"
    text = render(result, EvidenceStore(Path(result.output_dir)))
    assert "## Version A Feedback" in text and "## Version B Feedback" in text
    assert "## Cross-Candidate Findings" in text
    assert "## Participant Summaries" not in text


def test_live_feedback_report_leads_with_findings_and_keeps_raw_feedback_in_appendix(tmp_path):
    from pathlib import Path

    from genesia.reports import render
    from genesia.runtime import EvidenceStore

    task = task_fixture(tmp_path)
    task.methods[0].questions[0].feedback_role = "overall"
    result = run(task, gateway=ScriptedModel())
    finding = result.synthesis.findings[0]
    finding.feedback_type = "positive"
    finding.journey_stage = "overall"
    finding.interpretation = "Immediate feedback made the state easier to understand."
    finding.design_implication = "Keep the state visible while choices are revised."
    finding.uncertainty = "This is synthetic feedback."
    result.synthesis.recommendation_order = "score"
    store = EvidenceStore(Path(result.output_dir))
    markdown = render(result, store)
    html = render(result, store, html_output=True)
    assert markdown.index("## Executive Summary") < markdown.index("## Recommended Actions")
    assert markdown.index("## Recommended Actions") < markdown.index("## Shared Findings")
    assert markdown.index("## Shared Findings") < markdown.index("## Confidence & Limitations")
    assert "## Participant Summaries" not in markdown
    assert "Participant Summaries" not in html
    assert "### Decision Snapshot" in markdown and "## Shared Findings" in markdown
    assert "Immediate feedback made the state easier to understand." in markdown
    assert "Recommended action" in markdown
    assert 'class="decision-grid"' in html and html.count('class="insight-card"') == 1
    assert 'class="recommendation"' in html
    assert html.count('name="participant-feedback"') == 0
    assert "Feedback type:" not in markdown
    assert "Shared Findings" in html and "Responses, evidence and technical details" in html


def test_feedback_report_keeps_unavailable_product_feedback_out_of_main_report(tmp_path):
    from pathlib import Path

    from genesia.insights import analysis_input
    from genesia.reports import render
    from genesia.runtime import EvidenceStore, write_json

    task = task_fixture(tmp_path)
    task.methods[0].questions[0].feedback_role = "overall"
    result = run(task, gateway=ScriptedModel())
    result.responses[0].answers[0].basis = "automation"
    source = analysis_input(task, result.responses, result.episodes)
    store = EvidenceStore(Path(result.output_dir))
    input_ref = store.json(source, "analysis_input")
    result.report.analysis["input_ref"] = input_ref
    write_json(Path(result.output_dir) / "research_result.json", result)
    markdown = render(result, store)
    assert source["rows"][0]["status"] == "automation"
    assert "No post-use product feedback was available" not in markdown
    assert "Automation only" not in markdown


def test_feedback_schema_requires_evaluative_type_and_journey_stage():
    from pydantic import ValidationError

    from genesia.insights import synthesis_schema

    rows = [{"question": {"purpose": "experience", "feedback_role": "friction"}}]
    schema = synthesis_schema(rows)
    with pytest.raises(ValidationError):
        schema.model_validate(
            dict(summary="Feedback", limitations="Synthetic", findings=[dict(text="Issue")])
        )
    value = schema.model_validate(
        dict(
            summary="Feedback",
            limitations="Synthetic",
            findings=[dict(text="Control was unclear", feedback_type="friction", journey_stage="comparison")],
        )
    )
    assert value.findings[0].feedback_type == "friction"


@pytest.mark.parametrize(
    "feedback_type,category,role",
    [
        ("positive", "experience", "strength"),
        ("friction", "experience", "friction"),
        ("preference", "preference", "preference"),
        ("suggestion", "opportunity", "suggestion"),
    ],
)
def test_feedback_findings_require_matching_participant_evaluation(feedback_type, category, role):
    from genesia.insights import validate_citations

    row = {
        "answer_id": "a1",
        "status": "answered",
        "response_ref": "r1",
        "persona_id": "p1",
        "question": {"purpose": "experience", "feedback_role": "context"},
        "value": "I clicked a control",
    }
    finding = dict(
        id="f1",
        text="Participant evaluation",
        participants=["p1"],
        answer_ids=["a1"],
        evidence_refs=["r1"],
        feedback_type=feedback_type,
        category=category,
    )
    value = Synthesis(summary="Feedback", limitations="Synthetic", findings=[finding])
    with pytest.raises(ValueError, match="matching participant feedback question"):
        validate_citations(value, [row])
    row["question"]["feedback_role"] = role
    if feedback_type == "suggestion":
        row["question"]["purpose"] = "reflection"
    validate_citations(value, [row])


def test_automation_answers_remain_auditable_but_do_not_enter_synthesis(tmp_path):
    from pathlib import Path

    from genesia.insight_report import synthesize_insight_report
    from genesia.insights import analysis_input
    from genesia.runtime import EvidenceStore

    task = task_fixture(tmp_path)
    result = run(task, gateway=ScriptedModel())
    response = result.responses[0]
    answer = response.answers[0]
    answer.basis = "automation"
    source = analysis_input(task, result.responses, result.episodes)
    row = next(
        row
        for row in source["rows"]
        if row["persona_id"] == response.persona_id and row["method_id"] == response.method_id
    )
    assert row["status"] == "automation"
    model = ScriptedModel()
    synthesize_insight_report(
        task,
        result.responses,
        result.episodes,
        model,
        EvidenceStore(Path(tmp_path) / "analysis"),
    )
    assert all(
        row["basis"] != "automation"
        for purpose, payload in model.calls
        if purpose == "research_synthesis"
        for row in payload.get("rows", [])
    )


def test_final_synthesis_schema_rejects_ids_outside_selected_rows():
    from pydantic import ValidationError

    from genesia.insights import synthesis_schema

    rows = [
        {
            "answer_id": "a1",
            "persona_id": "p1",
            "response_ref": "r1",
            "question": {"purpose": "experience"},
        }
    ]
    schema = synthesis_schema(rows)
    valid = {
        "summary": "Summary",
        "limitations": "Synthetic",
        "findings": [
            {
                "id": "f1",
                "text": "Supported",
                "answer_ids": ["a1"],
                "participants": ["p1"],
                "evidence_refs": ["r1"],
            }
        ],
    }
    assert schema.model_validate(valid).findings[0].answer_ids == ["a1"]
    valid["findings"][0]["answer_ids"] = ["excluded"]
    with pytest.raises(ValidationError):
        schema.model_validate(valid)


def test_descriptive_counts_do_not_infer_significance(tmp_path):
    result = run(task_fixture(tmp_path), gateway=ScriptedModel())
    stats = result.metrics["descriptive_statistics"]
    assert "no statistical significance" in stats["basis"]
    assert all(question["n_answered"] == 3 for question in stats["questions"])
    assert result.synthesis.recommendations


def test_analysis_input_stable_ids_and_missing_ledger(tmp_path):
    from genesia.insights import analysis_input

    task = task_fixture(tmp_path)
    result = run(task, gateway=ScriptedModel())
    source = analysis_input(task, result.responses[:-1], result.episodes)
    assert len(source["rows"]) == 12
    assert len({row["answer_id"] for row in source["rows"]}) == 12
    assert source == analysis_input(task, result.responses[:-1], result.episodes)
    assert sum(row["status"] == "missing" for row in source["rows"]) == 1
    assert all(item["n_selected"] == 3 for item in source["question_quality"])


@pytest.mark.parametrize("refs", [["r1", "frame1"], ["frame1"], ["r1", "r2"]])
def test_citation_errors_identify_finding_and_expected_response_refs(refs):
    from genesia.insights import validate_citations

    rows = [
        {
            "answer_id": "a1",
            "status": "answered",
            "response_ref": "r1",
            "persona_id": "p1",
            "question": {"purpose": "experience"},
            "evidence_refs": ["frame1"],
        }
    ]
    value = Synthesis(
        summary="Synthetic account",
        limitations="Synthetic",
        findings=[dict(id="f1", text="Account", participants=["p1"], answer_ids=["a1"], evidence_refs=refs)],
    )
    with pytest.raises(ValueError, match="Finding f1 response refs") as error:
        validate_citations(value, rows)
    assert "expected ['r1']" in str(error.value)
    assert "not screenshot/observation evidence_refs" in str(error.value)
    assert value.findings[0].evidence_refs == refs
    value.findings[0].evidence_refs = ["r1"]
    validate_citations(value, rows)


def test_quotes_must_match_answer(tmp_path):
    from genesia.insights import analysis_input, validate_citations

    task = task_fixture(tmp_path)
    result = run(task, gateway=ScriptedModel())
    rows = analysis_input(task, result.responses, result.episodes)["rows"]
    finding = result.synthesis.findings[0]
    row = next(row for row in rows if row["response_ref"] in finding.evidence_refs)
    finding.answer_ids = [row["answer_id"]]
    finding.evidence_refs = [row["response_ref"]]
    finding.participants = [row["persona_id"]]
    finding.quotes = [{"answer_id": row["answer_id"], "text": "invented quotation"}]
    value = Synthesis.model_validate(result.synthesis.model_dump())
    with pytest.raises(ValueError, match="original answer"):
        validate_citations(value, rows)
