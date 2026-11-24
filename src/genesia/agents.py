from __future__ import annotations

import json
from importlib.resources import files
from typing import Literal, Union
from urllib.parse import unquote, urlsplit

from pydantic import Field, create_model

from .environments import Environment
from .runtime import BudgetLedger, EvidenceStore, ModelGateway, StageBudgetExceeded, write_json
from .schemas import (
    Action,
    Answer,
    Answers,
    Episode,
    ExecutionResult,
    ExperienceNote,
    FollowupDecision,
    MethodResponse,
    MethodSpec,
    Observation,
    Question,
    SessionIntent,
    Step,
    StudySpec,
)


def persona_role_policy() -> str:
    return files("genesia").joinpath("resources/persona_role.md").read_text("utf-8")


def survey_response_policy() -> str:
    return files("genesia").joinpath("resources/survey_response.md").read_text("utf-8")


def answer_role_policy() -> str:
    return (
        persona_role_policy()
        .replace("stable session intent", "stable task orientation")
        .replace("that shaped your use.", "that characterize you in this context.")
    )


def answer_voice_instruction() -> str:
    return files("genesia").joinpath("resources/persona_voice.md").read_text("utf-8").rstrip()


def survey_answer_policy() -> str:
    before_open, remainder = survey_response_policy().split("#### Open Text\n", 1)
    _, after_open = remainder.split("### 4. Survey Consistency", 1)
    return (
        before_open + "#### Open Text\n\n"
        "- Answer in the supplied person's first-person identity. Let supported communication habits "
        "and the specific question determine wording, directness, detail and answer length.\n"
        "- There is no common sentence count or required answer structure. Do not pad a short response, "
        "add a routine second sentence, or trim useful explanation merely to match a standard length.\n"
        "- Answer content should fit this person's relevant needs and priorities; do not make an answer "
        "sound personal by inventing experiences or reciting the profile.\n"
        "- Do not output hidden reasoning or chain-of-thought.\n\n"
        "\n### 4. Survey Consistency" + after_open
    )


def profile_survey_instruction() -> str:
    return (
        "You are the person described in the supplied profile, answering a questionnaire about a hypothetical "
        "idea. For this questionnaire, ground personal judgments in the profile and product-experience "
        "claims in the supplied records.\n\n"
        + answer_voice_instruction()
        + "\n\nGrounding and response rules:\n"
        "- Use the supplied profile and hypothetical background for possible needs, preferences and concerns. "
        "Do not describe the idea as something you already used or claim unobserved product behavior.\n"
        "- Explain only what the question asks and what this person's context reasonably supports. "
        "Do not invent an incident to make an answer more vivid.\n"
        "- Preserve question IDs, question order, exact choice options and the requested answer types. "
        "For explain=true, put the explanation in reason.\n"
        "- When the supplied context cannot support an answer, use value=null and follow the survey "
        "grounding rules rather than inventing information.\n"
        "- Return only the requested JSON answer object. Do not output an analysis, a voice plan, hidden "
        "reasoning, or an account of how you used the profile."
    )


def research_instruction() -> str:
    return (
        "You have finished trying the product. Answer as the same person who used it, from your "
        "own needs, habits, tastes and actual experience, not as an analyst. The questionnaire "
        "does not change who you are.\n\n"
        "Interview rules:\n"
        "1. Use first person and preserve one coherent participant voice. Answer the specific "
        "focus of every question exactly once and in the listed order.\n"
        "2. Use the Persona profile for personal background. Use the chronological timeline, supplied "
        "material text and adjacent images as memory for the experience; do not cite or annotate them. "
        "Supplied material is not proof of live product execution.\n"
        "3. Only claim actions that executed and effects supported by observations. Do not invent "
        "hidden features, past product use, persistence, or results outside the recorded session.\n"
        "4. Consider each candidate's own merits. Do not claim an exercised feature in one "
        "candidate is better than an untried counterpart in another. Different paths and similar "
        "opinions are valid; do not force variety or a preference.\n"
        "5. State hesitation, uncertainty, indifference, praise or criticism plainly when it fits. "
        "If the experience cannot support an answer, use value=null rather than guessing.\n"
        "6. Treat unavailable behavior or an unexplained no-response as uncertain; do not assume it "
        "is a product defect. A suggestion may express what you want without claiming a failure.\n"
        "7. Stay fully present as this specific person throughout the interview. Let the complete "
        "profile, stable preferences, actual actions and observed experience naturally shape what you "
        "notice, how you feel, what you emphasize, and how you speak. Do not become a generic UX "
        "reviewer. Do not invent catchphrases, accents, dramatic mannerisms, hidden thoughts, or "
        "experiences that were not supplied. Real people can be uncertain, inconsistent, indifferent, "
        "brief, emotional, or difficult to categorize. Do not append formulaic labels or methodological "
        "disclaimers.\n"
        "8. Keep exact supplied options in value. For explain=true, put the concrete explanation "
        "in reason. Return exactly the requested JSON object and no markdown.\n\n"
        "For survey-only input, follow survey_response_policy and use profile grounding. A system "
        "limit is not the participant's personal satisfaction."
    )


