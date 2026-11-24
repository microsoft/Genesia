import json

import pytest

from genesia.environments import (
    CapturedEnvironment,
    CardReviewEnvironment,
    ContextReviewEnvironment,
    EnvironmentBuilderAgent,
    material_files,
)
from genesia.runtime import EvidenceStore
from genesia.schemas import Action, EnvironmentAssessment, EnvironmentSpec, Graph, GraphNode, SourceSpec


class NoModel:
    def complete(self, *args, **kwargs):
        raise AssertionError("Scenario and canonical graphs do not need a builder model")


def test_assessment_schema_exposes_the_per_list_citation_constraint():
    schema = EnvironmentAssessment.model_json_schema()
    for model in ("AssessedUIState", "AssessedTransition"):
        description = schema["$defs"][model]["properties"]["evidence"]["description"]
        assert "source_id" in description and "at most once" in description
        assert "contiguous" in description and "verbatim" in description


@pytest.mark.parametrize("duplicate_in", ["states", "transitions"])
def test_assessment_keeps_duplicate_source_rejection_and_allows_shared_documents(duplicate_in):
    sources = [{"id": "spec", "kind": "document", "text": "Home. Detail. Open goes from Home to Detail."}]
    value = EnvironmentAssessment.model_validate(
        {
            "summary": "A document describes two states",
            "states": [
                {
                    "id": "home",
                    "title": "Home",
                    "description": "Home",
                    "evidence": [{"source_id": "spec", "quote": "Home."}],
                },
                {
                    "id": "detail",
                    "title": "Detail",
                    "description": "Detail",
                    "evidence": [{"source_id": "spec", "quote": "Detail."}],
                },
            ],
            "transitions": [
                {
                    "source": "home",
                    "target": "detail",
                    "label": "Open",
                    "evidence": [{"source_id": "spec", "quote": "Open goes from Home to Detail."}],
                }
            ],
        }
    )
    value.validate_sources(sources)
    records = getattr(value, duplicate_in)
    records[0].evidence.append(records[0].evidence[0].model_copy(update={"quote": "Home."}))
    with pytest.raises(ValueError, match="Duplicate source citations"):
        value.validate_sources(sources)


class CompileModel:
    def complete(self, purpose, payload, schema, **kwargs):
        if purpose == "environment_readiness":
            result = schema.model_validate(
                dict(
                    summary="Fixture content assessment",
                    states=[
                        dict(
                            id=f"state-{index}",
                            title=source["name"],
                            description="Visible UI state",
                            evidence=[dict(source_id=source["id"])],
                        )
                        for index, source in enumerate(payload["sources"])
                        if source["kind"] == "image"
                    ],
                )
            )
            kwargs["validate"](result)
            return result
        if purpose == "ui_card_extract":
            return schema.model_validate(
                {"title": payload["source"]["name"], "description": "Visible UI state"}
            )
        if purpose == "ui_card_bind":
            result = schema.model_validate(
                {
                    "states": [
                        {"id": f"state-{index}", "title": card["title"], "card_ids": [card["id"]]}
                        for index, card in enumerate(payload["cards"])
                    ]
                }
            )
            kwargs["validate"](result)
            return result
        raise AssertionError(purpose)


def test_auto_non_ui_image_stays_context_after_agent_assessment(tmp_path):
    class ContextModel:
        def complete(self, purpose, payload, schema, **kwargs):
            assert purpose == "environment_readiness"
            assert kwargs["images"] == [payload["sources"][0]["id"]]
            assert "persona" not in payload and "methods" not in payload
            result = schema.model_validate(
                dict(summary="Photograph, not a UI", states=[], transitions=[], issues=["No UI states"])
            )
            kwargs["validate"](result)
            return result

    image = tmp_path / "photo.png"
    image.write_bytes(b"fixture image")
    store = EvidenceStore(tmp_path / "run")
    result = EnvironmentBuilderAgent(ContextModel(), store).compile(
        EnvironmentSpec(mode="auto", sources=[SourceSpec(kind="image", path=str(image))]), "Review"
    )
    assert result.level == "context" and not result.cards and result.graph is None
    assert result.assessment.summary == "Photograph, not a UI"
    assert (store.root / "environment_readiness.json").exists()


