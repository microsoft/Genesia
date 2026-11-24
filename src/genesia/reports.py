"""Offline report rendering. All prose and counts come from the saved result."""

import html
import json
from urllib.parse import quote

STYLE = """
:root { color-scheme: light; --ink:#202a28; --muted:#5e6865; --accent:#076c5c;
--line:#d8dfdb; --paper:#fff; --wash:#f2f5f3; --warning:#a33d23; }
* { box-sizing:border-box; letter-spacing:0; }
body { margin:0; color:var(--ink); background:var(--wash);
font:16px/1.65 'Segoe UI', sans-serif; }
header { border-top:6px solid var(--accent); background:var(--paper); padding:32px max(24px,calc((100% - 1100px)/2)); }
header p { color:var(--muted); margin:8px 0; }
h1 { font:600 32px/1.2 Georgia,serif; margin:12px 0; overflow-wrap:anywhere; }
h2 { font-size:23px; line-height:1.3; margin:0 0 20px; }
h3 { font-size:18px; line-height:1.4; }
.label { color:var(--warning); font-size:12px; font-weight:700; text-transform:uppercase; }
.layout { display:grid; grid-template-columns:210px minmax(0,1fr); gap:40px;
max-width:1148px; margin:auto; padding:32px 24px; }
nav { position:sticky; top:20px; align-self:start; font-size:14px; }
nav a { display:block; padding:6px 0; }
.mobile-nav { display:none; }
a { color:var(--accent); text-underline-offset:3px; overflow-wrap:anywhere; }
main { min-width:0; }
section { padding:28px 0; border-bottom:1px solid var(--line); scroll-margin-top:20px; }
section:first-child { padding-top:0; }
p,li,td,pre,figcaption { overflow-wrap:anywhere; }
article { border-left:3px solid var(--accent); padding:4px 0 4px 20px; margin:24px 0; }
.meta { font-size:13px; color:var(--muted); }
.decision-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; margin:24px 0; }
.decision-metric { border:1px solid var(--line); background:var(--paper); padding:16px; }
.decision-metric strong { display:block; font:600 22px/1.25 Georgia,serif; margin-top:4px; }
.insight-card { border-left:4px solid var(--accent); background:var(--paper); padding:18px 20px; margin:16px 0; }
.insight-card h3 { margin:0 0 10px; }
.insight-card p { margin:8px 0; }
.evidence-count { display:inline-block; color:var(--accent); font-weight:700; margin-bottom:8px; }
.recommendation { border:1px solid var(--line); background:var(--paper); padding:18px 20px; margin:16px 0; }
.recommendation h3 { margin:6px 0 10px; }
.recommendation .label { color:var(--accent); }
.participant-list { margin-top:20px; }
.participant { border:1px solid var(--line); background:var(--paper); margin:8px 0; }
.participant summary { display:flex; justify-content:space-between; gap:16px; padding:14px 16px; cursor:pointer; }
.participant summary strong { font-size:16px; }
.participant dl { border-top:1px solid var(--line); margin:0; padding:4px 16px 16px; }
.participant dt { margin-top:14px; }
.participant dd { margin:4px 0 0; }
blockquote { border-left:2px solid var(--line); margin:16px 0; padding-left:16px; }
figure { margin:20px 0; } img { display:block; width:100%; max-height:500px; object-fit:contain;
object-position:left; background:white; border:1px solid var(--line); }
figcaption { color:var(--muted); font-size:13px; }
.table { overflow-x:auto; } table { width:100%; border-collapse:collapse; font-size:14px; }
th,td { text-align:left; padding:10px; border-bottom:1px solid var(--line); vertical-align:top; }
th { background:#e7eeea; } pre { white-space:pre-wrap; font-size:12px; }
details { margin:12px 0; } summary { cursor:pointer; font-weight:600; }
@media(max-width:760px) { .layout { display:block; padding:24px 18px; }
nav { position:static; border-bottom:1px solid var(--line); padding-bottom:20px; margin-bottom:24px; }
.desktop-nav { display:none; } .mobile-nav { display:block; margin:0; }
header { padding:24px 18px; } h1 { font-size:28px; } }
@media print { body,header { background:white; } .layout { display:block; } nav { display:none; }
article,figure { break-inside:avoid; } a { color:inherit; } }
"""


