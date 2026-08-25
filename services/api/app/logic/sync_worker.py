"""Background Shopify sync — ported from Mimir core.py."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.logic.pricing import calculate_shop_listing_price
from app.logic.shopify_client import ShopifyClient
from app.models import InventoryItem, OnlinePullQueue, Sale, ShopifyCredentials, SyncOutbox


def publish_notifications(items: list[dict]) -> None:
    """Deliver batch alerts through the existing notification pathway.

    Kept as a separate, replaceable seam so delivery failures are isolated
    from transactional inventory truth by construction. The default
    publisher is a no-op: alerts surface in the batch result and POS toast
    polling; Web Push integration rides the preserved notification work at
    the recorded integration gate.
    """
    return None


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

    Slice-02 outbound: per-line observation arbitration, idempotent sell
    events (full and short share ONE key), over-sale exception reuse,
    vendor alerts via the existing notification pathway, auto-pause at
    zero untouched, and poison-line containment (failed_permanent skips
    only that line).
    """
    from app.inventory_truth import core as truth
    from app.inventory_truth import core_outbound as out

    status = truth.cutover_status(db, shop_id)
    if status != "complete":
        return {
            "new_pulls": 0,
            "notifications": [],
            "message": f"Shopify stock pull frozen during inventory-truth cutover (status: {status})",
        }

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
    failed_lines: list[dict] = []
    # Per-line transactions: a poisoned line rolls back only itself and can
    # never discard earlier lines' committed work (Adversarial F3b).
    committed_any = False

    for order in orders:
        order_id = str(order.get("id"))
        try:
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

            line_position = 0  # per-order counter: deterministic id-less refs
            for line in order.get("line_items", []):
                sku = (line.get("sku") or "").upper()
                if not sku:
                    continue
                quantity = int(line.get("quantity", 1))
                price = float(line.get("price", 0.0))
                # Id-less lines get an order-scoped positional ref so sibling
                # lines never collide on the arbitration key and retries are
                # stable regardless of prior failures.
                line_position += 1
                line_ref = str(line.get("id") or f"noline-{line_position}")

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

                try:
                    line_ok, line_notifications = _process_pull_line(
                        db,
                        shop_id=shop_id,
                        order_id=order_id,
                        line_ref=line_ref,
                        line=line,
                        sku=sku,
                        quantity=quantity,
                        price=price,
                        inv_item=inv_item,
                    )
                except out.LinePermanentError as exc:
                    db.rollback()
                    failed_lines.append(
                        {"order_id": order_id, "line_id": line_ref, "sku": sku, "error": str(exc)}
                    )
                    continue
                except Exception as exc:
                    # Unexpected line failure: same containment contract —
                    # roll back only this line and keep the batch alive.
                    db.rollback()
                    failed_lines.append(
                        {
                            "order_id": order_id,
                            "line_id": line_ref,
                            "sku": sku,
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
                    continue
                db.commit()
                # Publish alerts only after the line commits: a rollback can
                # never leave a phantom notification in the batch result.
                notifications.extend(line_notifications)
                committed_any = True
                if line_ok:
                    new_pulls += 1
        except Exception as exc:
            # Order-level containment: a malformed order payload can never
            # prevent later orders from processing (per-order isolation).
            db.rollback()
            failed_lines.append(
                {"order_id": order_id, "line_id": None, "sku": None,
                 "error": f"order failed: {type(exc).__name__}: {exc}"}
            )
            continue

    if not committed_any:
        db.rollback()

    if notifications:
        try:
            publish_notifications(notifications)
        except Exception as exc:
            # Alert delivery failure must never roll back or resolve the
            # committed inventory truth: the exception stays open and the
            # batch still reports what could not be delivered.
            print(f"ALERT DELIVERY FAILED ({len(notifications)} pending): {exc}")

    return {
        "new_pulls": new_pulls,
        "notifications": notifications,
        "failed_permanent_lines": failed_lines,
        "message": f"Pulled {new_pulls} new items"
        + (f"; {len(failed_lines)} permanent failures" if failed_lines else ""),
    }


def _process_pull_line(
    db: Session,
    *,
    shop_id: str,
    order_id: str,
    line_ref: str,
    line: dict,
    sku: str,
    quantity: int,
    price: float,
    inv_item: InventoryItem,
) -> tuple[bool, list[dict]]:
    """One pull line = one transaction unit. Returns (no-op flag, line
    notifications). Notifications are returned to the caller and published
    only after this line commits, so a rollback can never leave a phantom
    vendor alert. Raises LinePermanentError to fail that line permanently;
    the caller rolls back this line only and continues the batch."""
    from app.inventory_truth import core_outbound as out

    # Lock the item row before reading stock so concurrent distinct lines
    # of the same SKU serialize their decrement (no lost update); the
    # observation ledger arbitrates same-line retries. populate_existing
    # forces the locked row's CURRENT committed values into the identity
    # map (a plain re-select would return stale cached attributes).
    # with_for_update is a no-op on SQLite.
    locked_item = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.shop_id == inv_item.shop_id,
            InventoryItem.id == inv_item.id,
        )
        .with_for_update()
        .populate_existing()
        .one()
    )

    # Transactional arbitration: retry/overlap loses on the observation
    # unique constraint and writes NOTHING.
    stock_before = int(locked_item.stock or 0)
    removed = min(quantity, max(stock_before, 0))
    claimed = out.claim_observation(
        db,
        shop_id=shop_id,
        channel="shopify",
        channel_ref=f"{order_id}:{line_ref}",
        sku=sku,
        quantity_requested=quantity,
        quantity_removed=removed,
        sale_id=None,
    )
    if not claimed:
        return False, []

    line_notifications: list[dict] = []

    # Over-sale: record only what was actually removed; the shortage lives
    # in the exception register, never phantom.
    over_sale = removed < quantity
    if over_sale:
        exc_state, _exc_id = out.record_over_sale_exception(
            db,
            shop_id=shop_id,
            channel_ref=f"{order_id}:{line_ref}",
            order_id=order_id,
            line_id=line_ref,
            sku=sku,
            requested=quantity,
            removed=removed,
        )
        line_notifications.append(
            {
                "type": "over_sale_short",
                "card_name": inv_item.name,
                "sku": sku,
                "order_id": order_id,
                "set_name": inv_item.set_name,
                "requested": quantity,
                "removed": removed,
                "exception_state": exc_state,
            }
        )

    locked_item.stock = stock_before - removed

    # Partner core.py — auto-pause when available stock hits 0
    available_qty = locked_item.stock - (locked_item.paused_stock or 0)
    if available_qty <= 0 and locked_item.sync_status == "active":
        locked_item.sync_status = "paused"

    cost = float(locked_item.cost or 0.0)
    profit = price - cost

    sale = Sale(
        shop_id=shop_id,
        item_name=inv_item.name,
        sku=sku,
        sold_price=price,
        profit=profit,
        transaction_type="online",
        net_revenue=price,
        game=inv_item.game,
    )
    db.add(sale)
    db.flush()

    out.write_sell_event(
        db,
        key=out.sell_key_shopify_line(shop_id, order_id, line_ref),
        shop_id=shop_id,
        sku=sku,
        inventory_item_id=inv_item.id,
        sale_id=sale.id,
        quantity_removed=removed,
        reason=f"short:{quantity - removed}" if over_sale else None,
        actor_clerk_user_id=None,
    )

    db.add(
        OnlinePullQueue(
            shop_id=shop_id,
            order_id=order_id,
            sku=sku,
            status="pending_pull",
        )
    )
    if not over_sale:
        line_notifications.append(
            {
                "type": "online_sale",
                "card_name": inv_item.name,
                "sku": sku,
                "order_id": order_id,
                "set_name": inv_item.set_name,
            }
        )
    return True, line_notifications


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
