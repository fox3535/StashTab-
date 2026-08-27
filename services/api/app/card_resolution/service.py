"""Shop-scoped intake/abstention. Identity only. No inventory writes."""

from __future__ import annotations

import hashlib
import json
import threading
from typing import Any

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.card_resolution.models import (
    CardResolutionAudit,
    CardResolutionCandidate,
    CardResolutionCatalog,
    CardResolutionEvidence,
    CardResolutionIntake,
    CardResolutionReview,
)
from app.card_resolution.scoring import (
    CONTRACT_VERSION,
    RULESET_VERSION,
    Candidate,
    Decision,
    Evidence,
    ScoringFailure,
    ScoringTimeout,
    decide,
    retrieve_candidates,
)
from app.deps import ShopContext
from app.feature_readiness import ensure_card_resolution_intake_ready
from app.models.base import new_uuid, utcnow
from app.models.inventory import InventoryItem

REVIEW_ROLES = frozenset({"owner", "staff"})
_INTAKE_LOCK = threading.Lock()


class InventoryWriteAttempted(RuntimeError):
    pass


def _canonical_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "game": payload.get("game"),
        "name": payload.get("name"),
        "set_name": payload.get("set_name"),
        "set_code": payload.get("set_code"),
        "collector_number": payload.get("collector_number"),
        "language": payload.get("language"),
        "printing": payload.get("printing"),
        "justtcg_id": payload.get("justtcg_id"),
        "tcgplayer_id": payload.get("tcgplayer_id"),
        "candidates": payload.get("candidates") or [],
    }


