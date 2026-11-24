import csv
import json
import random
from pathlib import Path

import yaml

from .runtime import canonical, digest
from .schemas import (
    CohortPlan,
    CohortSpec,
    Persona,
    PersonaCohortApproval,
    PersonaGenerationManifest,
)


def generation_artifact_issues(root: Path, manifest: PersonaGenerationManifest) -> list[str]:
    issues = []
    resolved_root = root.resolve()
    for relative, expected_sha256 in manifest.artifact_hashes.items():
        candidate = (root / relative).resolve()
        if not candidate.is_relative_to(resolved_root):
            issues.append(f"Generation artifact path escapes its directory: {relative}")
        elif not candidate.is_file():
            issues.append(f"Generation artifact is missing: {relative}")
        elif digest(candidate.read_bytes()) != expected_sha256:
            issues.append(f"Generation artifact hash mismatch: {relative}")
    return issues


def managed_generation_issues(spec: CohortSpec, people: list[Persona]) -> list[str]:
    source = Path(spec.source)
    manifest_path = source.parent / "generation-manifest.json"
    if not manifest_path.is_file():
        return []
    try:
        manifest = PersonaGenerationManifest.model_validate_json(manifest_path.read_text("utf-8"))
    except (OSError, ValueError) as error:
        return [f"Managed Persona generation manifest is invalid: {type(error).__name__}"]

    issues = []
    issues.extend(generation_artifact_issues(source.parent, manifest))
    if manifest.status != "completed":
        issues.append(f"Managed Persona generation is not completed: {manifest.status}")
    plan_path = source.parent / "cohort-plan.yaml"
    try:
        plan = CohortPlan.model_validate(yaml.safe_load(plan_path.read_text("utf-8")))
        plan_content = plan.model_dump(exclude={"status", "plan_sha256"})
        actual_plan_sha256 = digest(canonical(plan_content, compact=True))
        if (
            plan.status != "confirmed"
            or plan.plan_sha256 != manifest.plan_sha256
            or actual_plan_sha256 != manifest.plan_sha256
        ):
            issues.append("Managed Persona Cohort Plan hash or confirmation status is invalid")
    except (OSError, ValueError, yaml.YAMLError):
        issues.append("Managed Persona Cohort Plan could not be validated")
    snapshot_path = source.parent / "execution-snapshot.json"
    if (
        not snapshot_path.is_file()
        or digest(snapshot_path.read_bytes()) != manifest.execution_snapshot_sha256
    ):
        issues.append("Managed Persona execution snapshot hash does not match its manifest")
    if not source.is_file() or manifest.personas_sha256 != digest(source.read_bytes()):
        issues.append("Managed Persona file hash does not match its generation manifest")
    if manifest.requires_human_approval:
        approval_path = source.parent / "cohort-approval.json"
        try:
            approval = PersonaCohortApproval.model_validate_json(approval_path.read_text("utf-8"))
            if (
                approval.generation_manifest_sha256 != digest(manifest_path.read_bytes())
                or approval.personas_sha256 != manifest.personas_sha256
                or approval.approved_persona_ids != manifest.selected_persona_ids
            ):
                issues.append("Managed Persona cohort approval does not match its generation")
        except (OSError, ValueError):
            issues.append("Managed Persona cohort requires explicit approval with `genesia personas approve`")
    selected_ids = [person.id for person in people]
    if manifest.required_full_cohort and (
        len(selected_ids) != len(manifest.selected_persona_ids)
        or set(selected_ids) != set(manifest.selected_persona_ids)
    ):
        issues.append(
            "Managed Persona generation requires the complete cohort; generate a new cohort "
            "instead of sampling a subset"
        )
    return issues


def load_cohort(spec: CohortSpec) -> tuple[list[Persona], dict]:
    path = Path(spec.source)
    content = path.read_bytes()
    people = []
    if path.suffix.lower() == ".json":
        people = [Persona.model_validate(item) for item in json.loads(content)]
    else:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream, delimiter="\t")
            header = next(reader, [])
            if not header or header[0].lower() not in {"userid", "user_id", "id"}:
                raise ValueError("Persona TSV must have a UserId header")
            for row_number, row in enumerate(reader, 2):
                if not row:
                    continue
                if len(row) != 2:
                    raise ValueError(f"Invalid Persona TSV row {row_number}")
                people.append(Persona(id=row[0], profile=json.loads(row[1])))
    ids = [person.id for person in people]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate Persona IDs")
    for field, expected in spec.filters.items():

        def matches(person):
            value = person.profile
            for part in field.split("."):
                value = value.get(part) if isinstance(value, dict) else None
            return str(value).casefold() == expected.casefold()

        people = [person for person in people if matches(person)]
    if spec.ids:
        by_id = {person.id: person for person in people}
        if len(set(spec.ids)) != len(spec.ids) or any(person_id not in by_id for person_id in spec.ids):
            raise ValueError("Selected Persona IDs must be unique and present after filtering")
        people = [by_id[person_id] for person_id in spec.ids]
    else:
        if len(people) < spec.size:
            raise ValueError("Insufficient Personas after filtering")
        people = random.Random(spec.seed).sample(sorted(people, key=lambda person: person.id), spec.size)
    snapshot = {
        "dataset_sha256": digest(content),
        "seed": spec.seed,
        "ids": [person.id for person in people],
        "profiles_sha256": digest(canonical([person.model_dump() for person in people])),
    }
    return people, snapshot
