from __future__ import annotations

import json
import re
from typing import Any

from ..runtime import EvidenceStore, canonical, digest
from ..schemas import (
    CohortPlan,
    PersonaCandidateResponse,
    PersonaGenerationCheckpoint,
    PersonaRiskReview,
    PersonaSlot,
    PersonaSlotGenerationCheckpoint,
)
from .candidates import _candidate_profile, _validate_candidate_for_slot
from .cohort import _refill_conflict_projection, _similarity
from .prompts import _cohort_review_projection, _risk_review_payload, persona_generation_policy


def _recover_generation_checkpoint(
    plan: CohortPlan,
    slots: list[PersonaSlot],
    store: EvidenceStore,
    execution_snapshot_sha256: str,
) -> PersonaGenerationCheckpoint:
    slot_by_id = {slot.slot_id: slot for slot in slots}
    checkpoint = PersonaGenerationCheckpoint(
        plan_sha256=plan.plan_sha256 or "",
        execution_snapshot_sha256=execution_snapshot_sha256,
    )
    generation_requests: dict[str, tuple[str, dict[str, Any]]] = {}
    review_requests: dict[str, tuple[str, dict[str, Any]]] = {}
    transport_retries: set[str] = set()

    for ref in store.refs.values():
        if ref.kind == "persona_generation_transport_retry":
            retry = json.loads(store.path(ref.id).read_text("utf-8"))
            authorization_ref = store.refs[retry["authorization_ref"]]
            if authorization_ref.kind != "persona_transport_recovery":
                raise ValueError("Persona transport retry is missing its recovery authorization")
            authorization = json.loads(store.path(authorization_ref.id).read_text("utf-8"))
            saved_authorization = json.loads((store.root / "transport-recovery.json").read_text("utf-8"))
            source_manifest = store.root / "source-generation" / "generation-manifest.json"
            snapshot = json.loads((store.root / "execution-snapshot.json").read_text("utf-8"))
            recovery = snapshot.get("transport_recovery", {})
            if (
                authorization != saved_authorization
                or digest(source_manifest.read_bytes()) != authorization["source_manifest_sha256"]
                or recovery.get("authorization_sha256") != digest(canonical(authorization))
                or recovery.get("retained_persona_ids") != authorization["retained_persona_ids"]
            ):
                raise ValueError("Persona transport recovery lineage does not match its authorization")
            candidate_id = ref.persona_id or ""
            item = checkpoint.slots.get(candidate_id)
            approved = authorization["requests"].get(candidate_id)
            if (
                item is None
                or approved is None
                or candidate_id in transport_retries
                or item.stage != "failed"
                or item.candidate is not None
                or item.review_attempts != 0
                or item.generation_attempts != approved["generation_attempts"]
                or item.generation_request_refs[-1] != retry["request_ref"]
                or retry["request_ref"] != approved["request_ref"]
                or retry["failure_ref"] != approved["failure_ref"]
                or "ReadTimeout" not in (item.issue or "")
            ):
                raise ValueError("Persona transport retry does not match an authorized failed request")
            failure = json.loads(store.path(retry["failure_ref"]).read_text("utf-8"))
            if (
                store.refs[retry["failure_ref"]].kind != "persona_generation_failure"
                or failure["request_ref"] != retry["request_ref"]
                or "ReadTimeout" not in failure["issue"]
            ):
                raise ValueError("Persona transport retry has no matching read-timeout failure")
            transport_retries.add(candidate_id)
            generation_requests[candidate_id] = (
                retry["request_ref"],
                json.loads(store.path(retry["request_ref"]).read_text("utf-8")),
            )
            checkpoint.slots[candidate_id] = item.model_copy(update={"issue": "transport_retry_incomplete"})
            continue
        if ref.kind == "persona_generation_request":
            payload = json.loads(store.path(ref.id).read_text("utf-8"))
            if not ref.persona_id:
                raise ValueError(f"Cannot identify Persona generation request: {ref.id}")
            slot_id = str(payload["slot"]["slot_id"])
            variation_key = str(payload["variation_key"])
            match = re.fullmatch(
                rf"{plan.plan_sha256}:{plan.seed}:{re.escape(slot_id)}:(\d+)"
                r"(:semantic-repair-1|:refill-1)?",
                variation_key,
            )
            if slot_id not in slot_by_id or match is None:
                raise ValueError(f"Cannot recover Persona generation response: {ref.id}")
            candidate_index = int(match.group(1))
            candidate_id = f"{slot_id}-candidate-{candidate_index + 1}"
            slot = slot_by_id[slot_id]
            if (
                candidate_id != ref.persona_id
                or candidate_index >= plan.candidates_per_slot
                or payload["slot"] != slot.model_dump(mode="json")
            ):
                raise ValueError(f"Persona generation request does not match its slot: {ref.id}")
            existing = checkpoint.slots.get(candidate_id)
            reason = None
            if match.group(2):
                if plan.candidates_per_slot != 1 or existing is None or existing.generation_attempts != 1:
                    raise ValueError(f"Cannot recover bounded Persona refill: {ref.id}")
                if match.group(2) == ":semantic-repair-1":
                    if (
                        not existing.candidate
                        or existing.candidate.get("risk_review", {}).get("severity") != "high"
                    ):
                        raise ValueError(f"Cannot recover bounded Persona semantic repair: {ref.id}")
                    if payload.get("semantic_repair") != {
                        "rejected_profile": existing.candidate["profile"],
                        "risk_review": existing.candidate["risk_review"],
                    }:
                        raise ValueError(f"Persona semantic repair does not match its review: {ref.id}")
                    reason = "high_semantic_risk"
                else:
                    refill = payload.get("refill", {})
                    reason = refill.get("reason")
                    if reason not in {
                        "generation_failed",
                        "generation_incomplete",
                        "duplicate_profile_across_slots",
                    }:
                        raise ValueError(f"Cannot identify Persona refill deficit: {ref.id}")
                    if (reason.startswith("generation_") and existing.candidate is not None) or (
                        reason == "duplicate_profile_across_slots"
                        and (
                            existing.stage != "reviewed"
                            or not existing.candidate
                            or not refill.get("blocking_profiles")
                        )
                    ):
                        raise ValueError(f"Persona refill does not match its deficit: {ref.id}")
                    if refill.get("previous_profile") != (
                        existing.candidate["profile"] if existing.candidate else None
                    ):
                        raise ValueError(f"Persona refill does not match its previous profile: {ref.id}")
                    if reason == "duplicate_profile_across_slots":
                        conflict_ids = {
                            value.get("candidate_id")
                            for value in refill["blocking_profiles"]
                            if isinstance(value, dict)
                        }
                        blockers = [
                            item.candidate
                            for item in checkpoint.slots.values()
                            if item.stage == "reviewed"
                            and item.candidate_id != candidate_id
                            and item.candidate_id in conflict_ids
                        ]
                        expected_projections = [
                            projection
                            for value in blockers
                            for projection in (
                                _refill_conflict_projection(value),
                                _cohort_review_projection(value),
                            )
                        ]
                        if not all(
                            value in expected_projections for value in refill["blocking_profiles"]
                        ) or not any(
                            _similarity(existing.candidate["profile"], value["profile"])
                            >= plan.duplicate_similarity_threshold
                            for value in blockers
                            if (
                                _refill_conflict_projection(value) in refill["blocking_profiles"]
                                or _cohort_review_projection(value) in refill["blocking_profiles"]
                            )
                        ):
                            raise ValueError(f"Persona refill duplication evidence does not match: {ref.id}")
            elif existing is not None and not (
                plan.candidates_per_slot > 1
                and existing.candidate is None
                and existing.issue == "generation_incomplete"
            ):
                raise ValueError(f"Repeated initial Persona generation request: {ref.id}")
            generation_requests[candidate_id] = (ref.id, payload)
            checkpoint.slots[candidate_id] = PersonaSlotGenerationCheckpoint(
                candidate_id=candidate_id,
                slot_id=slot_id,
                candidate_index=candidate_index,
                stage="failed",
                candidate=existing.candidate if existing else None,
                issue="refill_incomplete" if reason else "generation_incomplete",
                generation_attempts=(existing.generation_attempts if existing else 0) + 1,
                review_attempts=existing.review_attempts if existing else 0,
                generation_request_refs=[
                    *(existing.generation_request_refs if existing else []),
                    ref.id,
                ],
                review_request_refs=existing.review_request_refs if existing else [],
                refill_reason=reason,
            )
            continue
        if ref.kind in {"persona_generation_response", "persona_generation_failure"}:
            request = generation_requests.pop(ref.persona_id or "", None)
            item = checkpoint.slots.get(ref.persona_id or "")
            if request is None or item is None:
                raise ValueError(f"Cannot match Persona generation response: {ref.id}")
            request_ref, payload = request
            if ref.kind == "persona_generation_failure":
                failure = json.loads(store.path(ref.id).read_text("utf-8"))
                if failure["request_ref"] != request_ref:
                    raise ValueError(f"Persona generation failure does not match its request: {ref.id}")
                checkpoint.slots[item.candidate_id] = item.model_copy(update={"issue": failure["issue"]})
                continue
            response = PersonaCandidateResponse.model_validate_json(store.path(ref.id).read_text("utf-8"))
            slot = slot_by_id[item.slot_id]
            _validate_candidate_for_slot(response, slot)
            profile = _candidate_profile(slot, response)
            repeated = (
                item.refill_reason is not None
                and item.candidate is not None
                and item.candidate["profile_sha256"] == digest(canonical(profile, compact=True))
            )
            history = []
            if item.refill_reason:
                previous = dict(item.candidate or {})
                previous.pop("repair_history", None)
                previous.update(
                    request_ref=item.generation_request_refs[0],
                    rejected_reason=item.refill_reason,
                )
                history.append(previous)
            checkpoint.slots[item.candidate_id] = item.model_copy(
                update={
                    "stage": "failed" if repeated else "generated",
                    "issue": f"refill_repeated_profile:{item.refill_reason}" if repeated else None,
                    "candidate": {
                        "candidate_id": item.candidate_id,
                        "slot_id": item.slot_id,
                        "profile": profile,
                        "profile_sha256": digest(canonical(profile, compact=True)),
                        "request_ref": request_ref,
                        "response_ref": ref.id,
                        **({"repair_history": history} if history else {}),
                    },
                }
            )
            continue
        if ref.kind == "persona_risk_review_request":
            if not ref.persona_id:
                raise ValueError(f"Cannot identify Persona risk review request: {ref.id}")
            item = checkpoint.slots.get(ref.persona_id)
            payload = json.loads(store.path(ref.id).read_text("utf-8"))
            if (
                item is None
                or item.stage != "generated"
                or not item.candidate
                or payload != _risk_review_payload(plan, slot_by_id[item.slot_id], item.candidate["profile"])
            ):
                raise ValueError(f"Persona risk review does not match its candidate: {ref.id}")
            review_requests[ref.persona_id] = (ref.id, payload)
            checkpoint.slots[item.candidate_id] = item.model_copy(
                update={
                    "stage": "generated",
                    "review_attempts": item.review_attempts + 1,
                    "review_request_refs": [*item.review_request_refs, ref.id],
                }
            )
            continue
        if ref.kind == "persona_risk_review_failure":
            request = review_requests.pop(ref.persona_id or "", None)
            item = checkpoint.slots.get(ref.persona_id or "")
            failure = json.loads(store.path(ref.id).read_text("utf-8"))
            if request is None or item is None or request[0] != failure["request_ref"]:
                raise ValueError(f"Cannot match Persona risk review failure: {ref.id}")
            checkpoint.slots[item.candidate_id] = item.model_copy(update={"issue": failure["issue"]})
            continue
        if ref.kind != "persona_risk_review_response":
            continue
        request = review_requests.pop(ref.persona_id or "", None)
        item = checkpoint.slots.get(ref.persona_id or "")
        if request is None or item is None or not item.candidate:
            raise ValueError(f"Cannot match Persona risk review response: {ref.id}")
        request_ref, payload = request
        if payload != _risk_review_payload(plan, slot_by_id[item.slot_id], item.candidate["profile"]):
            raise ValueError(f"Persona risk review does not match its candidate: {ref.id}")
        review = PersonaRiskReview.model_validate_json(store.path(ref.id).read_text("utf-8"))
        candidate = dict(item.candidate)
        candidate.update(
            {
                "risk_review": review.model_dump(mode="json"),
                "risk_review_request_ref": request_ref,
                "risk_review_response_ref": ref.id,
            }
        )
        rejected = review.severity == "high"
        checkpoint.slots[item.candidate_id] = item.model_copy(
            update={
                "stage": "failed" if rejected else "reviewed",
                "candidate": candidate,
                "issue": "high_semantic_risk" if rejected else None,
            }
        )
    return checkpoint


def _generation_snapshot_fields(
    plan: CohortPlan, execution_snapshot: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "version": 1,
        "generator": "genesia.persona_generation.v3",
        "plan_sha256": plan.plan_sha256,
        "candidates_per_slot": plan.candidates_per_slot,
        "duplicate_similarity_threshold": plan.duplicate_similarity_threshold,
        "candidate_schema_sha256": digest(
            canonical(PersonaCandidateResponse.model_json_schema(), compact=True)
        ),
        "risk_review_schema_sha256": digest(canonical(PersonaRiskReview.model_json_schema(), compact=True)),
        "persona_generation_policy_sha256": digest(persona_generation_policy().encode("utf-8")),
        **(execution_snapshot or {}),
    }
