from __future__ import annotations

from pathlib import Path
from typing import Protocol

import yaml

from .runtime import EvidenceStore, ModelGateway, write_json
from .schemas import (
    Action,
    ContextItem,
    EnvironmentAssessment,
    EnvironmentBuildResult,
    EnvironmentSpec,
    ExecutionResult,
    Graph,
    GraphEdge,
    GraphNode,
    Observation,
    Permissions,
    Target,
    UICard,
)
from .sources import inspect_sources, normalize_sources


class Environment(Protocol):
    def observe(self) -> Observation: ...
    def act(self, action: Action) -> ExecutionResult: ...
    def close(self) -> None: ...


def authorize(action: Action, observation: Observation, allowed: set[str]):
    if action.action not in allowed | {"stop"}:
        raise ValueError("Action is not available in this environment mode")
    if action.action in {"click", "right_click", "type", "select"}:
        targets = {target.id: target for target in observation.targets}
        if action.target_id not in targets or targets[action.target_id].disabled:
            raise ValueError("Target is absent or disabled in current observation")
        if action.action not in targets[action.target_id].actions:
            raise ValueError(f"Action {action.action} is incompatible with this target")


def material_files(spec: EnvironmentSpec) -> list[tuple[str, Path]]:
    return inspect_sources(spec)


class EnvironmentBuilderAgent:
    def __init__(self, gateway: ModelGateway, store: EvidenceStore, permissions: Permissions | None = None):
        self.gateway, self.store = gateway, store
        self.permissions = permissions or Permissions()

    def compile(self, spec: EnvironmentSpec, goal: str) -> EnvironmentBuildResult:
        if spec.mode != "auto":
            raise ValueError("Automatic compilation requires environment mode=auto")
        sources = normalize_sources(spec, self.store, self.permissions)
        kinds = {source.kind for source in spec.sources}

        if kinds == {"graph"}:
            graph = self._canonical_graph(sources)
            result = EnvironmentBuildResult(
                level="graph",
                graph=graph,
                issues=["Caller-supplied canonical graph; no content readiness assessment performed"],
            )
            write_json(self.store.root / "state_graph.json", graph)
        else:
            from .cards import compile_assessed_materials

            assessment = self.gateway.complete(
                "environment_readiness",
                {
                    "goal": goal,
                    "sources": sources,
                    "instruction": "Assess the CONTENT of these materials before constructing an environment. "
                    "Return concrete UI states only when visible in attached images or explicitly described "
                    "in text. Concept documents, photographs and non-UI video frames may support no states. "
                    "A document may describe several states. Group repeated images of the same stable state; "
                    "never merge error and success states or conflicting selected settings. Each image can "
                    "belong to only one state. Cite source_id for every state, and verbatim quote for each "
                    "text citation. Within each state's or transition's evidence list, use each source_id "
                    "at most once; choose one contiguous supporting text quote rather than separate "
                    "citations for a heading and its description. Different states may cite the same document. "
                    "Separately extract background as verbatim text citations for shared product context, "
                    "assumptions and material limitations, even from documents already cited by UI states. "
                    "Include every supplied global limitation relevant to this review. Do not copy entire "
                    "specifications, page-specific details, navigation or unseen UI content into background. "
                    "Different background passages may cite the same source, but do not repeat a citation. "
                    "For transitions cite verbatim TEXT explicitly describing the action and "
                    "endpoints. Do not infer transitions from screenshot order, filenames, visible buttons, "
                    "Figma images or timestamps. Runtime handles recording chronology separately. Use empty "
                    "lists when evidence is insufficient and explain gaps in issues. No imagined controls, "
                    "unseen pages, UI functionality or Persona opinions. This assessment is advisory: exact "
                    "citations are checked, but semantic truth requires human review.",
                },
                EnvironmentAssessment,
                images=[source["id"] for source in sources if source["kind"] == "image"],
                validate=lambda value: value.validate_sources(sources),
            )
            assessment.validate_sources(sources)
            write_json(self.store.root / "environment_readiness.json", assessment)
            self.store.json(assessment, "environment_readiness")
            result = compile_assessed_materials(sources, assessment, self.store)

        write_json(self.store.root / "environment_build.json", result)
        self.store.json(result, "environment_build")
        self.store.event(
            "environment_compiled",
            mode=spec.mode,
            level=result.level,
            sources=[source["id"] for source in sources],
            issues=result.issues,
        )
        return result

    @staticmethod
    def _canonical_graph(sources: list[dict]) -> Graph:
        graph_sources = [source for source in sources if source["kind"] == "graph"]
        if len(graph_sources) != 1:
            raise ValueError("Provide exactly one canonical graph per build")
        graph = Graph.model_validate(yaml.safe_load(graph_sources[0]["text"]))
        if graph.cards:
            raise ValueError(
                "Card-backed graphs require their artifact bundle, not a graph-only file; use cards input"
            )
        for node in graph.nodes:
            node.source_ids = [graph_sources[0]["id"]]
        for edge in graph.edges:
            edge.evidence_refs = [graph_sources[0]["id"]]
            edge.basis = "declared"
        return graph

    def build(self, spec: EnvironmentSpec, goal: str) -> Graph:
        if spec.mode == "auto":
            raise ValueError("Use compile() for environment mode=auto")
        sources = normalize_sources(spec, self.store, self.permissions)
        graph_sources = [source for source in sources if source["kind"] == "graph"]
        if graph_sources:
            graph = self._canonical_graph(sources)
        elif spec.mode in {"scenario", "image_direct"}:
            selected = (
                sources
                if spec.mode == "scenario"
                else [source for source in sources if source["kind"] == "image"]
            )
            if not selected:
                raise ValueError("Image-direct requires image sources")
            nodes = [
                GraphNode(
                    id=f"n{index}",
                    text=source["text"] or f"Review supplied frame: {source['name']}",
                    source_ids=[source["id"]],
                )
                for index, source in enumerate(selected)
            ]
            graph = Graph(
                start=nodes[0].id,
                nodes=nodes,
                edges=[
                    GraphEdge(
                        id=f"next{index}",
                        source=nodes[index].id,
                        target=nodes[index + 1].id,
                        label="Continue to next supplied material",
                    )
                    for index in range(len(nodes) - 1)
                ],
            )
        elif spec.mode == "walkthrough" or any(
            source.kind in {"video", "recording", "cards"} for source in spec.sources
        ):
            from .cards import build_card_graph

            graph = build_card_graph(sources, goal, self.gateway, self.store)
        else:
            valid_refs = {source["id"] for source in sources}

            def validate(graph):
                covered = {ref for node in graph.nodes for ref in node.source_ids}
                if covered != valid_refs:
                    raise ValueError("Every source must be referenced, with no invented source IDs")
                if any(not set(edge.evidence_refs).issubset(valid_refs) for edge in graph.edges):
                    raise ValueError("Graph edge references unknown source evidence")
                reachable = {graph.start}
                while True:
                    expanded = reachable | {edge.target for edge in graph.edges if edge.source in reachable}
                    if expanded == reachable:
                        break
                    reachable = expanded
                if reachable != {node.id for node in graph.nodes}:
                    raise ValueError("Every graph node must be reachable")

            graph = self.gateway.complete(
                "environment_build",
                {
                    "goal": goal,
                    "sources": sources,
                    "instruction": "Construct a small evidence-grounded experience graph. Inspect the materials, "
                    "identify meaningful states and available choices. No invented product capability. "
                    "Text descriptions are conceptual, not executed behavior. Image/recording nodes describe only "
                    "visible evidence. Edges for recordings may follow only the supplied chronological sequence. "
                    "Use every source ID at least once; all nodes reachable. Node text should describe what a "
                    "participant sees, not hidden source code or research questions. At most 12 nodes.",
                },
                Graph,
                images=[source["id"] for source in sources if source["kind"] == "image"],
                validate=validate,
            )
        self.store.json(graph, "environment_graph")
        self.store.event(
            "environment_built",
            mode=spec.mode,
            sources=[source["id"] for source in sources],
            nodes=len(graph.nodes),
            edges=len(graph.edges),
            fidelity="source_references_checked; semantic_fidelity_not_independently_verified",
        )
        return graph


