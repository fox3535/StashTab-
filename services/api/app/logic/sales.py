"""Sale finalization ported from Mimir logic.py."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.inventory_truth.core import ReceiveFrozenError
from app.logic.pricing import (
    calculate_net_profit,
    calculate_net_revenue,
    effective_sell_price,
)
from app.models import InventoryItem, Sale, SyncOutbox


class InsufficientStockError(RuntimeError):
    """POS insufficient stock: fail closed, stable machine-readable code,
    zero partial mutation (binding interpretation §17.4)."""

    def __init__(self, *, sku: str, requested: int, available: int):
        self.sku = sku
        self.requested = requested
        self.available = available
        super().__init__(
            f"INSUFFICIENT_STOCK: {sku} requested {requested}, available {available}"
        )

    @property
    def code(self) -> str:
        return "INSUFFICIENT_STOCK"


@dataclass
class CartLine:
    item: InventoryItem
    quantity: int
    unit_price: float


@dataclass
class FinalizedLine:
    item: InventoryItem
    quantity: int
    apportioned_price: float
    profit: float
    processing_fees: float
    trade_credit_deduction: float
    net_revenue: float


def build_cart_lines(
    db: Session,
    shop_id: str,
    line_inputs: list[tuple[str, int]],
) -> tuple[list[CartLine], float]:
    lines: list[CartLine] = []
    market_total = 0.0

    for sku, quantity in line_inputs:
        item = (
            db.query(InventoryItem)
            .filter(
                InventoryItem.shop_id == shop_id,
                InventoryItem.sku == sku.upper(),
            )
            .first()
        )
        if not item:
            raise ValueError(f"SKU not found: {sku}")
        if item.stock < quantity:
            raise ValueError(
                f"Insufficient stock for {item.sku} (have {item.stock})"
            )
        unit_price = effective_sell_price(item)
        market_total += unit_price * quantity
        lines.append(CartLine(item=item, quantity=quantity, unit_price=unit_price))

    return lines, market_total


def calculate_lot_sale_distribution(
    lines: list[CartLine],
    negotiated_total: float,
) -> list[FinalizedLine]:
    """Apportion negotiated total across cart lines by market weight."""
    market_total = sum(line.unit_price * line.quantity for line in lines)
    if market_total <= 0:
        return []

    distribution: list[FinalizedLine] = []
    for line in lines:
        line_market = line.unit_price * line.quantity
        weight = line_market / market_total
        apportioned = round(negotiated_total * weight, 2)
        cost = float(line.item.cost) * line.quantity
        profit = calculate_net_profit(apportioned, cost)
        distribution.append(
            FinalizedLine(
                item=line.item,
                quantity=line.quantity,
                apportioned_price=apportioned,
                profit=profit,
                processing_fees=0.0,
                trade_credit_deduction=0.0,
                net_revenue=apportioned,
            )
        )
    return distribution


def finalize_sale(
    db: Session,
    shop_id: str,
    lines: list[CartLine],
    final_sale_price: float,
    payment_method: str,
    *,
    trade_in_value: float = 0.0,
    show_session_id: str | None = None,
) -> list[int]:
    """
    Decrement stock, write Sale rows, outbound truth pairs, and SyncOutbox
    entries. Fail-closed on insufficient stock BEFORE any mutation.
    Returns created sale IDs.
    """
    from app.inventory_truth import core as truth
    from app.inventory_truth import core_outbound as out

    status = truth.cutover_status(db, shop_id)
    if status != "complete":
        raise ReceiveFrozenError(
            f"POS finalize frozen during inventory-truth cutover (status: {status})"
        )

    # Lock the item rows before the stock check so concurrent checkouts
    # serialize per item: the fail-closed validation cannot race a parallel
    # decrement (binding interpretation §17.4 holds under concurrency).
    # with_for_update is a no-op on SQLite; populate_existing refreshes
    # cached identity-map objects with the locked, current values.
    item_ids = sorted({line.item.id for line in lines})
    locked_items = {
        row.id: row
        for row in db.query(InventoryItem)
        .filter(
            InventoryItem.shop_id == shop_id,
            InventoryItem.id.in_(item_ids),
        )
        .with_for_update()
        .populate_existing()
        .all()
    }
    for line in lines:
        line.item = locked_items[line.item.id]

    # Fail closed before touching anything (binding interpretation §17.4).
    for line in lines:
        if line.item.stock < line.quantity:
            raise InsufficientStockError(
                sku=line.item.sku,
                requested=line.quantity,
                available=int(line.item.stock or 0),
            )

    distribution = calculate_lot_sale_distribution(lines, final_sale_price)
    sale_ids: list[int] = []

    for finalized in distribution:
        fees, trade_deduction, net_revenue = calculate_net_revenue(
            finalized.apportioned_price,
            payment_method,
        )
        finalized.processing_fees = fees
        finalized.trade_credit_deduction = trade_deduction
        finalized.net_revenue = net_revenue

        item = finalized.item
        item.stock -= finalized.quantity

        sale = Sale(
            shop_id=shop_id,
            item_name=item.name,
            sku=item.sku,
            sold_price=finalized.apportioned_price,
            profit=finalized.profit,
            transaction_type=payment_method,
            trade_in_value=trade_in_value,
            processing_fees=finalized.processing_fees,
            trade_credit_deduction=finalized.trade_credit_deduction,
            net_revenue=finalized.net_revenue,
            game=item.game,
            show_session_id=show_session_id,
        )
        db.add(sale)
        db.flush()
        sale_ids.append(sale.id)

        # Outbound truth: observation claim + sell event share the Sale
        # transaction; an arbitration loss rolls back to its savepoint so
        # the loser writes no event and no second decrement of truth state.
        claimed = out.claim_observation(
            db,
            shop_id=shop_id,
            channel="pos",
            channel_ref=str(sale.id),
            sku=item.sku,
            quantity_requested=finalized.quantity,
            quantity_removed=finalized.quantity,
            sale_id=sale.id,
        )
        out.write_sell_event(
            db,
            key=out.sell_key_sale(shop_id, sale.id),
            shop_id=shop_id,
            sku=item.sku,
            inventory_item_id=item.id,
            sale_id=sale.id,
            quantity_removed=finalized.quantity,
            reason=None,
            actor_clerk_user_id=None,
        )

        db.add(
            SyncOutbox(
                shop_id=shop_id,
                action_type="sale",
                sku=item.sku,
                quantity_change=-finalized.quantity,
                sync_status="pending",
            )
        )

    return sale_ids