def test_auto_document_compiles_to_context(tmp_path):
    source = tmp_path / "concept.md"
    source.write_text("A product concept without defined screens or transitions.", "utf-8")
    store = EvidenceStore(tmp_path / "run")

    result = EnvironmentBuilderAgent(CompileModel(), store).compile(
        EnvironmentSpec(mode="auto", sources=[SourceSpec(kind="document", path=str(source))]),
        "Review concept",
    )
    environment = ContextReviewEnvironment(result.context, store, {})

    assert result.level == "context" and result.graph is None and not result.cards
    assert "product concept" in environment.observe().text.casefold()
    assert (store.root / "environment_build.json").is_file()
    with pytest.raises(ValueError, match="compile"):
        EnvironmentBuilderAgent(NoModel(), store).build(
            EnvironmentSpec(mode="auto", sources=[SourceSpec(kind="document", path=str(source))]),
            "Review concept",
        )


def test_auto_images_compile_to_cards_without_graph(tmp_path):
    image = tmp_path / "screen.png"
    image.write_bytes(b"fixture image")
    store = EvidenceStore(tmp_path / "run")

    result = EnvironmentBuilderAgent(CompileModel(), store).compile(
        EnvironmentSpec(mode="auto", sources=[SourceSpec(kind="image", path=str(image))]),
        "Review screen",
    )
    environment = CardReviewEnvironment(result.cards, store, {})

    assert result.level == "cards" and result.graph is None and len(result.cards) == 1
    assert environment.observe().card_ids == ["card-001"]
    assert any("graph not generated" in issue for issue in result.issues)


def test_auto_recording_compiles_cards_into_chronology_graph(tmp_path):
    for name in ("001.png", "002.png"):
        (tmp_path / name).write_bytes(b"fixture image")
    manifest = tmp_path / "frames.json"
    manifest.write_text(
        '{"frames":[{"path":"001.png","timestamp_seconds":0},{"path":"002.png","timestamp_seconds":1}]}',
        "utf-8",
    )
    store = EvidenceStore(tmp_path / "run")

    result = EnvironmentBuilderAgent(CompileModel(), store).compile(
        EnvironmentSpec(mode="auto", sources=[SourceSpec(kind="recording", path=str(manifest))]),
        "Review recording",
    )

    assert result.level == "graph" and result.graph is not None
    assert len(result.graph.cards) == 2 and result.graph.observed_path == ["state-0", "state-1"]
    assert result.graph.edges[0].basis == "recorded_order"
    assert len(result.graph.edges[0].evidence_refs) == 2


class SpecModel:
    def __init__(self, *, connected=True, invalid=None):
        self.connected, self.invalid = connected, invalid

    def complete(self, purpose, payload, schema, **kwargs):
        assert purpose == "environment_readiness"
        ref = payload["sources"][0]["id"]
        data = dict(
            summary="Two explicit states in a spec",
            states=[
                dict(
                    id="home",
                    title="Home",
                    description="Home screen with Open button",
                    evidence=[dict(source_id=ref, quote="Home screen has an Open button.")],
                ),
                dict(
                    id="details",
                    title="Details",
                    description="Details screen",
                    evidence=[dict(source_id=ref, quote="Details screen has a title.")],
                ),
            ],
            transitions=[
                dict(
                    source="home",
                    target="details",
                    label="Open details",
                    evidence=[dict(source_id=ref, quote="Open takes Home to Details.")],
                )
            ]
            if self.connected
            else [],
        )
        if self.invalid == "source":
            data["states"][0]["evidence"][0]["source_id"] = "invented"
        elif self.invalid == "quote":
            data["transitions"][0]["evidence"][0]["quote"] = "Invented transition"
        elif self.invalid == "state":
            data["transitions"][0]["target"] = "invented"
        result = schema.model_validate(data)
        kwargs["validate"](result)
        return result