def default_interview_instruction() -> str:
    goal = (
        "INTERVIEW GOAL\n"
        "Answer the question being asked as the person who just used the product. When a question "
        "asks about confidence, feelings, preferences or changes, explain what in your actual "
        "experience helped or bothered you and why it mattered to your own needs, habits or "
        "circumstances. Where it fits, say what inconvenience you would accept, what would change "
        "your judgment, or what you would want changed and why. A list of clicks or a generic "
        "claim that something was clear does not by itself explain a personal judgment.\n"
        "Keep this in ordinary participant language, not an analyst's framework. Answer only the "
        "question's focus: a factual journey or stopping answer may be brief. Do not force a "
        "profile reference, tradeoff, complaint or suggestion into every answer. Relevant "
        "background can explain a feeling without being recited; it cannot establish an event "
        "that did not happen. Shared preferences, indifference and uncertainty remain valid.\n\n"
    )
    examples = files("genesia").joinpath("resources/interview_examples.md").read_text("utf-8")
    check = (
        "\nBEFORE RETURNING\n"
        "Check that each answer addresses its own question, product claims match actual execution "
        "and observation, and personal explanations fit supplied background rather than copied "
        "examples or label-based assumptions. Keep wishes distinct from observed results; do not "
        "invent costs or comparisons to sound personal. Check the requested IDs, order, options "
        "and JSON fields. Return only the answers, not this check or your reasoning."
    )
    return goal + research_instruction() + "\n\n" + examples + check + "\n\n" + answer_voice_instruction()


def answer_output_contract(method: MethodSpec) -> str:
    examples = []
    for question in method.questions:
        if question.kind == "single":
            value = f"<exactly one option: {' | '.join(question.options)}>"
        elif question.kind == "multiple":
            value = ["<zero or more exact supplied options>"]
        elif question.kind == "likert":
            value = {row: f"<exactly one option: {' | '.join(question.options)}>" for row in question.rows}
        else:
            value = "<this person's answer>"
        example = {"question_id": question.id, "value": value}
        if question.explain:
            example["reason"] = "<natural explanation for the selected option>"
        examples.append(example)
    return (
        "Return exactly one JSON object with one answer per question, in the listed order.\n"
        "Use each question_id exactly. For text questions, express this person's answer as instructed above. "
        "For choice and Likert questions, copy only supplied option text. Include reason only when "
        "explain=true. If the supplied context cannot support an answer, use value=null. The runtime infers grounding, "
        "binds applicable episode evidence, and validates all fields after return.\n"
        "The example below specifies JSON structure and question order only, "
        "not a speaking style, opening phrase or answer length.\n"
        + json.dumps({"answers": examples}, ensure_ascii=False, separators=(",", ":"))
    )


def participant_question(question: Question) -> dict:
    value = {"id": question.id, "text": question.text, "kind": question.kind}
    for field in ("candidate", "options", "rows"):
        field_value = getattr(question, field)
        if field_value:
            value[field] = field_value
    if question.explain:
        value["explain"] = True
    if not question.required:
        value["required"] = False
    return value


