"""Trade helpers ported from Mimir logic.py."""

from __future__ import annotations

import math

from sqlalchemy.orm import Session

from app.logic.pricing import calculate_shop_listing_price
from app.models import (
    InventoryItem,
    PendingTrade,
    PurchaseRecord,
    StagingItem,
    SyncOutbox,
    SystemSettings,
)


def get_trade_rates(db: Session, shop_id: str) -> tuple[float, float]:
    settings = (
        db.query(SystemSettings)
        .filter(SystemSettings.shop_id == shop_id)
        .first()
    )
    buy_rate = settings.buy_percentage if settings else 0.70
    trade_rate = settings.trade_percentage if settings else 0.80
    return float(buy_rate), float(trade_rate)


def calculate_partial_trade(
    incoming_card_market: float,
    outgoing_card_market: float,
    buy_rate: float = 0.7,
    trade_rate: float = 0.8,
) -> float:
    """Cash difference to close a trade-in deal."""
    buy_price = incoming_card_market * buy_rate
    trade_value = outgoing_card_market * trade_rate
    return round(buy_price - trade_value, 2)


def get_or_create_pending_trade(db: Session, shop_id: str) -> PendingTrade:
    trade = (
        db.query(PendingTrade)
        .filter(
            PendingTrade.shop_id == shop_id,
            PendingTrade.status == "pending",
        )
        .first()
    )
    if trade:
        return trade
    trade = PendingTrade(shop_id=shop_id, status="pending")
    db.add(trade)
    db.flush()
    return trade


def add_placeholder_trade(
    db: Session,
    shop_id: str,
    market_value: float,
    cash_paid: float,
) -> PendingTrade:
    trade = get_or_create_pending_trade(db, shop_id)
    trade.total_market_value = round(trade.total_market_value + market_value, 2)
    trade.total_cash_paid = round(trade.total_cash_paid + cash_paid, 2)
    return trade


def list_pending_trades(db: Session, shop_id: str) -> list[PendingTrade]:
    return (
        db.query(PendingTrade)
        .filter(
            PendingTrade.shop_id == shop_id,
            PendingTrade.status == "pending",
        )
        .order_by(PendingTrade.id.desc())
        .all()
    )


def clear_pending_trades(db: Session, shop_id: str) -> None:
    (
        db.query(PendingTrade)
        .filter(
            PendingTrade.shop_id == shop_id,
            PendingTrade.status == "pending",
        )
        .delete(synchronize_session=False)
    )