@pytest.mark.parametrize("connected,level", [(False, "cards"), (True, "graph")])
def test_auto_spec_assessed_by_content_not_extension(tmp_path, connected, level):
    source = tmp_path / "spec.md"
    source.write_text(
        "Home screen has an Open button. Details screen has a title. Open takes Home to Details.", "utf-8"
    )
    store = EvidenceStore(tmp_path / "run")
    result = EnvironmentBuilderAgent(SpecModel(connected=connected), store).compile(
        EnvironmentSpec(mode="auto", sources=[SourceSpec(kind="document", path=str(source))]), "Review"
    )
    assert result.level == level
    if result.graph:
        assert len(result.graph.cards) == 2
        assert all(node.card_ids for node in result.graph.nodes)
        assert result.graph.edges[0].basis == "declared"
        assert not result.graph.observed_path
    else:
        assert len(result.cards) == 2
        assert not (store.root / "state_graph.json").exists()


@pytest.mark.parametrize(
    "invalid,match", [("source", "unknown source"), ("quote", "quote"), ("state", "unknown readiness state")]
)
def test_readiness_rejects_invented_evidence(tmp_path, invalid, match):
    source = tmp_path / "spec.md"
    source.write_text(
        "Home screen has an Open button. Details screen has a title. Open takes Home to Details.", "utf-8"
    )
    store = EvidenceStore(tmp_path / "run")
    with pytest.raises(ValueError, match=match):
        EnvironmentBuilderAgent(SpecModel(invalid=invalid), store).compile(
            EnvironmentSpec(mode="auto", sources=[SourceSpec(kind="document", path=str(source))]), "Review"
        )
    assert not (store.root / "state_graph.json").exists()


def test_readiness_never_links_separate_recordings(tmp_path):
    for name in ("one.png", "two.png"):
        (tmp_path / name).write_bytes(b"fixture image")
    for name, image in [("first.json", "one.png"), ("second.json", "two.png")]:
        (tmp_path / name).write_text(json.dumps({"frames": [{"path": image, "timestamp_seconds": 0}]}))
    result = EnvironmentBuilderAgent(CompileModel(), EvidenceStore(tmp_path / "run")).compile(
        EnvironmentSpec(
            mode="auto",
            sources=[
                SourceSpec(kind="recording", path=str(tmp_path / name))
                for name in ("first.json", "second.json")
            ],
        ),
        "Review",
    )
    assert result.level == "cards" and result.graph is None


@pytest.mark.parametrize("connected", [False, True])
def test_auto_retains_background_with_ui_materials(tmp_path, connected):
    spec = tmp_path / "spec.md"
    spec.write_text(
        "Home screen has an Open button. Details screen has a title. Open takes Home to Details.", "utf-8"
    )
    brief = tmp_path / "brief.md"
    brief.write_text("Designed for shared family calendars.", "utf-8")
    store = EvidenceStore(tmp_path / "run")
    result = EnvironmentBuilderAgent(SpecModel(connected=connected), store).compile(
        EnvironmentSpec(
            mode="auto", sources=[SourceSpec(kind="document", path=str(path)) for path in (spec, brief)]
        ),
        "Review",
    )
    environment = (
        CapturedEnvironment(result.graph, store, "captured_graph", {}, context=result.context)
        if result.graph
        else CardReviewEnvironment(result.cards, store, {}, context=result.context)
    )
    observation = environment.observe()
    assert "Supplied background (not a UI state):" in observation.text
    assert "shared family calendars" in observation.text
    assert set(result.context[0].source_ids).issubset(observation.evidence_refs)
    assert "shared family calendars" in store.path(observation.evidence_refs[-1]).read_text("utf-8")