def answer_schema(method: MethodSpec, *, profile_only: bool = False):
    variants = []
    for index, question in enumerate(method.questions):
        value_type = str
        if question.kind == "single":
            value_type = Literal[tuple(question.options)]
        elif question.kind == "multiple":
            value_type = list[Literal[tuple(question.options)]]
        elif question.kind == "likert":
            value_type = dict[str, Literal[tuple(question.options)]]
        from .schemas import Answer

        basis_type = (
            Literal["profile", "not_observed"]
            if profile_only or question.purpose == "context"
            else Literal["experience", "automation", "not_observed"]
        )
        default_basis = "profile" if profile_only or question.purpose == "context" else "experience"

        variants.append(
            create_model(
                f"Answer{index}",
                __base__=Answer,
                question_id=(Literal[question.id], ...),
                value=(value_type | None, ...),
                reason=(
                    str,
                    Field(
                        default="",
                        description="Explain the selected answer in your own words using your experience. "
                        "Required for an answered question with explain=true. Keep exact options in value.",
                    ),
                ),
                basis=(
                    basis_type,
                    Field(
                        default=default_basis,
                        description="Grounding source, not the question purpose or feedback role. Use "
                        "experience for post-use reflection grounded in the session.",
                    ),
                ),
            )
        )
    item_type = variants[0] if len(variants) == 1 else Union[tuple(variants)]
    return create_model(
        "MethodAnswers",
        __base__=Answers,
        answers=(list[item_type], Field(min_length=len(variants), max_length=len(variants))),
    )


def bind_answer_evidence(
    answers: Answers, method: MethodSpec, timeline: list[dict], *, profile_only: bool = False
) -> None:
    for question, answer in zip(method.questions, answers.answers, strict=True):
        if answer.value is None:
            answer.basis = "not_observed"
            answer.evidence_refs = []
            continue
        if profile_only or question.purpose == "context":
            answer.basis = "profile"
            answer.evidence_refs = []
            continue
        if answer.basis != "automation":
            answer.basis = "experience"
        applicable = [
            item
            for item in timeline
            if not question.candidate
            or question.candidate in {item.get("candidate_before"), item.get("candidate_after")}
        ]
        answer.evidence_refs = list(
            dict.fromkeys(
                ref
                for item in applicable
                for state in (item["before"], item["after"])
                if state
                for ref in state["evidence_refs"]
            )
        )


def validate_answers(
    answers: Answers, method: MethodSpec, allowed_refs: set[str], *, profile_only: bool = False
):
    if [answer.question_id for answer in answers.answers] != [question.id for question in method.questions]:
        raise ValueError("Answer IDs and order must match every question exactly")
    for question, answer in zip(method.questions, answers.answers, strict=True):
        if answer.basis == "skipped":
            raise ValueError("Only the runtime may skip a conditional question")
        if profile_only and answer.basis not in {"profile", "not_observed"}:
            raise ValueError("Survey-only responses must be grounded in the Persona profile")
        if not set(answer.evidence_refs).issubset(allowed_refs):
            raise ValueError("Answer cites evidence outside this Persona's episode")
        if answer.basis == "experience" and not answer.evidence_refs:
            raise ValueError("Experience claims require episode evidence")
        if answer.basis == "automation" and not answer.evidence_refs:
            raise ValueError("Automation-limited answers require episode evidence")
        if answer.basis == "not_observed":
            if answer.value is not None:
                raise ValueError("Not-observed responses must have null value")
            continue
        value = answer.value
        if value is None and not question.required:
            continue
        if question.explain and not answer.reason.strip():
            raise ValueError("An answered explain=true question requires a concrete reason")
        if question.kind == "text" and (not isinstance(value, str) or not value.strip()):
            raise ValueError("Text answer must be nonempty")
        if question.kind == "single" and (not isinstance(value, str) or value not in question.options):
            raise ValueError("Single-choice answer must be an offered option")
        if question.kind == "multiple":
            if not isinstance(value, list) or (question.required and not value):
                raise ValueError("Multiple-choice answer must be a list")
            if len(value) != len(set(value)) or not set(value).issubset(question.options):
                raise ValueError("Multiple-choice options must be valid and unique")
        if question.kind == "likert":
            if not isinstance(value, dict) or set(value) != set(question.rows):
                raise ValueError("Likert rows must match exactly")
            if any(choice not in question.options for choice in value.values()):
                raise ValueError("Invalid Likert value")


