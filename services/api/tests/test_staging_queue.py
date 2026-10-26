"""Contract tests for the read-only staging queue (GET /admin/staging).

Pins what the Staging Queue screen (slice-15) relies on:
- newest rows first, at most 100, no total;
- one shop never sees another shop's staged items;
- exact response keys, including the slice-15 additive read-only fields
  condition / variant / card_type / needs_review, and never cost_basis;
- the GET writes nothing;
- intake merges identical identities (same condition) into one row with a
  summed quantity, while a different condition stays a separate row.

All rows are synthetic fixtures on in-memory SQLite.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.deps import ShopContext
from app.logic.intake import add_to_staging
from app.models import Base, Shop, StagingItem
from app.routers.admin import list_staging

EXPECTED_KEYS = {
    "id", "name", "sku", "market_price", "suggested_price", "image_url",
    "quantity", "set_name", "sequence_number",
    "condition", "variant", "card_type", "needs_review",
}


@pytest.fixture(autouse=True)
def _isolate_barcode_dir(tmp_path, monkeypatch):
    """add_to_staging writes a barcode PNG; keep it out of app/static."""
    from app.logic import labels

    monkeypatch.setattr(labels, "BARCODE_DIR", tmp_path / "barcodes")


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    session.add(Shop(id="shop-a", name="A", slug="a"))
    session.add(Shop(id="shop-b", name="B", slug="b"))
    session.commit()
    yield session
    session.close()


def _staged(shop_id, sku, **extra):
    fields = dict(
        shop_id=shop_id, sku=sku, name=f"FIXTURE {sku}", market_price=10.0,
        suggested_price=12.0, quantity=1, set_name="FIXTURE Set", sequence_number="1",
        condition="Near Mint", variant="Standard", card_type="Single",
    )
    fields.update(extra)
    return StagingItem(**fields)


def _queue(db, shop_id="shop-a"):
    return list_staging(ctx=ShopContext(shop_id=shop_id), db=db)


def test_exact_keys_include_condition_and_never_cost_basis(db):
    db.add(_staged("shop-a", "K-1", condition="Lightly Played", variant="Reverse Holo",
                   needs_review=True, cost_basis=7.0, image_path="/static/scraped_thumbnails/K-1.png"))
    db.commit()

    body = _queue(db)
    assert set(body) == {"items"}
    row = body["items"][0]
    assert set(row) == EXPECTED_KEYS
    assert "cost_basis" not in row
    assert row["condition"] == "Lightly Played"
    assert row["variant"] == "Reverse Holo"
    assert row["card_type"] == "Single"
    assert row["needs_review"] is True
    assert row["image_url"] == "/static/scraped_thumbnails/K-1.png"


def test_newest_first_and_capped_at_100(db):
    db.add_all([_staged("shop-a", f"CAP-{n:03d}") for n in range(105)])
    db.commit()

    items = _queue(db)["items"]
    assert len(items) == 100
    ids = [row["id"] for row in items]
    assert ids == sorted(ids, reverse=True)
    assert items[0]["sku"] == "CAP-104"


def test_shops_are_isolated(db):
    db.add_all([_staged("shop-a", "A-ONLY"), _staged("shop-b", "B-ONLY")])
    db.commit()

    assert [r["sku"] for r in _queue(db, "shop-a")["items"]] == ["A-ONLY"]
    assert [r["sku"] for r in _queue(db, "shop-b")["items"]] == ["B-ONLY"]


def test_get_writes_nothing(db):
    db.add(_staged("shop-a", "RO-1", quantity=3, market_price=20.0, suggested_price=25.0))
    db.commit()

    _queue(db)
    db.expire_all()
    stored = db.query(StagingItem).filter_by(sku="RO-1").one()
    assert (stored.quantity, stored.market_price, stored.suggested_price) == (3, 20.0, 25.0)
    assert db.query(StagingItem).count() == 1


def test_intake_merges_same_condition_but_not_different_condition(db):
    common = dict(name="FIXTURE Gengar", set_name="FIXTURE Set", sequence_number="157",
                  market_price=9.0)
    add_to_staging(db, "shop-a", condition="Near Mint", quantity=1, **common)
    add_to_staging(db, "shop-a", condition="Near Mint", quantity=2, **common)
    add_to_staging(db, "shop-a", condition="Lightly Played", quantity=1, **common)
    db.commit()

    rows = _queue(db)["items"]
    by_condition = {r["condition"]: r for r in rows}
    assert len(rows) == 2
    assert by_condition["Near Mint"]["quantity"] == 3
    assert by_condition["Lightly Played"]["quantity"] == 1
    # Only condition tells these two rows apart on screen.
    nm, lp = by_condition["Near Mint"], by_condition["Lightly Played"]
    assert (nm["name"], nm["set_name"], nm["sequence_number"]) == (lp["name"], lp["set_name"], lp["sequence_number"])
