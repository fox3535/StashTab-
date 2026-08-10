"""Local card image repository — persist artwork by SKU for offline-fast serving."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import requests

STATIC_ROOT = Path(__file__).resolve().parents[1] / "static"
THUMB_DIR = STATIC_ROOT / "scraped_thumbnails"


def thumbnail_relative_path(sku: str) -> str:
    return f"scraped_thumbnails/{sku}.png"


def thumbnail_public_url(sku: str) -> str:
    return f"/static/{thumbnail_relative_path(sku)}"


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
