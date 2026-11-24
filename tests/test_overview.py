from pathlib import Path

from test_workflow import ScriptedModel, task_fixture

from genesia import load_task, preflight, run
from genesia.schemas import EnvironmentSpec, MethodSpec, StudySpec


class OverviewModel(ScriptedModel):
    def complete(self, purpose, payload, schema, **kwargs):
        if purpose == "ui_card_bind":
            result = schema.model_validate(
                {
                    "states": [
                        dict(id=f"s{index}", title=card["title"], card_ids=[card["id"]])
                        for index, card in enumerate(payload["cards"])
                    ]
                }
            )
        elif purpose in {"study_review", "fidelity_review"}:
            result = schema.model_validate(dict(summary="Fixture review", issues=[]))
        elif purpose == "persona_action" and payload["observation"]["targets"]:
            result = schema.model_validate(dict(action="click", target_id="next", intent="Review next card"))
        elif purpose == "interview_moderator":
            result = schema.model_validate(dict(ask=False, text="", reason="Enough detail"))
        else:
            return super().complete(purpose, payload, schema, **kwargs)
        if kwargs.get("validate"):
            kwargs["validate"](result)
        return result


def test_overview_card_study_and_research_integration(tmp_path):
    task = task_fixture(tmp_path)
    cards = tmp_path / "cards"
    cards.mkdir()
    for index in range(3):
        (cards / f"0{index}_screen.md").write_text(f"Calendar screen {index}: save meeting.")
    task.environment = EnvironmentSpec(
        mode="walkthrough", max_steps=4, fidelity_review=True, sources=[dict(kind="cards", path=str(cards))]
    )
    task.study = StudySpec(review=True)
    task.methods[0] = MethodSpec(
        id="interview", kind="interview", max_followups=1, questions=[dict(id="q1", text="How clear was it?")]
    )
    result = run(task, gateway=OverviewModel())
    assert result.status == "completed"
    assert result.study_review["ok"]
    assert all(not episode.coverage["unseen_cards"] for episode in result.episodes)
    assert len(result.responses) == 12
    assert result.synthesis.recommendations
    assert (Path(result.output_dir) / "ui_cards.json").exists()
    assert "](appendix.md)" in (Path(result.output_dir) / "report.md").read_text("utf-8")
    assert "](artifacts/" in (Path(result.output_dir) / "appendix.md").read_text("utf-8")


def test_public_example_configuration(tmp_path):
    root = Path(__file__).parents[1]
    personas = tmp_path / "personas.json"
    personas.write_text(
        '[{"id":"p1","profile":{}},{"id":"p2","profile":{}},{"id":"p3","profile":{}}]',
        "utf-8",
    )
    for filename in ("task.yaml", "overview.yaml"):
        path = root / "examples" / filename
        assert path.read_text("utf-8").count("schema_version:") == 1
        task = load_task(path)
        task.cohort.source = str(personas)
        assert preflight(task)["ok"]
    task = load_task(root / "examples" / "task.yaml")
    assert task.environment.mode == "auto"
    assert [source.kind for source in task.environment.sources] == ["document"]
