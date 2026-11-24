# Recording Inputs

## Raw Video

Use `kind: video` for MP4/AVI or another format supported by the installed OpenCV build:

```yaml
environment:
  mode: auto
  sources:
    - kind: video
      path: ./recording.mp4
      trace_path: ./input-trace.jsonl
      sample_seconds: 3
      max_frames: 24
```

Genesia rejects files over 2GB and decoded duration over one hour. It samples uniformly at `sample_seconds`, bounds output by `max_frames`, and retains the final frame. Images larger than 1600 pixels on their longest side are reduced before evidence storage.

Uniform sampling can miss transient menus, errors, hover states and brief confirmation messages. Lowering `sample_seconds` improves temporal coverage but raises model calls and image cost. `max_frames` supports 2-120 frames.

## Chronological Frame Manifest

Use `kind: recording` when frames have already been selected:

```yaml
environment:
  mode: auto
  sources:
    - kind: recording
      path: ./recording/frames.json
      trace_path: ./recording/input-trace.jsonl
```

Manifest:

```json
{
  "frames": [
    {"path": "frames/001.png", "timestamp_seconds": 0.0},
    {"path": "frames/002.png", "timestamp_seconds": 2.5}
  ]
}
```

The manifest must be a JSON object with a `frames` array of frame objects. Frame paths must remain below the manifest directory, use PNG/JPEG/WebP, remain under 20MB each, and contain 1-120 entries. Timestamps default to sequence index and must be finite and nondecreasing.

## Trace

Accepted trace containers are a JSON object with `events`, a JSON array, or JSONL. Timestamp fields may be:

- `timestamp_seconds` as a nonnegative number;
- numeric `timestamp`;
- relative `HH:MM:SS.mmm` `timestamp`.

Every trace event must be a JSON object. Malformed manifest, trace-container or entry structures are reported as source-validation issues during preflight, before any model calls.

Trace events are attached to the sampled interval ending at each frame. Events beyond the sampled range are reported. A trace records supplied input evidence; it does not prove causation, execution success or resulting application state.

## Content Assessment And Generated Evidence

`auto` normalizes sources and assesses their content together; it does not route every recording to a walkthrough or require one Card per frame. Supporting `document` or `image` sources may be added to the same `sources` list. The builder returns a typed assessment, and code validates state IDs, endpoints, citations and verbatim transition text before selecting:

- Context when the evidence does not establish UI states;
- Cards when UI states are reviewable but connected transitions are not established;
- Graph when an entry reaches all states: a single recorded path supports walkthrough, while declared branches support captured-graph choice.

Runtime-derived `recorded_order` edges require adjacent identified frames in the same recording with increasing timestamps. Nondecreasing manifest timestamps are valid input, but equal timestamps do not establish an edge. Separate recordings, raw image order and Card numbering do not establish product transitions. A card-backed Graph binds every Card exactly once; material not bound to UI remains supplemental Context, labeled as background in the first observation.

Review `environment_readiness.json` for assessment and citations, `environment_build.json` for the validated level and issues, and `preparation.json` for research readiness. Inspect Cards and Graph artifacts only when produced. Context/Cards can be useful outputs, not compilation failures; model/provider failures remain failures. Source hashes and valid citations do not prove semantic fidelity.

## Explicit Prepared Inputs

Numbered `cards` and canonical `graph` sources are advanced prepared/debug inputs, not requirements for ordinary recordings. Canonical Graph imports explicitly bypass content assessment. Use an explicit `walkthrough` only for a caller-selected legacy/editorial sequence, and disclose that sequencing rather than treating it as automatically verified product navigation. `live` and `survey` bypass the compiler entirely; do not convert a live run into a recorded study after execution.
