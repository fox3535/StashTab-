"""Shopify catalog consistency check — ported from partner core.py."""

from __future__ import annotations

import os

from sqlalchemy.orm import Session

from app.logic.pricing import calculate_shop_price
from app.logic.shopify_client import ShopifyClient
from app.models import InventoryItem, ShopifyCredentials, SyncOutbox


def verify_shopify_consistency(db: Session, shop_id: str) -> tuple[bool, str]:
    creds = (
        db.query(ShopifyCredentials)
        .filter(ShopifyCredentials.shop_id == shop_id)
        .first()
    )
    if not creds:
        return False, "No Shopify credentials configured"

    try:
        client = ShopifyClient(creds)
        shopify_variants = client.fetch_all_variants()
    except Exception as exc:
        return False, f"Failed to fetch Shopify variants: {exc}"

    if not shopify_variants:
        return False, "No variants returned from Shopify"

    local_items = (
        db.query(InventoryItem).filter(InventoryItem.shop_id == shop_id).all()
    )
    mismatches = 0

    for item in local_items:
        target_stock = item.stock if item.sync_status != "paused" else 0
        target_price = calculate_shop_price(db, shop_id, float(item.price or 0.0))
        if item.shop_listing_price != target_price:
            item.shop_listing_price = target_price

        sku = item.sku
        if sku not in shopify_variants:
            continue

        shop_var = shopify_variants[sku]
        shop_price = float(shop_var["price"])
        shop_qty = int(shop_var["inventory_quantity"])
        shop_has_images = bool(shop_var.get("has_images"))

        local_img = item.custom_image_url or item.image_url
        has_valid_img = bool(
            local_img
            and (str(local_img).startswith("http") or os.path.exists(str(local_img)))
        )

        if abs(target_price - shop_price) > 0.01 or (has_valid_img and not shop_has_images):
            db.add(
                SyncOutbox(
                    shop_id=shop_id,
                    action_type="price_update",
                    sku=sku,
                    quantity_change=0,
                    new_price=target_price,
                    sync_status="pending",
                )
            )
            mismatches += 1
        elif target_stock != shop_qty:
            db.add(
                SyncOutbox(
                    shop_id=shop_id,
                    action_type="stock_update",
                    sku=sku,
                    quantity_change=0,
                    new_price=0.0,
                    sync_status="pending",
                )
            )
            mismatches += 1

    db.commit()
    return True, f"Queued {mismatches} fixes to sync outbox"
