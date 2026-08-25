"""Outbound runtime for slice-02 (STASHTAB-INVENTORY-TRUTH-001 v1.1.0).

Implements the frozen DIRECTIVE-SLICE-02 v3 mechanics:
- per-line observation ledger with transactional same-channel arbitration
- POS/show sell events keyed `sell_sale:{shop}:{sale_id}` in the Sale tx
- Shopify pull line events keyed `sell_shopify_order_line:{shop}:{order}:{line}`
  (full and short sales share ONE key; delta carries the truth)
- over-sale: −S event + reused open exception + vendor alert, batch-safe
- append-only refund/return records; confirmed whole-unit resalable
  returns pair their positive event atomically
- reconciliation extended: per-type event sums, open exceptions,
  duplicate-suspicion surfacing (detect only — never merge/compensate)

Similarity signals never link, suppress, reverse, or compensate here.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.inventory_truth.models_truth import (
    InventoryChannelObservation,
    InventoryEvent,
    InventoryException,
    RefundRecord,
    ReturnRecord,
)

logger = logging.getLogger("inventory_truth.outbound")


class OutboundFrozenError(RuntimeError):
    """Cutover not complete for this shop — outbound dual-write rejected."""


class LinePermanentError(RuntimeError):
    """failed_permanent for a single pulled line; caller continues batch."""


def require_outbound_open(db: Session, shop_id: str) -> None:
    from app.inventory_truth.core import cutover_status

    if cutover_status(db, shop_id) != "complete":
        raise OutboundFrozenError(
            f"inventory-truth outbound frozen for shop {shop_id}"
        )


def _is_unique_violation(exc: Exception) -> bool:
    text_repr = str(exc).lower()
    orig = str(getattr(exc, "orig", "") or "").lower()
    return "unique" in orig or "unique" in text_repr


def sell_key_sale(shop_id: str, sale_id: int) -> str:
    return f"sell_sale:{shop_id}:{sale_id}"


def sell_key_shopify_line(shop_id: str, order_ref: str, line_ref: str) -> str:
    return f"sell_shopify_order_line:{shop_id}:{order_ref}:{line_ref}"


def return_key(shop_id: str, return_record_id: int) -> str:
    return f"return_return_record:{shop_id}:{return_record_id}"


# --- Observation ledger -----------------------------------------------------


def claim_observation(
    db: Session,
    *,
    shop_id: str,
    channel: str,
    channel_ref: str,
    sku: str,
    quantity_requested: int,
    quantity_removed: int,
    sale_id: int | None,
) -> bool:
    """Insert-or-get within the caller's transaction/savepoint.

    Returns True if THIS call owns the observation (first writer).
    Returns False on same-channel retry/overlap (unique violation) after
    rolling back ONLY to the savepoint — the loser writes nothing.
    Raises LinePermanentError only when the existing observation contradicts
    the claimed IDENTITY (same line ref, different sku/requested qty).
    A different computed `removed` caused by intervening stock changes is
    expected drift, never a contradiction: retries are no-op regardless of
    stock movement (DIRECTIVE-SLICE-02 §6 step 5).
    """
    nested = db.begin_nested()
    try:
        existing = (
            db.query(InventoryChannelObservation)
            .filter(
                InventoryChannelObservation.shop_id == shop_id,
                InventoryChannelObservation.channel == channel,
                InventoryChannelObservation.channel_ref == channel_ref,
            )
            .first()
        )
        if existing is not None:
            if existing.sku != sku or existing.quantity_requested != quantity_requested:
                nested.commit()  # release savepoint before failing the line
                raise LinePermanentError(
                    f"observation {channel}:{channel_ref} exists with "
                    "contradictory identity"
                )
            nested.commit()
            return False
        db.add(
            InventoryChannelObservation(
                shop_id=shop_id,
                channel=channel,
                channel_ref=channel_ref,
                sale_id=sale_id,
                sku=sku,
                quantity_requested=quantity_requested,
                quantity_removed=quantity_removed,
            )
        )
        db.flush()
        nested.commit()
        return True
    except IntegrityError as exc:
        nested.rollback()
        if _is_unique_violation(exc):
            # Concurrent first-writer won between our SELECT and INSERT.
            logger.info(
                "observation %s:%s lost arbitration race — no-op",
                channel,
                channel_ref,
            )
            return False
        raise LinePermanentError(
            f"observation insert failed for {channel}:{channel_ref}"
        ) from exc


# --- Sell event -------------------------------------------------------------


def write_sell_event(
    db: Session,
    *,
    key: str,
    shop_id: str,
    sku: str,
    inventory_item_id: int | None,
    sale_id: int | None,
    quantity_removed: int,
    reason: str | None,
    actor_clerk_user_id: str | None = None,
) -> str:
    """Idempotent LOTLESS outbound event write.

    Counterpart trio is event ↔ observation ↔ Sale row (DIRECTIVE-SLICE-02
    §4 lotless-outbound collision rules) — NOT lot↔event. Retry rules
    mirror DESIGN §2 step-for-step: both exist consistently → no_op;
    event exists with contradictory type/delta → failed_permanent;
    concurrent unique loss → no_op after verifying the winner's facts.
    lot_id stays NULL: the frozen design requires a lot for receive/loss
    only, and linking sells to an arbitrary lot would corrupt per-lot
    remaining arithmetic.

    Returns "created" | "no_op".
    """
    nested = db.begin_nested()
    try:
        event = (
            db.query(InventoryEvent)
            .filter(
                InventoryEvent.shop_id == shop_id,
                InventoryEvent.idempotency_key == key,
            )
            .first()
        )
        if event is not None:
            if (
                event.event_type != "sell"
                or event.quantity_delta != -quantity_removed
            ):
                raise LinePermanentError(
                    f"sell event {key} exists with contradictory type/delta"
                )
            nested.commit()
            return "no_op"

        db.add(
            InventoryEvent(
                shop_id=shop_id,
                sku=sku,
                lot_id=None,
                inventory_item_id=inventory_item_id,
                sale_id=sale_id,
                reverses_event_id=None,
                event_type="sell",
                quantity_delta=-quantity_removed,
                overlay_quantity=None,
                reason=reason,
                actor_clerk_user_id=actor_clerk_user_id,
                idempotency_key=key,
            )
        )
        db.flush()
        nested.commit()
    except IntegrityError as exc:
        nested.rollback()
        if not _is_unique_violation(exc):
            raise LinePermanentError(
                f"integrity failure writing sell event {key}"
            ) from exc
        # Lost a same-key insert race: verify what won matches our facts.
        winner = (
            db.query(InventoryEvent)
            .filter(
                InventoryEvent.shop_id == shop_id,
                InventoryEvent.idempotency_key == key,
            )
            .first()
        )
        if (
            winner is None
            or winner.event_type != "sell"
            or winner.quantity_delta != -quantity_removed
        ):
            raise LinePermanentError(f"sell event {key} race inconsistency")
        logger.info("sell event %s lost insert race — no-op", key)
    except LinePermanentError:
        nested.rollback()
        raise
    return "created"


# --- Over-sale exceptions ---------------------------------------------------


def record_over_sale_exception(
    db: Session,
    *,
    shop_id: str,
    channel_ref: str,
    order_id: str,
    line_id: str,
    sku: str,
    requested: int,
    removed: int,
) -> tuple[str, int]:
    """Reuse-not-stack: one open critical exception per canonical line key.

    A retry/replay of the same order-line reuses the open exception and
    never stacks another. Distinct lines accumulate their own exceptions.
    Concurrency-safe: unique violation on (kind, ref) → reuse existing.

    Returns ("created" | "reused" | "already_resolved", exception_id).
    """
    ref = sell_key_shopify_line(shop_id, order_id, line_id)
    unsatisfied = requested - removed
    detail = json.dumps(
        {
            "channel": "shopify",
            "channel_ref": channel_ref,
            "order_id": order_id,
            "line_id": line_id,
            "requested": requested,
            "removed": removed,
        }
    )
    nested = db.begin_nested()
    try:
        existing = (
            db.query(InventoryException)
            .filter(
                InventoryException.shop_id == shop_id,
                InventoryException.kind == "over_sale_short",
                InventoryException.exception_ref == ref,
            )
            .with_for_update()
            .first()
        )
        if existing is not None:
            if existing.status != "open":
                # Resolved earlier by a human; a NEW distinct shortage on the
                # same line may not silently resurrect it — surface permanent.
                nested.commit()  # release savepoint before failing the line
                raise LinePermanentError(
                    f"exception for {ref} already resolved; cannot auto-reopen"
                )
            nested.commit()
            return "reused", existing.id
        exc_row = InventoryException(
            shop_id=shop_id,
            kind="over_sale_short",
            exception_ref=ref,
            sku=sku,
            quantity_unsatisfied=unsatisfied,
            detail=detail,
            status="open",
        )
        db.add(exc_row)
        db.flush()
        nested.commit()
        return "created", exc_row.id
    except IntegrityError as exc:
        nested.rollback()
        if not _is_unique_violation(exc):
            raise
        row = (
            db.query(InventoryException)
            .filter(
                InventoryException.shop_id == shop_id,
                InventoryException.kind == "over_sale_short",
                InventoryException.exception_ref == ref,
            )
            .first()
        )
        if row is None:
            raise LinePermanentError(f"exception {ref} race inconsistency")
        if row.status != "open":
            return "already_resolved", row.id
        return "reused", row.id


# --- Duplicate suspicion ----------------------------------------------------


def record_duplicate_suspicion(
    db: Session,
    *,
    shop_id: str,
    pos_observation_ids: list[int],
    shopify_observation_ids: list[int],
    sku: str,
    window_detail: dict,
) -> str:
    """Surface-only detection output. Similarity NEVER links rows here:
    this records an exception naming candidate observations for human
    resolution; no compensating event may be written by this path."""
    ref = f"duplicate_suspicion:{shop_id}:{sku}:{window_detail['window_start']}:{window_detail['window_end']}"
    nested = db.begin_nested()
    try:
        existing = (
            db.query(InventoryException)
            .filter(
                InventoryException.shop_id == shop_id,
                InventoryException.kind == "duplicate_suspicion",
                InventoryException.exception_ref == ref,
            )
            .first()
        )
        if existing is not None:
            nested.commit()
            return "reused"
        db.add(
            InventoryException(
                shop_id=shop_id,
                kind="duplicate_suspicion",
                exception_ref=ref,
                sku=sku,
                quantity_unsatisfied=None,
                detail=json.dumps(
                    {
                        "pos_observation_ids": pos_observation_ids,
                        "shopify_observation_ids": shopify_observation_ids,
                        **window_detail,
                    }
                ),
                status="open",
            )
        )
        db.flush()
        nested.commit()
    except IntegrityError as exc:
        nested.rollback()
        if not _is_unique_violation(exc):
            raise
    return "created"


# --- Refund / return records -------------------------------------------------


def create_refund_record(
    db: Session,
    *,
    shop_id: str,
    outbound_event_id: int,
    amount,
    reason: str | None,
    actor_clerk_user_id: str | None,
) -> RefundRecord:
    """Append-only financial record; zero inventory effect."""
    from decimal import Decimal

    amount = Decimal(str(round(float(amount), 2)))
    if amount < 0:
        raise ValueError("refund amount must be non-negative")
    row = RefundRecord(
        shop_id=shop_id,
        outbound_event_id=outbound_event_id,
        amount=amount,
        reason=reason,
        actor_clerk_user_id=actor_clerk_user_id,
    )
    db.add(row)
    db.flush()
    return row


def confirm_return(
    db: Session,
    *,
    shop_id: str,
    sku: str,
    quantity_confirmed: int,
    outcome: str,
    condition_note: str | None,
    refund_record_id: int | None,
    outbound_event_id: int | None,
    inventory_item_id: int | None,
    actor_clerk_user_id: str | None,
    return_record_id: int | None = None,
) -> tuple[str, int]:
    """Vendor-owned resalable decision (binding interpretation §17.6).

    Only confirmed WHOLE units with outcome `resalable` increase inventory:
    exactly one positive receive-class event keyed
    `return_return_record:{shop}:{id}` in the SAME transaction as the
    append-only record insert.

    Idempotent by record, not just by event key: pass `return_record_id` to
    confirm/re-confirm an existing record; the same (shop, refund, outbound)
    triple also resolves to an existing record on retry. A repeat never
    inserts a second return_record (append-only audit stays one-row-per-
    physical-return); it only verifies/repairs its paired event.
    """
    if quantity_confirmed <= 0 or int(quantity_confirmed) != float(quantity_confirmed):
        raise ValueError("returns must be whole positive units")

    row = None
    if return_record_id is not None:
        row = (
            db.query(ReturnRecord)
            .filter(
                ReturnRecord.shop_id == shop_id,
                ReturnRecord.id == return_record_id,
            )
            .first()
        )
        if row is not None and (
            row.sku != sku
            or row.quantity_confirmed != quantity_confirmed
            or row.outcome != outcome
        ):
            raise LinePermanentError(
                f"return record {row.id} contradicts confirmation arguments"
            )
    if row is None:
        # Fact-based reuse requires a concrete anchor (refund or outbound
        # reference). Without one, two physically distinct returns of
        # identical facts would be indistinguishable — always insert.
        if refund_record_id is not None or outbound_event_id is not None:
            query = db.query(ReturnRecord).filter(ReturnRecord.shop_id == shop_id)
            if refund_record_id is not None:
                query = query.filter(ReturnRecord.refund_record_id == refund_record_id)
            else:
                query = query.filter(ReturnRecord.refund_record_id.is_(None))
            if outbound_event_id is not None:
                query = query.filter(ReturnRecord.outbound_event_id == outbound_event_id)
            else:
                query = query.filter(ReturnRecord.outbound_event_id.is_(None))
            # Full-fact match only: a retry of the SAME confirmation reuses its
            # record; a different inspection outcome (e.g. damaged instead of
            # resalable) is a distinct physical return and gets its own row.
            row = (
                query.filter(
                    ReturnRecord.sku == sku,
                    ReturnRecord.quantity_confirmed == quantity_confirmed,
                    ReturnRecord.outcome == outcome,
                )
                .first()
            )

    if row is not None:
        # Repeat confirm: verify the paired event exists with matching facts;
        # repair it if the crash happened between flushes. No second record.
        key = return_key(shop_id, row.id)
        nested = db.begin_nested()
        try:
            existing_event = (
                db.query(InventoryEvent)
                .filter(
                    InventoryEvent.shop_id == shop_id,
                    InventoryEvent.idempotency_key == key,
                )
                .first()
            )
            if existing_event is None and row.outcome == "resalable":
                db.add(
                    InventoryEvent(
                        shop_id=shop_id,
                        sku=sku,
                        lot_id=None,  # lotless return event; never invent stock
                        inventory_item_id=inventory_item_id,
                        sale_id=None,
                        reverses_event_id=None,
                        event_type="receive",
                        quantity_delta=row.quantity_confirmed,
                        overlay_quantity=None,
                        reason=f"return_confirm:{row.id}",
                        actor_clerk_user_id=row.actor_clerk_user_id,
                        idempotency_key=key,
                    )
                )
                db.flush()
            elif existing_event is not None and (
                existing_event.event_type != "receive"
                or existing_event.quantity_delta != row.quantity_confirmed
            ):
                raise LinePermanentError(f"return event {key} contradicts record")
            nested.commit()
        except IntegrityError as exc:
            nested.rollback()
            if not _is_unique_violation(exc):
                raise LinePermanentError(f"return event write failed for {key}") from exc
        return ("reused", row.id)

    if outcome != "resalable":
        # Damaged returns are recorded but never increase inventory.
        new_row = ReturnRecord(
            shop_id=shop_id,
            refund_record_id=refund_record_id,
            outbound_event_id=outbound_event_id,
            sku=sku,
            quantity_confirmed=quantity_confirmed,
            outcome=outcome,
            condition_note=condition_note,
            actor_clerk_user_id=actor_clerk_user_id,
        )
        db.add(new_row)
        # Savepoint-scoped insert: on an arbitration loss only this insert
        # unwinds; any paired refund record in the outer transaction
        # survives. Concurrent confirmation of identical facts wins; we
        # reuse its record — never a second append-only row.
        nested = db.begin_nested()
        try:
            db.flush()
            nested.commit()
        except IntegrityError as exc:
            nested.rollback()
            if not _is_unique_violation(exc):
                raise
            winner = (
                db.query(ReturnRecord)
                .filter(
                    ReturnRecord.shop_id == shop_id,
                    ReturnRecord.refund_record_id == refund_record_id,
                    ReturnRecord.outbound_event_id == outbound_event_id,
                    ReturnRecord.sku == sku,
                    ReturnRecord.quantity_confirmed == quantity_confirmed,
                    ReturnRecord.outcome == outcome,
                )
                .first()
            )
            if winner is None:
                raise LinePermanentError("return record race inconsistency") from exc
            return "reused", winner.id
        return "recorded_no_inventory", new_row.id

    new_row = ReturnRecord(
        shop_id=shop_id,
        refund_record_id=refund_record_id,
        outbound_event_id=outbound_event_id,
        sku=sku,
        quantity_confirmed=quantity_confirmed,
        outcome=outcome,
        condition_note=condition_note,
        actor_clerk_user_id=actor_clerk_user_id,
    )
    db.add(new_row)
    # Same savepoint-scoped arbitration as the damaged path above.
    nested = db.begin_nested()
    try:
        db.flush()
        nested.commit()
    except IntegrityError as exc:
        nested.rollback()
        if not _is_unique_violation(exc):
            raise
        winner = (
            db.query(ReturnRecord)
            .filter(
                ReturnRecord.shop_id == shop_id,
                ReturnRecord.refund_record_id == refund_record_id,
                ReturnRecord.outbound_event_id == outbound_event_id,
                ReturnRecord.sku == sku,
                ReturnRecord.quantity_confirmed == quantity_confirmed,
                ReturnRecord.outcome == outcome,
            )
            .first()
        )
        if winner is None:
            raise LinePermanentError("return record race inconsistency") from exc
        # The concurrent winner already owns the record AND its paired
        # event; this loser reuses without writing anything.
        return "reused", winner.id

    key = return_key(shop_id, new_row.id)
    nested = db.begin_nested()
    try:
        existing_event = (
            db.query(InventoryEvent)
            .filter(
                InventoryEvent.shop_id == shop_id,
                InventoryEvent.idempotency_key == key,
            )
            .first()
        )
        if existing_event is not None:
            if (
                existing_event.event_type != "receive"
                or existing_event.quantity_delta != quantity_confirmed
            ):
                raise LinePermanentError(f"return event {key} contradicts record")
            nested.commit()
        else:
            db.add(
                InventoryEvent(
                    shop_id=shop_id,
                    sku=sku,
                    lot_id=None,  # lotless return event; never invent stock
                    inventory_item_id=inventory_item_id,
                    sale_id=None,
                    reverses_event_id=None,
                    event_type="receive",
                    quantity_delta=quantity_confirmed,
                    overlay_quantity=None,
                    reason=f"return_confirm:{new_row.id}",
                    actor_clerk_user_id=actor_clerk_user_id,
                    idempotency_key=key,
                )
            )
            db.flush()
            nested.commit()
    except IntegrityError as exc:
        nested.rollback()
        if not _is_unique_violation(exc):
            raise LinePermanentError(f"return event write failed for {key}") from exc
    except LinePermanentError:
        nested.rollback()
        raise
    return "created", new_row.id


# --- Reconciliation extension -----------------------------------------------


def reconcile_shop_extended(db: Session, shop_id: str) -> dict:
    """Slice-01 equation plus slice-02 outputs:
    - per-type event delta breakdown
    - open exception register (shortages + suspicions)
    - per-channel observation totals (both refs visible)
    Mismatch rule unchanged: SUM(delta) per SKU vs snapshot stock.
    """
    from sqlalchemy import func

    from app.inventory_truth.core import reconcile_shop
    from app.models import InventoryItem

    mismatches = reconcile_shop(db, shop_id)

    type_rows = (
        db.query(InventoryEvent.event_type, func.sum(InventoryEvent.quantity_delta))
        .filter(InventoryEvent.shop_id == shop_id)
        .group_by(InventoryEvent.event_type)
        .all()
    )

    obs_rows = (
        db.query(
            InventoryChannelObservation.channel,
            func.sum(InventoryChannelObservation.quantity_removed),
        )
        .filter(InventoryChannelObservation.shop_id == shop_id)
        .group_by(InventoryChannelObservation.channel)
        .all()
    )

    open_exceptions = (
        db.query(InventoryException)
        .filter(
            InventoryException.shop_id == shop_id,
            InventoryException.status == "open",
        )
        .all()
    )

    # Directive §7: reconcile is the surfacing moment. Detection runs here
    # (alert-only) so suspicions reach the vendor without any linking or
    # compensation. Failures must not break the reconciliation report.
    try:
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        surfaced = detect_duplicate_suspicions(
            db,
            shop_id=shop_id,
            window_start=now - timedelta(hours=24),
            window_end=now,
        )
    except Exception as exc:  # pragma: no cover - detection is advisory
        logger.warning("duplicate-suspicion detection failed: %s", exc)
        surfaced = []

    return {
        "mismatches": mismatches,
        "event_totals_by_type": {t: int(v or 0) for t, v in type_rows},
        "observation_totals_by_channel": {c: int(v or 0) for c, v in obs_rows},
        "duplicate_suspicions_surfaced": surfaced,
        "open_exceptions": [
            {
                "id": e.id,
                "kind": e.kind,
                "ref": e.exception_ref,
                "sku": e.sku,
                "quantity_unsatisfied": e.quantity_unsatisfied,
                "detail": json.loads(e.detail) if e.detail else {},
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in open_exceptions
        ],
    }


def detect_duplicate_suspicions(
    db: Session,
    *,
    shop_id: str,
    window_start,
    window_end,
) -> list[dict]:
    """Compare per-SKU observed units (POS + pull) against snapshot-derived
    availability evidence in the window. When observations exceed evidence,
    name BOTH channels' candidates in one suspicion exception. Detect only:
    no merge, no suppression, no compensation."""
    from datetime import timedelta

    from sqlalchemy import func

    from app.models import InventoryItem

    start = window_start - timedelta(minutes=5)
    end = window_end + timedelta(minutes=5)

    def _obs_by_sku(channel: str) -> dict[str, list[int]]:
        rows = (
            db.query(
                InventoryChannelObservation.sku,
                func.sum(InventoryChannelObservation.quantity_removed),
                func.min(InventoryChannelObservation.id),
                func.max(InventoryChannelObservation.id),
            )
            .filter(
                InventoryChannelObservation.shop_id == shop_id,
                InventoryChannelObservation.channel == channel,
                InventoryChannelObservation.created_at >= start,
                InventoryChannelObservation.created_at <= end,
            )
            .group_by(InventoryChannelObservation.sku)
            .all()
        )
        return {
            r[0]: {"units": int(r[1] or 0), "min_id": r[2], "max_id": r[3]}
            for r in rows
        }

    pos = _obs_by_sku("pos")
    pull = _obs_by_sku("shopify")

    items = {
        i.sku: i for i in db.query(InventoryItem).filter(InventoryItem.shop_id == shop_id).all()
    }

    surfaced: list[dict] = []
    for sku in set(pos) & set(pull):
        item = items.get(sku)
        if item is None:
            continue
        observed = pos[sku]["units"] + pull[sku]["units"]
        # Evidence bound: units that could physically have left this SKU in
        # the window. Conservative floor is current (post-window) stock.
        available_floor = int(item.stock or 0)
        if observed <= available_floor:
            continue  # stock still covers the observations — nothing suspect
        if min(pos[sku]["units"], pull[sku]["units"]) > 0:
            result = record_duplicate_suspicion(
                db,
                shop_id=shop_id,
                pos_observation_ids=[pos[sku]["min_id"], pos[sku]["max_id"]],
                shopify_observation_ids=[pull[sku]["min_id"], pull[sku]["max_id"]],
                sku=sku,
                window_detail={
                    "window_start": start.isoformat(),
                    "window_end": end.isoformat(),
                    "pos_units": pos[sku]["units"],
                    "shopify_units": pull[sku]["units"],
                    "snapshot_stock": available_floor,
                },
            )
            surfaced.append({"sku": sku, "status": result})
    return surfaced
