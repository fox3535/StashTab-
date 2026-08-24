"""Slice-03 adjustment writer (STASHTAB-INVENTORY-TRUTH-001 v1.2.0).

One locked path: lock item, compute signed delta, insert event + evidence
+ snapshot, then optionally emit adjust_anomaly after commit.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.inventory_truth.core import cutover_status
from app.inventory_truth.models_truth import (
    InventoryAdjustment,
    InventoryEvent,
    InventoryException,
)
from app.models import InventoryItem, Sale

logger = logging.getLogger("inventory_truth.adjust")

REASON_CODES = frozenset(
    {
        "count_correction",
        "data_entry_error",
        "shrinkage",
        "damage",
        "theft",
        "found",
        "cycle_count_variance",
        "csv_correction",
        "reverse_of",
    }
)
LOSS_CLASS = frozenset({"shrinkage", "damage", "theft"})
ANOMALY_ABS = 100
ANOMALY_PCT = 0.5
ANOMALY_ONHAND_MIN = 10
ANOMALY_FREQ = 10
ANOMALY_WINDOW_HOURS = 24


class AdjustFrozenError(RuntimeError):
    pass


class AdjustRejected(ValueError):
    pass


class AdjustConflict(RuntimeError):
    pass


class AdjustForbidden(PermissionError):
    pass


def require_adjust_open(db: Session, shop_id: str) -> None:
    if cutover_status(db, shop_id) != "complete":
        raise AdjustFrozenError(
            f"inventory-truth quantity adjust frozen for shop {shop_id}"
        )


def _payload_hash(item_id: int, input_mode: str, target_or_delta: int, reason_code: str) -> str:
    raw = f"{item_id}|{input_mode}|{target_or_delta}|{reason_code}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _event_key(source: str, shop_id: str, pk: str) -> str:
    if source == "admin_patch":
        return f"admin_adjust:{shop_id}:{pk}"
    if source == "cycle_count_variance":
        return f"count_adjust:{shop_id}:{pk}"
    if source == "csv":
        return f"csv_adjust:{shop_id}:{pk}"
    raise AdjustRejected(f"unknown source {source}")


def apply_adjustment(
    db: Session,
    *,
    shop_id: str,
    item_id: int,
    input_mode: str,
    reason_code: str,
    actor_clerk_user_id: str,
    source: str,
    target: int | None = None,
    delta: int | None = None,
    reason_note: str | None = None,
    client_idempotency_key: str | None = None,
    csv_upload_id: str | None = None,
    csv_row_identity: str | None = None,
    commit: bool = True,
) -> dict:
    require_adjust_open(db, shop_id)
    if not actor_clerk_user_id:
        raise AdjustForbidden("verified actor required")
    if reason_code not in REASON_CODES or reason_code == "reverse_of":
        raise AdjustRejected("invalid reason_code")
    if source not in ("admin_patch", "csv", "cycle_count_variance"):
        raise AdjustRejected("invalid source")
    if input_mode not in ("absolute", "signed"):
        raise AdjustRejected("invalid input_mode")

    if source in ("admin_patch", "cycle_count_variance"):
        if not client_idempotency_key:
            raise AdjustRejected("Idempotency-Key required")
        try:
            uuid.UUID(str(client_idempotency_key))
        except ValueError as exc:
            raise AdjustRejected("Idempotency-Key must be a UUID") from exc
        event_key = _event_key(source, shop_id, client_idempotency_key)
        lookup = (
            db.query(InventoryAdjustment)
            .filter(
                InventoryAdjustment.shop_id == shop_id,
                InventoryAdjustment.client_idempotency_key == client_idempotency_key,
            )
            .first()
        )
    else:
        if not csv_upload_id or not csv_row_identity:
            raise AdjustRejected("csv upload id and row identity required")
        event_key = _event_key(source, shop_id, f"{csv_upload_id}:{csv_row_identity}")
        lookup = (
            db.query(InventoryAdjustment)
            .filter(
                InventoryAdjustment.shop_id == shop_id,
                InventoryAdjustment.csv_upload_id == csv_upload_id,
                InventoryAdjustment.csv_row_identity == csv_row_identity,
            )
            .first()
        )

    target_or_delta = target if input_mode == "absolute" else delta
    if target_or_delta is None:
        raise AdjustRejected("absolute target or signed delta required")
    digest = _payload_hash(item_id, input_mode, int(target_or_delta), reason_code)
    if lookup is not None:
        if lookup.payload_hash != digest:
            raise AdjustConflict("idempotency key reused with a different payload")
        return _evidence(lookup, replayed=True)

    item = (
        db.query(InventoryItem)
        .filter(InventoryItem.shop_id == shop_id, InventoryItem.id == item_id)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if item is None:
        raise AdjustRejected("item not found")
    qty_before = int(item.stock or 0)
    if input_mode == "absolute":
        qty_delta = int(target) - qty_before
    else:
        qty_delta = int(delta)
    if qty_delta == 0:
        raise AdjustRejected("zero delta")
    qty_after = qty_before + qty_delta
    if qty_after < 0:
        raise AdjustRejected("adjustment would make remaining negative")
    if reason_code in LOSS_CLASS and qty_delta >= 0:
        raise AdjustRejected("loss-class reason requires a negative delta")
    if reason_code == "found" and qty_delta <= 0:
        raise AdjustRejected("found requires a positive delta")

    event = InventoryEvent(
        shop_id=shop_id,
        sku=item.sku,
        lot_id=None,
        inventory_item_id=item.id,
        sale_id=None,
        reverses_event_id=None,
        event_type="adjust",
        quantity_delta=qty_delta,
        overlay_quantity=None,
        reason=reason_code,
        actor_clerk_user_id=actor_clerk_user_id,
        idempotency_key=event_key,
    )
    db.add(event)
    db.flush()
    row = InventoryAdjustment(
        shop_id=shop_id,
        inventory_event_id=event.id,
        inventory_item_id=item.id,
        sku=item.sku,
        qty_before=qty_before,
        qty_delta=qty_delta,
        qty_after=qty_after,
        input_mode=input_mode,
        reason_code=reason_code,
        reason_note=reason_note,
        source=source,
        actor_clerk_user_id=actor_clerk_user_id,
        original_actor_clerk_user_id=None,
        client_idempotency_key=client_idempotency_key,
        csv_upload_id=csv_upload_id,
        csv_row_identity=csv_row_identity,
        payload_hash=digest,
        reverses_event_id=None,
    )
    db.add(row)
    item.stock = qty_after
    db.flush()
    if commit:
        db.commit()
        db.refresh(row)
        _emit_anomaly(db, row)
    return _evidence(row, replayed=False)


def reverse_adjustment(
    db: Session,
    *,
    shop_id: str,
    original_event_id: int,
    actor_clerk_user_id: str,
    commit: bool = True,
) -> dict:
    require_adjust_open(db, shop_id)
    if not actor_clerk_user_id:
        raise AdjustForbidden("verified actor required")
    original = (
        db.query(InventoryAdjustment)
        .filter(
            InventoryAdjustment.shop_id == shop_id,
            InventoryAdjustment.inventory_event_id == original_event_id,
        )
        .first()
    )
    if original is None:
        raise AdjustRejected("original adjustment not found")
    if original.source == "reverse":
        raise AdjustRejected("reverse of a reverse is not permitted")
    existing = (
        db.query(InventoryAdjustment)
        .filter(
            InventoryAdjustment.shop_id == shop_id,
            InventoryAdjustment.reverses_event_id == original_event_id,
        )
        .first()
    )
    if existing is not None:
        raise AdjustConflict("adjustment already fully reversed")

    orig_event = (
        db.query(InventoryEvent)
        .filter(
            InventoryEvent.shop_id == shop_id,
            InventoryEvent.id == original_event_id,
        )
        .one()
    )
    orig_pk = orig_event.idempotency_key.split(f":{shop_id}:", 1)[-1]
    source_token = orig_event.idempotency_key.split(":", 1)[0]
    reverse_key = f"reverse_{source_token}:{shop_id}:{orig_pk}"

    item = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.shop_id == shop_id,
            InventoryItem.id == original.inventory_item_id,
        )
        .with_for_update()
        .populate_existing()
        .one()
    )
    qty_before = int(item.stock or 0)
    qty_delta = -original.qty_delta
    qty_after = qty_before + qty_delta
    if qty_after < 0:
        raise AdjustRejected("reverse would make remaining negative")

    event = InventoryEvent(
        shop_id=shop_id,
        sku=item.sku,
        lot_id=None,
        inventory_item_id=item.id,
        sale_id=None,
        reverses_event_id=original_event_id,
        event_type="reverse",
        quantity_delta=qty_delta,
        overlay_quantity=None,
        reason="reverse_of",
        actor_clerk_user_id=actor_clerk_user_id,
        idempotency_key=reverse_key,
    )
    db.add(event)
    db.flush()
    row = InventoryAdjustment(
        shop_id=shop_id,
        inventory_event_id=event.id,
        inventory_item_id=item.id,
        sku=item.sku,
        qty_before=qty_before,
        qty_delta=qty_delta,
        qty_after=qty_after,
        input_mode="signed",
        reason_code="reverse_of",
        reason_note=None,
        source="reverse",
        actor_clerk_user_id=actor_clerk_user_id,
        original_actor_clerk_user_id=original.actor_clerk_user_id,
        client_idempotency_key=None,
        csv_upload_id=None,
        csv_row_identity=None,
        payload_hash=_payload_hash(item.id, "signed", qty_delta, "reverse_of"),
        reverses_event_id=original_event_id,
    )
    db.add(row)
    item.stock = qty_after
    db.flush()
    if commit:
        db.commit()
        db.refresh(row)
        _emit_anomaly(db, row)
    return _evidence(row, replayed=False)


def apply_csv_adjustments(
    db: Session,
    *,
    shop_id: str,
    actor_clerk_user_id: str,
    role: str | None,
    upload_id: str,
    rows: list[dict],
    default_reason: str = "csv_correction",
) -> dict:
    require_adjust_open(db, shop_id)
    if role != "owner":
        raise AdjustForbidden("CSV quantity apply is owner-only")
    try:
        uuid.UUID(str(upload_id))
    except ValueError as exc:
        raise AdjustRejected("csv upload id must be a UUID") from exc
    if not rows:
        raise AdjustRejected("csv has no rows")

    collapsed: dict[str, dict] = {}
    for row in rows:
        identity = str(row["row_identity"])
        target = int(row["target"])
        reason = str(row.get("reason_code") or default_reason)
        if identity in collapsed:
            if collapsed[identity]["target"] != target:
                raise AdjustRejected("duplicate SKU with conflicting targets")
            continue
        collapsed[identity] = {**row, "target": target, "reason_code": reason}

    # Fail the file if any row is a new item.
    for identity, row in collapsed.items():
        exists = (
            db.query(InventoryItem)
            .filter(InventoryItem.shop_id == shop_id, InventoryItem.sku == identity)
            .first()
        )
        if exists is None:
            raise AdjustRejected("csv contains a new-item quantity row")

    results = []
    for identity, row in collapsed.items():
        item = (
            db.query(InventoryItem)
            .filter(InventoryItem.shop_id == shop_id, InventoryItem.sku == identity)
            .one()
        )
        results.append(
            apply_adjustment(
                db,
                shop_id=shop_id,
                item_id=item.id,
                input_mode="absolute",
                target=row["target"],
                reason_code=row["reason_code"],
                actor_clerk_user_id=actor_clerk_user_id,
                source="csv",
                csv_upload_id=upload_id,
                csv_row_identity=identity,
                commit=False,
            )
        )
    db.commit()
    for result in results:
        adj = (
            db.query(InventoryAdjustment)
            .filter(InventoryAdjustment.id == result["adjustment_id"])
            .one()
        )
        _emit_anomaly(db, adj)
    return {"applied": len(results), "results": results}


def _emit_anomaly(db: Session, row: InventoryAdjustment) -> None:
    try:
        triggers = []
        if abs(row.qty_delta) >= ANOMALY_ABS:
            triggers.append("abs")
        if row.qty_before >= ANOMALY_ONHAND_MIN and abs(row.qty_delta) >= ANOMALY_PCT * row.qty_before:
            triggers.append("pct")
        since = datetime.now(timezone.utc) - timedelta(hours=ANOMALY_WINDOW_HOURS)
        freq = (
            db.query(func.count(InventoryAdjustment.id))
            .filter(
                InventoryAdjustment.shop_id == row.shop_id,
                InventoryAdjustment.sku == row.sku,
                InventoryAdjustment.created_at >= since,
            )
            .scalar()
            or 0
        )
        if freq > ANOMALY_FREQ:
            triggers.append("freq")
        if not triggers:
            return
        orig_event = (
            db.query(InventoryEvent)
            .filter(InventoryEvent.id == row.inventory_event_id)
            .one()
        )
        refs = [orig_event.idempotency_key]
        if "freq" in triggers:
            window_start = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            refs.append(f"adjust_freq:{row.sku}:{window_start.date().isoformat()}")
        for ref in refs:
            existing = (
                db.query(InventoryException)
                .filter(
                    InventoryException.shop_id == row.shop_id,
                    InventoryException.kind == "adjust_anomaly",
                    InventoryException.exception_ref == ref,
                )
                .first()
            )
            if existing is not None:
                continue
            db.add(
                InventoryException(
                    shop_id=row.shop_id,
                    kind="adjust_anomaly",
                    exception_ref=ref,
                    sku=row.sku,
                    quantity_unsatisfied=abs(row.qty_delta),
                    detail=json.dumps({"triggers": triggers, "adjustment_id": row.id}),
                    status="open",
                )
            )
        db.commit()
    except Exception as exc:  # noqa: BLE001 — alert failure must not hide adjust
        logger.exception("adjust_anomaly emit failed: %s", exc)
        db.rollback()


def _evidence(row: InventoryAdjustment, *, replayed: bool) -> dict:
    return {
        "adjustment_id": row.id,
        "event_id": row.inventory_event_id,
        "shop_id": row.shop_id,
        "sku": row.sku,
        "qty_before": row.qty_before,
        "qty_delta": row.qty_delta,
        "qty_after": row.qty_after,
        "reason_code": row.reason_code,
        "source": row.source,
        "replayed": replayed,
        "actor_clerk_user_id": row.actor_clerk_user_id,
        "original_actor_clerk_user_id": row.original_actor_clerk_user_id,
    }


def sale_count(db: Session, shop_id: str) -> int:
    return db.query(func.count(Sale.id)).filter(Sale.shop_id == shop_id).scalar() or 0


def recon_by_reason(db: Session, shop_id: str) -> dict[str, int]:
    rows = (
        db.query(InventoryAdjustment.reason_code, func.sum(InventoryAdjustment.qty_delta))
        .filter(InventoryAdjustment.shop_id == shop_id)
        .group_by(InventoryAdjustment.reason_code)
        .all()
    )
    return {str(code): int(total or 0) for code, total in rows}
