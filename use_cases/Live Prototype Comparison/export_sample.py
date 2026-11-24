"""Maintain the historical Dayline publication; not a general exporter for new runs.

This is an offline presentation exporter, not a research or analysis runtime.
Requires Pillow and the original private study, analysis-only and GIF export directories.
The private GIF manifest supplies alias/sequence provenance; public media is rebuilt
from original evidence, not edited screenshots or a rerun of the study.
New runs already provide report.html, appendix.html and recorded screenshot evidence.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import importlib.util
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
SOURCE_TO_PUBLIC = {"B": "A", "D": "B"}
CHOICES = ("Design A", "Design B", "No meaningful preference", "Insufficient experience")
VARIANT_NOTICE = (
    "Public display aliases: Design A is source Design B; Design B is source Design D. "
    "Version labels in prose, quotations and question IDs are relabeled for readability only. "
    "The original study, participant order, answers, decisions and counts are unchanged."
)
EDITION_NOTICE = (
    "Public research edition. Findings, recommendations, participant counts and research limitations "
    "are retained. Internal infrastructure, release and troubleshooting notes are omitted. "
    "Full source records remain unchanged and private."
)
STUDY_STATUS = (
    "Participant experience and answers are complete. The original full-study run remains partial; "
    "the published native report comes from completed analysis of the same saved material. "
    "No participant sessions were repeated."
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def report_helpers():
    path = HERE / "report_helpers.py"
    spec = importlib.util.spec_from_file_location("comparison_report_helpers", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load existing report sanitization helpers")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def public_text(text: str, aliases: dict[str, str], sessions: set[str]) -> str:
    for identifier, alias in aliases.items():
        text = text.replace(identifier, alias)
    text = re.sub(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/][^`\s<>\"')]+", "PRIVATE_SOURCE_DIRECTORY", text)
    if any(identifier in text for identifier in sessions):
        raise ValueError("Refusing to publish a source session identifier")
    return text


def public_variant_text(text: str) -> str:
    """Relabel original study prose once; preserve generic A/B experiment terminology."""
    pattern = r"A[/\uff0f]B|(?<![A-Za-z0-9_])([bd])_([a-z_]+)|(?<![A-Za-z0-9_])([BD])(?![A-Za-z_])"

    def replace(match: re.Match[str]) -> str:
        question, suffix, label = match.groups()
        if question:
            return SOURCE_TO_PUBLIC[question.upper()].lower() + "_" + suffix
        return SOURCE_TO_PUBLIC[label] if label else match[0]

    return re.sub(pattern, replace, text)


def public_case_text(text: str) -> str:
    """Replace source-report batch labels, not dates, run IDs or research claims."""
    for old, new in (
        ("# case1022", "# Dayline A/B"),
        ("Dayline release1022", "Dayline"),
        ("fresh RELEASE case1022", "Dayline A/B"),
        ("fresh release1022", "\u672c\u6b21\u51bb\u7ed3\u7248\u672c"),
        ("release1022 \u7684 `PYTHONPATH`", "\u7814\u7a76\u51bb\u7ed3\u7248\u672c \u7684 `PYTHONPATH`"),
        ("\u4e0e 1019 \u7684", "\u4e0e \u5148\u524d\u7814\u7a76 \u7684"),
        ("\u5408\u5e76 1019 \u7ed3\u679c", "\u5408\u5e76 \u5148\u524d\u7814\u7a76 \u7ed3\u679c"),
        ("1019 \u4e0e\u672c\u6b21", "\u5148\u524d\u7814\u7a76 \u4e0e\u672c\u6b21"),
    ):
        text = text.replace(old, new)
    return text


def public_native_report(text: str, *, html_format: bool = False) -> str:
    prefixes = (
        "Analysis-only rerun of ",
        "Run stage: ",
        "The complete protocol, original answers, trajectories and analysis records ",
    )
    if html_format:
        text = re.sub(r"<p>(?:Source run: )?\d{8}T\d{6}Z-[a-f0-9]+</p>", "", text)
        for prefix in prefixes:
            text = re.sub(rf"<li>{re.escape(prefix)}.*?</li>", "", text, flags=re.S)
    else:
        text = re.sub(r"(?m)^(?:Source run|Run): \d{8}T\d{6}Z-[a-f0-9]+\n", "", text)
        for prefix in prefixes:
            text = re.sub(rf"(?m)^- {re.escape(prefix)}[^\n]*\n?", "", text)
    return text


def check_publication_text(text: str, *, private_values: tuple[str, ...] = ()) -> None:
    forbidden = (
        "PRIVATE_SOURCE_DIRECTORY",
        "PYTHONPATH",
        "ReadTimeout",
        "ModelFailure",
        "research-work",
        "research.audit.json",
        "0.2.1rc1",
    )
    if any(value and value in text for value in (*forbidden, *private_values)):
        raise ValueError("Public edition still contains internal operational details")


def frame_annotations(step: dict[str, Any], alias: str, total: int, candidate: str) -> dict[str, str]:
    action = step["action"]
    kind = action["action"]
    target = next(
        (item for item in step["observation"]["targets"] if item["id"] == action.get("target_id")), None
    )
    label = kind.upper()
    if kind == "advance":
        label = "ADVANCE to B (study handoff, not a product control)"
    elif kind == "stop":
        label = "STOP (study control)"
    elif kind == "scroll":
        label += f" {action['value']}"
    elif target is not None:
        label += f" | {target.get('name') or target['id']}"
    return {
        "title": f"Dayline | {alias} | Design {candidate} | Step {step['number']}/{total}",
        "action": label,
    }


def render_frame(path: Path, step: dict[str, Any], annotations: dict[str, str]) -> Image.Image:
    with Image.open(path) as source:
        screenshot = source.convert("RGB")
    canvas = Image.new("RGB", (screenshot.width, screenshot.height + 116), "#152238")
    canvas.paste(screenshot, (0, 88))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=20)
    small = ImageFont.load_default(size=16)
    draw.text((16, 8), annotations["title"], font=font, fill="white")
    label = annotations["action"]
    while draw.textlength(label, font=font) > screenshot.width - 32:
        label = label[:-4] + "..."
    draw.text((16, 37), label, font=font, fill="#ffd60a")
    draw.text(
        (16, 64),
        "Saved observation BEFORE this action; yellow marker = recorded click target.",
        font=small,
        fill="#d4dfef",
    )
    draw.text(
        (16, canvas.height - 24),
        "SIMULATED Persona | Saved screenshots, not video | 2s/step, 4s final hold; not actual timing",
        font=small,
        fill="#d4dfef",
    )
    if step["action"]["action"] in {"click", "right_click"}:
        target = next(
            (item for item in step["observation"]["targets"] if item["id"] == step["action"]["target_id"]),
            None,
        )
        if target is None or any(
            not isinstance(target.get(key), (int, float)) or isinstance(target[key], bool)
            for key in ("x", "y")
        ):
            raise ValueError("Click target has no recorded coordinates")
        x, y = target["x"], target["y"]
        if not (0 <= x < screenshot.width and 0 <= y < screenshot.height):
            raise ValueError("Recorded click lies outside the source screenshot")
        y += 88
        draw.ellipse((x - 15, y - 15, x + 15, y + 15), outline="#152238", width=7)
        draw.ellipse((x - 15, y - 15, x + 15, y + 15), outline="#ffd60a", width=4)
        draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill="#ffd60a")
    frame = canvas.resize((960, round(canvas.height * 960 / canvas.width)), Image.Resampling.LANCZOS)
    screenshot.close()
    canvas.close()
    return frame


def write_journey_gif(
    run_dir: Path, episode: dict[str, Any], evidence: dict[str, Any], target: Path, alias: str
) -> dict[str, Any]:
    steps = episode["steps"]
    if episode["candidate_labels"] != ["Design B", "Design D"] or episode["mode"] != "live":
        raise ValueError(
            "Historical publication exporter requires the original Design B/Design D source study. "
            "For new A/B runs, use their native report.html and appendix.html."
        )
    if [step["number"] for step in steps] != list(range(1, len(steps) + 1)):
        raise ValueError("Steps must be complete and chronological")
    handoffs = [i for i, step in enumerate(steps) if step["action"]["action"] == "advance"]
    if len(handoffs) != 1 or not 0 < handoffs[0] < len(steps) - 1:
        raise ValueError("Expected one handoff between two nonempty stages")
    if episode["final_observation"]["image_refs"] != steps[-1]["observation"]["image_refs"]:
        raise ValueError("An additional final observation needs explicit export support")
    frames, provenance = [], []
    first_url = urlsplit(steps[0]["observation"]["url"])
    origin = (first_url.scheme, first_url.netloc)
    for index, step in enumerate(steps):
        observation = step["observation"]
        observed_url = urlsplit(observation["url"])
        design = parse_qs(observed_url.query).get("design")
        expected = "b" if index <= handoffs[0] else "d"
        if (
            (observed_url.scheme, observed_url.netloc) != origin
            or design != [expected]
            or not step["result"]["success"]
            or len(observation["image_refs"]) != 1
        ):
            raise ValueError("Unexpected source stage, failed action or incomplete screenshot")
        ref_id = observation["image_refs"][0]
        row = evidence[ref_id]
        path = (run_dir / row["path"]).resolve()
        if (
            row["kind"] != "frame"
            or row["persona_id"] != episode["persona"]["id"]
            or row["session_id"] != episode["session_id"]
            or not path.is_relative_to(run_dir.resolve())
            or not path.is_file()
            or sha256(path) != row["sha256"]
        ):
            raise ValueError("Screenshot ownership, confinement or integrity mismatch")
        candidate = SOURCE_TO_PUBLIC[expected.upper()]
        annotation = frame_annotations(step, alias, len(steps), candidate)
        frames.append(render_frame(path, step, annotation))
        provenance.append(
            {
                "evidence_ref": ref_id,
                "sha256": row["sha256"],
                "candidate": candidate,
                "source_candidate": expected.upper(),
                "step": step["number"],
                "annotations": annotation,
            }
        )
    if len({frame.size for frame in frames}) != 1:
        raise ValueError("All source screenshots must share dimensions")
    durations = [2000] * (len(frames) - 1) + [4000]
    frames[0].save(
        target,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        disposal=2,
        optimize=True,
    )
    with Image.open(target) as image:
        if image.n_frames != len(frames) or image.info.get("loop") != 0:
            raise ValueError("GIF lost a recorded step or loop setting")
        for index in range(image.n_frames):
            image.seek(index)
            image.load()
            if image.size != frames[index].size or image.info["duration"] != durations[index]:
                raise ValueError("Exported GIF dimensions or timing changed")
    size = list(frames[0].size)
    for frame in frames:
        frame.close()
    return {"frames": len(frames), "size": size, "duration_ms": sum(durations), "source_frames": provenance}


def gallery(participants: list[dict[str, Any]], counts: dict[str, int]) -> str:
    cards = []
    for participant in participants:
        alias = participant["alias"]
        cards.append(
            f'<section id="{alias}"><h2>{alias} · {participant["steps"]} steps · '
            f"{html.escape(participant['preference'])}</h2>"
            f'<p><a href="{participant["gif"]}">Open / download full A → B GIF</a></p>'
            "<details><summary>Play full journey</summary>"
            f'<img loading="lazy" src="{participant["gif"]}" alt="{alias} A to B journey">'
            "</details></section>"
        )
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Dayline A/B comparison · Journey gallery</title><style>"
        "body{font:16px/1.7 system-ui;max-width:1100px;margin:32px auto;padding:20px;color:#202124}"
        ".note{background:#fff3d6;padding:18px}section{border-top:1px solid #ddd;padding:12px 0}"
        "img{max-width:100%;height:auto}summary{cursor:pointer}code{overflow-wrap:anywhere}"
        "</style><h1>Dayline · 20-Persona A → B comparison</h1>"
        '<p><a href="report.html">Native report</a> · <a href="standalone-report.html">Standalone report</a> · '
        '<a href="manifest.json">Provenance / SHA-256</a> · '
        '<a href="../README.md">Protocol and reproduction</a></p>'
        '<div class="note"><strong>SIMULATED — not human-participant video.</strong> '
        "20 synthetic Personas, 400 valid answers, 340 saved steps, zero failed actions. "
        "All twenty complete journeys are included, not a selection of favorable examples. "
        "Fixed A → B order and different self-chosen tasks do not establish causal A/B effects. "
        "Yellow rings mark recorded click targets, not mouse paths. Each frame is the saved observation "
        "before its labeled action; the next saved observation is not proof of an immediate effect. "
        "ADVANCE and STOP are study controls. Playback is 2 seconds per step and a 4-second final hold, "
        "not actual elapsed time. GIFs use public A/B annotations over verified source screenshots at 960px. "
        "No model calls or new browser sessions were used to publish this sample.</div>"
        f"<p>Preference: A {counts['Design A']}/20 · B {counts['Design B']}/20 · "
        f"No meaningful preference {counts['No meaningful preference']}/20 · "
        f"Insufficient experience {counts['Insufficient experience']}/20.</p>"
        f"<p>{STUDY_STATUS} "
        "Profiles, source Persona/session IDs, raw requests, full traces and private appendices are excluded. "
        "Simulated prototype fixtures and Persona-written synthetic task briefs remain visible.</p>"
        + f"<details><summary>Version-label provenance</summary><p>{VARIANT_NOTICE}</p></details>"
        + "".join(cards)
        + "</html>"
    )


def export_sample(study_run: Path, analysis_run: Path, journey_dir: Path, output: Path) -> dict[str, Any]:
    for directory in (study_run, analysis_run):
        subprocess.run([sys.executable, "-m", "genesia", "verify", str(directory)], check=True)
    existing = {path.name for path in output.iterdir()} if output.exists() else set()
    if existing - {"README.md", "README_CN.md"}:
        raise ValueError("Refusing to overwrite an existing sample")
    tracked = {
        directory / name: sha256(directory / name)
        for directory in (study_run, analysis_run)
        for name in ("research_result.json", "run_manifest.json", "evidence.json")
    }
    study = read_json(study_run / "research_result.json")
    analysis = read_json(analysis_run / "research_result.json")
    source_manifest = read_json(study_run / "run_manifest.json")
    private_values = (
        source_manifest["task"]["model"]["provider"],
        source_manifest["task"]["model"]["model"],
    )
    analysis_manifest = read_json(analysis_run / "run_manifest.json")
    media = read_json(journey_dir / "manifest.json")
    if (
        analysis["status"] != "completed"
        or analysis_manifest["phase"] != "analysis_only"
        or analysis_manifest["source_run_id"] != study["run_id"]
        or study["episodes"] != analysis["episodes"]
        or study["responses"] != analysis["responses"]
        or media["source_run"] != study["run_id"]
    ):
        raise ValueError("Analysis and media must derive from the same intact study")
    ids = source_manifest["cohort"]["ids"]
    if len(ids) != 20 or len(set(ids)) != 20:
        raise ValueError("This sample requires the complete twenty-Persona cohort")
    aliases = {identifier: f"P{index:02d}" for index, identifier in enumerate(ids, 1)}
    sessions = {episode["session_id"] for episode in study["episodes"]}
    episodes = {episode["persona"]["id"]: episode for episode in study["episodes"]}
    responses = {response["persona_id"]: response for response in study["responses"]}
    media_rows = {row["persona_id"]: row for row in media["participants"]}
    if set(episodes) != set(ids) or set(responses) != set(ids) or set(media_rows) != set(ids):
        raise ValueError("The public sample must cover every source participant")
    if any(not response["valid"] or len(response["answers"]) != 20 for response in responses.values()):
        raise ValueError("Every participant must have twenty valid answers")
    output.mkdir(parents=True, exist_ok=True)
    (output / "journeys").mkdir()
    participants = []
    feedback = []
    counts = Counter({choice: 0 for choice in CHOICES})
    evidence = {row["id"]: row for row in read_json(study_run / "evidence.json")}
    for identifier, alias in aliases.items():
        episode = episodes[identifier]
        row = media_rows[identifier]
        gif = row["gifs"]["paired"]
        steps = episode["steps"]
        if row["alias"] != alias or row["session_id"] != episode["session_id"]:
            raise ValueError("Private media aliases/ownership do not match the source")
        if gif["source_steps"] != [step["number"] for step in steps]:
            raise ValueError("Private media omitted or reordered source steps")
        if len(gif["source_frames"]) != len(steps):
            raise ValueError("Private media frame provenance is incomplete")
        for step, frame in zip(steps, gif["source_frames"], strict=True):
            ref = evidence[frame["evidence_ref"]]
            if (
                step["observation"]["image_refs"] != [frame["evidence_ref"]]
                or ref["persona_id"] != identifier
                or ref["session_id"] != episode["session_id"]
                or ref["sha256"] != frame["sha256"]
            ):
                raise ValueError("Private GIF screenshot ownership/hash mismatch")
        source = journey_dir / gif["file"]
        if sha256(source) != gif["sha256"]:
            raise ValueError("Private GIF hash mismatch")
        preference = next(
            answer for answer in responses[identifier]["answers"] if answer["question_id"] == "x_preference"
        )
        public_preference = public_variant_text(preference["value"])
        if public_preference not in CHOICES:
            raise ValueError("Unexpected preference option")
        counts[public_preference] += 1
        relative = f"journeys/{alias.lower()}-paired.gif"
        properties = write_journey_gif(study_run, episode, evidence, output / relative, alias)
        participants.append(
            {
                "alias": alias,
                "steps": len(steps),
                "preference": public_preference,
                "gif": relative,
                **properties,
                "source_gif_sha256": gif["sha256"],
            }
        )
        feedback.append(
            {
                "participant": alias,
                "question_id": "x_preference",
                "value": public_preference,
                "reason": public_variant_text(public_text(preference["reason"], aliases, sessions)),
            }
        )
        print(f"{alias}: verified {len(steps)} complete journey frames", flush=True)
    helpers = report_helpers()
    markdown = helpers._sanitize_markdown(
        public_variant_text(public_text((analysis_run / "report.md").read_text("utf-8"), aliases, sessions)),
        aliases,
        analysis["run_id"],
    )
    markdown = re.sub(
        r"(?m)^\[(?:Original responses and execution records|Markdown appendix|Structured result)\].*$",
        "",
        markdown,
    )
    markdown = public_native_report(markdown)
    markdown = "> " + EDITION_NOTICE + "\n\n> " + VARIANT_NOTICE + "\n\n> " + STUDY_STATUS + "\n\n" + markdown
    markdown += (
        "\n\n## Public sample\n\n"
        "[20 complete journey GIFs](index.html) · [Source lineage and file hashes](manifest.json)\n\n"
        "Private source appendices, profiles and raw execution records are not distributed.\n"
    )
    (output / "report.md").write_text(markdown, encoding="utf-8")
    visual = helpers._sanitize_html(
        public_variant_text(
            public_text((analysis_run / "report.html").read_text("utf-8"), aliases, sessions)
        ),
        aliases,
        analysis["run_id"],
    )
    visual = re.sub(
        r'<a\b[^>]*href="(?:appendix\.html|appendix\.md|research_result\.json)"[^>]*>.*?</a>',
        '<span class="meta">Original raw records retained privately.</span>',
        visual,
        flags=re.S,
    )
    visual = public_native_report(visual, html_format=True)
    visual = visual.replace("<main>", f'<main><p class="meta">{VARIANT_NOTICE}</p>', 1)
    visual = visual.replace(
        "<main>", f'<main><p class="meta">{EDITION_NOTICE}</p><p class="meta">{STUDY_STATUS}</p>', 1
    )
    notice = (
        '<p class="meta">Public privacy-minimized edition. '
        '<a href="index.html">20 complete journey GIFs</a> · '
        '<a href="manifest.json">Source lineage and hashes</a>. '
        "Study lineage is recorded in the publication manifest.</p>"
    )
    (output / "report.html").write_text(visual.replace("<main>", "<main>" + notice, 1), "utf-8")
    first_gif = participants[0]["gif"]
    payload = base64.b64encode((output / first_gif).read_bytes()).decode("ascii")
    preview = (
        "<section><h2>One embedded journey example: P01, full A → B</h2>"
        "<p>Saved screenshots, not video. All twenty journeys are in the separate sample gallery. "
        "Yellow rings mark recorded clicks; playback timing is synthetic (2s/step, 4s final hold).</p>"
        f'<img style="max-width:100%" src="data:image/gif;base64,{payload}" '
        'alt="P01 complete A to B synthetic journey"></section>'
    )
    standalone = helpers._standalone_html(visual).replace("</main>", preview + "</main>", 1)
    (output / "standalone-report.html").write_text(standalone, encoding="utf-8")
    write_json(
        output / "preferences.json",
        {"version_label_notice": VARIANT_NOTICE, "counts": dict(counts), "answers": feedback},
    )
    case = study_run.parent.parent
    design = read_json(case / "execution" / "design.json")
    source_hashes = design["prototype_source_hashes"]
    for filename, expected in source_hashes.items():
        if sha256(case / "prototype" / filename) != expected:
            raise ValueError(f"Pinned prototype source changed: {filename}")
    write_json(
        output / "prototype.json",
        {
            "product": "Dayline",
            "source": "Frozen, hash-verified study snapshot; not current checkout",
            "redistributed": False,
            "license": "MIT",
            "commit_recorded": False,
            "versions": [
                {"label": "Design A", "source_label": "Design B", "route": "/?design=b&research=1"},
                {"label": "Design B", "source_label": "Design D", "route": "/?design=d&research=1"},
            ],
            "source_files_sha256": source_hashes,
            "limits": "Same snapshot, different routes. No real Agent, account, send or publish action.",
        },
    )
    (output / "index.html").write_text(gallery(participants, dict(counts)), encoding="utf-8")
    for path in output.rglob("*"):
        if path.suffix in {".md", ".html", ".json"}:
            text = path.read_text("utf-8")
            if public_text(text, aliases, sessions) != text:
                raise ValueError(f"Unredacted identity or private absolute path: {path.name}")
            check_publication_text(text, private_values=private_values)
    if any(sha256(path) != before for path, before in tracked.items()):
        raise ValueError("Source study/analysis files changed during publication")
    manifest = {
        "sample_schema_version": "2",
        "version_label_notice": VARIANT_NOTICE,
        "version_labels": [
            {"public": "Design A", "source": "Design B"},
            {"public": "Design B", "source": "Design D"},
        ],
        "study_date": "2026-10-22",
        "synthetic": True,
        "source_study_run_id": study["run_id"],
        "source_study_status": study["status"],
        "source_analysis_run_id": analysis["run_id"],
        "source_analysis_status": analysis["status"],
        "same_episodes_and_responses": True,
        "source_files_unchanged": True,
        "cohort": {
            "mode": "fixed authorized cohort; original IDs excluded",
            "size": 20,
            "seed": source_manifest["cohort"]["seed"],
        },
        "valid_responses": 20,
        "invalid_responses": 0,
        "missing_responses": 0,
        "answers": 400,
        "recorded_steps": sum(row["steps"] for row in participants),
        "failed_actions": study["metrics"]["failed_actions"],
        "preference_counts": dict(counts),
        "analysis_answer_coverage": "400/400",
        "evidence_verification": [
            {"run": directory.name, **read_json(directory / "evidence_verification.json")}
            for directory in (study_run, analysis_run)
        ],
        "source_hashes": {f"{path.parent.name}/{path.name}": value for path, value in tracked.items()},
        "privacy": {
            "aliases": True,
            "full_profiles_removed": True,
            "source_ids_removed": True,
            "session_ids_removed": True,
            "raw_requests_removed": True,
            "complete_traces_removed": True,
            "private_appendices_removed": True,
            "prototype_fixture_labels_and_synthetic_task_briefs_visible": True,
            "publication_requested_by_repository_owner": True,
        },
        "publication": {
            "model_calls": 0,
            "new_browser_sessions": 0,
            "gif_count": 20,
            "all_recorded_steps_included": True,
            "width": 960,
            "frame_ms": 2000,
            "final_frame_ms": 4000,
            "timing_is_synthetic": True,
            "standalone_embedded_journeys": 1,
            "overlays_regenerated_from_verified_source_frames": True,
            "font": "Pillow bundled default font",
            "internal_operational_details_removed": True,
            "model_and_release_configuration": "Retained privately; not part of this public edition",
        },
        "participants": participants,
        "files": [
            {
                "path": path.relative_to(output).as_posix(),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in sorted(output.rglob("*"))
            if path.is_file()
        ],
    }
    check_publication_text(json.dumps(manifest), private_values=private_values)
    write_json(output / "manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study-run", type=Path, required=True)
    parser.add_argument("--analysis-run", type=Path, required=True)
    parser.add_argument("--journey-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=HERE / "sample")
    args = parser.parse_args()
    result = export_sample(
        args.study_run.resolve(),
        args.analysis_run.resolve(),
        args.journey_dir.resolve(),
        args.output.resolve(),
    )
    print(f"Published {len(result['participants'])} complete journeys to {args.output}")


if __name__ == "__main__":
    main()