def execution_trace(episode: Episode) -> list[dict]:
    trace = []
    reflections = {note.step: note.reflection.model_dump() for note in episode.experience_notes}
    for index, step in enumerate(episode.steps):
        after = (
            episode.steps[index + 1].observation
            if index + 1 < len(episode.steps)
            else episode.final_observation
        )
        trace.append(
            {
                "step": step.number,
                "observation_id": step.observation.id,
                "url": step.observation.url,
                "before_evidence_refs": step.observation.evidence_refs,
                "after_observation_id": after.id if after else None,
                "url_after": after.url if after else None,
                "after_evidence_refs": after.evidence_refs if after else [],
                "action": step.action.action,
                "target": next(
                    (
                        target.name
                        for target in step.observation.targets
                        if target.id == step.action.target_id
                    ),
                    None,
                ),
                "value": step.action.value,
                "intent": step.action.intent,
                "expected_result": step.action.expected_result,
                "execution_success": step.result.success,
                "result": step.result.message,
                "participant_reflection": reflections.get(step.number),
            }
        )
    return trace


def participant_history(episode: Episode) -> list[dict]:
    return [
        {key: value for key, value in step.items() if key != "participant_reflection"}
        for step in execution_trace(episode)
    ]


def experience_timeline(
    episode: Episode,
    selected_images: set[str],
    *,
    complete: bool,
    stage_labels: list[str] | None = None,
) -> list[dict]:
    def page_name(url: str) -> str:
        parsed = urlsplit(url)
        route = (parsed.fragment or parsed.path).split("?", 1)[0].rstrip("/")
        segment = unquote(route.rsplit("/", 1)[-1]).replace("-", " ").replace("_", " ")
        return segment.title() if segment else "Current page"

    def state(observation: Observation | None) -> dict | None:
        if observation is None:
            return None
        included_images = [ref for ref in observation.image_refs if ref in selected_images]
        included = complete or bool(included_images)
        evidence_refs = observation.evidence_refs if included else []
        if observation.mode != "live":
            # Image sampling does not remove material text or authorize omitted image references.
            evidence_refs = [
                ref
                for ref in observation.evidence_refs
                if ref not in observation.image_refs or ref in selected_images
            ]
        result = {
            "observation_id": observation.id,
            "url": observation.url,
            "page": page_name(observation.url),
            "image_refs": included_images,
            "evidence_refs": evidence_refs,
        }
        if observation.mode != "live":
            result["material_text"] = observation.text
        return result

    timeline = []
    stage_labels = episode.candidate_labels if stage_labels is None else stage_labels

    def stage_label(number: int) -> str | None:
        return stage_labels[number - 1] if number <= len(stage_labels) else None

    if not episode.steps and episode.final_observation:
        observation = episode.final_observation
        final_state = state(observation)
        return [
            {
                "step_id": "initial-state",
                "action": None,
                "before": None,
                "after": final_state,
                "stage_before": 1,
                "stage_after": 1,
                "candidate_before": stage_label(1),
                "candidate_after": stage_label(1),
                "attached_images": [
                    {"role": "after", "ref": ref} for ref in (final_state or {}).get("image_refs", [])
                ],
            }
        ]
    trace = participant_history(episode)
    stage = 1
    for index, (step, action) in enumerate(zip(episode.steps, trace, strict=True)):
        after = (
            episode.steps[index + 1].observation
            if index + 1 < len(episode.steps)
            else episode.final_observation
        )
        before = state(step.observation)
        after_state = state(after)
        attached = [
            {"role": role, "ref": ref}
            for role, state_value in (("before", before), ("after", after_state))
            for ref in (state_value or {}).get("image_refs", [])
        ]
        stage_after = stage + 1 if action["action"] == "advance" and action["execution_success"] else stage
        timeline.append(
            {
                "step_id": f"step-{step.number}",
                "action": {
                    key: action[key]
                    for key in (
                        "action",
                        "target",
                        "value",
                        "intent",
                        "expected_result",
                        "execution_success",
                        "result",
                    )
                },
                "before": before,
                "after": after_state,
                "stage_before": stage,
                "stage_after": stage_after,
                "candidate_before": stage_label(stage),
                "candidate_after": stage_label(stage_after),
                "attached_images": attached,
            }
        )
        stage = stage_after
    return timeline


