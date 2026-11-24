import pytest

from genesia.schemas import CardBindings, Graph, UICard


def card(card_id, sequence):
    return UICard(
        id=card_id, title="Screen", description="Visible state", source_ids=["source"], sequence=sequence
    )


def test_exactly_once_bindings():
    bindings = CardBindings(states=[dict(id="s", title="Screen", card_ids=["a", "a"])])
    with pytest.raises(ValueError, match="exactly once"):
        bindings.validate_cards([card("a", 0), card("b", 1)])


def test_screenshot_schema_cannot_claim_verified_controls():
    from genesia.schemas import CardDescription

    with pytest.raises(ValueError):
        CardDescription(
            title="Screen", description="Visible button", controls=[dict(label="Save", status="verified")]
        )


def test_graph_rejects_unbound_card():
    with pytest.raises(ValueError, match="exactly-once"):
        Graph(
            start="s",
            nodes=[dict(id="s", text="Screen", source_ids=["source"], card_ids=["a"])],
            cards=[card("a", 0), card("b", 1)],
        )


def test_graph_rejects_unsupported_observed_path():
    with pytest.raises(ValueError, match="unsupported"):
        Graph(
            start="a",
            nodes=[dict(id=node, text="Screen", source_ids=["source"]) for node in ["a", "b"]],
            observed_path=["a", "b"],
        )


def test_recording_edges_come_only_from_chronology():
    from genesia.cards import graph_from_bindings

    cards = [card("a", 0), card("b", 1), card("c", 2)]
    bindings = CardBindings(
        states=[
            dict(id="home", title="Home", card_ids=["a", "c"]),
            dict(id="edit", title="Edit", card_ids=["b"]),
        ]
    )
    graph = graph_from_bindings(cards, bindings)
    assert graph.observed_path == ["home", "edit", "home"]
    assert {(edge.source, edge.target) for edge in graph.edges} == {("home", "edit"), ("edit", "home")}


def test_walkthrough_shows_current_card_only_and_reports_unseen(tmp_path):
    from genesia.cards import graph_from_bindings
    from genesia.environments import WalkthroughEnvironment
    from genesia.runtime import EvidenceStore
    from genesia.schemas import Action

    store = EvidenceStore(tmp_path)
    cards = [card("a", 0), card("b", 1)]
    for item in cards:
        item.source_ids = [store.put(item.id.encode(), "source", ".txt")]
    graph = graph_from_bindings(
        cards, CardBindings(states=[dict(id="s", title="State", card_ids=["a", "b"])])
    )
    env = WalkthroughEnvironment(graph, store, "walkthrough", {})
    assert env.observe().card_ids == ["a"]
    assert env.coverage()["unseen_cards"] == ["b"]
    env.act(Action(action="click", target_id="next", intent="Continue"))
    assert env.observe().card_ids == ["b"]
    assert env.coverage()["unseen_cards"] == []


@pytest.mark.parametrize("mode", ["context", "cards", "walkthrough", "captured_graph"])
def test_persona_can_advance_through_five_distinct_materials(tmp_path, mode):
    from test_workflow import ScriptedModel

    from genesia.agents import PersonaAgent
    from genesia.cards import graph_from_bindings
    from genesia.environments import (
        CapturedEnvironment,
        CardReviewEnvironment,
        ContextReviewEnvironment,
        WalkthroughEnvironment,
    )
    from genesia.runtime import BudgetLedger, EvidenceStore
    from genesia.schemas import BudgetSpec, ContextItem, Episode, Persona

    store = EvidenceStore(tmp_path)
    cards = [card(f"card-{index}", index) for index in range(5)]
    for item in cards:
        item.source_ids = [store.put(item.id.encode(), "source", ".txt")]
    if mode == "context":
        environment = ContextReviewEnvironment(
            [
                ContextItem(
                    id=item.id, text=item.description, source_ids=item.source_ids, sequence=item.sequence
                )
                for item in cards
            ],
            store,
            {},
        )
    elif mode == "cards":
        environment = CardReviewEnvironment(cards, store, {})
    else:
        bindings = CardBindings(
            states=[dict(id="stable", title="Same stable state", card_ids=[item.id for item in cards])]
            if mode == "walkthrough"
            else [dict(id=item.id, title=item.title, card_ids=[item.id]) for item in cards]
        )
        graph = graph_from_bindings(cards, bindings)
        for edge in graph.edges:
            edge.label = "Next supplied material"
        environment = (
            WalkthroughEnvironment(graph, store, mode, {})
            if mode == "walkthrough"
            else CapturedEnvironment(graph, store, mode, {})
        )

    class ReadingModel(ScriptedModel):
        def complete(self, purpose, payload, schema, **kwargs):
            if purpose == "persona_action":
                targets = payload["observation"]["targets"]
                data = (
                    dict(action="click", target_id=targets[0]["id"], intent="Read the next material")
                    if targets
                    else dict(action="stop", intent="Finished reading", outcome="completed")
                )
                return schema.model_validate(data)
            return super().complete(purpose, payload, schema, **kwargs)

    episode = Episode(session_id="s", persona=Persona(id="p", profile={}), goal="Read materials", mode=mode)
    agent = PersonaAgent(episode, ReadingModel(), store, BudgetLedger(BudgetSpec()))
    agent.experience(environment, 6)
    assert episode.phase == "research" and episode.outcome == "completed"
    assert [step.action.action for step in episode.steps] == ["click"] * 4 + ["stop"]
    assert all(step.result.success for step in episode.steps)
    if mode == "context":
        assert episode.coverage["reviewed_items"] == 5
    else:
        assert episode.coverage["unseen_cards"] == []
