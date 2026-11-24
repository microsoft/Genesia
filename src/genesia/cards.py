from .runtime import EvidenceStore, ModelGateway, write_json
from .schemas import (
    CardBindings,
    CardDescription,
    ContextItem,
    EnvironmentAssessment,
    EnvironmentBuildResult,
    Graph,
    GraphEdge,
    GraphNode,
    UICard,
)


def compile_assessed_materials(
    sources: list[dict], assessment: EnvironmentAssessment, store: EvidenceStore
) -> EnvironmentBuildResult:
    assessment.validate_sources(sources)
    issues = list(assessment.issues)
    issues.append("Model-assisted content assessment; citation validity is not semantic verification")
    referenced = {
        citation.source_id
        for item in [*assessment.states, *assessment.transitions]
        for citation in item.evidence
    }
    context = []
    for index, source in enumerate(sources):
        background = [
            citation.quote for citation in assessment.background if citation.source_id == source["id"]
        ]
        if source["id"] in referenced and not background:
            continue
        text = (
            "\n\n".join(background)
            if source["id"] in referenced
            else source["text"] or f"Review supplied material: {source['name']}"
        )
        context.append(
            ContextItem(
                id=f"context-{index + 1:03d}",
                text=text,
                source_ids=[source["id"]],
                image_refs=[source["id"]] if source["kind"] == "image" else [],
                sequence=index,
            )
        )
    if not assessment.states:
        return EnvironmentBuildResult(
            level="context",
            assessment=assessment,
            issues=issues,
            context=context,
        )

    by_id = {source["id"]: source for source in sources}
    cards, nodes = [], []
    image_states = {}
    for state in assessment.states:
        bound = []
        state_sources = sorted(
            [by_id[citation.source_id] for citation in state.evidence],
            key=lambda source: source["sequence"],
        )
        text_sources = [source for source in state_sources if source["kind"] != "image"]
        static_images = [
            source
            for source in state_sources
            if source["kind"] == "image" and source.get("provenance") != "recorded"
        ]
        recorded_images = [
            source
            for source in state_sources
            if source["kind"] == "image" and source.get("provenance") == "recorded"
        ]
        groups = [text_sources + static_images] if static_images or not recorded_images else []
        groups.extend(text_sources + [image] for image in recorded_images)
        for group in groups:
            group = sorted(group, key=lambda source: source["sequence"])
            images = [source for source in group if source["kind"] == "image"]
            primary = min(images or group, key=lambda source: source["sequence"])
            card = UICard(
                id=f"card-{len(cards) + 1:03d}",
                title=state.title,
                description=state.description,
                source_ids=[source["id"] for source in group],
                controls=state.controls,
                image_refs=[source["id"] for source in images],
                sequence=primary["sequence"],
                timestamp_seconds=primary.get("timestamp_seconds"),
                provenance=primary.get("provenance", "supplied"),
                trace_events=primary.get("trace_events", []),
            )
            cards.append(card)
            bound.append(card.id)
        for source in state_sources:
            if source["kind"] == "image":
                image_states[source["id"]] = state.id
        nodes.append(
            GraphNode(
                id=state.id,
                text=state.title + "\n" + state.description,
                card_ids=bound,
                source_ids=[citation.source_id for citation in state.evidence],
            )
        )
    save_cards(cards, store)
    if context:
        issues.append(
            "Unbound materials and cited global passages are retained as supplied background context"
        )

    edges = []
    for transition in assessment.transitions:
        edges.append(
            GraphEdge(
                id=f"transition-{len(edges) + 1:03d}",
                source=transition.source,
                target=transition.target,
                label=transition.label,
                evidence_refs=[item.source_id for item in transition.evidence],
                basis="declared",
            )
        )
        node = next(node for node in nodes if node.id == transition.source)
        node.source_ids = list(dict.fromkeys(node.source_ids + edges[-1].evidence_refs))

    for before, after in zip(sources, sources[1:]):
        source_state, target_state = image_states.get(before["id"]), image_states.get(after["id"])
        if (
            source_state
            and target_state
            and source_state != target_state
            and before.get("provenance") == after.get("provenance") == "recorded"
            and before.get("parent_ref")
            and before.get("parent_ref") == after.get("parent_ref")
            and after.get("timestamp_seconds", 0) > before.get("timestamp_seconds", 0)
            and not any(edge.source == source_state and edge.target == target_state for edge in edges)
        ):
            edges.append(
                GraphEdge(
                    id=f"transition-{len(edges) + 1:03d}",
                    source=source_state,
                    target=target_state,
                    label="Continue observed recording order (not verified causality)",
                    evidence_refs=[before["id"], after["id"]],
                    basis="recorded_order",
                )
            )

    observed_path = []
    parents = {source.get("parent_ref") for source in sources}
    if len(parents) == 1 and None not in parents and all(source["id"] in image_states for source in sources):
        for source in sources:
            state_id = image_states[source["id"]]
            if not observed_path or observed_path[-1] != state_id:
                observed_path.append(state_id)
    pairs = {(edge.source, edge.target) for edge in edges}
    if any(pair not in pairs for pair in zip(observed_path, observed_path[1:])):
        observed_path = []

    start = observed_path[0] if observed_path else None
    for candidate in [start] if start else [node.id for node in nodes]:
        reachable = {candidate}
        while True:
            expanded = reachable | {edge.target for edge in edges if edge.source in reachable}
            if reachable == expanded:
                break
            reachable = expanded
        if reachable == {node.id for node in nodes}:
            start = candidate
            break
    else:
        start = None
    if not edges or start is None:
        issues.append("No connected transition evidence for all UI states; graph not generated")
        return EnvironmentBuildResult(
            level="cards",
            cards=cards,
            context=context,
            issues=issues,
            assessment=assessment,
        )

    graph = Graph(start=start, nodes=nodes, edges=edges, cards=cards, observed_path=observed_path)
    save_graph(graph, store)
    return EnvironmentBuildResult(
        level="graph",
        graph=graph,
        context=context,
        issues=issues,
        assessment=assessment,
    )