def representative_images(refs: list[str], limit: int) -> list[str]:
    refs = list(dict.fromkeys(refs))
    if limit == 0 or not refs:
        return []
    if len(refs) <= limit:
        return refs
    if limit == 1:
        return [refs[-1]]
    indexes = [round(index * (len(refs) - 1) / (limit - 1)) for index in range(limit)]
    return [refs[index] for index in dict.fromkeys(indexes)]


def validate_action_choice(
    value: Action,
    allowed_actions: list[str],
    observation: Observation,
    steps: list[Step],
    required_url_fragments: list[str] | None = None,
) -> None:
    if value.action not in allowed_actions:
        raise ValueError(f"Action {value.action} is not currently allowed")
    if value.action == "stop" and required_url_fragments:
        visited_urls = [step.observation.url for step in steps] + [observation.url]
        missing = [
            fragment
            for fragment in required_url_fragments
            if not any(fragment in url for url in visited_urls)
        ]
        if missing:
            raise ValueError(f"Stop requires visiting configured URL areas first: {missing}")
    if not value.target_id:
        return
    targets = {target.id: target for target in observation.targets}
    if value.target_id not in targets or targets[value.target_id].disabled:
        raise ValueError("Target is absent or disabled in current observation")
    target = targets[value.target_id]
    if value.action not in target.actions:
        raise ValueError(
            f"Action {value.action} is incompatible with target {value.target_id}; "
            f"use one of {target.actions}"
        )

    signature = (value.action, target.name, value.value)
    recent = []
    for step in steps[-2:]:
        previous_target = next(
            (item.name for item in step.observation.targets if item.id == step.action.target_id), None
        )
        recent.append(
            (step.action.action, previous_target, step.action.value) == signature
            and step.result.success
            and (
                observation.mode == "live"
                or (step.observation.mode, step.observation.state_id, step.observation.card_ids)
                == (observation.mode, observation.state_id, observation.card_ids)
            )
        )
    if len(recent) == 2 and all(recent):
        raise ValueError("Do not repeat the same successful targeted action more than twice")