def report_sections(result, store):
    """Build English report chrome without translating research content."""
    context = result.report
    synthesis = result.synthesis
    manifest_path = store.root / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text("utf-8")) if manifest_path.is_file() else {}
    coherent = bool(synthesis and synthesis.recommendation_order == "decision")
    answer_index = {}
    source = {}
    if context and (input_ref := context.analysis.get("input_ref")) and input_ref in store.refs:
        source = json.loads(store.path(input_ref).read_text("utf-8"))
        answer_index = {row["answer_id"]: row for row in source["rows"]}
    sections = []

    def section(title, paragraphs=(), items=(), table=None):
        block = {
            "title": title,
            "paragraphs": list(paragraphs),
            "items": list(items),
            "table": table,
            "findings": [],
            "feedback_profiles": [],
            "snapshot": [],
            "executive_findings": [],
            "recommendations": [],
            "feedback_groups": [],
            "compact_feedback": False,
        }
        sections.append(block)
        return block

    stats = result.metrics.get("descriptive_statistics", {})
    findings = synthesis.findings + synthesis.segment_differences if synthesis else []
    candidates = list(
        dict.fromkeys(
            row["question"]["candidate"] for row in answer_index.values() if row["question"].get("candidate")
        )
    )
    configured_candidates = candidates or manifest.get("task", {}).get("environment", {}).get(
        "candidate_labels", []
    )

    def recommendation_target(item):
        targets = {
            finding.candidate for finding in findings if finding.id in item.finding_ids and finding.candidate
        }
        if len(targets) == 1:
            return next(iter(targets))
        if len(configured_candidates) > 1:
            return "Cross-version"
        if configured_candidates:
            return configured_candidates[0]
        return "This study"

    eligible_answers = context.analysis.get("n_eligible_answers", 0) if context else 0
    reviewed_answers = len(set(context.analysis.get("reviewed_answer_ids", []))) if context else 0
    executive = section(
        ("Summary") if coherent else ("Executive Summary"),
        [
            synthesis.summary
            if synthesis
            else "Analysis is unavailable. This report preserves the available responses and failure details; no conclusions were invented."
        ],
        [
            ("Synthetic Persona feedback, not research with real participants or a population estimate."),
        ],
    )
    if coherent:
        executive["items"] = list(synthesis.summary_points) + executive["items"]
        if result.errors:
            executive["items"].extend(result.errors)
        if manifest.get("source_status") in {"partial", "failed"}:
            executive["items"].append(
                f"Source status: {manifest['source_status']}; see analysis lineage in the evidence section."
            )
    executive["snapshot"] = [
        {
            "label": "Valid responses",
            "value": str(result.metrics.get("valid_responses", 0)),
        },
    ]
    if coherent:
        executive["snapshot"] = []
    for item in stats.get("questions", []):
        if item.get("counts"):
            executive["snapshot"].append(
                {
                    "label": item["question_id"].replace("_", " ").title(),
                    "value": " · ".join(
                        f"{option}: {count} ({item['percent_of_answered'].get(option, 0)}%)"
                        for option, count in item["counts"].items()
                    ),
                }
            )
    recommendation_block = section(
        ("Next actions") if coherent else ("Recommended Actions"),
        ["Prioritized from the evidence; ranking is decision support, not measured impact."],
    )
    recommendation_block["recommendations"] = (
        [
            {
                "rank": index,
                "action": item.action,
                "kind": item.kind,
                "rationale": item.rationale,
                "finding_ids": item.finding_ids,
                "target": recommendation_target(item),
                "priority": item.priority_score,
                "confidence": item.confidence,
            }
            for index, item in enumerate(synthesis.recommendations, 1)
        ]
        if synthesis
        else []
    )
    role_labels = {
        "context": "Relevant context",
        "overall": "Overall reaction",
        "journey": "Journey feedback",
        "strength": "What worked",
        "friction": "Friction",
        "comparison": "Comparison and control",
        "preference": "Preference and tradeoff",
        "design": "Design critique",
        "suggestion": "Suggestion",
        "verdict": "Final verdict",
    }
    role_rows = [row for row in answer_index.values() if row.get("question", {}).get("feedback_role")]
    feedback_profiles = []
    if role_rows:
        for episode in result.episodes:
            entries = [
                {
                    "role": role_labels[row["question"]["feedback_role"]],
                    "candidate": row["question"].get("candidate"),
                    "kind": row["question"].get("kind", "text"),
                    "feedback_role": row["question"]["feedback_role"],
                    "question_id": row["question_id"],
                    "value": row["value"],
                    "reason": row.get("reason", ""),
                    "basis": row["basis"],
                }
                for row in role_rows
                if row["persona_id"] == episode.persona.id and row.get("status") == "answered"
            ]
            product_entries = [entry for entry in entries if entry["role"] != role_labels["context"]]
            unavailable = [
                row
                for row in role_rows
                if row["persona_id"] == episode.persona.id
                and row["question"].get("feedback_role") != "context"
                and row.get("status") != "answered"
            ]
            note = (
                "No post-use product feedback was available; product questions were automation-only, not observed or unanswered."
                if not product_entries
                else f"{len(unavailable)} product feedback topic(s) were unavailable."
                if unavailable
                else ""
            )
            if entries or note:
                selected = [
                    entry
                    for entry in product_entries
                    if entry["feedback_role"] != "preference" and entry["kind"] == "text"
                ]
                if not selected:
                    selected = [
                        dict(entry, value=entry["reason"]) for entry in product_entries if entry["reason"]
                    ]
                priority = {
                    "preference": 0,
                    "verdict": 0,
                    "friction": 1,
                    "suggestion": 2,
                    "comparison": 3,
                    "strength": 4,
                    "design": 5,
                    "journey": 6,
                    "overall": 7,
                }
                ranked = sorted(
                    selected,
                    key=lambda entry: (priority.get(entry["feedback_role"], 8), entry["question_id"]),
                )
                chosen = []
                for candidate in dict.fromkeys(entry["candidate"] for entry in ranked if entry["candidate"]):
                    chosen.append(next(entry for entry in ranked if entry["candidate"] == candidate))
                for entry in ranked:
                    if entry not in chosen:
                        chosen.append(entry)
                selected = chosen[:3]
                if len(product_entries) > len(selected):
                    note = " ".join(
                        filter(
                            None,
                            [note, "Additional original feedback remains available in the appendix."],
                        )
                    )
                for entry in selected:
                    if entry["candidate"]:
                        entry["role"] = f"{entry['candidate']} - {entry['role']}"
                attributes = next(
                    (
                        item["attributes"]
                        for item in source.get("participant_context", [])
                        if item["persona_id"] == episode.persona.id
                    ),
                    {},
                )
                relevant = "; ".join(
                    str(attributes[key])
                    for key in ("job_category", "industry", "seniority")
                    if attributes.get(key) and str(attributes[key]).casefold() != "unknown"
                )
                if relevant:
                    note = " ".join(filter(None, [f"Supplied background: {relevant}.", note]))
                feedback_profiles.append(
                    {"persona_id": episode.persona.id, "entries": selected, "note": note}
                )
    candidate_blocks = {}
    if coherent:
        findings_block = section("Findings")
        findings_block["compact_feedback"] = True
        finding_blocks = {}
    elif role_rows:
        for candidate in candidates:
            block = section(
                f"{candidate} Feedback",
                ["Reviewed strengths, difficulties and opportunities for this candidate."],
            )
            block["compact_feedback"] = True
            candidate_blocks[candidate] = block
        findings_block = section(
            "Cross-Candidate Findings" if candidates else "Shared Findings",
            [
                (
                    "Cross-participant conclusions from reviewed feedback. Detailed questions, answers and evidence remain in the appendix and structured files."
                )
            ],
        )
        findings_block["compact_feedback"] = True
        finding_blocks = {}
    else:
        feedback_titles = {
            "positive": "Design Strengths",
            "friction": "Friction and Unmet Needs",
            "mixed": "Mixed Feedback",
            "preference": "Preferences and Tradeoffs",
            "suggestion": "User Suggestions",
            "neutral": "Key Findings",
        }
        finding_blocks = {
            feedback_type: section(
                title,
                ["Cross-participant synthesis grounded in the saved research evidence."],
            )
            for feedback_type, title in feedback_titles.items()
            if any(finding.feedback_type == feedback_type for finding in findings)
        }
        findings_block = None
    for finding in findings:
        refs = []
        counter_refs = [
            answer_index[ref]["response_ref"] for ref in finding.counter_answer_ids if ref in answer_index
        ]
        for ref in dict.fromkeys(finding.evidence_refs + counter_refs):
            if ref in store.refs:
                refs.append((ref, store.refs[ref].path))
        pictures = []
        cited_observations = set()
        for answer_id in finding.answer_ids:
            cited_observations.update(answer_index.get(answer_id, {}).get("evidence_refs", []))
        for episode in result.episodes:
            if episode.persona.id not in finding.participants:
                continue
            for observation in [step.observation for step in episode.steps] + (
                [episode.final_observation] if episode.final_observation else []
            ):
                if not cited_observations.intersection(observation.evidence_refs):
                    continue
                for ref in observation.image_refs:
                    if ref in store.refs and store.refs[ref].path not in [item[1] for item in pictures]:
                        pictures.append(
                            (
                                f"{episode.persona.id}: {observation.url or observation.id}",
                                store.refs[ref].path,
                            )
                        )
        counter_participants = sorted(
            {answer_index[ref]["persona_id"] for ref in finding.counter_answer_ids if ref in answer_index}
        )
        mixed_participants = sorted(set(finding.participants).intersection(counter_participants))
        finding_data = {
            "id": finding.id,
            "title": (
                f"{finding.candidate} - {finding.title or finding.text}"
                if coherent and finding.candidate
                else finding.title or finding.text
            ),
            "coherent": coherent,
            "text": finding.text,
            "claim_type": finding.claim_type,
            "category": finding.category,
            "feedback_type": finding.feedback_type,
            "journey_stage": finding.journey_stage,
            "interpretation": finding.interpretation,
            "design_implication": finding.design_implication,
            "uncertainty": finding.uncertainty,
            "evidence_details": finding.evidence_details,
            "scope_status": finding.scope_status,
            "questions": list(
                dict.fromkeys(
                    f"{row['method_id']} / {row['question_id']} ({row['question'].get('purpose', 'experience')}): {row['question']['text']}"
                    for ref in finding.answer_ids + finding.counter_answer_ids
                    if (row := answer_index.get(ref))
                )
            ),
            "participants": finding.participants,
            "support_count": len(set(finding.participants)),
            "counter_participants": counter_participants,
            "mixed_participants": mixed_participants,
            "answers": finding.answer_ids,
            "quotes": [item.model_dump() for item in finding.quotes],
            "refs": refs,
            "pictures": pictures[:2],
        }
        block = (
            candidate_blocks.get(finding.candidate) or findings_block or finding_blocks[finding.feedback_type]
        )
        block["findings"].append(finding_data)
    boundaries = list(
        dict.fromkeys(
            limitation
            for episode in result.episodes
            if episode.prototype
            for limitation in episode.prototype.known_limitations
        )
    )
    if role_rows or coherent:
        coverage = context.analysis.get("exploration_coverage", {}) if context else {}
        steps = coverage.get("steps", {})
        exposure = coverage.get("candidate_exposure", {})
        segment_counts = context.analysis.get("segment_counts", {}) if context else {}
        coverage_items = []
        if coverage:
            coverage_items.append(
                (
                    f"Exploration coverage: {coverage.get('participants', 0)} Personas, "
                    f"{steps.get('minimum', 0)}–{steps.get('maximum', 0)} steps each "
                    f"(average {steps.get('average', 0)}); "
                )
                + ", ".join(f"{label}: {count}" for label, count in exposure.items())
            )
        if coherent and context and context.input_mode == "survey":
            coverage_items = []
        for dimension, groups in segment_counts.items():
            coverage_items.append(
                f"{dimension}: "
                + "; ".join(f"{label}: {count}" for label, count in groups.items())
                + (". Descriptive for this synthetic cohort only.")
            )
        scope_items = [
            f"Input: {context.input_mode if context else 'unknown'}; requested Personas: {result.metrics.get('requested_personas', 0)}.",
            "Synthetic Persona research, not human-participant evidence or a population estimate.",
            "Evidence review is a model judgment; citations and hashes establish provenance, not semantic truth.",
            (
                f"Analysis coverage: {reviewed_answers}/{eligible_answers} eligible answers; "
                f"{len(findings)} findings; "
                f"{len(synthesis.recommendations) if synthesis else 0} recommendations."
            ),
            "The complete protocol, original answers, trajectories and analysis records remain in the local appendix and structured artifacts.",
            *boundaries,
            *coverage_items,
            *result.errors,
        ]
        if coherent:
            scope_items.insert(
                1,
                f"Responses: {result.metrics.get('valid_responses', 0)} valid; "
                f"{result.metrics.get('invalid_responses', 0)} invalid; "
                f"{result.metrics.get('missing_responses', 0)} missing. "
                f"Failed actions: {result.metrics.get('failed_actions', 0)}.",
            )
            if "environment_build" in result.metrics:
                build = result.metrics["environment_build"]
                scope_items.extend(
                    [f"Environment readiness: {build['level']}; {build['summary']}", *build["issues"]]
                )
        if manifest.get("phase") == "analysis_only":
            scope_items.append(
                f"Analysis-only rerun of {manifest['source_run_id']}; participant sessions and answers "
                f"were reused without new product interactions. Source status: "
                f"{manifest.get('source_status', 'not recorded')}."
            )
            scope_items.extend(manifest.get("source_errors", []))
        section(
            ("Limitations") if coherent else ("Confidence & Limitations"),
            [synthesis.limitations if synthesis else "No validated synthesis available."],
            () if coherent else scope_items,
        )
        if coherent:
            section("Appendix / Evidence", items=scope_items)
        return sections
    if context:
        for method in context.methods:
            section(
                f"Questions: {method['id']}",
                [f"Research method: {method['kind']}"],
                [f"{question['id']}: {question['text']}" for question in method["questions"]],
            )
    section(
        "Descriptive Statistics",
        [stats.get("basis", "")],
        table={
            "headers": [
                "Method / Question",
                "Answered",
                "Not observed",
                "Automation only",
                "Skipped",
                "Missing / invalid",
                "Choices (n, % of answered)",
            ],
            "rows": [
                [
                    f"{item['method_id']} / {item['question_id']}",
                    item["n_answered"],
                    item["n_not_observed"],
                    item.get("n_automation", 0),
                    item["n_skipped"],
                    item["n_missing_or_invalid"],
                    "; ".join(
                        f"{option}: {count} ({item['percent_of_answered'].get(option, 0)}%)"
                        for option, count in item["counts"].items()
                    )
                    or (
                        json.dumps(item["matrix_counts"], ensure_ascii=False)
                        if item.get("matrix_counts")
                        else "Open text"
                    ),
                ]
                for item in stats.get("questions", [])
            ],
        },
    )
    if context and context.input_mode != "survey":
        section(
            "Experience Coverage",
            ["Outcomes below are Persona self-report or runtime status, not verified product success."],
            [
                f"{episode.persona.id}: {len(episode.steps)} decisions; {episode.outcome} ({episode.outcome_basis})."
                for episode in result.episodes
            ],
        )
    if "environment_build" in result.metrics:
        build = result.metrics["environment_build"]
        section(
            "Environment Readiness", [f"Compiled level: {build['level']}", build["summary"]], build["issues"]
        )
    if boundaries:
        section("Prototype Boundaries", items=boundaries)
    section(
        "Limitations",
        [synthesis.limitations if synthesis else "No validated synthesis available."],
        [
            "Citations and hashes verify provenance, not semantic truth.",
            "Only supplied materials and encountered states were considered.",
        ],
    )
    if result.errors:
        section("Errors", items=result.errors)
    if context:
        section(
            "Analysis Coverage",
            [
                f"Strategy: {context.analysis.get('strategy', 'unavailable')}; status: {context.analysis.get('status', 'unavailable')}"
            ],
            [
                f"Eligible answers: {context.analysis.get('n_eligible_answers', 0)}; processed: {len(context.analysis.get('covered_answer_ids', []))}.",
                f"Answers checked against candidate themes: {len(set(context.analysis.get('reviewed_answer_ids', [])))}.",
            ],
        )
    if manifest.get("phase") == "analysis_only":
        section(
            "Analysis Lineage",
            [
                f"Analysis-only rerun of {manifest['source_run_id']}. The same participant sessions and answers were reused; no new product interactions were performed. Source status: {manifest.get('source_status', 'not recorded')}."
            ],
            manifest.get("source_errors", []),
        )
    return sections


