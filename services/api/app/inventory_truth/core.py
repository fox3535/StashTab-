"""Receive-foundation runtime: canonical keys, idempotent dual-write,
cutover/freeze, and reconciliation — per frozen contract v1.0.0.

Writes only `receive`, `loss`, and `reverse` of those (DESIGN.md §1).
No Sale row is created for loss. Snapshot `InventoryItem.stock` / WA
`cost` remain the operational source; this module never recomputes them.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.inventory_truth.models_truth import (
    AcquisitionLot,
    InventoryEvent,
    InventoryTruthCutover,
)

logger = logging.getLogger("inventory_truth")

RECEIVE_SOURCES = ("purchase_record", "staging_commit", "opening")
SHRINKAGE_SOURCES = ("shrinkage",)


def canonical_key(source: str, shop_id: str, source_pk: int | str, generation: int = 0) -> str:
    """Locked format: `{source}:{shop_id}:{source_pk}` with `:gen:{n}` for
    opening/shrinkage. No `:receive` suffix (DESIGN.md §2)."""
    key = f"{source}:{shop_id}:{source_pk}"
    if generation:
        key = f"{key}:gen:{generation}"
    return key


def cutover_status(db: Session, shop_id: str) -> str | None:
    row = (
        db.query(InventoryTruthCutover)
        .filter(InventoryTruthCutover.shop_id == shop_id)
        .first()
    )
    return row.status if row else None


def require_receive_open(db: Session, shop_id: str) -> None:
    """Fail closed unless a completed gen:1 cutover exists for the shop.

    Live receives are rejected during freeze/locking and when no cutover
    exists (MIGRATION.md §Order step 3/4)."""
    status = cutover_status(db, shop_id)
    if status != "complete":
        raise ReceiveFrozenError(
            f"inventory-truth receive frozen for shop {shop_id} (cutover status: {status})"
        )


class ReceiveFrozenError(RuntimeError):
    pass


class PermanentPairError(RuntimeError):
    """Event exists without its lot — failed_permanent, does not skip."""


def _write_pair(
    db: Session,
    *,
    shop_id: str,
    sku: str,
    source: str,
    source_pk: int | str,
    inventory_item_id: int | None,
    purchase_record_id: int | None,
    quantity_acquired: int,
    unit_cost: Decimal,
    label: str | None,
    reason: str | None,
    actor_clerk_user_id: str | None,
    generation: int,
) -> str:
    """Insert lot + matching event in ONE transaction with the SAME
    canonical key on both rows. Idempotent per DESIGN.md §2 retry rules.

    Returns "created" or "no_op".
    """
    if quantity_acquired <= 0:
        raise ValueError("quantity_acquired must be positive")

    is_shrinkage = source in SHRINKAGE_SOURCES
    key = canonical_key(source, shop_id, source_pk, generation)
    event_type = "loss" if is_shrinkage else "receive"
    delta = -quantity_acquired if is_shrinkage else quantity_acquired

    # One savepoint wraps existence checks + inserts: a concurrent-duplicate
    # unique violation rolls back ONLY this pair (DESIGN.md §2 rule 5) and
    # leaves the caller's transaction — snapshot updates already flushed —
    # fully intact.
    nested = db.begin_nested()
    try:
        lot = (
            db.query(AcquisitionLot)
            .filter(AcquisitionLot.shop_id == shop_id, AcquisitionLot.idempotency_key == key)
            .first()
        )
        event = (
            db.query(InventoryEvent)
            .filter(InventoryEvent.shop_id == shop_id, InventoryEvent.idempotency_key == key)
            .first()
        )

        if lot is not None and event is not None:
            if (
                lot.quantity_acquired != quantity_acquired
                or lot.source_type != source
                or event.event_type != event_type
            ):
                raise PermanentPairError(
                    f"idempotency key {key} exists with mismatched type/quantity"
                )
            nested.commit()
            return "no_op"

        if event is not None and lot is None:
            # Rule 4: event without lot is failed_permanent — never skip.
            raise PermanentPairError(f"event exists without lot for key {key}")

        effective_delta = delta
        effective_type = event_type
        if lot is not None:
            # Lot exists, event missing: rebuild the event from the STORED
            # lot's quantity/type, never from the caller's arguments.
            effective_type = "loss" if lot.source_type in SHRINKAGE_SOURCES else "receive"
            effective_delta = (
                -lot.quantity_acquired
                if lot.source_type in SHRINKAGE_SOURCES
                else lot.quantity_acquired
            )

        if lot is None:
            lot = AcquisitionLot(
                shop_id=shop_id,
                sku=sku,
                inventory_item_id=inventory_item_id,
                purchase_record_id=purchase_record_id,
                source_type=source,
                idempotency_key=key,
                quantity_acquired=quantity_acquired,
                unit_cost=unit_cost,
                status="active",
                label=label,
                note=reason,
            )
            db.add(lot)
            db.flush()  # assign lot.id for the event FK

        if event is None:
            db.add(
                InventoryEvent(
                    shop_id=shop_id,
                    sku=sku,
                    lot_id=lot.id,
                    inventory_item_id=inventory_item_id,
                    sale_id=None,  # receive-first: never set
                    reverses_event_id=None,
                    event_type=effective_type,
                    quantity_delta=effective_delta,
                    overlay_quantity=None,
                    reason=reason,
                    actor_clerk_user_id=actor_clerk_user_id,
                    idempotency_key=key,
                )
            )

        nested.commit()
    except IntegrityError as exc:
        nested.rollback()
        if _is_unique_violation(exc):
            logger.info("inventory-truth concurrent duplicate for key %s treated as retry", key)
            return "no_op"
        # FK restrict violations etc. are real defects, not retries.
        raise PermanentPairError(f"integrity failure writing truth pair for key {key}") from exc

    return "created"


def _is_unique_violation(exc: IntegrityError) -> bool:
    orig = str(exc.orig or "").lower() if getattr(exc, "orig", None) is not None else ""
    return "unique" in orig or "unique constraint" in str(exc).lower()


def record_purchase_receive(
    db: Session,
    *,
    shop_id: str,
    sku: str,
    purchase_record_id: int,
    inventory_item_id: int | None,
    quantity: int,
    unit_cost: Decimal,
    actor_clerk_user_id: str | None = None,
) -> str:
    """Live trade receive dual-write. Source `purchase_record` only — never
    also staging_commit, even if staging was deleted in the trade apply
    (DESIGN.md §2)."""
    return _write_pair(
        db,
        shop_id=shop_id,
        sku=sku,
        source="purchase_record",
        source_pk=purchase_record_id,
        inventory_item_id=inventory_item_id,
        purchase_record_id=purchase_record_id,
        quantity_acquired=quantity,
        unit_cost=unit_cost,
        label=None,
        reason=None,
        actor_clerk_user_id=actor_clerk_user_id,
        generation=0,
    )


def record_staging_commit_receive(
    db: Session,
    *,
    shop_id: str,
    sku: str,
    staging_item_id: int,
    inventory_item_id: int | None,
    quantity: int,
    unit_cost: Decimal,
    actor_clerk_user_id: str | None = None,
) -> str:
    """Live staging-commit dual-write; staging id captured BEFORE delete."""
    return _write_pair(
        db,
        shop_id=shop_id,
        sku=sku,
        source="staging_commit",
        source_pk=staging_item_id,
        inventory_item_id=inventory_item_id,
        purchase_record_id=None,
        quantity_acquired=quantity,
        unit_cost=unit_cost,
        label=None,
        reason=None,
        actor_clerk_user_id=actor_clerk_user_id,
        generation=0,
    )


def backfill_purchase_record(
    db: Session,
    *,
    shop_id: str,
    sku: str,
    purchase_record_id: int,
    inventory_item_id: int | None,
    quantity: int,
    unit_cost: Decimal,
) -> str:
    """Backfill A — purchase records; SAME key as live dual-write, so rerun
    is a no-op (MIGRATION.md §Backfill A)."""
    return _write_pair(
        db,
        shop_id=shop_id,
        sku=sku,
        source="purchase_record",
        source_pk=purchase_record_id,
        inventory_item_id=inventory_item_id,
        purchase_record_id=purchase_record_id,
        quantity_acquired=quantity,
        unit_cost=unit_cost,
        label=None,
        reason="backfill_purchase",
        actor_clerk_user_id=None,
        generation=0,
    )


def backfill_opening_or_shrinkage(
    db: Session,
    *,
    shop_id: str,
    item,
    generation: int = 1,
) -> str:
    """Backfill B — opening gap inside the cutover lock (MIGRATION.md §B).

    gap = stock - SUM(event delta for shop+sku).
    gap > 0 → opening lot + receive +gap (synthetic/provisional).
    gap < 0 → shrinkage lot + loss -abs(gap); NOT a Sale.
    gap = 0 → nothing. Rerun uses the same gen keys → no-op.
    """
    event_sum = (
        db.query(func_event_delta_sum())
        .filter(
            InventoryEvent.shop_id == shop_id,
            InventoryEvent.sku == item.sku,
        )
        .scalar()
    )
    gap = int(item.stock or 0) - int(event_sum or 0)
    if gap == 0:
        return "no_op"

    source = "opening" if gap > 0 else "shrinkage"
    return _write_pair(
        db,
        shop_id=shop_id,
        sku=item.sku,
        source=source,
        source_pk=item.id,
        inventory_item_id=item.id,
        purchase_record_id=None,
        quantity_acquired=abs(gap),
        unit_cost=Decimal(str(round(float(item.cost or 0.0), 2))),
        label="synthetic_provisional" if gap > 0 else None,
        reason="backfill_opening_provisional" if gap > 0 else "backfill_shrinkage_provisional",
        actor_clerk_user_id=None,
        generation=generation,
    )


def func_event_delta_sum():
    from sqlalchemy import func

    return func.coalesce(func.sum(InventoryEvent.quantity_delta), 0)


def run_cutover(db: Session, shop_id: str, generation: int = 1) -> dict:
    """Per-shop cutover transaction: watermark row + lock, backfill A then
    B, complete. No live receive can commit during freeze because
    require_receive_open rejects while status != complete (MIGRATION.md §4)."""
    existing = (
        db.query(InventoryTruthCutover)
        .filter(
            InventoryTruthCutover.shop_id == shop_id,
            InventoryTruthCutover.generation == generation,
        )
        .with_for_update()
        .first()
    )
    if existing is not None and existing.status == "complete":
        return {"status": "already_complete", "generation": generation}
    if existing is None:
        existing = InventoryTruthCutover(
            shop_id=shop_id,
            generation=generation,
            status="locking",
        )
        db.add(existing)
        db.flush()
    elif existing.status == "failed_permanent":
        return {"status": "failed_permanent", "generation": generation}
    # status == "locking" (e.g. after a crash): re-enter the same procedure.

    from datetime import datetime, timezone

    from app.models import InventoryItem, PurchaseRecord

    existing.frozen_at = datetime.now(timezone.utc)
    db.flush()

    # Lock the shop's inventory_item and purchase_record rows used in this
    # generation (MIGRATION.md §Order step 4). On Postgres these block
    # concurrent receives until commit; SQLite serializes writers anyway.
    item_rows = (
        db.query(InventoryItem)
        .filter(InventoryItem.shop_id == shop_id)
        .with_for_update()
        .all()
    )
    db.query(PurchaseRecord).filter(PurchaseRecord.shop_id == shop_id).with_for_update().all()

    # Backfill A — purchase records (same keys as live dual-write).
    purchase_rows = (
        db.query(PurchaseRecord)
        .filter(PurchaseRecord.shop_id == shop_id)
        .order_by(PurchaseRecord.id.asc())
        .all()
    )
    items_by_sku = {i.sku: i for i in item_rows}

    backfilled = 0
    for pr in purchase_rows:
        item = items_by_sku.get(pr.sku)
        result = backfill_purchase_record(
            db,
            shop_id=shop_id,
            sku=pr.sku,
            purchase_record_id=pr.id,
            inventory_item_id=item.id if item is not None else None,
            quantity=pr.quantity,
            unit_cost=Decimal(str(round(float(pr.cost_per_unit), 2))),
        )
        if result == "created":
            backfilled += 1

    # Backfill B — opening gap per item, inside the same locked transaction.
    opened = 0
    for item in items_by_sku.values():
        result = backfill_opening_or_shrinkage(db, shop_id=shop_id, item=item, generation=generation)
        if result == "created":
            opened += 1

    existing.status = "complete"
    existing.opened_at = datetime.now(timezone.utc)
    db.commit()
    return {
        "status": "complete",
        "generation": generation,
        "purchase_backfilled": backfilled,
        "opening_created": opened,
    }


def reconcile_shop(db: Session, shop_id: str) -> dict:
    """event_remaining(sku) must equal inventory_item.stock (DESIGN.md §1
    recon). Returns per-SKU mismatches; empty dict = 0 unaccounted."""
    from app.models import InventoryItem

    rows = (
        db.query(
            InventoryEvent.sku,
            func_event_delta_sum(),
        )
        .filter(InventoryEvent.shop_id == shop_id)
        .group_by(InventoryEvent.sku)
        .all()
    )
    event_remaining = {sku: int(total or 0) for sku, total in rows}

    mismatches: dict[str, dict] = {}
    for item in db.query(InventoryItem).filter(InventoryItem.shop_id == shop_id).all():
        remaining = event_remaining.pop(item.sku, 0)
        if remaining != int(item.stock or 0):
            mismatches[item.sku] = {
                "event_remaining": remaining,
                "snapshot_stock": int(item.stock or 0),
            }
    for sku, remaining in event_remaining.items():
        mismatches[sku] = {"event_remaining": remaining, "snapshot_stock": None}
    return mismatches
