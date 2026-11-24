"""Bounded source adapters. Importing this module performs no network or model calls."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from pathlib import Path
from urllib.parse import quote, urlsplit

import requests

from .runtime import EvidenceStore
from .schemas import EnvironmentSpec, Permissions, SourceSpec

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def confined_path(parent: Path, relative: str) -> Path:
    path = (parent / relative).resolve()
    if not path.is_relative_to(parent.resolve()):
        raise ValueError("Material path escapes manifest directory")
    if not path.is_file():
        raise ValueError("Referenced material is missing")
    return path


def read_document(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(path)
        if len(reader.pages) > 200:
            raise ValueError("PDF exceeds 200 pages; scope the document")
        text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
    elif path.suffix.lower() == ".docx":
        from docx import Document

        document = Document(path)
        text = "\n".join(
            [paragraph.text for paragraph in document.paragraphs]
            + [" | ".join(cell.text for cell in row.cells) for table in document.tables for row in table.rows]
        )
    else:
        text = path.read_text(encoding="utf-8-sig")
    if not text.strip():
        raise ValueError("Document has no extractable text; supply images for scanned documents")
    if len(text.encode("utf-8")) > 200_000:
        raise ValueError("Extracted text exceeds 200KB; scope the document")
    return text


def trace_events(path: str | None) -> list[dict]:
    if not path:
        return []
    text = Path(path).read_text("utf-8-sig")
    if Path(path).suffix.lower() in {".txt", ".jsonl"}:
        raw = [
            json.loads(line)
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
    else:
        raw = json.loads(text)
    if not isinstance(raw, (list, dict)):
        raise ValueError("Trace JSON must be an events array or an object containing events")
    events = raw if isinstance(raw, list) else raw.get("events")
    if not isinstance(events, list) or len(events) > 100_000:
        raise ValueError("Trace requires a bounded events array")
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("Trace events must be JSON objects")
        timestamp = event.get("timestamp_seconds", event.get("timestamp"))
        if isinstance(timestamp, str) and re.fullmatch(r"\d{2}:\d{2}:\d{2}(?:\.\d+)?", timestamp):
            hours, minutes, seconds = timestamp.split(":")
            if int(minutes) >= 60 or float(seconds) >= 60:
                raise ValueError("Invalid relative trace clock")
            timestamp = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        if not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp) or timestamp < 0:
            raise ValueError("Trace events need finite relative timestamp_seconds")
        event["timestamp_seconds"] = timestamp
    return sorted(events, key=lambda event: event["timestamp_seconds"])


def inspect_sources(spec: EnvironmentSpec) -> list[tuple[str, Path]]:
    result = []
    if any(source.kind == "graph" for source in spec.sources) and len(spec.sources) != 1:
        raise ValueError(
            "Canonical graph input cannot be mixed with other sources; import cards or use a single graph"
        )
    for source in spec.sources:
        if source.kind == "figma":
            if not re.fullmatch(r"[A-Za-z0-9_-]+", source.path) or len(source.figma_nodes) > 24:
                raise ValueError("Figma path must be a file key, with at most 24 nodes")
            continue
        path = Path(source.path).resolve()
        if source.kind == "cards":
            if not path.is_dir():
                raise ValueError("Cards input requires a directory of numbered Markdown files")
            cards = sorted(path.glob("*.md"))
            if not cards or len(cards) > 120:
                raise ValueError("Card folder requires 1-120 numbered Markdown cards")
            numbers = [
                int(re.match(r"^(\d+)_", card.name)[1]) if re.match(r"^(\d+)_", card.name) else -1
                for card in cards
            ]
            if -1 in numbers or len(numbers) != len(set(numbers)):
                raise ValueError("Card filenames require unique NN_ chronology prefixes")
            result.extend(("document", card) for card in cards)
            if any(card.stat().st_size > 200_000 for card in cards):
                raise ValueError("Each card must be under 200KB")
            continue
        if not path.is_file():
            raise ValueError(f"Material not found: {path}")
        limit = 2_000_000_000 if source.kind == "video" else 20_000_000
        if path.stat().st_size > limit:
            raise ValueError("Source exceeds file size limit")
        if source.kind == "image" and path.suffix.lower() not in IMAGE_SUFFIXES:
            raise ValueError("Images must be PNG, JPEG or WebP")
        if source.kind == "recording":
            manifest = json.loads(path.read_text("utf-8-sig"))
            if not isinstance(manifest, dict):
                raise ValueError("Recording manifest must be a JSON object")
            frames = manifest.get("frames", [])
            if not isinstance(frames, list) or not frames or len(frames) > 120:
                raise ValueError("Recording manifest requires 1-120 frames")
            previous = -1.0
            for index, frame in enumerate(frames):
                if not isinstance(frame, dict):
                    raise ValueError("Recording frames must be JSON objects")
                frame_path = confined_path(path.parent, frame["path"])
                if frame_path.suffix.lower() not in IMAGE_SUFFIXES:
                    raise ValueError("Recording frames must be images")
                if frame_path.stat().st_size > 20_000_000:
                    raise ValueError("Recording frame exceeds 20MB")
                timestamp = frame.get("timestamp_seconds", float(index))
                if (
                    not isinstance(timestamp, (float, int))
                    or not math.isfinite(timestamp)
                    or timestamp < previous
                ):
                    raise ValueError("Recording timestamps must be finite and chronological")
                previous = timestamp
                result.append(("image", frame_path))
        if source.trace_path:
            trace_events(source.trace_path)
        result.append((source.kind, path))
    return result


def _file_digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def decode_video(source: SourceSpec, store: EvidenceStore) -> list[dict]:
    import cv2

    path = Path(source.path)
    capture = cv2.VideoCapture(str(path))
    try:
        fps = capture.get(cv2.CAP_PROP_FPS)
        count = capture.get(cv2.CAP_PROP_FRAME_COUNT)
        if (
            not capture.isOpened()
            or not math.isfinite(fps)
            or not math.isfinite(count)
            or fps <= 0
            or count <= 0
        ):
            raise ValueError("Video cannot be decoded or lacks valid duration")
        duration = count / fps
        if duration > 3600:
            raise ValueError("Video exceeds one hour; provide a scoped segment")
        timestamps = [
            index * source.sample_seconds for index in range(math.ceil(duration / source.sample_seconds))
        ]
        if len(timestamps) >= source.max_frames:
            timestamps = [
                index * max(0, (count - 1) / fps) / (source.max_frames - 1)
                for index in range(source.max_frames)
            ]
        elif timestamps[-1] < (count - 1) / fps:
            timestamps.append((count - 1) / fps)
        source_ref = store.json(
            {
                "name": path.name,
                "sha256": _file_digest(path),
                "duration_seconds": duration,
                "fps": fps,
                "policy": "uniform bounded sampling; transient states may be missed",
            },
            "video_source",
        )
        frames = []
        for timestamp in timestamps:
            capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
            ok, frame = capture.read()
            if not ok:
                raise ValueError(f"Frame decode failed at {timestamp:.3f}s")
            if max(frame.shape[:2]) > 1600:
                scale = 1600 / max(frame.shape[:2])
                frame = cv2.resize(frame, (int(frame.shape[1] * scale), int(frame.shape[0] * scale)))
            ok, encoded = cv2.imencode(".jpg", frame)
            if not ok:
                raise ValueError("Frame encoding failed")
            ref = store.put(encoded.tobytes(), "source_image", ".jpg")
            frames.append(
                {
                    "id": ref,
                    "kind": "image",
                    "name": f"{path.name}@{timestamp:.3f}s",
                    "text": "",
                    "timestamp_seconds": timestamp,
                    "provenance": "recorded",
                    "parent_ref": source_ref,
                }
            )
        return frames
    finally:
        capture.release()


def _download(http, url: str, *, headers=None, limit=20_000_000) -> bytes:
    with http.get(url, headers=headers, timeout=30, allow_redirects=False, stream=True) as response:
        if response.status_code != 200:
            raise ValueError(f"Source request failed with HTTP {response.status_code}")
        chunks, total = [], 0
        for chunk in response.iter_content(65536):
            total += len(chunk)
            if total > limit:
                raise ValueError("Source download exceeds size bound")
            chunks.append(chunk)
        return b"".join(chunks)


def export_figma(source: SourceSpec, store: EvidenceStore, permissions: Permissions) -> list[dict]:
    if not permissions.fetch_figma:
        raise ValueError("Figma network access requires fetch_figma permission")
    token = os.environ.get(source.token_env)
    if not token:
        raise ValueError("Figma token environment variable is not configured")
    with requests.Session() as http:
        http.trust_env = False
        url = f"https://api.figma.com/v1/images/{quote(source.path, safe='')}?format=png&ids={quote(','.join(source.figma_nodes), safe='')}"
        metadata = json.loads(_download(http, url, headers={"X-Figma-Token": token}, limit=1_000_000))
        frames = []
        for node in source.figma_nodes:
            image_url = metadata.get("images", {}).get(node)
            parsed = urlsplit(image_url or "")
            host = parsed.hostname or ""
            if (
                parsed.scheme != "https"
                or parsed.username
                or parsed.password
                or parsed.port not in {None, 443}
                or not any(
                    host == domain or host.endswith("." + domain) for domain in ("figma.com", "amazonaws.com")
                )
            ):
                raise ValueError("Figma returned a missing or non-allowlisted export URL")
            data = _download(http, image_url)
            if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("Figma export is not a PNG")
            ref = store.put(data, "source_image", ".png")
            frames.append(
                {
                    "id": ref,
                    "kind": "image",
                    "name": f"Figma {source.path}/{node}",
                    "text": "",
                    "provenance": "design",
                }
            )
        return frames


def normalize_sources(spec: EnvironmentSpec, store: EvidenceStore, permissions: Permissions) -> list[dict]:
    inspect_sources(spec)
    result = []
    for source in spec.sources:
        path = Path(source.path)
        if source.kind == "video":
            items = decode_video(source, store)
        elif source.kind == "figma":
            items = export_figma(source, store, permissions)
        elif source.kind == "recording":
            manifest = json.loads(path.read_text("utf-8-sig"))
            parent = store.json(manifest, "recording_manifest")
            items = []
            for index, frame in enumerate(manifest["frames"]):
                image = confined_path(path.parent, frame["path"])
                suffix = ".jpg" if image.suffix.lower() == ".jpeg" else image.suffix.lower()
                ref = store.put(image.read_bytes(), "source_image", suffix)
                items.append(
                    {
                        "id": ref,
                        "kind": "image",
                        "name": image.name,
                        "text": "",
                        "timestamp_seconds": frame.get("timestamp_seconds", float(index)),
                        "provenance": "recorded",
                        "parent_ref": parent,
                    }
                )
        elif source.kind == "cards" and path.is_dir():
            items = []
            paths = sorted(path.glob("*.md"), key=lambda item: int(item.name.split("_", 1)[0]))
            for card_path in paths:
                text = read_document(card_path)
                ref = store.put(text.encode("utf-8"), "source", ".txt")
                items.append(
                    {
                        "id": ref,
                        "kind": "card",
                        "name": card_path.stem,
                        "text": text,
                        "provenance": "supplied",
                    }
                )
        else:
            kind = source.kind
            if kind == "image":
                suffix = ".jpg" if path.suffix.lower() == ".jpeg" else path.suffix.lower()
                ref = store.put(path.read_bytes(), "source_image", suffix)
                text = ""
            else:
                text = read_document(path)
                ref = store.put(text.encode("utf-8"), "source", ".txt")
                store.json(
                    {"name": path.name, "sha256": _file_digest(path), "extracted_ref": ref},
                    "source_provenance",
                )
            items = [{"id": ref, "kind": kind, "name": path.name, "text": text, "provenance": "design"}]
        events = trace_events(source.trace_path)
        if events:
            store.json(events, "input_trace")
            timestamps = [item["timestamp_seconds"] for item in items if "timestamp_seconds" in item]
            if timestamps and any(event["timestamp_seconds"] > max(timestamps) for event in events):
                store.event(
                    "trace_outside_sample_range",
                    count=sum(event["timestamp_seconds"] > max(timestamps) for event in events),
                )
        for index, item in enumerate(items):
            if "timestamp_seconds" in item:
                start = 0 if index == 0 else items[index - 1]["timestamp_seconds"]
                end = item["timestamp_seconds"]
                item["trace_events"] = [
                    event
                    for event in events
                    if (
                        start <= event["timestamp_seconds"] <= end
                        if index == 0
                        else start < event["timestamp_seconds"] <= end
                    )
                ]
            item["sequence"] = len(result)
            result.append(item)
    if not result:
        raise ValueError("No source material was produced")
    return result
