import pytest
from pydantic import ValidationError

from genesia.schemas import (
    Action,
    ContextItem,
    EnvironmentBuildResult,
    EnvironmentSpec,
    Graph,
    MethodSpec,
    ModelSpec,
    Question,
    StudySpec,
    TaskSpec,
    UICard,
)


def test_unsupported_provider_rejected():
    with pytest.raises(ValidationError):
        ModelSpec(provider="unsupported", model="test")


def test_openai_compatible_remote_requires_https_and_key_environment():
    model = ModelSpec(
        provider="openai_compatible",
        base_url="https://api.example.com/v1",
        model="vision-model",
        api_key_env="EXAMPLE_API_KEY",
    )
    assert model.provider == "openai_compatible"
    with pytest.raises(ValidationError, match="api_key_env"):
        ModelSpec(
            provider="openai_compatible",
            base_url="https://api.example.com/v1",
            model="test",
            api_key_env=None,
        )
    with pytest.raises(ValidationError, match="HTTPS"):
        ModelSpec(
            provider="openai_compatible",
            base_url="http://api.example.com/v1",
            model="test",
            api_key_env="EXAMPLE_API_KEY",
        )


def test_required_inputs():
    with pytest.raises(ValidationError):
        EnvironmentSpec(mode="captured_graph")
    with pytest.raises(ValidationError):
        EnvironmentSpec(mode="live", start_url="file:///secret")


def test_live_stop_url_fragments_must_be_relative_and_unique():
    with pytest.raises(ValidationError, match="unique relative"):
        EnvironmentSpec(
            mode="live",
            start_url="http://localhost",
            required_url_fragments_before_stop=["https://example.com/page"],
        )
    with pytest.raises(ValidationError, match="unique relative"):
        EnvironmentSpec(
            mode="live",
            start_url="http://localhost",
            required_url_fragments_before_stop=["/page", "/page"],
        )


def test_live_candidate_labels_align_with_url_stages():
    spec = EnvironmentSpec(
        mode="live",
        start_url="http://localhost/?design=b",
        handoff_urls=["http://localhost/?design=a"],
        candidate_labels=["Design B", "Design A"],
    )

    assert spec.candidate_labels == ["Design B", "Design A"]
    with pytest.raises(ValidationError, match="require explicit"):
        EnvironmentSpec(
            mode="live",
            start_url="http://localhost/?design=b",
            handoff_urls=["http://localhost/?design=a"],
        )
    with pytest.raises(ValidationError, match="align"):
        EnvironmentSpec(
            mode="live",
            start_url="http://localhost/?design=b",
            handoff_urls=["http://localhost/?design=a"],
            candidate_labels=["Design B"],
        )
    with pytest.raises(ValidationError, match="limited to live"):
        EnvironmentSpec(
            mode="scenario",
            sources=[{"kind": "document", "path": "fixture.md"}],
            candidate_labels=["Candidate"],
        )


def test_environment_build_level_matches_artifacts():
    context = ContextItem(id="c1", text="Product concept", source_ids=["e1"], sequence=0)
    card = UICard(id="card-1", title="Screen", description="Visible state", source_ids=["e1"], sequence=0)
    assert EnvironmentBuildResult(level="context", context=[context]).level == "context"
    assert EnvironmentBuildResult(level="cards", cards=[card]).level == "cards"
    with pytest.raises(ValidationError, match="without a graph"):
        EnvironmentBuildResult(
            level="cards",
            cards=[card],
            graph=Graph(start="n", nodes=[dict(id="n", text="State", source_ids=["e1"])]),
        )


def test_minimum_actions_must_leave_room_to_stop():
    with pytest.raises(ValidationError, match="leave one step"):
        EnvironmentSpec(
            mode="live",
            start_url="http://127.0.0.1:3000",
            max_steps=3,
            min_actions_before_stop=3,
        )


def test_survey_mode_has_no_environment_and_accepts_only_surveys(tmp_path):
    people = tmp_path / "people.json"
    people.write_text('[{"id":"p1","profile":{}}]', "utf-8")
    base = {
        "goal": "Answer a product survey",
        "cohort": {"source": str(people), "size": 1},
        "environment": {"mode": "survey"},
        "methods": [{"id": "survey", "kind": "survey", "questions": [{"id": "q1", "text": "Why?"}]}],
        "model": {"model": "fixture"},
    }
    assert TaskSpec.model_validate(base).environment.sources == []
    with pytest.raises(ValidationError, match="only survey methods"):
        TaskSpec.model_validate(
            {
                **base,
                "methods": [
                    {"id": "interview", "kind": "interview", "questions": [{"id": "q1", "text": "Why?"}]}
                ],
            }
        )
    with pytest.raises(ValidationError, match="does not use environment"):
        EnvironmentSpec(mode="survey", sources=[{"kind": "document", "path": "fake.md"}])


def test_duplicate_questions_rejected():
    question = Question(id="q1", text="Why?")
    with pytest.raises(ValidationError):
        MethodSpec(id="interview", kind="interview", questions=[question, question])


@pytest.mark.parametrize(
    "buckets",
    [
        ["30-39", "40+"],
        ["<30", "40-49", "50+"],
        ["<30", "29-39", "40+"],
        ["<30", "thirties", "40+"],
        ["<30", "30-39", "40-49"],
        ["<30", "30+", "50+"],
    ],
)
def test_numeric_segment_buckets_reject_invalid_ranges(buckets):
    with pytest.raises(ValidationError):
        StudySpec.model_validate(
            {"segments": {"age_group": {"source": "Core Identity.age", "buckets": buckets}}}
        )


@pytest.mark.parametrize("dimensions", [["region"], ["region", "region"], ["region", "missing"]])
def test_segment_combinations_reject_bad_dimensions(dimensions):
    with pytest.raises(ValidationError):
        StudySpec(
            segments={"region": {"source": "Core Identity.region"}},
            segment_combinations={"combined": dimensions},
        )


def test_invalid_graph_edge_rejected():
    with pytest.raises(ValidationError):
        Graph(
            start="a",
            nodes=[dict(id="a", text="Home", source_ids=["s1"])],
            edges=[dict(id="go", source="a", target="missing", label="Go")],
        )


@pytest.mark.parametrize(
    "payload",
    [
        dict(action="click", intent="open"),
        dict(action="stop", intent="done"),
        dict(action="shell", intent="run"),
    ],
)
def test_invalid_actions_rejected(payload):
    with pytest.raises(ValidationError):
        Action(**payload)


@pytest.mark.parametrize(
    "payload",
    [
        dict(action="scroll", value="sideways", intent="Move"),
        dict(action="scroll", value="down", target_id="button", intent="Move"),
        dict(action="advance", target_id="button", intent="Continue"),
    ],
)
def test_invalid_untargeted_actions_rejected(payload):
    with pytest.raises(ValidationError):
        Action(**payload)


def test_likert_requires_rows():
    with pytest.raises(ValidationError):
        Question(id="q", text="Rate", kind="likert", options=["Good"])