class PersonaAgent:
    def __init__(
        self,
        episode: Episode,
        gateway: ModelGateway,
        store: EvidenceStore,
        budget: BudgetLedger,
        study: StudySpec | None = None,
    ):
        self.episode, self.gateway, self.store, self.budget = episode, gateway, store, budget
        self.responses = []
        self.study = study or StudySpec()

    @property
    def owner(self):
        return {"persona_id": self.episode.persona.id, "session_id": self.episode.session_id}

    def save(self):
        write_json(self.store.root / "episodes" / f"{self.episode.session_id}.json", self.episode)

    def begin_survey(self):
        episode = self.episode
        if episode.mode != "survey" or episode.phase != "experience":
            raise ValueError("Survey research can begin only from a new survey episode")
        episode.intent = self.gateway.complete(
            "persona_intent",
            {
                "persona": episode.persona.model_dump(),
                "goal": episode.goal,
                "persona_role_policy": persona_role_policy(),
                "survey_response_policy": survey_response_policy(),
                "instruction": "Follow persona_role_policy to establish a stable first-person survey response "
                "intent. Follow survey_response_policy for profile grounding. Do not invent product use, "
                "observations or external facts.",
            },
            SessionIntent,
        )
        episode.phase = "research"
        episode.outcome = "survey_ready"
        episode.outcome_basis = "profile_grounded_survey; no product experience"
        self.save()
        self.store.event("research_gate_opened", **self.owner, outcome=episode.outcome)

    def experience(
        self,
        environment: Environment,
        max_steps: int,
        min_actions_before_stop: int = 0,
        required_url_fragments_before_stop: list[str] | None = None,
    ):
        episode = self.episode
        try:
            episode.intent = self.gateway.complete(
                "persona_intent",
                {
                    "persona": episode.persona.model_dump(),
                    "goal": episode.goal,
                    "persona_role_policy": persona_role_policy(),
                    "prototype": episode.prototype.model_dump() if episode.prototype else None,
                    "instruction": "You are the supplied person about to try the product. Establish your own "
                    "brief first-person intent: what draws your attention, how you usually approach something "
                    "unfamiliar, your patience and when you personally would move on. Use the relevant habits, "
                    "preferences and context of this whole person, not a generic usability checklist or a "
                    "demographic stereotype. This is not a UX critique; you have not seen the interface yet. "
                    "The assigned task supplies scope, not a personality or a list of evaluation criteria. "
                    "Do not set your goal or stopping standard to producing a comparison, report or findings. "
                    "Do not invent past events or preselect unseen controls. Keep every field concise and in "
                    "the task language; genuine uncertainty or lack of special preferences is fine.",
                },
                SessionIntent,
            )
            self.save()
            for number in range(1, max_steps + 1):
                self.budget.check()
                observation = environment.observe()
                episode.final_observation = observation
                previous = episode.steps[-1] if episode.steps else None
                action_schema = Action
                action_images = list(
                    dict.fromkeys(
                        (previous.observation.image_refs if previous and episode.prototype else [])
                        + observation.image_refs
                    )
                )
                allowed_actions = (
                    ["click", "right_click", "type", "select", "press", "scroll", "wait", "stop"]
                    if episode.mode == "live"
                    else ["click", "wait", "stop"]
                )
                if episode.mode == "live" and getattr(environment, "can_go_back", False):
                    allowed_actions.append("back")
                if episode.mode == "live" and getattr(environment, "can_advance", False):
                    allowed_actions.append("advance")
                if len(episode.steps) < min_actions_before_stop:
                    allowed_actions.remove("stop")

                def validate_action(value: Action):
                    validate_action_choice(
                        value,
                        allowed_actions,
                        observation,
                        episode.steps,
                        required_url_fragments_before_stop,
                    )

                action = self.gateway.complete(
                    "persona_action",
                    {
                        "session_id": episode.session_id,
                        "persona": episode.persona.model_dump(),
                        "goal": episode.goal,
                        "intent": episode.intent.model_dump(),
                        "history": participant_history(episode),
                        "observation": observation.model_dump(),
                        "prototype": episode.prototype.model_dump() if episode.prototype else None,
                        "previous_observation": {
                            "id": previous.observation.id,
                            "image_refs": previous.observation.image_refs,
                        }
                        if previous
                        else None,
                        "allowed_actions": allowed_actions,
                        "persona_role_policy": persona_role_policy(),
                        "instruction": "Use the product as this person, not as a tester or UX reviewer. "
                        "Choose one next action from what you see, your own interest and what happened so far. "
                        "For exploration, try relevant controls and inspect the result, follow your curiosity "
                        "and revisit or adjust when useful. Do not mechanically tour every page or fill a "
                        "click quota. Merely accepting the starting screen is not hands-on experience. "
                        "Keep intent as a short personal reason for the next action, not a running design "
                        "evaluation. Leave reflection null; the subsequent interview is separate. "
                        "Stop when you personally would stop, or explain what prevented exploration. Do not "
                        "stop because you have enough material for a report. When ready to leave this version, "
                        "use advance if another version is available; this opens it in a fresh context and "
                        "does not require repeating the same path. You may abandon for a genuine blocker. "
                        "Stay within scope. If an option is known unavailable, do not keep probing it. "
                        "No visible change alone does not establish its cause. Only claim recorded actions; "
                        "expected_result is an expectation, not proof. Use current target IDs and allowed "
                        "actions. Scroll uses up/down; scroll and advance omit target_id. Do not repeat the "
                        "same successful action on the same target more than twice. Write in the task language. "
                        f"Before stopping, visit URL areas containing all configured fragments: "
                        f"{required_url_fragments_before_stop or []}. "
                        "In captured/scenario modes you review supplied materials, not an executing product. "
                        "Do not claim failed actions succeeded. For press use only Enter/Escape/Tab/Shift+Tab/"
                        "ArrowDown/ArrowUp/ArrowLeft/ArrowRight/Space. Select uses the visible native option label.",
                    },
                    action_schema,
                    images=action_images,
                    validate=validate_action,
                )
                validate_action(action)
                if previous and action.reflection is not None:
                    note = ExperienceNote(
                        step=previous.number,
                        before_observation_id=previous.observation.id,
                        after_observation_id=observation.id,
                        before_evidence_refs=previous.observation.evidence_refs,
                        after_evidence_refs=observation.evidence_refs,
                        reflection=action.reflection,
                    )
                    episode.experience_notes.append(note)
                    self.store.json(note, "experience_note", **self.owner)
                if action.action == "stop":
                    execution = ExecutionResult(
                        success=True, message="Persona stopped; no browser action executed"
                    )
                else:
                    try:
                        execution = environment.act(action)
                    except ValueError as error:
                        execution = ExecutionResult(success=False, message=str(error))
                step = Step(number=number, observation=observation, action=action, result=execution)
                episode.steps.append(step)
                if action.action != "stop":
                    episode.final_observation = None
                self.store.json(step, "step", **self.owner)
                self.store.event(
                    "experience_step",
                    **self.owner,
                    step=number,
                    action=action.action,
                    success=execution.success,
                )
                self.save()
                if action.action == "stop":
                    episode.final_observation = observation
                    episode.outcome = action.outcome
                    episode.outcome_basis = "persona_self_report; not independent task validation"
                    break
            else:
                episode.final_observation = environment.observe()
                episode.outcome = "max_steps"
                episode.outcome_basis = "automation_step_limit"
            episode.phase = "research"
            if hasattr(environment, "coverage"):
                episode.coverage = environment.coverage()
            self.store.event("research_gate_opened", **self.owner, outcome=episode.outcome)
        except StageBudgetExceeded as error:
            episode.final_observation = environment.observe()
            episode.outcome = "exploration_budget"
            episode.outcome_basis = "automation_budget_limit"
            episode.phase = "research"
            if hasattr(environment, "coverage"):
                episode.coverage = environment.coverage()
            self.store.event("experience_budget_ended", **self.owner, reason=str(error))
            self.store.event("research_gate_opened", **self.owner, outcome=episode.outcome)
        except Exception:
            episode.phase = "failed"
            episode.outcome = "failed"
            episode.outcome_basis = "runtime_error"
            raise
        finally:
            try:
                self.save()
            finally:
                environment.close()

    def research(self, method: MethodSpec) -> MethodResponse:
        if self.episode.phase != "research":
            raise ValueError("Research questions are unavailable until experience has ended")
        episode = self.episode
        observations = [step.observation for step in episode.steps]
        if episode.final_observation:
            observations.append(episode.final_observation)
        observations = list({observation.id: observation for observation in observations}.values())
        all_images = list(
            dict.fromkeys(ref for observation in observations for ref in observation.image_refs)
        )
        if method.evidence_mode == "complete" and len(all_images) > method.max_images:
            raise ValueError(
                "Complete interview evidence exceeds max_images; increase the bound or explicitly select sampled mode"
            )
        images = (
            all_images
            if method.evidence_mode == "complete"
            else representative_images(all_images, method.max_images)
        )
        selected_images = set(images)
        timeline = experience_timeline(
            episode,
            selected_images,
            complete=method.evidence_mode == "complete" or not all_images,
            stage_labels=list(
                dict.fromkeys(question.candidate for question in method.questions if question.candidate)
            ),
        )
        owner = self.owner
        allowed = {
            ref
            for item in timeline
            for state in (item["before"], item["after"])
            if state
            for ref in state["evidence_refs"]
        }
        evidence_selection = {
            "mode": method.evidence_mode,
            "total_images": len(all_images),
            "attached_images": len(images),
            "omitted_images": len([ref for ref in all_images if ref not in selected_images]),
            "timeline_steps": len(timeline),
        }
        response = MethodResponse(**owner, method_id=method.id, kind=method.kind, valid=True)
        profile_only = episode.mode == "survey"
        role_policy = answer_role_policy()
        response_policy = survey_answer_policy() if method.kind == "survey" else None

        def answer_batch(questions):
            batch_method = method.model_copy(
                update={"questions": [question.model_copy(update={"ask_if": {}}) for question in questions]}
            )
            batch_number = len(response.batches) + 1

            def validate_batch(value):
                bind_answer_evidence(value, batch_method, timeline, profile_only=profile_only)
                validate_answers(value, batch_method, allowed, profile_only=profile_only)

            answers = self.gateway.complete(
                "persona_research",
                {
                    "episode_summary": {
                        "session_id": episode.session_id,
                        "persona": episode.persona.model_dump(),
                        "goal": episode.goal,
                        "intent": episode.intent.model_dump() if episode.intent else None,
                        "outcome": episode.outcome,
                        "outcome_basis": episode.outcome_basis,
                        "prototype": episode.prototype.model_dump() if episode.prototype else None,
                    },
                    "experience_timeline": timeline,
                    "method": {
                        "id": batch_method.id,
                        "kind": batch_method.kind,
                        "questions": [participant_question(question) for question in batch_method.questions],
                    },
                    "evidence_selection": evidence_selection,
                    "prior_batch_answers": [answer.model_dump() for answer in response.answers],
                    "prior_followups": response.followups,
                    "prior_own_responses": self.responses,
                    "persona_role_policy": role_policy,
                    "survey_response_policy": response_policy,
                    "instruction": (
                        profile_survey_instruction()
                        if profile_only
                        else default_interview_instruction()
                        if method.kind == "interview"
                        else research_instruction() + "\n\n" + answer_voice_instruction()
                    ),
                },
                answer_schema(batch_method, profile_only=profile_only),
                interleave_key="experience_timeline",
                output_contract=answer_output_contract(batch_method),
                validate=validate_batch,
            )
            batch_ref = self.store.json(
                {
                    "method": method.id,
                    "batch": batch_number,
                    "questions": [question.model_dump() for question in questions],
                    "answers": answers.model_dump(),
                    "evidence_selection": evidence_selection,
                },
                "method_batch",
                **owner,
            )
            response.batches.append(
                {
                    "batch": batch_number,
                    "question_ids": [question.id for question in questions],
                    "valid": True,
                    "evidence_ref": batch_ref,
                }
            )
            write_json(
                self.store.root / "research" / episode.session_id / f"{method.id.encode().hex()}.json",
                response,
            )
            return [Answer.model_validate(answer.model_dump()) for answer in answers.answers]

        try:
            pending = []
            for question in method.questions:
                if question.ask_if and pending:
                    response.answers.extend(answer_batch(pending))
                    pending = []
                previous = {answer.question_id: answer.value for answer in response.answers}
                if question.ask_if and not all(
                    previous.get(parent) == expected for parent, expected in question.ask_if.items()
                ):
                    response.answers.append(Answer(question_id=question.id, value=None, basis="skipped"))
                    continue
                pending.append(question)
                if len(pending) >= method.batch_size:
                    response.answers.extend(answer_batch(pending))
                    pending = []
            if pending:
                response.answers.extend(answer_batch(pending))
            for index in range(method.max_followups):

                def validate_followup(decision):
                    if decision.ask and (
                        decision.parent_question_id not in {question.id for question in method.questions}
                        or not decision.text.strip()
                    ):
                        raise ValueError("Follow-up requires a known parent question and nonempty text")

                decision = self.gateway.complete(
                    "interview_moderator",
                    {
                        "method": method.model_dump(),
                        "answers": [answer.model_dump() for answer in response.answers],
                        "followups": response.followups,
                        "instruction": "Act as a neutral interviewer. Ask at most one "
                        "short clarifying question grounded in an actual answer, not a leading recommendation. "
                        "Do not introduce unseen features. Stop (ask=false) when sufficient. Give parent question ID.",
                    },
                    FollowupDecision,
                    validate=validate_followup,
                )
                self.store.json(decision, "moderator_decision", **owner)
                if not decision.ask:
                    break
                question = Question(id=f"followup-{index + 1}", text=decision.text)
                answer = answer_batch([question])[0]
                response.followups.append(
                    {
                        "question": question.model_dump(),
                        "parent_question_id": decision.parent_question_id,
                        "answer": answer.model_dump(),
                    }
                )
        except Exception as error:
            response.valid = False
            response.error = f"{type(error).__name__}: method did not validate"
            response.batches.append(
                {"batch": len(response.batches) + 1, "valid": False, "error": type(error).__name__}
            )
        write_json(
            self.store.root / "research" / episode.session_id / f"{method.id.encode().hex()}.json", response
        )
        response.evidence_ref = self.store.json(response, "method_response", **owner)
        self.responses.append(response.model_dump())
        self.store.event(
            "method_finished",
            **owner,
            method_id=method.id,
            valid=response.valid,
            evidence_ref=response.evidence_ref,
        )
        return response