def apply_trade_values_to_staging(
    db: Session,
    shop_id: str,
    pending_trade_ids: list[int],
) -> tuple[bool, str]:
    """Distribute cash paid across staging items by market weight, then promote."""
    trades = (
        db.query(PendingTrade)
        .filter(
            PendingTrade.shop_id == shop_id,
            PendingTrade.id.in_(pending_trade_ids),
            PendingTrade.status == "pending",
        )
        .all()
    )
    if not trades:
        return False, "No valid pending trades found."

    sum_cash_paid = sum(t.total_cash_paid for t in trades)
    staging_items = (
        db.query(StagingItem)
        .filter(StagingItem.shop_id == shop_id)
        .order_by(StagingItem.id.asc())
        .all()
    )
    if not staging_items:
        return False, "No items in the Staging Dock."

    total_staging_mkt = sum(
        (item.market_price or 0.0) * (item.quantity or 1) for item in staging_items
    )
    if total_staging_mkt <= 0:
        return False, "Total staging market value is zero — cannot distribute cost basis."

    success_count = 0
    error_count = 0

    for staging_item in staging_items:
        try:
            qty = staging_item.quantity or 1
            item_mkt = (staging_item.market_price or 0.0) * qty
            weight = item_mkt / total_staging_mkt
            total_item_cost = sum_cash_paid * weight
            cost_per_unit = round(total_item_cost / qty, 2)

            existing_item = (
                db.query(InventoryItem)
                .filter(
                    InventoryItem.shop_id == shop_id,
                    InventoryItem.name == staging_item.name,
                    InventoryItem.set_name == staging_item.set_name,
                    InventoryItem.sequence_number == staging_item.sequence_number,
                    InventoryItem.variant == staging_item.variant,
                    InventoryItem.condition == staging_item.condition,
                )
                .first()
            )

            shop_price = calculate_shop_listing_price(
                db,
                shop_id,
                staging_item.market_price or 0.0,
                staging_item.card_type or "Single",
            )
            new_sticker_price = staging_item.suggested_price

            if existing_item:
                total_qty = existing_item.stock + qty
                if total_qty > 0:
                    new_avg_cost = (
                        (existing_item.cost * existing_item.stock)
                        + (cost_per_unit * qty)
                    ) / total_qty
                    existing_item.cost = round(new_avg_cost, 2)
                existing_item.stock = total_qty
                existing_item.price = staging_item.market_price or existing_item.price
                existing_item.shop_listing_price = shop_price
                existing_item.sticker_price = new_sticker_price
                if not existing_item.image_url and staging_item.image_path:
                    existing_item.image_url = staging_item.image_path
                db.add(
                    SyncOutbox(
                        shop_id=shop_id,
                        action_type="stock_update",
                        sku=existing_item.sku,
                        quantity_change=qty,
                        new_price=0.0,
                        sync_status="pending",
                    )
                )
                db.add(
                    SyncOutbox(
                        shop_id=shop_id,
                        action_type="price_update",
                        sku=existing_item.sku,
                        quantity_change=0,
                        new_price=shop_price,
                        sync_status="pending",
                    )
                )
                db.add(
                    PurchaseRecord(
                        shop_id=shop_id,
                        sku=existing_item.sku,
                        quantity=qty,
                        cost_per_unit=cost_per_unit,
                    )
                )
            else:
                new_inv = InventoryItem(
                    shop_id=shop_id,
                    sku=staging_item.sku,
                    name=staging_item.name or "Unknown",
                    set_name=staging_item.set_name,
                    sequence_number=staging_item.sequence_number,
                    cost=cost_per_unit,
                    price=staging_item.market_price or 0.0,
                    shop_listing_price=shop_price,
                    sticker_price=new_sticker_price,
                    card_type=staging_item.card_type,
                    variant=staging_item.variant,
                    condition=staging_item.condition,
                    stock=qty,
                    image_url=staging_item.image_path,
                    game=staging_item.game or "Pokemon",
                    sync_status="approved",
                )
                db.add(new_inv)
                db.add(
                    PurchaseRecord(
                        shop_id=shop_id,
                        sku=new_inv.sku,
                        quantity=new_inv.stock,
                        cost_per_unit=cost_per_unit,
                    )
                )

            db.delete(staging_item)
            success_count += 1
        except Exception:
            error_count += 1

    for trade in trades:
        trade.status = "applied"

    return True, (
        f"Applied {len(trades)} trade(s) (${sum_cash_paid:.2f}) across "
        f"{success_count} staging items. Errors: {error_count}."
    )


def list_resticker_items(db: Session, shop_id: str) -> list[InventoryItem]:
    settings = (
        db.query(SystemSettings)
        .filter(SystemSettings.shop_id == shop_id)
        .first()
    )
    threshold = float(settings.resticker_threshold if settings else 2.0)

    items = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.shop_id == shop_id,
            InventoryItem.sticker_price.isnot(None),
            InventoryItem.stock > 0,
        )
        .order_by(InventoryItem.name.asc())
        .all()
    )
    return [
        item
        for item in items
        if abs(float(item.sticker_price or 0) - math.ceil(float(item.price or 0)))
        >= threshold
    ]


def mark_restickered(db: Session, shop_id: str, item_id: int) -> InventoryItem | None:
    item = (
        db.query(InventoryItem)
        .filter(InventoryItem.shop_id == shop_id, InventoryItem.id == item_id)
        .first()
    )
    if not item:
        return None
    item.sticker_price = float(math.ceil(float(item.price or 0)))
    return item


def mark_all_restickered(db: Session, shop_id: str) -> int:
    items = list_resticker_items(db, shop_id)
    for item in items:
        item.sticker_price = float(math.ceil(float(item.price or 0)))
    return len(items)