@pytest.mark.parametrize("connected", [False, True])
def test_auto_retains_cited_global_background_without_exposing_other_states(tmp_path, connected):
    class BackgroundModel(SpecModel):
        def complete(self, purpose, payload, schema, **kwargs):
            assessment = super().complete(purpose, payload, schema, **kwargs)
            assessment.background = [
                dict(source_id=payload["sources"][0]["id"], quote=quote)
                for quote in ("The data is synthetic.", "History is empty in a fresh session.")
            ]
            kwargs["validate"](assessment)
            return assessment

    source = tmp_path / "spec.md"
    source.write_text(
        "The data is synthetic. Home screen has an Open button. Details screen has a title. "
        "Open takes Home to Details. History is empty in a fresh session. "
        "UNVISITED_PAGE_HAS_A_SECRET_PANEL.",
        "utf-8",
    )
    store = EvidenceStore(tmp_path / "run")
    result = EnvironmentBuilderAgent(BackgroundModel(connected=connected), store).compile(
        EnvironmentSpec(mode="auto", sources=[SourceSpec(kind="document", path=str(source))]), "Review"
    )
    assert len(result.context) == 1
    assert result.context[0].text == "The data is synthetic.\n\nHistory is empty in a fresh session."
    environment = (
        CapturedEnvironment(result.graph, store, "captured_graph", {}, context=result.context)
        if connected
        else CardReviewEnvironment(result.cards, store, {}, context=result.context)
    )
    observation = environment.observe()
    assert "Supplied background (not a UI state):" in observation.text
    assert "The data is synthetic." in observation.text
    assert "History is empty in a fresh session." in observation.text
    assert "Details screen has a title." not in observation.text
    assert "UNVISITED_PAGE_HAS_A_SECRET_PANEL" not in observation.text
    assert set(result.context[0].source_ids).issubset(observation.evidence_refs)
    saved = store.path(observation.evidence_refs[-1]).read_text("utf-8")
    assert "History is empty in a fresh session." in saved
    assert "UNVISITED_PAGE_HAS_A_SECRET_PANEL" not in saved
    assert json.loads((store.root / "environment_readiness.json").read_text())["background"]


@pytest.mark.parametrize(
    "background,match",
    [
        ([dict(source_id="missing", quote="The data is synthetic.")], "unknown source"),
        ([dict(source_id="spec", quote="Invented global limitation.")], "quote"),
        ([dict(source_id="image")], "explicit text evidence"),
        ([dict(source_id="spec", quote="")], "quote"),
        (
            [dict(source_id="spec", quote="The data is synthetic.")] * 2,
            "Duplicate",
        ),
    ],
)
def test_global_background_requires_exact_nonduplicate_text_citations(background, match):
    assessment = EnvironmentAssessment(summary="Supplied background", background=background)
    sources = [
        dict(id="spec", kind="document", text="The data is synthetic."),
        dict(id="image", kind="image", text=""),
    ]
    with pytest.raises(ValueError, match=match):
        assessment.validate_sources(sources)


@pytest.mark.parametrize("with_ui", [False, True])
def test_background_does_not_duplicate_an_already_unbound_document(tmp_path, with_ui):
    from genesia.cards import compile_assessed_materials

    store = EvidenceStore(tmp_path)
    ref = store.put(b"The data is synthetic.", "source", ".txt")
    sources = [dict(id=ref, name="brief", kind="document", text="The data is synthetic.", sequence=0)]
    states = []
    if with_ui:
        image = store.put(b"screen", "source_image", ".png")
        sources.append(dict(id=image, name="screen", kind="image", text="", sequence=1))
        states.append(dict(id="s", title="Screen", description="Screen", evidence=[dict(source_id=image)]))
    result = compile_assessed_materials(
        sources,
        EnvironmentAssessment(
            summary="Review",
            states=states,
            background=[dict(source_id=ref, quote="The data is synthetic.")],
        ),
        store,
    )
    assert len(result.context) == 1
    assert result.context[0].text == "The data is synthetic."


