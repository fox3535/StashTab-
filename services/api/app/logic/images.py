"""Local card image repository — persist artwork by SKU for offline-fast serving."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import requests
from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from app.logic.pokemon_api import PokemonAPI
from app.models import InventoryItem, StagingItem

STATIC_ROOT = Path(__file__).resolve().parents[1] / "static"
THUMB_DIR = STATIC_ROOT / "scraped_thumbnails"

# Partner Validate & Fetch Images match threshold
IMAGE_MATCH_THRESHOLD = 65


def thumbnail_relative_path(sku: str) -> str:
    return f"scraped_thumbnails/{sku}.png"


def thumbnail_public_url(sku: str) -> str:
    return f"/static/{thumbnail_relative_path(sku)}"


def clear_thumbnail(sku: str) -> None:
    path = THUMB_DIR / f"{sku}.png"
    if path.exists():
        try:
            path.unlink()
        except Exception:
            pass


def persist_card_image(sku: str, source: str | None) -> str | None:
    """
    Copy or download card artwork into static/scraped_thumbnails/{sku}.png.
    Returns public URL path (/static/...) or None on failure.
    """
    if not source:
        return None

    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    dest = THUMB_DIR / f"{sku}.png"

    try:
        # Already a local API path
        if source.startswith("/static/"):
            local = STATIC_ROOT / source.removeprefix("/static/")
            if local.exists() and local.resolve() != dest.resolve():
                dest.write_bytes(local.read_bytes())
            return thumbnail_public_url(sku) if dest.exists() else source

        # Absolute local file
        path = Path(source)
        if path.exists() and path.is_file():
            dest.write_bytes(path.read_bytes())
            return thumbnail_public_url(sku)

        # Remote URL
        parsed = urlparse(source)
        if parsed.scheme in ("http", "https"):
            resp = requests.get(source, timeout=20, headers={"User-Agent": "StashTab/1.0"})
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            return thumbnail_public_url(sku)
    except Exception:
        return None

    return None


def validate_and_fetch_images(db: Session, shop_id: str) -> dict[str, int]:
    """
    Partner SettingsFrame run_fetch_images — walk unlocked non-sealed inventory
    and staging, fuzz-match API names >= 65, persist thumbnails.
    """
    api = PokemonAPI()
    inv_items = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.shop_id == shop_id,
            InventoryItem.image_locked.is_(False),
            InventoryItem.card_type != "Sealed",
        )
        .all()
    )
    staging_items = (
        db.query(StagingItem)
        .filter(
            StagingItem.shop_id == shop_id,
            StagingItem.image_locked.is_(False),
            StagingItem.card_type != "Sealed",
        )
        .all()
    )

    fetched = 0
    rejected = 0

    def _process(item: InventoryItem | StagingItem, *, is_staging: bool) -> None:
        nonlocal fetched, rejected
        name = item.name or ""
        res = api.fetch_card_data(
            set_name=item.set_name or "",
            sequence_number=item.sequence_number or "",
            ocr_name=name,
        )

        def reject() -> None:
            nonlocal rejected
            rejected += 1
            if is_staging:
                item.image_path = ""
            else:
                item.image_url = ""
            if item.sku:
                clear_thumbnail(item.sku)

        if res and res.get("high_res_image") and res.get("clean_name"):
            score = fuzz.WRatio(name.lower(), res["clean_name"].lower())
            if score >= IMAGE_MATCH_THRESHOLD:
                public = persist_card_image(item.sku, res["high_res_image"])
                url = public or res["high_res_image"]
                if is_staging:
                    item.image_path = url
                else:
                    item.image_url = url
                fetched += 1
            else:
                reject()
        else:
            reject()

    for inv in inv_items:
        _process(inv, is_staging=False)
    for st in staging_items:
        _process(st, is_staging=True)

    if fetched or rejected:
        db.commit()

    return {
        "fetched": fetched,
        "rejected": rejected,
        "scanned": len(inv_items) + len(staging_items),
    }
