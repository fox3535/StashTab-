"""Backfill missing or broken card images from public TCG APIs.

Usage:
    python scripts/backfill_images.py              # only fill missing images
    python scripts/backfill_images.py --force      # re-fetch ALL images (fixes card-backs)
    python scripts/backfill_images.py --game Magic # only one game
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

from app.config import settings
from app.database import SessionLocal, init_db
from app.logic.images import persist_card_image
from app.logic.pokemon_api import PokemonAPI
from app.models import InventoryItem, Shop


# ---------------------------------------------------------------------------
# Magic: Scryfall (free, no key, 50-100ms rate limit)
# ---------------------------------------------------------------------------

def fetch_magic_image(name: str, set_name: str | None = None) -> str | None:
    """Look up card art from Scryfall by name (fuzzy) + optional set."""
    url = "https://api.scryfall.com/cards/named"
    params: dict[str, str] = {"fuzzy": name}
    if set_name:
        # Scryfall uses set codes, but sometimes set name works via full-text
        params["set"] = set_name.lower().replace(" ", "")[:4]

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, params=params)
            if resp.status_code == 404:
                # Retry without set constraint
                params.pop("set", None)
                resp = client.get(url, params=params)
            if resp.status_code != 200:
                return None
            data = resp.json()
            # Prefer png > large > normal
            images = data.get("image_uris", {})
            return images.get("png") or images.get("large") or images.get("normal")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# One Piece: optcgapi.com (free, no key, has images)
# ---------------------------------------------------------------------------

def fetch_onepiece_image(name: str, set_name: str | None = None, sku: str | None = None) -> str | None:
    """Look up One Piece card image from optcgapi.com."""
    # Extract a searchable name (strip "Leader" suffix from seed data names)
    search_name = name.replace(" Leader", "").strip()

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                "https://optcgapi.com/api/sets/filtered/",
                params={"card_name": search_name, "card_type": "Leader"},
            )
            if resp.status_code != 200:
                return None
            cards = resp.json()
            if not cards:
                # Retry without Leader filter (might be a Character card)
                resp = client.get(
                    "https://optcgapi.com/api/sets/filtered/",
                    params={"card_name": search_name},
                )
                if resp.status_code != 200:
                    return None
                cards = resp.json()

            if not cards:
                return None

            # Prefer matching set name
            if set_name:
                matches = [
                    c for c in cards
                    if set_name.lower() in c.get("set_name", "").lower()
                ]
                if matches:
                    cards = matches

            # Take first non-parallel result
            for card in cards:
                if "Parallel" not in card.get("card_name", ""):
                    return card.get("card_image")
            return cards[0].get("card_image")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Pokemon: existing PokemonAPI client
# ---------------------------------------------------------------------------

def fetch_pokemon_image(
    name: str, set_name: str | None, sequence_number: str | None
) -> str | None:
    """Look up Pokemon card art via pokemontcg.io."""
    # If we have a sequence number, use the existing structured lookup
    if sequence_number:
        api = PokemonAPI()
        result = api.fetch_card_data(
            set_name=set_name or "",
            sequence_number=sequence_number,
            card_name=name,
        )
        if result:
            return result.get("high_res_image")

    # Fallback: search by name (+ set) directly
    headers = {"User-Agent": "StashTab/1.0"}
    api_key = getattr(settings, "pokemon_tcg_api_key", "") or None
    if api_key:
        headers["X-Api-Key"] = api_key

    queries = []
    if name and set_name:
        queries.append(f'name:"{name}" set.name:"{set_name}"')
    if name:
        queries.append(f'name:"{name}"')

    try:
        with httpx.Client(timeout=10.0) as client:
            for q in queries:
                resp = client.get(
                    "https://api.pokemontcg.io/v2/cards",
                    params={"q": q, "pageSize": 5},
                    headers=headers,
                )
                if resp.status_code != 200:
                    continue
                cards = resp.json().get("data", [])
                if cards:
                    # Pick best name match
                    best = max(
                        cards,
                        key=lambda c: (c.get("name", "").lower() == name.lower()),
                    )
                    img = best.get("images", {}).get("large")
                    if img:
                        return img
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Main backfill logic
# ---------------------------------------------------------------------------

GAME_FETCHERS = {
    "Pokemon": lambda item: fetch_pokemon_image(
        item.name, item.set_name, item.sequence_number
    ),
    "Magic": lambda item: fetch_magic_image(item.name, item.set_name),
    "One Piece": lambda item: fetch_onepiece_image(item.name, item.set_name, sku=item.sku),
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill card images from TCG APIs")
    parser.add_argument("--force", action="store_true", help="Re-fetch all images, even existing ones")
    parser.add_argument("--game", type=str, default=None, help="Only backfill a specific game")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be fetched without downloading")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()

    shop = db.query(Shop).first()
    if not shop:
        print("No shop found. Run seed_dev.py first.")
        db.close()
        return

    query = db.query(InventoryItem).filter(InventoryItem.shop_id == shop.id)

    if args.game:
        query = query.filter(InventoryItem.game == args.game)

    if not args.force:
        # Only items missing an image
        query = query.filter(
            (InventoryItem.image_url.is_(None)) | (InventoryItem.image_url == "")
        )

    items = query.all()
    print(f"Found {len(items)} items to process (force={args.force}, game={args.game or 'all'})")

    success = 0
    failed = 0
    skipped = 0

    for item in items:
        game = item.game or "Pokemon"
        fetcher = GAME_FETCHERS.get(game)

        if not fetcher:
            print(f"  SKIP {item.sku} ({item.name}) — no fetcher for game '{game}'")
            skipped += 1
            continue

        print(f"  Looking up: {item.name} [{game}] ({item.sku})...", end=" ", flush=True)

        if args.dry_run:
            print("(dry-run, skipping)")
            continue

        image_url = fetcher(item)

        if not image_url:
            print("NOT FOUND")
            failed += 1
            time.sleep(0.1)  # be nice to APIs
            continue

        # Download and persist locally
        local_path = persist_card_image(item.sku, image_url)
        if local_path:
            item.image_url = local_path
            item.image_locked = True
            print(f"OK -> {local_path}")
            success += 1
        else:
            # Fall back to remote URL directly
            item.image_url = image_url
            item.image_locked = True
            print(f"OK (remote) -> {image_url[:80]}")
            success += 1

        # Rate-limit: pokemontcg free tier = ~20 req/min, scryfall = ~100ms
        time.sleep(0.15)

    db.commit()
    db.close()

    print(f"\nDone! {success} updated, {failed} not found, {skipped} skipped.")


if __name__ == "__main__":
    main()
