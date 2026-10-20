"""Contract tests for the read-only resticker queue.

Pins what the Resticker Queue screen tells vendors:
- only in-stock items with a recorded sticker price are considered;
- an item is listed when |sticker_price - ceil(price)| >= the shop's
  resticker_threshold (default $2.00);
- results are sorted by name and are not capped;
- suggested_sticker is computed by the API as ceil(price);
- one shop never sees another shop's items;
- the GET route returns only id/sku/name/price/sticker_price/suggested_sticker
  and does not change any sticker price.

All rows are synthetic fixtures on in-memory SQLite.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.deps import ShopContext
from app.logic.trades import list_resticker_items
from app.models import Base, InventoryItem, Shop, SystemSettings
from app.routers.admin import list_resticker_queue


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


def _item(shop_id, sku, *, price, sticker, stock=1, name=None):
    return InventoryItem(
        shop_id=shop_id, sku=sku, name=name or f"FIXTURE {sku}",
        price=price, sticker_price=sticker, stock=stock,
    )


def test_default_threshold_and_filters(db):
    db.add_all([
        _item("shop-a", "DRIFT-UP", price=12.10, sticker=10.0),    # ceil 13, diff 3 -> listed
        _item("shop-a", "EXACT-2", price=8.00, sticker=10.0),      # ceil 8, diff 2 -> listed (>=)
        _item("shop-a", "SMALL", price=9.50, sticker=9.0),         # ceil 10, diff 1 -> not listed
        _item("shop-a", "NO-STICKER", price=50.0, sticker=None),   # never stickered -> not listed
        _item("shop-a", "SOLD-OUT", price=50.0, sticker=1.0, stock=0),
    ])
    db.commit()

    assert sorted(i.sku for i in list_resticker_items(db, "shop-a")) == ["DRIFT-UP", "EXACT-2"]


def test_threshold_follows_shop_setting(db):
    db.add(SystemSettings(shop_id="shop-a", resticker_threshold=5.0))
    db.add_all([
        _item("shop-a", "DIFF-3", price=13.0, sticker=10.0),
        _item("shop-a", "DIFF-6", price=16.0, sticker=10.0),
    ])
    db.commit()

    assert [i.sku for i in list_resticker_items(db, "shop-a")] == ["DIFF-6"]


def test_sorted_by_name_and_uncapped(db):
    db.add_all([
        _item("shop-a", f"Q-{n:03d}", price=20.0, sticker=1.0, name=f"Card {n:03d}")
        for n in range(150, 0, -1)
    ])
    db.commit()

    items = list_resticker_items(db, "shop-a")
    assert len(items) == 150
    assert [i.name for i in items] == sorted(i.name for i in items)


def test_shops_are_isolated(db):
    db.add_all([
        _item("shop-a", "A-ONLY", price=20.0, sticker=1.0),
        _item("shop-b", "B-ONLY", price=20.0, sticker=1.0),
    ])
    db.commit()

    assert [i.sku for i in list_resticker_items(db, "shop-a")] == ["A-ONLY"]
    assert [i.sku for i in list_resticker_items(db, "shop-b")] == ["B-ONLY"]


def test_route_returns_only_contract_fields_and_writes_nothing(db):
    db.add(_item("shop-a", "ROUTE-1", price=12.10, sticker=10.0))
    db.add(_item("shop-b", "OTHER-SHOP", price=20.0, sticker=1.0))
    db.commit()

    body = list_resticker_queue(ctx=ShopContext(shop_id="shop-a"), db=db)
    assert set(body) == {"items"}
    assert len(body["items"]) == 1
    row = body["items"][0]
    assert set(row) == {"id", "sku", "name", "price", "sticker_price", "suggested_sticker"}
    assert row["sku"] == "ROUTE-1"
    assert row["sticker_price"] == 10.0
    assert row["suggested_sticker"] == 13.0

    db.expire_all()
    stored = db.query(InventoryItem).filter(InventoryItem.sku == "ROUTE-1").one()
    assert stored.sticker_price == 10.0
