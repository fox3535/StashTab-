"""Intake and staging — ported from partner logic.py (subset)."""

from __future__ import annotations

import secrets

from sqlalchemy.orm import Session

from app.logic.images import persist_card_image
from app.logic.labels import generate_item_barcode
from app.logic.pricing import calculate_shop_listing_price, suggested_price_for_shop
from app.models import InventoryItem, StagingItem, SyncOutbox, SystemSettings


def _new_sku(db: Session, shop_id: str) -> str:
    while True:
        sku = f"CS-{secrets.token_hex(2).upper()}"
        inv_exists = (
            db.query(InventoryItem)
            .filter(InventoryItem.shop_id == shop_id, InventoryItem.sku == sku)
            .first()
        )
        staging_exists = (
            db.query(StagingItem)
            .filter(StagingItem.shop_id == shop_id, StagingItem.sku == sku)
            .first()
        )
        if not inv_exists and not staging_exists:
            return sku


def _get_buy_rate(db: Session, shop_id: str) -> float:
    settings = (
        db.query(SystemSettings).filter(SystemSettings.shop_id == shop_id).first()
    )
    return float(settings.buy_percentage if settings else 0.70)


def _resolve_persistent_sku(
    db: Session,
    shop_id: str,
    *,
    name: str,
    set_name: str | None,
    sequence_number: str | None,
    variant: str,
    condition: str,
    card_type: str,
) -> str:
    """Reuse inventory SKU when the same card identity returns (partner persistent SKU)."""
    existing_inv = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.shop_id == shop_id,
            InventoryItem.name == name,
            InventoryItem.set_name == set_name,
            InventoryItem.sequence_number == sequence_number,
            InventoryItem.variant == variant,
            InventoryItem.condition == condition,
            InventoryItem.card_type == card_type,
        )
        .first()
    )
    if existing_inv:
        return existing_inv.sku
    return _new_sku(db, shop_id)


def add_to_staging(
    db: Session,
    shop_id: str,
    *,
    name: str,
    set_name: str | None,
    sequence_number: str | None,
    market_price: float,
    image_url: str | None = None,
    condition: str = "Near Mint",
    variant: str = "Standard",
    quantity: int = 1,
    card_type: str = "Single",
    game: str = "Pokemon",
) -> StagingItem:
    buy_rate = _get_buy_rate(db, shop_id)
    cost_basis = round(market_price * buy_rate, 2)
    is_sealed = card_type == "Sealed"
    resolved_set = set_name if not is_sealed else (set_name or name)
    resolved_seq = sequence_number if not is_sealed else None

    # Merge quantity if already in staging with same identity
    existing_staging = (
        db.query(StagingItem)
        .filter(
            StagingItem.shop_id == shop_id,
            StagingItem.name == name,
            StagingItem.set_name == resolved_set,
            StagingItem.sequence_number == resolved_seq,
            StagingItem.variant == variant,
            StagingItem.condition == condition,
            StagingItem.card_type == card_type,
        )
        .first()
    )
    if existing_staging:
        existing_staging.quantity = (existing_staging.quantity or 1) + quantity
        existing_staging.market_price = market_price
        existing_staging.cost_basis = cost_basis
        existing_staging.suggested_price = suggested_price_for_shop(
            db, shop_id, market_price
        )
        if image_url and not existing_staging.image_path:
            local = persist_card_image(existing_staging.sku, image_url)
            existing_staging.image_path = local or image_url
        db.flush()
        return existing_staging

    sku = _resolve_persistent_sku(
        db,
        shop_id,
        name=name,
        set_name=resolved_set,
        sequence_number=resolved_seq,
        variant=variant,
        condition=condition,
        card_type=card_type,
    )

    local_image = persist_card_image(sku, image_url) or image_url
    suggested = suggested_price_for_shop(db, shop_id, market_price)
    generate_item_barcode(sku, market_price=market_price, format="QR")

    item = StagingItem(
        shop_id=shop_id,
        sku=sku,
        name=name,
        set_name=resolved_set,
        sequence_number=resolved_seq,
        market_price=market_price,
        cost_basis=cost_basis,
        suggested_price=suggested,
        condition=condition,
        variant=variant,
        quantity=quantity,
        image_path=local_image,
        barcode_path=f"/static/barcodes/{sku}.png",
        card_type=card_type,
        game=game,
        needs_review=not is_sealed,
    )
    db.add(item)
    db.flush()
    return item


def commit_staging_item(db: Session, shop_id: str, staging_id: int) -> InventoryItem:
    staging = (
        db.query(StagingItem)
        .filter(StagingItem.shop_id == shop_id, StagingItem.id == staging_id)
        .first()
    )
    if not staging:
        raise ValueError("Staging item not found")

    listing_price = calculate_shop_listing_price(
        db,
        shop_id,
        staging.market_price,
        staging.card_type or "Single",
    )

    # Prefer identity merge (persistent SKU), then fall back to SKU match
    existing = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.shop_id == shop_id,
            InventoryItem.name == staging.name,
            InventoryItem.set_name == staging.set_name,
            InventoryItem.sequence_number == staging.sequence_number,
            InventoryItem.variant == staging.variant,
            InventoryItem.condition == staging.condition,
            InventoryItem.card_type == (staging.card_type or "Single"),
        )
        .first()
    )
    if not existing:
        existing = (
            db.query(InventoryItem)
            .filter(
                InventoryItem.shop_id == shop_id,
                InventoryItem.sku == staging.sku,
            )
            .first()
        )

    qty = staging.quantity or 1
    if existing:
        total_qty = existing.stock + qty
        if total_qty > 0:
            existing.cost = round(
                ((existing.cost * existing.stock) + (staging.cost_basis * qty))
                / total_qty,
                2,
            )
        existing.stock = total_qty
        existing.price = staging.market_price
        existing.sticker_price = staging.suggested_price
        existing.shop_listing_price = listing_price
        if staging.image_path and not existing.image_url:
            existing.image_url = staging.image_path
        if staging.game:
            existing.game = staging.game
        inv = existing
    else:
        inv = InventoryItem(
            shop_id=shop_id,
            sku=staging.sku,
            name=staging.name or "Unknown",
            set_name=staging.set_name,
            sequence_number=staging.sequence_number,
            cost=staging.cost_basis,
            price=staging.market_price,
            sticker_price=staging.suggested_price,
            shop_listing_price=listing_price,
            stock=qty,
            condition=staging.condition,
            variant=staging.variant,
            card_type=staging.card_type,
            image_url=staging.image_path,
            game=staging.game or "Pokemon",
            sync_status="approved",
        )
        db.add(inv)
        db.flush()

    generate_item_barcode(inv.sku, market_price=inv.price, format="QR")

    db.add(
        SyncOutbox(
            shop_id=shop_id,
            action_type="stock_update",
            sku=inv.sku,
            quantity_change=qty,
            sync_status="pending",
        )
    )
    db.delete(staging)
    return inv


def commit_all_staging(db: Session, shop_id: str) -> list[str]:
    items = (
        db.query(StagingItem)
        .filter(StagingItem.shop_id == shop_id)
        .order_by(StagingItem.id.asc())
        .all()
    )
    ids = [s.id for s in items]
    skus: list[str] = []
    for staging_id in ids:
        inv = commit_staging_item(db, shop_id, staging_id)
        skus.append(inv.sku)
    return skus