@pytest.mark.parametrize("connected", [False, True])
def test_static_state_cards_keep_text_and_images_together_in_image_order(tmp_path, connected):
    from genesia.cards import compile_assessed_materials

    store = EvidenceStore(tmp_path)
    text = "First state. Second state. Open takes First to Second."
    spec = store.put(text.encode(), "source", ".txt")
    first = store.put(b"first-image", "source_image", ".png")
    second = store.put(b"second-image", "source_image", ".png")
    detail = store.put(b"first-image-detail", "source_image", ".png")
    sources = [
        dict(id=spec, kind="document", name="spec", text=text, sequence=0, provenance="design"),
        dict(id=first, kind="image", name="first", text="", sequence=1, provenance="design"),
        dict(id=second, kind="image", name="second", text="", sequence=2, provenance="design"),
        dict(id=detail, kind="image", name="detail", text="", sequence=3, provenance="design"),
    ]
    assessment = EnvironmentAssessment(
        summary="Two static UI states, including two views of the first state",
        states=[
            dict(
                id="second",
                title="Second",
                description="Second state.",
                evidence=[dict(source_id=spec, quote="Second state."), dict(source_id=second)],
            ),
            dict(
                id="first",
                title="First",
                description="First state.",
                evidence=[
                    dict(source_id=spec, quote="First state."),
                    dict(source_id=first),
                    dict(source_id=detail),
                ],
            ),
        ],
        transitions=[
            dict(
                source="first",
                target="second",
                label="Open",
                evidence=[dict(source_id=spec, quote="Open takes First to Second.")],
            )
        ]
        if connected
        else [],
    )
    result = compile_assessed_materials(sources, assessment, store)
    cards = result.graph.cards if connected else result.cards
    assert len(cards) == 2
    assert sorted(card.sequence for card in cards) == [1, 2]
    assert all(spec in card.source_ids and card.image_refs for card in cards)
    environment = (
        CapturedEnvironment(result.graph, store, "captured_graph", {})
        if connected
        else CardReviewEnvironment(cards, store, {})
    )
    observation = environment.observe()
    assert observation.text == "First\nFirst state."
    assert observation.image_refs == [first, detail]
    assert {spec, first, detail}.issubset(observation.evidence_refs)
    assert second not in observation.evidence_refs
    environment.act(
        Action(
            action="click",
            target_id=observation.targets[0].id,
            intent="Review second supplied state",
        )
    )
    observation = environment.observe()
    assert observation.text == "Second\nSecond state."
    assert observation.image_refs == [second]
    assert environment.coverage()["unseen_cards"] == []


def test_assessed_recording_preserves_separate_frames_and_return_order(tmp_path):
    from genesia.cards import compile_assessed_materials
    from genesia.environments import WalkthroughEnvironment

    store = EvidenceStore(tmp_path)
    parent = store.json({"name": "recording"}, "recording_manifest")
    frames = [store.put(f"frame-{i}".encode(), "source_image", ".png") for i in range(3)]
    sources = [
        dict(
            id=ref,
            kind="image",
            name=f"frame-{i}",
            text="",
            sequence=i,
            timestamp_seconds=i,
            provenance="recorded",
            parent_ref=parent,
            trace_events=[{"timestamp_seconds": i}],
        )
        for i, ref in enumerate(frames)
    ]
    assessment = EnvironmentAssessment(
        summary="A recorded return to the same stable state",
        states=[
            dict(
                id="home",
                title="Home",
                description="Home",
                evidence=[dict(source_id=frames[0]), dict(source_id=frames[2])],
            ),
            dict(id="edit", title="Edit", description="Edit", evidence=[dict(source_id=frames[1])]),
        ],
    )
    result = compile_assessed_materials(sources, assessment, store)
    assert result.level == "graph" and result.graph.observed_path == ["home", "edit", "home"]
    assert len(result.graph.cards) == 3
    environment = WalkthroughEnvironment(result.graph, store, "walkthrough", {})
    for index, image in enumerate(frames):
        observation = environment.observe()
        assert observation.image_refs == [image]
        card = next(card for card in result.graph.cards if card.id == observation.card_ids[0])
        assert card.timestamp_seconds == index
        assert card.trace_events == [{"timestamp_seconds": index}]
        assert card.provenance == "recorded"
        if observation.targets:
            environment.act(Action(action="click", target_id="next", intent="Continue supplied recording"))
    assert environment.coverage()["unseen_cards"] == []