def evidence_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(_canonical_payload(payload), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _load_list(value: str | None) -> list:
    if not value:
        return []
    parsed = json.loads(value)
    return parsed if isinstance(parsed, list) else []


def _inventory_count(db: Session, shop_id: str) -> int:
    return int(db.query(InventoryItem).filter(InventoryItem.shop_id == shop_id).count())


def _assert_no_inventory_write(before: int, db: Session, shop_id: str) -> None:
    if _inventory_count(db, shop_id) != before:
        raise InventoryWriteAttempted("card resolution must not write inventory")


def _candidate_from_row(row: CardResolutionCatalog) -> Candidate:
    return Candidate(
        shop_id=row.shop_id,
        game=row.game,
        name=row.name,
        set_name=row.set_name,
        set_code=row.set_code,
        collector_number=row.collector_number,
        language=row.language,
        printing=row.printing,
        justtcg_id=row.justtcg_id,
        tcgplayer_id=row.tcgplayer_id,
        source="catalog",
        row_id=row.id,
    )


def _candidate_from_payload(item: dict[str, Any], fallback_shop: str) -> Candidate:
    return Candidate(
        shop_id=str(item.get("shop_id") or fallback_shop),
        game=item.get("game"),
        name=item.get("name"),
        set_name=item.get("set_name"),
        set_code=item.get("set_code"),
        collector_number=item.get("collector_number"),
        language=item.get("language"),
        printing=item.get("printing"),
        justtcg_id=item.get("justtcg_id"),
        tcgplayer_id=item.get("tcgplayer_id"),
        source="request",
        row_id=str(item["id"]) if item.get("id") else None,
    )


def _response(intake: CardResolutionIntake, review_id: str | None = None) -> dict[str, Any]:
    return {
        "intake_id": intake.intake_id,
        "shop_id": intake.shop_id,
        "result": intake.result,
        "state": intake.state,
        "reason_codes": _load_list(intake.reason_codes),
        "identity_confidence": (
            None
            if intake.identity_confidence_hundredths is None
            else round(intake.identity_confidence_hundredths / 100, 2)
        ),
        "price_confidence": intake.price_confidence,
        "confidence_components": json.loads(intake.confidence_components or "{}"),
        "ruleset_version": intake.ruleset_version,
        "contract_version": intake.contract_version,
        "decision_source": intake.decision_source,
        "winner_identity_key": intake.winner_identity_key,
        "justtcg_invoked": False,
        "review_id": review_id,
    }


def _review_id(db: Session, shop_id: str, intake_pk: str) -> str | None:
    review = (
        db.query(CardResolutionReview)
        .filter(
            CardResolutionReview.shop_id == shop_id,
            CardResolutionReview.intake_pk == intake_pk,
        )
        .one_or_none()
    )
    return None if review is None else review.id


def _persist_decision(
    db: Session,
    ctx: ShopContext,
    payload: dict[str, Any],
    hashed: str,
    decision: Decision,
) -> CardResolutionIntake:
    now = utcnow()
    codes = list(decision.reason_codes)
    winner = decision.winner
    intake = CardResolutionIntake(
        id=new_uuid(),
        shop_id=ctx.shop_id,
        intake_id=str(payload["intake_id"]),
        evidence_hash=hashed,
        result=decision.result,
        state=decision.state,
        reason_codes=_dump(codes),
        identity_confidence_hundredths=decision.identity_confidence_hundredths,
        price_confidence=None,
        confidence_components=_dump(winner.components if winner else {}),
        ruleset_version=RULESET_VERSION,
        contract_version=CONTRACT_VERSION,
        decision_source=decision.decision_source,
        winner_identity_key=winner.identity_key if winner else None,
        justtcg_invoked=False,
        actor_clerk_user_id=ctx.clerk_user_id,
        created_at=now,
        updated_at=now,
    )
    db.add(intake)
    db.flush()
    db.add(
        CardResolutionEvidence(
            id=new_uuid(),
            shop_id=ctx.shop_id,
            intake_pk=intake.id,
            intake_id=intake.intake_id,
            payload_json=_dump(_canonical_payload(payload)),
            created_at=now,
        )
    )
    ranked = sorted(decision.scored, key=lambda row: row.total, reverse=True)
    for index, row in enumerate(ranked, start=1):
        db.add(
            CardResolutionCandidate(
                id=new_uuid(),
                shop_id=ctx.shop_id,
                intake_pk=intake.id,
                rank=index,
                identity_key=row.identity_key,
                score_hundredths=row.total,
                components_json=_dump(row.components),
                eligible=row.eligible,
                retrieved_via_fuzzy=row.retrieved_via_fuzzy,
                payload_json=_dump({"name": row.candidate.name, "game": row.candidate.game}),
            )
        )
    review = None
    if decision.result == "abstained":
        review = CardResolutionReview(
            id=new_uuid(),
            shop_id=ctx.shop_id,
            intake_pk=intake.id,
            intake_id=intake.intake_id,
            status="open",
            reason_codes=_dump(codes),
            created_at=now,
        )
        db.add(review)
        db.flush()
    db.add(
        CardResolutionAudit(
            id=new_uuid(),
            shop_id=ctx.shop_id,
            intake_pk=intake.id,
            review_id=None if review is None else review.id,
            action=f"intake_{decision.result}",
            actor_clerk_user_id=ctx.clerk_user_id,
            payload_json=_dump({"reason_codes": codes, "justtcg_invoked": False}),
            created_at=now,
        )
    )
    return intake


def submit_intake(db: Session, ctx: ShopContext, payload: dict[str, Any]) -> dict[str, Any]:
    ensure_card_resolution_intake_ready(db)
    if payload.get("shop_id") and payload["shop_id"] != ctx.shop_id:
        raise HTTPException(status_code=403, detail="Shop mismatch")
    intake_id = str(payload.get("intake_id") or "").strip()
    if not intake_id:
        raise HTTPException(status_code=422, detail="intake_id is required")
    hashed = evidence_hash(payload)
    with _INTAKE_LOCK:
        return _submit_intake_locked(db, ctx, payload, intake_id, hashed)


def _submit_intake_locked(
    db: Session,
    ctx: ShopContext,
    payload: dict[str, Any],
    intake_id: str,
    hashed: str,
) -> dict[str, Any]:
    existing = (
        db.query(CardResolutionIntake)
        .filter(
            CardResolutionIntake.shop_id == ctx.shop_id,
            CardResolutionIntake.intake_id == intake_id,
        )
        .one_or_none()
    )
    if existing is not None:
        if existing.evidence_hash != hashed:
            raise HTTPException(status_code=409, detail="intake_id conflict")
        return _response(existing, _review_id(db, ctx.shop_id, existing.id))

    before = _inventory_count(db, ctx.shop_id)
    catalog = db.query(CardResolutionCatalog).filter(CardResolutionCatalog.shop_id == ctx.shop_id).all()
    request_candidates = [
        _candidate_from_payload(item, ctx.shop_id) for item in (payload.get("candidates") or [])
    ]
    merged, retrieve_codes = retrieve_candidates(
        [_candidate_from_row(row) for row in catalog],
        request_candidates,
        ctx.shop_id,
    )
    evidence = Evidence.from_payload(payload)
    if retrieve_codes:
        decision = Decision(
            result="rejected",
            state="rejected",
            reason_codes=retrieve_codes,
            winner=None,
            scored=[],
            identity_confidence_hundredths=None,
        )
    else:
        try:
            decision = decide(evidence, merged)
        except ScoringTimeout:
            decision = Decision(
                result="abstained",
                state="pending_human_review",
                reason_codes=["scorer_timeout"],
                winner=None,
                scored=[],
                identity_confidence_hundredths=None,
            )
        except HTTPException:
            raise
        except (ScoringFailure, Exception):
            decision = Decision(
                result="abstained",
                state="pending_human_review",
                reason_codes=["scorer_failure"],
                winner=None,
                scored=[],
                identity_confidence_hundredths=None,
            )

    try:
        existing = (
            db.query(CardResolutionIntake)
            .filter(
                CardResolutionIntake.shop_id == ctx.shop_id,
                CardResolutionIntake.intake_id == intake_id,
            )
            .one_or_none()
        )
        if existing is not None:
            if existing.evidence_hash != hashed:
                raise HTTPException(status_code=409, detail="intake_id conflict")
            return _response(existing, _review_id(db, ctx.shop_id, existing.id))
        _persist_decision(db, ctx, payload, hashed, decision)
        db.flush()
        _assert_no_inventory_write(before, db, ctx.shop_id)
        db.commit()
    except IntegrityError:
        db.rollback()
        db.expire_all()
        stored = (
            db.query(CardResolutionIntake)
            .filter(
                CardResolutionIntake.shop_id == ctx.shop_id,
                CardResolutionIntake.intake_id == intake_id,
            )
            .one_or_none()
        )
        if stored is None:
            raise
        if stored.evidence_hash != hashed:
            raise HTTPException(status_code=409, detail="intake_id conflict")
        return _response(stored, _review_id(db, ctx.shop_id, stored.id))
    except InventoryWriteAttempted:
        db.rollback()
        raise HTTPException(status_code=500, detail="inventory write blocked") from None

    db.expire_all()
    stored = (
        db.query(CardResolutionIntake)
        .filter(
            CardResolutionIntake.shop_id == ctx.shop_id,
            CardResolutionIntake.intake_id == intake_id,
        )
        .one()
    )
    return _response(stored, _review_id(db, ctx.shop_id, stored.id))


def list_reviews(db: Session, ctx: ShopContext, status: str = "open") -> list[dict[str, Any]]:
    ensure_card_resolution_intake_ready(db)
    rows = (
        db.query(CardResolutionReview)
        .filter(
            CardResolutionReview.shop_id == ctx.shop_id,
            CardResolutionReview.status == status,
        )
        .all()
    )
    return [
        {
            "review_id": row.id,
            "intake_id": row.intake_id,
            "shop_id": row.shop_id,
            "status": row.status,
            "reason_codes": _load_list(row.reason_codes),
            "decision": row.decision,
        }
        for row in rows
    ]


def decide_review(db: Session, ctx: ShopContext, review_id: str, decision: str) -> dict[str, Any]:
    ensure_card_resolution_intake_ready(db)
    if ctx.role not in REVIEW_ROLES:
        raise HTTPException(status_code=403, detail="Reviewer role required")
    if decision not in {"accept_identity", "reject", "defer"}:
        raise HTTPException(status_code=422, detail="Invalid review decision")
    with _INTAKE_LOCK:
        return _decide_review_locked(db, ctx, review_id, decision)


def _decide_review_locked(
    db: Session, ctx: ShopContext, review_id: str, decision: str
) -> dict[str, Any]:
    review = (
        db.query(CardResolutionReview)
        .filter(CardResolutionReview.id == review_id, CardResolutionReview.shop_id == ctx.shop_id)
        .one_or_none()
    )
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    intake = (
        db.query(CardResolutionIntake)
        .filter(
            CardResolutionIntake.id == review.intake_pk,
            CardResolutionIntake.shop_id == ctx.shop_id,
        )
        .one()
    )
    if review.status == "decided":
        if review.decision == decision:
            return _response(intake, review.id)
        raise HTTPException(status_code=409, detail="review already decided")
    before = _inventory_count(db, ctx.shop_id)
    now = utcnow()
    if decision == "defer":
        review.status = "deferred"
        review.decision = "defer"
        review.decided_by = ctx.clerk_user_id
        review.decided_at = now
    elif decision == "accept_identity":
        review.status = "decided"
        review.decision = "accept_identity"
        review.decided_by = ctx.clerk_user_id
        review.decided_at = now
        intake.result = "accepted"
        intake.state = "accepted"
        intake.decision_source = "human"
        intake.updated_at = now
    else:
        review.status = "decided"
        review.decision = "reject"
        review.decided_by = ctx.clerk_user_id
        review.decided_at = now
        intake.result = "rejected"
        intake.state = "rejected"
        intake.decision_source = "human"
        intake.updated_at = now
    db.add(
        CardResolutionAudit(
            id=new_uuid(),
            shop_id=ctx.shop_id,
            intake_pk=review.intake_pk,
            review_id=review.id,
            action=f"review_{decision}",
            actor_clerk_user_id=ctx.clerk_user_id,
            payload_json=_dump({"decision": decision}),
            created_at=now,
        )
    )
    db.flush()
    _assert_no_inventory_write(before, db, ctx.shop_id)
    db.commit()
    db.refresh(intake)
    return _response(intake, review.id)
