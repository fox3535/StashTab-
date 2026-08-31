"""F2 slice-01 controlled receive (AMENDMENT-1.3.0 §4–§6, DIRECTIVE §2/§4).

One thin receive transaction: readiness gate, idempotency replay by
`(shop_id, client_idempotency_key)`, snapshot insert-or-bump (mirror of
the accepted new-item branch in `logic/trades.py`, WITHOUT `SyncOutbox`),
`purchase_record` insert, and the frozen lot+event dual-write. Commit
happens only at the end; a concurrent loser rolls back its ENTIRE
transaction and re-resolves by client key (commit-at-end design).

Payload-equality evidence is the SHA-256 digest of the canonical tuple
`(sku, quantity, unit_cost)` rounded exactly as validated; on replay it
is recomputed from the stored purchase columns. Digest mismatch for the
same client key returns 409 and writes nothing.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import FeatureNotReadyError
from app.feature_readiness import ensure_inventory_mutations_ready
from app.inventory_truth import core as truth
from app.inventory_truth.core import PermanentPairError, ReceiveFrozenError
from app.models import InventoryItem, PurchaseRecord


class ReceiveConflictError(RuntimeError):
    """Same client key, different payload digest — 409, zero writes."""


@dataclass(frozen=True)
class ReceiveResult:
    result: str  # "created" | "no_op"
    inventory_item_id: int
    sku: str
    stock: int
    purchase_record_id: int


def canonical_cost(unit_cost: float) -> Decimal:
    """Canonical two-decimal form shared by validation, storage, digests."""
    return Decimal(str(round(float(unit_cost), 2)))


def payload_digest(sku: str, quantity: int, unit_cost: Decimal) -> str:
    """Evidence-correlation digest of the canonical (sku, quantity,
    unit_cost) tuple (AMENDMENT-1.3.0 §4)."""
    canonical = f"{sku}|{int(quantity)}|{unit_cost.quantize(Decimal('0.01'))}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _stored_digest(record: PurchaseRecord) -> str:
    return payload_digest(record.sku, int(record.quantity), canonical_cost(record.cost_per_unit))


def _find_by_client_key(db: Session, shop_id: str, client_key: str) -> PurchaseRecord | None:
    return (
        db.query(PurchaseRecord)
        .filter(
            PurchaseRecord.shop_id == shop_id,
            PurchaseRecord.client_idempotency_key == client_key,
        )
        .first()
    )


def _result_from_record(db: Session, record: PurchaseRecord, result: str) -> ReceiveResult:
    item = (
        db.query(InventoryItem)
        .filter(InventoryItem.shop_id == record.shop_id, InventoryItem.sku == record.sku)
        .first()
    )
    return ReceiveResult(
        result=result,
        inventory_item_id=item.id if item is not None else 0,
        sku=record.sku,
        stock=int(item.stock) if item is not None else 0,
        purchase_record_id=record.id,
    )


def _attempt(
    db: Session,
    *,
    shop_id: str,
    client_key: str,
    sku: str,
    name: str,
    quantity: int,
    unit_cost: Decimal,
    set_name: str | None,
    sequence_number: str | None,
    actor_clerk_user_id: str | None,
) -> ReceiveResult:
    """Steps 2–5 of the one-transaction sequence. No commit here."""
    existing = _find_by_client_key(db, shop_id, client_key)
    if existing is not None:
        if _stored_digest(existing) != payload_digest(sku, quantity, unit_cost):
            raise ReceiveConflictError(
                f"client idempotency key already used with a different payload"
            )
        return _result_from_record(db, existing, "no_op")

    item = (
        db.query(InventoryItem)
        .filter(InventoryItem.shop_id == shop_id, InventoryItem.sku == sku)
        .first()
    )
    cost_value = float(unit_cost)
    if item is not None:
        # Weighted-average bump; only stock/cost move (grant envelope §7).
        total_qty = int(item.stock) + quantity
        if total_qty > 0:
            new_avg_cost = (
                (float(item.cost) * int(item.stock)) + (cost_value * quantity)
            ) / total_qty
            item.cost = round(new_avg_cost, 2)
        item.stock = total_qty
    else:
        # Mirror of the accepted new-item branch (logic/trades.py 248–285),
        # without SyncOutbox; receive creates the item, never truth.
        item = InventoryItem(
            shop_id=shop_id,
            sku=sku,
            name=name,
            set_name=set_name,
            sequence_number=sequence_number,
            cost=cost_value,
            price=0.0,
            stock=quantity,
            game="Pokemon",
            sync_status="approved",
        )
        db.add(item)
        db.flush()

    record = PurchaseRecord(
        shop_id=shop_id,
        sku=sku,
        quantity=quantity,
        cost_per_unit=cost_value,
        client_idempotency_key=client_key,
    )
    db.add(record)
    db.flush()

    truth.record_purchase_receive(
        db,
        shop_id=shop_id,
        sku=sku,
        purchase_record_id=record.id,
        inventory_item_id=item.id,
        quantity=quantity,
        unit_cost=unit_cost,
        actor_clerk_user_id=actor_clerk_user_id,
    )
    return ReceiveResult(
        result="created",
        inventory_item_id=item.id,
        sku=item.sku,
        stock=int(item.stock),
        purchase_record_id=record.id,
    )


def receive_controlled(
    db: Session,
    *,
    shop_id: str,
    client_key: str,
    sku: str,
    name: str,
    quantity: int,
    unit_cost: float,
    set_name: str | None = None,
    sequence_number: str | None = None,
    actor_clerk_user_id: str | None = None,
) -> ReceiveResult:
    """Execute the controlled receive in ONE transaction, commit only at
    the end. Raises FeatureNotReadyError (503) until cutover complete,
    ReceiveConflictError (409) on digest mismatch. Concurrent duplicate
    client keys: the loser's entire transaction rolls back and the request
    re-resolves by key against the winner, returning `no_op`."""
    cost = canonical_cost(unit_cost)
    kwargs = dict(
        shop_id=shop_id,
        client_key=client_key,
        sku=sku,
        name=name,
        quantity=quantity,
        unit_cost=cost,
        set_name=set_name,
        sequence_number=sequence_number,
        actor_clerk_user_id=actor_clerk_user_id,
    )
    try:
        ensure_inventory_mutations_ready(db, shop_id)
    except ReceiveFrozenError as exc:
        raise FeatureNotReadyError("inventory_truth") from exc

    try:
        result = _attempt(db, **kwargs)
        db.commit()
        return result
    except ReceiveConflictError:
        # Digest mismatch at step 2: roll back and surface 409, zero writes.
        db.rollback()
        raise
    except PermanentPairError:
        db.rollback()
        raise ReceiveConflictError("truth pair mismatch for client idempotency key")
    except IntegrityError:
        # Losing concurrent writer (partial unique on client key, or the
        # accepted duplicate-(shop_id, sku) race): roll back the ENTIRE
        # uncommitted transaction, then re-resolve against the winner.
        db.rollback()
        winner = _find_by_client_key(db, shop_id, client_key)
        if winner is None:
            raise ReceiveConflictError("concurrent receive conflict; nothing committed")
        if _stored_digest(winner) != payload_digest(sku, quantity, cost):
            raise ReceiveConflictError(
                "client idempotency key already used with a different payload"
            )
        return _result_from_record(db, winner, "no_op")
    except Exception:
        # §6 partial failure: ANY failure rolls back all four objects.
        db.rollback()
        raise
