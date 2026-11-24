import json

import pytest

from genesia.api import preflight
from genesia.runtime import EvidenceStore
from genesia.schemas import EnvironmentSpec, Permissions, SourceSpec
from genesia.sources import export_figma, normalize_sources, read_document, trace_events


@pytest.mark.media
def test_decode_video_and_align_trace(tmp_path):
    cv2 = pytest.importorskip("cv2")
    numpy = pytest.importorskip("numpy")
    video = tmp_path / "flow.avi"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 5, (64, 48))
    assert writer.isOpened()
    for index in range(15):
        writer.write(numpy.full((48, 64, 3), index * 15, dtype=numpy.uint8))
    writer.release()
    trace = tmp_path / "trace.json"
    trace.write_text(json.dumps({"events": [{"timestamp_seconds": 0.5, "action": "click"}]}))
    spec = EnvironmentSpec(
        mode="walkthrough",
        sources=[
            SourceSpec(kind="video", path=str(video), trace_path=str(trace), sample_seconds=1, max_frames=4)
        ],
    )
    store = EvidenceStore(tmp_path / "run")
    sources = normalize_sources(spec, store, Permissions())
    assert len(sources) == 4
    assert sources[0]["timestamp_seconds"] == 0
    assert sum(len(source["trace_events"]) for source in sources) == 1
    assert store.verify()["valid"]


@pytest.mark.media
def test_auto_non_ui_video_stays_context(tmp_path):
    from genesia.environments import EnvironmentBuilderAgent

    class NonUIModel:
        def complete(self, purpose, payload, schema, **kwargs):
            assert purpose == "environment_readiness"
            assert len(kwargs["images"]) == 2
            assert all(source["provenance"] == "recorded" for source in payload["sources"])
            result = schema.model_validate(
                dict(summary="Solid color frames, no UI", states=[], transitions=[])
            )
            kwargs["validate"](result)
            return result

    cv2 = pytest.importorskip("cv2")
    numpy = pytest.importorskip("numpy")
    video = tmp_path / "colors.avi"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 5, (64, 48))
    assert writer.isOpened()
    try:
        for index in range(5):
            writer.write(numpy.full((48, 64, 3), index * 30, dtype=numpy.uint8))
    finally:
        writer.release()
    store = EvidenceStore(tmp_path / "run")
    result = EnvironmentBuilderAgent(NonUIModel(), store).compile(
        EnvironmentSpec(mode="auto", sources=[SourceSpec(kind="video", path=str(video), max_frames=2)]),
        "Review",
    )
    assert result.level == "context" and len(result.context) == 2
    assert not (store.root / "ui_cards.json").exists()
    assert not (store.root / "state_graph.json").exists()
    assert store.verify()["valid"]


@pytest.mark.media
def test_docx_extracts_tables(tmp_path):
    docx = pytest.importorskip("docx")
    document = docx.Document()
    document.add_paragraph("Create a meeting")
    document.add_table(rows=1, cols=1).cell(0, 0).text = "Save"
    path = tmp_path / "spec.docx"
    document.save(path)
    assert "Save" in read_document(path)


def test_figma_requires_permission_before_token_or_network(tmp_path):
    with pytest.raises(ValueError, match="permission"):
        export_figma(
            SourceSpec(kind="figma", path="key", figma_nodes=["1:2"]), EvidenceStore(tmp_path), Permissions()
        )


def test_invalid_trace_fails(tmp_path):
    path = tmp_path / "trace.json"
    path.write_text('{"events":[{"timestamp_seconds":-1}]}')
    with pytest.raises(ValueError, match="timestamp_seconds"):
        trace_events(str(path))


@pytest.mark.parametrize(
    ("recording", "trace", "issue"),
    [
        ([], None, "Recording manifest"),
        ({"frames": {"path": "frame.png"}}, None, "Recording manifest"),
        ({"frames": [1]}, None, "Recording frames"),
        ({"frames": [{"path": "frame.png"}]}, "null", "Trace"),
        ({"frames": [{"path": "frame.png"}]}, "[1]", "Trace events"),
        ({"frames": [{"path": "frame.png"}]}, '{"events":[{"timestamp":0}]}', None),
    ],
)
def test_recording_and_trace_shapes_return_preflight_results(tmp_path, recording, trace, issue):
    from PIL import Image
    from test_workflow import task_fixture

    task = task_fixture(tmp_path)
    Image.new("RGB", (32, 32), "white").save(tmp_path / "frame.png")
    recording_path = tmp_path / "recording.json"
    recording_path.write_text(json.dumps(recording), encoding="utf-8")
    trace_path = None
    if trace is not None:
        trace_path = tmp_path / "trace.json"
        trace_path.write_text(trace, encoding="utf-8")
    task.environment = EnvironmentSpec(
        mode="auto",
        sources=[
            SourceSpec(
                kind="recording",
                path=str(recording_path),
                trace_path=str(trace_path) if trace_path else None,
            )
        ],
    )
    task.permissions.send_screenshots = True

    checks = preflight(task)

    if issue is None:
        assert checks["ok"], checks["issues"]
    else:
        assert not checks["ok"]
        assert any(message.startswith("Materials:") and issue in message for message in checks["issues"])


def test_mixed_canonical_graph_cannot_silently_drop_materials(tmp_path):
    from genesia.sources import inspect_sources

    spec = EnvironmentSpec(
        mode="captured_graph",
        sources=[SourceSpec(kind="graph", path="graph.json"), SourceSpec(kind="document", path="spec.md")],
    )
    with pytest.raises(ValueError, match="mixed"):
        inspect_sources(spec)


def test_legacy_jsonl_and_numeric_trace_timestamps(tmp_path):
    path = tmp_path / "input.txt"
    path.write_text('# Recording metadata\n{"timestamp":"00:00:03.744","message":"Click"}\n')
    assert trace_events(str(path))[0]["timestamp_seconds"] == 3.744
    path = tmp_path / "processed.json"
    path.write_text('[{"timestamp":1.5,"action":"click"}]')
    assert trace_events(str(path))[0]["timestamp_seconds"] == 1.5


def test_figma_export_and_host_policy(tmp_path, monkeypatch):
    from genesia import sources

    monkeypatch.setenv("FIGMA_ACCESS_TOKEN", "fixture-only-not-a-real-token")
    urls = []

    def download(http, url, **kwargs):
        urls.append((url, kwargs.get("headers")))
        if len(urls) == 1:
            return json.dumps({"images": {"1:2": "https://figma.com/export.png"}}).encode()
        return b"\x89PNG\r\n\x1a\nfixture"

    monkeypatch.setattr(sources, "_download", download)
    spec = SourceSpec(kind="figma", path="key", figma_nodes=["1:2"])
    result = export_figma(spec, EvidenceStore(tmp_path), Permissions(fetch_figma=True))
    assert result[0]["provenance"] == "design"
    assert urls[1][1] is None
    monkeypatch.setattr(
        sources, "_download", lambda *args, **kwargs: b'{"images":{"1:2":"https://127.0.0.1/private"}}'
    )
    with pytest.raises(ValueError, match="allowlisted"):
        export_figma(spec, EvidenceStore(tmp_path), Permissions(fetch_figma=True))