def _evidence_contributors(support_count: int, counter_count: int) -> str:
    return (
        f"Evidence contributors: {support_count} from cited supporting answers; "
        f"{counter_count} from cited counter answers. "
        "These sets may overlap and are not votes on every claim."
    )


def render(result, store, *, html_output=False):
    sections = report_sections(result, store)
    coherent = bool(result.synthesis and result.synthesis.recommendation_order == "decision")
    manifest_path = store.root / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text("utf-8")) if manifest_path.is_file() else {}
    language = (
        result.report.analysis.get("language")
        if result.report and result.report.analysis.get("language")
        else manifest.get("task", {}).get("insight", {}).get("language", "en")
    )
    if not html_output:
        lines = [
            "# Genesia Research Report [SIMULATED]",
            "",
            f"Run: {result.run_id}",
            "",
        ]
        for section in sections:
            lines.extend([f"## {section['title']}", "", *section["paragraphs"], ""])
            lines.extend(f"- {item}" for item in section["items"])
            if section["snapshot"]:
                lines.extend(["", "### Decision Snapshot"])
                lines.extend(f"- **{item['label']}:** {item['value']}" for item in section["snapshot"])
            if section["executive_findings"]:
                lines.extend(["", "### Key Insights"])
                for finding in section["executive_findings"]:
                    lines.extend(
                        [
                            "",
                            f"#### {finding['text']}",
                            f"- **{_evidence_contributors(finding['support_count'], len(finding['counter_participants']))}**",
                        ]
                    )
                    if finding["interpretation"]:
                        lines.append(f"- {finding['interpretation']}")
                    if finding["design_implication"]:
                        lines.append(f"- **Recommended action:** {finding['design_implication']}")
                    if finding["uncertainty"]:
                        lines.append(f"- **To validate:** {finding['uncertainty']}")
            for recommendation in section["recommendations"]:
                lines.extend(
                    [
                        "",
                        f"### {recommendation['rank']}. {recommendation['action']}",
                        f"- **Target:** {recommendation['target']}",
                        f"- {recommendation['rationale']}",
                    ]
                )
                if coherent:
                    lines.append(
                        ("Based on: ")
                        + ", ".join(
                            f"[{ref}](#finding-{quote(ref, safe='')})"
                            for ref in recommendation["finding_ids"]
                        )
                    )
            for profile in section["feedback_profiles"]:
                lines.extend(["", f"### {profile['persona_id']}"])
                if profile["note"]:
                    lines.append(f"_{profile['note']}_")
                lines.extend(
                    f"- **{entry['role']}** ({entry['basis']}): {entry['value']}"
                    for entry in profile["entries"]
                )
            for finding in section["findings"]:
                if finding["coherent"]:
                    lines.extend(["", f'<a id="finding-{html.escape(finding["id"], quote=True)}"></a>'])
                lines.extend(
                    [
                        "",
                        f"### {finding['title']}",
                        *(
                            [finding["text"], ""]
                            if finding["coherent"] and finding["title"] != finding["text"]
                            else []
                        ),
                        _evidence_contributors(
                            finding["support_count"], len(finding["counter_participants"])
                        ),
                    ]
                )
                if finding["interpretation"]:
                    lines.append(finding["interpretation"])
                if finding["design_implication"]:
                    lines.append(
                        ("" if finding["coherent"] else "**Recommended action:** ")
                        + finding["design_implication"]
                    )
                if finding["uncertainty"] and not finding["coherent"]:
                    lines.append(f"**To validate:** {finding['uncertainty']}")
                if finding["evidence_details"] or (finding["coherent"] and finding["uncertainty"]):
                    lines.extend(
                        [
                            "",
                            "<details><summary>View evidence details</summary>",
                            "",
                            *[f"- {item}" for item in finding["evidence_details"]],
                            *(
                                [f"- To validate: {finding['uncertainty']}"]
                                if finding["coherent"] and finding["uncertainty"]
                                else []
                            ),
                            "",
                            "</details>",
                        ]
                    )
                if not section["compact_feedback"]:
                    lines.append(
                        f"{finding['claim_type']}; simulated Personas: {', '.join(finding['participants'])}"
                    )
                    lines.extend(f"- Source question: {question}" for question in finding["questions"])
                    lines.append(
                        "Evidence: " + ", ".join(f"[{label}]({path})" for label, path in finding["refs"])
                    )
                    lines.extend(f"![{label}]({path})" for label, path in finding["pictures"])
            for group in section["feedback_groups"]:
                lines.extend(
                    [
                        f"### {group['title']}",
                        f"Respondents: {group['count']}; "
                        + ("Small sample" if group["count"] < 5 else "Descriptive only"),
                    ]
                )
                lines.extend(f"- {theme}" for theme in group["themes"])
                lines.append("<details><summary>Original feedback</summary>\n")
                lines.extend(
                    f"- **{entry['persona_id']} / {entry['question']}**: {entry['value']} ({entry['answer_id']})"
                    for entry in group["entries"]
                )
                lines.append("\n</details>")
            if table := section["table"]:

                def clean(value):
                    return str(value).replace("|", "\\|").replace("\n", " ")

                lines.extend(
                    ["| " + " | ".join(table["headers"]) + " |", "|" + "---|" * len(table["headers"])]
                )
                lines.extend("| " + " | ".join(map(clean, row)) + " |" for row in table["rows"])
            lines.append("")
        lines.extend(
            [
                *(["## Appendix"] if not coherent else []),
                "",
                "[Original responses and execution records](appendix.html)",
                "[Markdown appendix](appendix.md)",
                "[Structured result](research_result.json)",
            ]
        )
        return "\n".join(lines)

    def escape(value):
        return html.escape(str(value), quote=True)

    def link(path):
        return escape(quote(path, safe="/.-_"))

    nav, content = [], []
    for index, section in enumerate(sections):
        nav.append(f'<a href="#section-{index}">{escape(section["title"])}</a>')
        body = [f"<h2>{escape(section['title'])}</h2>"]
        body.extend(f"<p>{escape(item)}</p>" for item in section["paragraphs"])
        if section["items"]:
            body.append("<ul>" + "".join(f"<li>{escape(item)}</li>" for item in section["items"]) + "</ul>")
        if section["snapshot"]:
            body.append('<div class="decision-grid">')
            body.extend(
                f'<div class="decision-metric"><span class="meta">{escape(item["label"])}</span>'
                f"<strong>{escape(item['value'])}</strong></div>"
                for item in section["snapshot"]
            )
            body.append("</div>")
        if section["executive_findings"]:
            body.append("<h3>Key Insights</h3>")
            for finding in section["executive_findings"]:
                body.extend(
                    [
                        '<article class="insight-card">',
                        f'<span class="evidence-count">{escape(_evidence_contributors(finding["support_count"], len(finding["counter_participants"])))}</span>',
                        f"<h3>{escape(finding['title'])}</h3>",
                        *(
                            [f"<p>{escape(finding['text'])}</p>"]
                            if finding["coherent"] and finding["title"] != finding["text"]
                            else []
                        ),
                    ]
                )
                if finding["interpretation"]:
                    body.append(f"<p>{escape(finding['interpretation'])}</p>")
                if finding["design_implication"]:
                    body.append(
                        ("<p>" if finding["coherent"] else "<p><strong>Recommended action:</strong> ")
                        + f"{escape(finding['design_implication'])}</p>"
                    )
                if finding["uncertainty"] and not finding["coherent"]:
                    body.append(
                        f'<p class="meta"><strong>To validate:</strong> {escape(finding["uncertainty"])}</p>'
                    )
                body.append("</article>")
        for recommendation in section["recommendations"]:
            body.extend(
                [
                    '<article class="recommendation">',
                    f'<span class="label">Target: {escape(recommendation["target"])}</span>',
                    f"<h3>{recommendation['rank']}. {escape(recommendation['action'])}</h3>",
                    f"<p>{escape(recommendation['rationale'])}</p>",
                ]
            )
            if coherent:
                body.append(
                    '<p class="meta">'
                    + ("Based on: ")
                    + ", ".join(
                        f'<a href="#finding-{link(ref)}">{escape(ref)}</a>'
                        for ref in recommendation["finding_ids"]
                    )
                    + "</p>"
                )
            body.append("</article>")
        if section["feedback_profiles"]:
            body.append('<div class="participant-list">')
        for profile_index, profile in enumerate(section["feedback_profiles"]):
            open_state = " open" if profile_index == 0 else ""
            body.append(
                f'<details class="participant" name="participant-feedback"{open_state}>'
                f"<summary><strong>{escape(profile['persona_id'])}</strong>"
                f'<span class="meta">{len(profile["entries"])} feedback topics</span></summary><dl>'
            )
            if profile["note"]:
                body.append(f'<p class="meta">{escape(profile["note"])}</p>')
            body.extend(
                f'<dt><strong>{escape(entry["role"])}</strong> <span class="meta">{escape(entry["basis"])}</span></dt>'
                f"<dd>{escape(entry['value'])}</dd>"
                for entry in profile["entries"]
            )
            body.append("</dl></details>")
        if section["feedback_profiles"]:
            body.append("</div>")
        for finding in section["findings"]:
            body.extend(
                [
                    (
                        f'<article class="insight-card" id="finding-{escape(finding["id"])}">'
                        if finding["coherent"]
                        else '<article class="insight-card">'
                    ),
                    f"<h3>{escape(finding['title'])}</h3>",
                    *(
                        [f"<p>{escape(finding['text'])}</p>"]
                        if finding["coherent"] and finding["title"] != finding["text"]
                        else []
                    ),
                    f'<span class="evidence-count">{escape(_evidence_contributors(finding["support_count"], len(finding["counter_participants"])))}</span>',
                ]
            )
            if finding["interpretation"]:
                body.append(f"<p>{escape(finding['interpretation'])}</p>")
            if finding["design_implication"]:
                body.append(
                    ("<p>" if finding["coherent"] else "<p><strong>Recommended action:</strong> ")
                    + f"{escape(finding['design_implication'])}</p>"
                )
            if finding["uncertainty"] and not finding["coherent"]:
                body.append(
                    f'<p class="meta"><strong>To validate:</strong> {escape(finding["uncertainty"])}</p>'
                )
            if finding["evidence_details"] or (finding["coherent"] and finding["uncertainty"]):
                body.append("<details><summary>View evidence details</summary><ul>")
                body.extend(f"<li>{escape(item)}</li>" for item in finding["evidence_details"])
                if finding["coherent"] and finding["uncertainty"]:
                    body.append(f"<li>To validate: {escape(finding['uncertainty'])}</li>")
                body.append("</ul></details>")
            if not section["compact_feedback"]:
                body.append(
                    "<details><summary>Source questions</summary><ul>"
                    + "".join(f"<li>{escape(question)}</li>" for question in finding["questions"])
                    + "</ul></details>"
                )
                body.append(
                    "<details><summary>Source evidence</summary><p>"
                    + ", ".join(
                        f'<a href="{link(path)}">{escape(label)}</a>' for label, path in finding["refs"]
                    )
                    + "</p></details>"
                )
                body.extend(
                    f'<figure><a href="{link(path)}"><img loading="lazy" src="{link(path)}" alt="{escape(label)}"></a><figcaption>{escape(label)}</figcaption></figure>'
                    for label, path in finding["pictures"]
                )
            body.append("</article>")
        for group in section["feedback_groups"]:
            note = "Small sample" if group["count"] < 5 else "Descriptive only"
            body.append(
                f"<details><summary>{escape(group['title'])} ({group['count']} respondents; {note})</summary>"
            )
            body.extend(f"<p>{escape(theme)}</p>" for theme in group["themes"])
            for entry in group["entries"]:
                body.append(
                    f"<p><strong>{escape(entry['persona_id'])} / {escape(entry['question'])}</strong><br>"
                    f"{escape(entry['value'])}<br><span class='meta'>{escape(entry['answer_id'])}</span></p>"
                )
            body.append("</details>")
        if table := section["table"]:
            body.append(
                '<div class="table"><table><thead><tr>'
                + "".join(f"<th>{escape(item)}</th>" for item in table["headers"])
                + "</tr></thead><tbody>"
            )
            body.extend(
                "<tr>" + "".join(f"<td>{escape(item)}</td>" for item in row) + "</tr>"
                for row in table["rows"]
            )
            body.append("</tbody></table></div>")
        section_class = ' class="executive"' if section["title"] in {"Executive Summary", "Summary"} else ""
        content.append(f'<section id="section-{index}"{section_class}>' + "".join(body) + "</section>")
    resources = (
        '<a href="appendix.html">Responses, evidence and technical details</a> / '
        '<a href="report.md">Markdown</a> / <a href="research_result.json">JSON</a>'
    )
    if coherent:
        content[-1] = content[-1].removesuffix("</section>") + resources + "</section>"
    else:
        content.append("<section><h2>Appendix</h2>" + resources + "</section>")
    links = "".join(nav)
    navigation = f'<div class="desktop-nav">{links}</div><details class="mobile-nav"><summary>Contents</summary>{links}</details>'
    return document(
        result.run_id,
        "".join(content),
        navigation,
        language="zh-CN" if language == "zh-CN" else "en",
    )


