"""Background Shopify sync — ported from Mimir core.py."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.logic.pricing import calculate_shop_listing_price
from app.logic.shopify_client import ShopifyClient
from app.models import InventoryItem, OnlinePullQueue, Sale, ShopifyCredentials, SyncOutbox


def _shopify_payload(
    db: Session,
    shop_id: str,
    inv_item: InventoryItem,
    outbox_item: SyncOutbox | None = None,
) -> dict:
    if (
        outbox_item
        and outbox_item.action_type == "price_update"
        and outbox_item.new_price
        and outbox_item.new_price > 0
    ):
        listing_price = float(outbox_item.new_price)
    else:
        listing_price = inv_item.shop_listing_price or calculate_shop_listing_price(
            db, shop_id, inv_item.price, inv_item.card_type or "Single"
        )

    quantity = (
        max(0, inv_item.stock - (inv_item.paused_stock or 0))
        if inv_item.sync_status != "paused"
        else 0
    )

    return {
        "name": inv_item.name,
        "sequence_number": inv_item.sequence_number,
        "set_name": inv_item.set_name,
        "condition": inv_item.condition,
        "market_price": inv_item.price,
        "shop_listing_price": listing_price,
        "sku": inv_item.sku,
        "quantity": quantity,
        "card_type": inv_item.card_type,
        "variant": inv_item.variant,
        "custom_image_url": inv_item.custom_image_url or inv_item.image_url,
        "game": inv_item.game,
    }


def _full_sync_inventory_item(
    shopify: ShopifyClient,
    db: Session,
    shop_id: str,
    inv_item: InventoryItem,
    outbox_item: SyncOutbox | None = None,
) -> bool:
    payload = _shopify_payload(db, shop_id, inv_item, outbox_item)
    success, _msg = shopify.create_or_update_product(payload)
    if success and inv_item.sync_status == "approved":
        inv_item.sync_status = "active"
    return success


def get_pending_sync_count(db: Session, shop_id: str) -> int:
    return (
        db.query(SyncOutbox)
        .filter(
            SyncOutbox.shop_id == shop_id,
            SyncOutbox.sync_status == "pending",
        )
        .count()
    )


def pull_shopify_orders(db: Session, shop_id: str) -> dict[str, int | list[dict]]:
    """
    Port of Mimir core._pull_shopify_orders — scoped by shop_id.
    Creates OnlinePullQueue entries, decrements stock, records online sales.
    """
    creds = (
        db.query(ShopifyCredentials)
        .filter(ShopifyCredentials.shop_id == shop_id)
        .first()
    )
    if not creds:
        return {"new_pulls": 0, "notifications": [], "message": "No Shopify credentials"}

    try:
        shopify = ShopifyClient(creds)
        orders_data = shopify.get_recent_unfulfilled_orders()
    except Exception as exc:
        return {"new_pulls": 0, "notifications": [], "message": str(exc)}

    orders = orders_data.get("orders", [])
    new_pulls = 0
    notifications: list[dict] = []

    for order in orders:
        order_id = str(order.get("id"))
        existing_order = (
            db.query(OnlinePullQueue)
            .filter(
                OnlinePullQueue.shop_id == shop_id,
                OnlinePullQueue.order_id == order_id,
            )
            .first()
        )
        if existing_order:
            continue

        for line in order.get("line_items", []):
            sku = (line.get("sku") or "").upper()
            if not sku:
                continue
            quantity = int(line.get("quantity", 1))
            price = float(line.get("price", 0.0))

            inv_item = (
                db.query(InventoryItem)
                .filter(
                    InventoryItem.shop_id == shop_id,
                    InventoryItem.sku == sku,
                )
                .first()
            )
            if not inv_item:
                continue

            if inv_item.stock >= quantity:
                inv_item.stock -= quantity
            else:
                inv_item.stock = 0

            # Partner core.py — auto-pause when available stock hits 0
            available_qty = inv_item.stock - (inv_item.paused_stock or 0)
            if available_qty <= 0 and inv_item.sync_status == "active":
                inv_item.sync_status = "paused"

            cost = float(inv_item.cost or 0.0)
            profit = price - cost

            db.add(
                Sale(
                    shop_id=shop_id,
                    item_name=inv_item.name,
                    sku=sku,
                    sold_price=price,
                    profit=profit,
                    transaction_type="online",
                    net_revenue=price,
                    game=inv_item.game,
                )
            )
            db.add(
                OnlinePullQueue(
                    shop_id=shop_id,
                    order_id=order_id,
                    sku=sku,
                    status="pending_pull",
                )
            )
            notifications.append(
                {
                    "type": "online_sale",
                    "card_name": inv_item.name,
                    "sku": sku,
                    "order_id": order_id,
                    "set_name": inv_item.set_name,
                }
            )
            new_pulls += 1

    if new_pulls:
        db.commit()

    return {
        "new_pulls": new_pulls,
        "notifications": notifications,
        "message": f"Pulled {new_pulls} new items",
    }


def get_recent_online_notifications(
    db: Session, shop_id: str, minutes: int = 10
) -> list[dict]:
    """Recent online pulls for POS toast polling."""
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    pulls = (
        db.query(OnlinePullQueue)
        .filter(
            OnlinePullQueue.shop_id == shop_id,
            OnlinePullQueue.status == "pending_pull",
            OnlinePullQueue.timestamp >= since,
        )
        .order_by(OnlinePullQueue.timestamp.desc())
        .limit(20)
        .all()
    )
    results: list[dict] = []
    for pull in pulls:
        inv = (
            db.query(InventoryItem)
            .filter(
                InventoryItem.shop_id == shop_id,
                InventoryItem.sku == pull.sku,
            )
            .first()
        )
        results.append(
            {
                "id": pull.id,
                "type": "online_sale",
                "card_name": inv.name if inv else pull.sku,
                "sku": pull.sku,
                "order_id": pull.order_id,
                "timestamp": pull.timestamp.isoformat() if pull.timestamp else None,
            }
        )
    return results


def process_sync_outbox(db: Session, shop_id: str) -> dict[str, int | str]:
    creds = (
        db.query(ShopifyCredentials)
        .filter(ShopifyCredentials.shop_id == shop_id)
        .first()
    )
    if not creds:
        return {"synced": 0, "failed": 0, "message": "No Shopify credentials configured"}

    try:
        shopify = ShopifyClient(creds)
    except Exception as exc:
        return {"synced": 0, "failed": 0, "message": f"Shopify client error: {exc}"}

    outbox_items = (
        db.query(SyncOutbox)
        .filter(
            SyncOutbox.shop_id == shop_id,
            SyncOutbox.sync_status == "pending",
        )
        .order_by(SyncOutbox.id.asc())
        .all()
    )
    approved_items = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.shop_id == shop_id,
            InventoryItem.sync_status == "approved",
        )
        .all()
    )

    synced = 0
    failed = 0
    synced_product_skus: set[str] = set()

    for item in outbox_items:
        time.sleep(0.5)
        if item.action_type == "sale":
            success, _msg = shopify.adjust_inventory(item.sku, item.quantity_change)
            if success:
                item.sync_status = "synced"
                synced += 1
            else:
                failed += 1
            continue

        if item.action_type in ("price_update", "stock_update"):
            inv_item = (
                db.query(InventoryItem)
                .filter(
                    InventoryItem.shop_id == shop_id,
                    InventoryItem.sku == item.sku,
                )
                .first()
            )
            if not inv_item:
                item.sync_status = "synced"
                synced += 1
                continue

            if item.sku in synced_product_skus:
                item.sync_status = "synced"
                if inv_item.sync_status == "approved":
                    inv_item.sync_status = "active"
                synced += 1
                continue

            if _full_sync_inventory_item(shopify, db, shop_id, inv_item, item):
                item.sync_status = "synced"
                synced_product_skus.add(item.sku)
                synced += 1
            else:
                failed += 1

    for inv_item in approved_items:
        if inv_item.sync_status == "active" or inv_item.sku in synced_product_skus:
            continue
        time.sleep(0.5)
        if _full_sync_inventory_item(shopify, db, shop_id, inv_item):
            synced_product_skus.add(inv_item.sku)
            synced += 1
        else:
            failed += 1

    db.commit()
    return {
        "synced": synced,
        "failed": failed,
        "message": f"Processed {synced + failed} items",
    }


def run_full_sync(db: Session, shop_id: str) -> dict:
    """Pull orders then process outbox."""
    pull_result = pull_shopify_orders(db, shop_id)
    outbox_result = process_sync_outbox(db, shop_id)
    return {
        "pull": pull_result,
        "outbox": outbox_result,
    }