class ContextReviewEnvironment:
    def __init__(self, items: list[ContextItem], store: EvidenceStore, owner: dict):
        self.items, self.store, self.owner = sorted(items, key=lambda item: item.sequence), store, owner
        self.cursor = 0
        self.sequence = 0
        self.latest = None

    def observe(self):
        self.sequence += 1
        item = self.items[self.cursor]
        observation = Observation(
            id=f"o{self.sequence}",
            text=item.text,
            mode="context",
            state_id=item.id,
            image_refs=item.image_refs,
            evidence_refs=item.source_ids.copy(),
            targets=[Target(id="next", name="Next supplied material")]
            if self.cursor < len(self.items) - 1
            else [],
        )
        observation.evidence_refs.append(self.store.json(observation, "observation", **self.owner))
        self.latest = observation
        return observation

    def act(self, action):
        authorize(action, self.latest, {"click", "wait"})
        if action.action == "click":
            self.cursor += 1
        return ExecutionResult(success=True, message="Advanced supplied context; not product execution")

    def close(self):
        pass

    def coverage(self):
        return {"reviewed_items": self.cursor + 1, "expected_items": len(self.items)}


def attach_context(observation: Observation, context: list[ContextItem]) -> None:
    if not context:
        return
    observation.text += "\n\nSupplied background (not a UI state):\n" + "\n\n".join(
        item.text for item in context
    )
    observation.evidence_refs = list(
        dict.fromkeys(observation.evidence_refs + [ref for item in context for ref in item.source_ids])
    )
    observation.image_refs = list(
        dict.fromkeys(observation.image_refs + [ref for item in context for ref in item.image_refs])
    )