def test_recorded_cards_share_spec_evidence_without_creating_extra_text_frames(tmp_path):
    from genesia.cards import compile_assessed_materials

    store = EvidenceStore(tmp_path)
    spec = store.put(b"The recorded state shows a form.", "source", ".txt")
    frames = [store.put(f"frame-{index}".encode(), "source_image", ".png") for index in range(2)]
    sources = [
        dict(
            id=spec,
            kind="document",
            name="spec",
            text="The recorded state shows a form.",
            sequence=0,
        )
    ] + [
        dict(
            id=ref,
            kind="image",
            name=f"frame-{index}",
            text="",
            sequence=index + 1,
            timestamp_seconds=index,
            provenance="recorded",
            parent_ref="recording",
            trace_events=[{"timestamp_seconds": index}],
        )
        for index, ref in enumerate(frames)
    ]
    result = compile_assessed_materials(
        sources,
        EnvironmentAssessment(
            summary="Two frames of the same stable state",
            states=[
                dict(
                    id="form",
                    title="Form",
                    description="The recorded state shows a form.",
                    evidence=[
                        dict(source_id=spec, quote="The recorded state shows a form."),
                        *[dict(source_id=ref) for ref in frames],
                    ],
                )
            ],
        ),
        store,
    )
    assert result.level == "cards" and len(result.cards) == 2
    for index, card in enumerate(result.cards):
        assert card.source_ids == [spec, frames[index]]
        assert card.image_refs == [frames[index]]
        assert card.sequence == index + 1 and card.timestamp_seconds == index
        assert card.trace_events == [{"timestamp_seconds": index}]
        assert card.provenance == "recorded"


def test_scenario_reads_supplied_material(tmp_path):
    source = tmp_path / "spec.md"
    source.write_text("A simple calendar with a Save button.", encoding="utf-8")
    spec = EnvironmentSpec(mode="scenario", sources=[SourceSpec(kind="document", path=str(source))])
    store = EvidenceStore(tmp_path / "run")
    graph = EnvironmentBuilderAgent(NoModel(), store).build(spec, "Review calendar")
    environment = CapturedEnvironment(graph, store, "scenario", {"persona_id": "p", "session_id": "s"})
    observation = environment.observe()
    assert "Save button" in observation.text
    assert store.refs[observation.evidence_refs[-1]].session_id == "s"
    with pytest.raises(ValueError):
        environment.act(Action(action="click", target_id="invented", intent="Click"))


def test_auto_canonical_graph_bypasses_assessment_and_rebinds_evidence(tmp_path):
    path = tmp_path / "graph.json"
    path.write_text(
        json.dumps(
            dict(
                start="home",
                nodes=[dict(id=name, text=name, source_ids=["old-source"]) for name in ("home", "help")],
                edges=[
                    dict(
                        id="open",
                        source="home",
                        target="help",
                        label="Open Help",
                        evidence_refs=["old-source"],
                    )
                ],
            )
        ),
        "utf-8",
    )
    store = EvidenceStore(tmp_path / "run")
    result = EnvironmentBuilderAgent(NoModel(), store).compile(
        EnvironmentSpec(mode="auto", sources=[SourceSpec(kind="graph", path=str(path))]), "Review"
    )
    assert result.level == "graph" and result.assessment is None
    assert result.graph.edges[0].evidence_refs == result.graph.nodes[0].source_ids
    assert set(result.graph.edges[0].evidence_refs).issubset(store.refs)
    assert not (store.root / "environment_readiness.json").exists()


def test_readiness_rejects_image_only_transition_claims():
    sources = [dict(id=name, kind="image", text="") for name in ("first", "second")]
    assessment = EnvironmentAssessment.model_validate(
        dict(
            summary="Two screenshots",
            states=[
                dict(id=name, title=name, description="UI", evidence=[dict(source_id=name)])
                for name in ("first", "second")
            ],
            transitions=[
                dict(
                    source="first", target="second", label="Assumed next", evidence=[dict(source_id="first")]
                )
            ],
        )
    )
    with pytest.raises(ValueError, match="explicit text evidence"):
        assessment.validate_sources(sources)