def document(run_id, content, navigation="", *, language="en"):
    return (
        f'<!doctype html><html lang="{language}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'\">"
        "<title>Genesia Research Report</title>"
        f"<style>{STYLE}</style></head><body>"
        '<header><span class="label">Simulated Research</span>'
        "<h1>Genesia Research Report</h1>"
        f'<p>{html.escape(run_id)}</p></header><div class="layout"><nav>{navigation}</nav>'
        f"<main>{content}</main></div></body></html>"
    )


def write_reports(result, store, appendix):
    root = store.root
    (root / "report.md").write_text(render(result, store), "utf-8")
    (root / "report.html").write_text(render(result, store, html_output=True), "utf-8")
    (root / "appendix.md").write_text(appendix, "utf-8")
    body = '<section><h2>Original Responses and Audit</h2><p><a href="report.html">Back to report</a> / <a href="appendix.md">Markdown</a></p>'
    body += "<p>Persona answers are self-reports. Links identify evidence, not verified task success.</p>"
    for response in result.responses:
        body += f"<details><summary>{html.escape(response.persona_id)} / {html.escape(response.method_id)} / valid={response.valid}</summary>"
        for answer in response.answers:
            body += f"<h3>{html.escape(answer.question_id)}</h3><p>{html.escape(json.dumps(answer.value, ensure_ascii=False))}</p>"
            if answer.reason:
                body += f"<p>{html.escape(answer.reason)}</p>"
            body += f'<p class="meta">Basis: {html.escape(answer.basis)}</p>'
        body += "</details>"
    body += "<p>Full structured statistics, segments, readiness, responses and execution traces:</p>"
    body += (
        "<details><summary>Research result</summary><pre>"
        + html.escape(result.model_dump_json(indent=2))
        + "</pre></details>"
    )
    body += (
        "<details><summary>Evidence index</summary><ul>"
        + "".join(
            f'<li><a href="{html.escape(quote(ref.path, safe="/.-_"))}">{html.escape(ref.id)}: {html.escape(ref.kind)}</a></li>'
            for ref in store.refs.values()
        )
        + "</ul></details></section>"
    )
    (root / "appendix.html").write_text(document(result.run_id, body), "utf-8")