class CardReviewEnvironment:
    def __init__(self, cards: list[UICard], store: EvidenceStore, owner: dict, *, context=None):
        self.cards, self.store, self.owner = sorted(cards, key=lambda card: card.sequence), store, owner
        self.context = context or []
        self.cursor = 0
        self.sequence = 0
        self.latest = None

    def observe(self):
        self.sequence += 1
        card = self.cards[self.cursor]
        observation = Observation(
            id=f"o{self.sequence}",
            text=card.title + "\n" + card.description,
            mode="cards",
            state_id=card.id,
            card_ids=[card.id],
            image_refs=card.image_refs,
            evidence_refs=card.source_ids.copy(),
            targets=[Target(id="next", name="Next UI card")] if self.cursor < len(self.cards) - 1 else [],
        )
        if self.sequence == 1:
            attach_context(observation, self.context)
        observation.evidence_refs.append(self.store.json(observation, "observation", **self.owner))
        self.latest = observation
        return observation

    def act(self, action):
        authorize(action, self.latest, {"click", "wait"})
        if action.action == "click":
            self.cursor += 1
        return ExecutionResult(success=True, message="Advanced supplied UI card; not product execution")

    def close(self):
        pass

    def coverage(self):
        reviewed = {card.id for card in self.cards[: self.cursor + 1]}
        expected = {card.id for card in self.cards}
        return {
            "visited_cards": sorted(reviewed),
            "unseen_cards": sorted(expected - reviewed),
            "expected_cards": len(expected),
        }


class CapturedEnvironment:
    def __init__(self, graph: Graph, store: EvidenceStore, mode: str, owner: dict, *, context=None):
        self.graph, self.store, self.mode, self.owner = graph, store, mode, owner
        self.context = context or []
        self.current = graph.start
        self.sequence = 0
        self.visited_cards = set()
        self.visited_states = set()

    def observe(self):
        self.sequence += 1
        node = next(node for node in self.graph.nodes if node.id == self.current)
        images = [ref for ref in node.source_ids if self.store.refs[ref].kind == "source_image"]
        observation = Observation(
            id=f"o{self.sequence}",
            text=node.text,
            mode=self.mode,
            targets=[
                Target(id=edge.id, name=edge.label) for edge in self.graph.edges if edge.source == node.id
            ],
            image_refs=images,
            evidence_refs=list(node.source_ids),
            state_id=node.id,
            card_ids=list(node.card_ids),
        )
        if self.sequence == 1:
            attach_context(observation, self.context)
        self.visited_cards.update(observation.card_ids)
        self.visited_states.add(node.id)
        ref = self.store.json(observation, "observation", **self.owner)
        observation.evidence_refs.append(ref)
        self.latest = observation
        return observation

    def act(self, action):
        authorize(action, self.latest, {"click", "wait"})
        if action.action == "click":
            edge = next(
                edge
                for edge in self.graph.edges
                if edge.source == self.current and edge.id == action.target_id
            )
            self.current = edge.target
        return ExecutionResult(
            success=True, message="Captured material transition; not live product execution"
        )

    def close(self):
        pass

    def coverage(self):
        expected = {card.id for card in self.graph.cards}
        return {
            "visited_states": sorted(self.visited_states),
            "visited_cards": sorted(self.visited_cards),
            "unseen_cards": sorted(expected - self.visited_cards),
            "expected_cards": len(expected),
        }


class WalkthroughEnvironment(CapturedEnvironment):
    def __init__(self, graph, store, mode, owner, curated_path=None, *, context=None):
        super().__init__(graph, store, mode, owner, context=context)
        self.cards = sorted(graph.cards, key=lambda card: card.sequence)
        if not self.cards:
            raise ValueError("Walkthrough requires card-backed sources")
        if curated_path:
            by_id = {card.id: card for card in self.cards}
            if len(curated_path) != len(set(curated_path)) or not set(curated_path).issubset(by_id):
                raise ValueError("Curated path must contain unique, known card IDs")
            self.cards = [by_id[card_id] for card_id in curated_path]
        self.cursor = 0

    def observe(self):
        self.sequence += 1
        card = self.cards[self.cursor]
        state = next(node for node in self.graph.nodes if card.id in node.card_ids)
        observation = Observation(
            id=f"o{self.sequence}",
            text=card.title + "\n" + card.description,
            mode=self.mode,
            state_id=state.id,
            card_ids=[card.id],
            image_refs=card.image_refs,
            evidence_refs=card.source_ids.copy(),
            targets=[Target(id="next", name="Next supplied card")]
            if self.cursor < len(self.cards) - 1
            else [],
        )
        if self.sequence == 1:
            attach_context(observation, self.context)
        self.visited_cards.add(card.id)
        self.visited_states.add(state.id)
        observation.evidence_refs.append(self.store.json(observation, "observation", **self.owner))
        self.latest = observation
        return observation

    def act(self, action):
        authorize(action, self.latest, {"click", "wait"})
        if action.action == "click":
            self.cursor += 1
        return ExecutionResult(
            success=True, message="Advanced curated card sequence; not live product execution"
        )

    def coverage(self):
        expected = {card.id for card in self.cards}
        return {
            "visited_states": sorted(self.visited_states),
            "visited_cards": sorted(self.visited_cards),
            "unseen_cards": sorted(expected - self.visited_cards),
            "expected_cards": len(expected),
        }
