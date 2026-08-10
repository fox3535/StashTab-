"""Inventory reporting helpers — paperweight / stagnant stock."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import InventoryItem, SystemSettings


def get_paperweight_days(db: Session, shop_id: str) -> int:
    settings = (
        db.query(SystemSettings).filter(SystemSettings.shop_id == shop_id).first()
    )
    return int(settings.paperweight_days if settings else 60)


def paperweight_cutoff(db: Session, shop_id: str) -> datetime:
    days = get_paperweight_days(db, shop_id)
    return datetime.now(timezone.utc) - timedelta(days=days)


def count_paperweight_units(db: Session, shop_id: str) -> int:
    cutoff = paperweight_cutoff(db, shop_id)
    total = (
        db.query(func.coalesce(func.sum(InventoryItem.stock), 0))
        .filter(
            InventoryItem.shop_id == shop_id,
            InventoryItem.stock > 0,
            InventoryItem.date_added < cutoff,
        )
        .scalar()
    )
    return int(total or 0)


def list_paperweight_items(db: Session, shop_id: str, limit: int = 100) -> list[InventoryItem]:
    cutoff = paperweight_cutoff(db, shop_id)
    return (
        db.query(InventoryItem)
        .filter(
            InventoryItem.shop_id == shop_id,
            InventoryItem.stock > 0,
            InventoryItem.date_added < cutoff,
        )
        .order_by(InventoryItem.date_added.asc())
        .limit(limit)
        .all()
    )
