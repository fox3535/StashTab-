"""Show price capture — ported from partner web_checkout_module.py."""

from __future__ import annotations

import math
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import InventoryItem, ShowPriceCapture, ShowPriceCaptureItem


def capture_show_prices(
    db: Session, shop_id: str, name: str | None = None
) -> dict:
    items = (
        db.query(InventoryItem)
        .filter(InventoryItem.shop_id == shop_id, InventoryItem.stock > 0)
        .all()
    )
    if not items:
        return {"success": False, "message": "No in-stock items to capture"}

    capture_name = name or f"Show Capture - {datetime.now(timezone.utc).strftime('%b %d, %Y')}"
    capture = ShowPriceCapture(
        shop_id=shop_id,
        name=capture_name,
        item_count=len(items),
        total_value=0.0,
    )
    db.add(capture)
    db.flush()

    total_val = 0.0
    for item in items:
        rounded = float(math.ceil(float(item.price or 0.0)))
        item.sticker_price = rounded
        total_val += rounded * int(item.stock or 0)
        db.add(
            ShowPriceCaptureItem(
                shop_id=shop_id,
                capture_id=capture.id,
                sku=item.sku,
                sticker_price=rounded,
            )
        )

    capture.total_value = total_val
    db.commit()
    return {
        "success": True,
        "message": f"Captured {len(items)} items — total sticker value ${total_val:.2f}",
        "capture_id": capture.id,
        "item_count": len(items),
        "total_value": total_val,
    }
