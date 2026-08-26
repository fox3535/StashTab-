"""Seed a dev shop with sample inventory for POS testing."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, init_db
from app.models import InventoryItem, Shop, SystemSettings
from app.models.base import new_uuid

SAMPLES = [
    ("CS-0001", "Charizard ex", "Obsidian Flames", 149.99, 89.99, 3, "Pokemon", 155.0),
    ("CS-0002", "Pikachu VMAX", "Vivid Voltage", 45.0, 22.0, 5, "Pokemon", None),
    ("CS-0003", "Luffy Leader", "Romance Dawn", 32.0, 18.0, 2, "One Piece", 35.0),
    ("CS-0004", "Umbreon VMAX", "Evolving Skies", 280.0, 165.0, 1, "Pokemon", 299.0),
    ("CS-0005", "Gengar ex", "Paldean Fates", 38.0, 20.0, 4, "Pokemon", None),
    ("CS-0006", "Zoro Leader", "Romance Dawn", 28.0, 15.0, 3, "One Piece", 30.0),
    ("CS-0007", "Lightning Bolt", "Alpha", 12.0, 5.0, 8, "Magic", 15.0),
    ("CS-0008", "Counterspell", "Ice Age", 8.0, 3.0, 6, "Magic", None),
    ("CS-0009", "Mew ex", "151", 52.0, 28.0, 2, "Pokemon", 55.0),
    ("CS-0010", "Nami Leader", "Awakening of the New Era", 18.0, 10.0, 4, "One Piece", None),
    ("CS-0011", "Rayquaza VMAX", "Evolving Skies", 95.0, 55.0, 1, "Pokemon", 99.0),
    ("CS-0012", "Sol Ring", "Commander Masters", 3.5, 1.5, 10, "Magic", 4.0),
    ("CS-0013", "Shanks Leader", "Awakening of the New Era", 42.0, 24.0, 2, "One Piece", 45.0),
    ("CS-0014", "Gardevoir ex", "151", 22.0, 12.0, 3, "Pokemon", None),
    ("CS-0015", "Black Lotus", "Alpha", 25000.0, 15000.0, 0, "Magic", None),
    ("CS-0016", "Ace Leader", "Romance Dawn", 35.0, 20.0, 2, "One Piece", 38.0),
    ("CS-0017", "Miraidon ex", "Scarlet & Violet", 18.0, 9.0, 5, "Pokemon", None),
    ("CS-0018", "Thoughtseize", "Theros", 15.0, 8.0, 3, "Magic", 18.0),
    ("CS-0019", "Yamato Leader", "Kingdoms of Intrigue", 55.0, 32.0, 1, "One Piece", 58.0),
    ("CS-0020", "Iono", "Paldea Evolved", 28.0, 14.0, 4, "Pokemon", 30.0),
]

# Pokemon TCG API hi-res images (partner app fetches these on intake)
IMAGE_URLS: dict[str, str] = {
    "CS-0001": "https://images.pokemontcg.io/sv3/223_hires.png",
    "CS-0002": "https://images.pokemontcg.io/swsh4/188_hires.png",
    "CS-0004": "https://images.pokemontcg.io/swsh7/215_hires.png",
    "CS-0005": "https://images.pokemontcg.io/sv4pt5/091_hires.png",
    "CS-0009": "https://images.pokemontcg.io/sv3pt5/193_hires.png",
    "CS-0011": "https://images.pokemontcg.io/swsh7/111_hires.png",
    "CS-0014": "https://images.pokemontcg.io/sv3pt5/86_hires.png",
    "CS-0017": "https://images.pokemontcg.io/sv1/81_hires.png",
    "CS-0020": "https://images.pokemontcg.io/sv2/185_hires.png",
}


def main() -> None:
    from app.config import settings

    env = (settings.parsed_app_env or "").lower()
    if env in ("staging", "production"):
        raise SystemExit("Refusing to run development seed against staging/production.")
    init_db()
    db = SessionLocal()

    shop = db.query(Shop).filter(Shop.slug == "dev-shop").first()
    if not shop:
        shop = Shop(id=new_uuid(), name="Dev Shop", slug="dev-shop")
        db.add(shop)
        db.commit()
        db.refresh(shop)
        print(f"Created shop: {shop.id}")
    else:
        print(f"Using shop: {shop.id}")

    settings = (
        db.query(SystemSettings)
        .filter(SystemSettings.shop_id == shop.id)
        .first()
    )
    if not settings:
        db.add(SystemSettings(shop_id=shop.id))

    for sku, name, set_name, price, cost, stock, game, sticker in SAMPLES:
        if stock == 0:
            continue
        existing = (
            db.query(InventoryItem)
            .filter(InventoryItem.shop_id == shop.id, InventoryItem.sku == sku)
            .first()
        )
        if existing:
            if not existing.image_url and sku in IMAGE_URLS:
                existing.image_url = IMAGE_URLS[sku]
            continue
        db.add(
            InventoryItem(
                shop_id=shop.id,
                sku=sku,
                name=name,
                set_name=set_name,
                cost=cost,
                price=price,
                sticker_price=sticker if sticker else price,
                stock=stock,
                game=game,
                sync_status="active",
                image_url=IMAGE_URLS.get(sku),
            )
        )

    db.commit()
    print("Seed complete. Set NEXT_PUBLIC_DEV_SHOP_ID=" + shop.id)
    db.close()


if __name__ == "__main__":
    main()