def save_cards(cards: list[UICard], store: EvidenceStore) -> None:
    for card in cards:
        store.json(card, "ui_card")
        path = store.root / "ui_cards" / f"{card.id}.md"
        path.parent.mkdir(exist_ok=True)
        image_links = [f"![{ref}](../{store.refs[ref].path})" for ref in card.image_refs]
        path.write_text(
            f"# {card.title}\n\n{card.description}\n\n"
            + "\n".join(image_links)
            + f"\n\nSequence: {card.sequence}; provenance: {card.provenance}\n",
            encoding="utf-8",
        )
    write_json(store.root / "ui_cards.json", cards)


def construct_cards(sources: list[dict], gateway: ModelGateway, store: EvidenceStore) -> list[UICard]:
    cards = []
    for source in sources:
        images = [source["id"]] if source["kind"] == "image" else []
        if source["kind"] == "card":
            description = CardDescription(title=source["name"], description=source["text"])
        else:
            description = gateway.complete(
                "ui_card_extract",
                {
                    "source": source,
                    "instruction": "Describe this one source faithfully. Only visible controls and text, no imagined "
                    "functionality. Control status is visible-unverified or visual-only unless explicitly disabled. "
                    "Do not call a control verified from a screenshot or a click trace alone. "
                    "Preserve errors, selected options and missing/blocked states. Keep descriptions concise.",
                },
                CardDescription,
                images=images,
            )
            if any(control.status == "verified" for control in description.controls):
                raise ValueError("Source-only extraction cannot verify live controls")
        card = UICard(
            id=f"card-{len(cards) + 1:03d}",
            title=description.title,
            description=description.description,
            controls=description.controls,
            source_ids=[source["id"]],
            image_refs=images,
            sequence=len(cards),
            timestamp_seconds=source.get("timestamp_seconds"),
            provenance=source.get("provenance", "supplied"),
            trace_events=source.get("trace_events", []),
        )
        cards.append(card)
    save_cards(cards, store)
    return cards


def graph_from_bindings(cards: list[UICard], bindings: CardBindings) -> Graph:
    bindings.validate_cards(cards)
    by_id = {card.id: card for card in cards}
    nodes = [
        GraphNode(
            id=state.id,
            text=state.title + "\n" + "\n".join(by_id[card].description for card in state.card_ids),
            card_ids=state.card_ids,
            source_ids=list(dict.fromkeys(ref for card in state.card_ids for ref in by_id[card].source_ids)),
        )
        for state in bindings.states
    ]
    state_for_card = {card: state.id for state in bindings.states for card in state.card_ids}
    visits = []
    for card in sorted(cards, key=lambda card: card.sequence):
        state = state_for_card[card.id]
        if not visits or visits[-1] != state:
            visits.append(state)
    pairs = list(dict.fromkeys(zip(visits, visits[1:])))
    edges = [
        GraphEdge(
            id=f"transition-{index}",
            source=source,
            target=target,
            label=f"Continue supplied sequence to {target}",
        )
        for index, (source, target) in enumerate(pairs)
    ]
    return Graph(start=visits[0], nodes=nodes, cards=cards, edges=edges, observed_path=visits)


def build_card_graph(sources: list[dict], goal: str, gateway: ModelGateway, store: EvidenceStore) -> Graph:
    cards = construct_cards(sources, gateway, store)
    bindings = gateway.complete(
        "ui_card_bind",
        {
            "goal": goal,
            "cards": [card.model_dump() for card in cards],
            "instruction": "Group every card exactly once into stable user situations, not one state per click. "
            "Reuse a state for a recorded return. Do not combine errors and success into the same state. "
            "Never introduce an empty state. The runtime will derive transitions from supplied chronology. "
            "For unrelated design screens, this is an editorial review order, not proof of product navigation.",
        },
        CardBindings,
        validate=lambda value: value.validate_cards(cards),
    )
    store.json(bindings, "card_bindings")
    graph = graph_from_bindings(cards, bindings)
    save_graph(graph, store)
    return graph


def save_graph(graph: Graph, store: EvidenceStore) -> None:
    write_json(store.root / "state_graph.json", graph)
    aliases = {node.id: f"s{index}" for index, node in enumerate(graph.nodes)}
    lines = ["stateDiagram-v2", f"    [*] --> {aliases[graph.start]}"]
    for node in graph.nodes:
        label = node.text.split("\n")[0].replace('"', "'").replace("\r", " ")
        lines.append(f'    state "{label}" as {aliases[node.id]}')
    lines.extend(f"    {aliases[edge.source]} --> {aliases[edge.target]}" for edge in graph.edges)
    (store.root / "states.mmd").write_text("\n".join(lines) + "\n", encoding="utf-8")