def test_mixed_image_and_text_can_support_declared_graph(tmp_path):
    class MixedModel(CompileModel):
        def complete(self, purpose, payload, schema, **kwargs):
            assessment = super().complete(purpose, payload, schema, **kwargs)
            text = next(source for source in payload["sources"] if source["kind"] == "document")
            assessment.transitions = [
                dict(
                    source=assessment.states[0].id,
                    target=assessment.states[1].id,
                    label="Open Details",
                    evidence=[dict(source_id=text["id"], quote=text["text"])],
                )
            ]
            kwargs["validate"](assessment)
            return assessment

    for name in ("home.png", "details.png"):
        (tmp_path / name).write_bytes(b"fixture image")
    (tmp_path / "flow.md").write_text("Open takes Home to Details.", "utf-8")
    store = EvidenceStore(tmp_path / "run")
    result = EnvironmentBuilderAgent(MixedModel(), store).compile(
        EnvironmentSpec(
            mode="auto",
            sources=[
                SourceSpec(kind="image", path=str(tmp_path / "home.png")),
                SourceSpec(kind="image", path=str(tmp_path / "details.png")),
                SourceSpec(kind="document", path=str(tmp_path / "flow.md")),
            ],
        ),
        "Review",
    )
    assert result.level == "graph" and len(result.graph.cards) == 2
    assert result.graph.edges[0].basis == "declared"
    assert result.graph.edges[0].evidence_refs
    assert set(result.graph.edges[0].evidence_refs).issubset(store.refs)
    assert not result.context


def test_auto_does_not_treat_provider_failure_as_missing_ui(tmp_path):
    class FailedModel:
        def complete(self, *args, **kwargs):
            raise RuntimeError("Provider unavailable")

    source = tmp_path / "concept.md"
    source.write_text("A product concept.", "utf-8")
    store = EvidenceStore(tmp_path / "run")
    with pytest.raises(RuntimeError, match="Provider unavailable"):
        EnvironmentBuilderAgent(FailedModel(), store).compile(
            EnvironmentSpec(mode="auto", sources=[SourceSpec(kind="document", path=str(source))]), "Review"
        )
    assert not (store.root / "environment_build.json").exists()


def test_capture_cannot_type(tmp_path):
    store = EvidenceStore(tmp_path)
    ref = store.put(b"screen", "source", ".txt")
    graph = Graph(start="a", nodes=[GraphNode(id="a", text="Screen", source_ids=[ref])])
    environment = CapturedEnvironment(graph, store, "captured_graph", {})
    environment.observe()
    with pytest.raises(ValueError):
        environment.act(Action(action="type", target_id="anything", value="text", intent="Fill"))


def test_recording_paths_confined(tmp_path):
    manifest = tmp_path / "frames.json"
    manifest.write_text('{"frames":[{"path":"../outside.png"}]}', encoding="utf-8")
    with pytest.raises(ValueError, match="escapes"):
        material_files(
            EnvironmentSpec(mode="image_direct", sources=[SourceSpec(kind="recording", path=str(manifest))])
        )


def test_image_direct_preserves_recording_frame_order(tmp_path):
    for index in range(2):
        (tmp_path / f"frame{index}.png").write_bytes(b"fixture image " + bytes([index]))
    manifest = tmp_path / "frames.json"
    manifest.write_text('{"frames":[{"path":"frame0.png"},{"path":"frame1.png"}]}', encoding="utf-8")
    store = EvidenceStore(tmp_path / "run")
    spec = EnvironmentSpec(mode="image_direct", sources=[SourceSpec(kind="recording", path=str(manifest))])
    graph = EnvironmentBuilderAgent(NoModel(), store).build(spec, "Review")
    environment = CapturedEnvironment(graph, store, spec.mode, {})
    first = environment.observe()
    environment.act(Action(action="click", target_id=first.targets[0].id, intent="Next frame"))
    second = environment.observe()
    assert store.path(first.image_refs[0]).read_bytes().endswith(bytes([0]))
    assert store.path(second.image_refs[0]).read_bytes().endswith(bytes([1]))
