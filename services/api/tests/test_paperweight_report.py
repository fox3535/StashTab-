"""Contract tests for the read-only paperweight report.

Pins what the Paperweight Report screen tells vendors:
- only in-stock items added before the shop's cutoff are listed, oldest first;
- the cutoff follows the shop's paperweight_days setting (default 60);
- the item list is capped at the 100 oldest items, while the unit total is not;
- one shop never sees another shop's items;
- the route returns only units + id/sku/name/stock/price/date_added.

All rows are synthetic fixtures on in-memory SQLite.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.deps import ShopContext
from app.logic.inventory_reports import count_paperweight_units, list_paperweight_items
from app.models import Base, InventoryItem, Shop, SystemSettings
from app.routers.admin import paperweight_queue


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


def _days_ago(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def _item(shop_id: str, sku: str, *, age_days: int, stock: int = 1, price: float = 5.0):
    return InventoryItem(
        shop_id=shop_id, sku=sku, name=f"FIXTURE {sku}", stock=stock, price=price,
        date_added=_days_ago(age_days),
    )


def test_lists_only_in_stock_items_past_default_cutoff_oldest_first(db):
    db.add_all([
        _item("shop-a", "OLD-90", age_days=90, stock=2),
        _item("shop-a", "OLD-61", age_days=61, stock=3),
        _item("shop-a", "NEW-10", age_days=10, stock=5),
        _item("shop-a", "SOLD-OUT", age_days=120, stock=0),
    ])
    db.commit()

    skus = [i.sku for i in list_paperweight_items(db, "shop-a")]
    assert skus == ["OLD-90", "OLD-61"]
    assert count_paperweight_units(db, "shop-a") == 5


def test_cutoff_follows_shop_setting(db):
    db.add(SystemSettings(shop_id="shop-a", paperweight_days=30))
    db.add_all([
        _item("shop-a", "AGE-45", age_days=45),
        _item("shop-a", "AGE-20", age_days=20),
    ])
    db.commit()

    assert [i.sku for i in list_paperweight_items(db, "shop-a")] == ["AGE-45"]


def test_list_is_capped_at_100_but_units_are_not(db):
    db.add_all([_item("shop-a", f"CAP-{n:03d}", age_days=200 + n, stock=2) for n in range(105)])
    db.commit()

    items = list_paperweight_items(db, "shop-a")
    assert len(items) == 100
    # Oldest first: CAP-104 is the oldest row.
    assert items[0].sku == "CAP-104"
    assert count_paperweight_units(db, "shop-a") == 210


def test_shops_are_isolated(db):
    db.add_all([
        _item("shop-a", "A-ONLY", age_days=90),
        _item("shop-b", "B-ONLY", age_days=90, stock=7),
    ])
    db.commit()

    assert [i.sku for i in list_paperweight_items(db, "shop-a")] == ["A-ONLY"]
    assert count_paperweight_units(db, "shop-a") == 1
    assert [i.sku for i in list_paperweight_items(db, "shop-b")] == ["B-ONLY"]


def test_route_returns_only_contract_fields(db):
    db.add(_item("shop-a", "ROUTE-1", age_days=90, stock=4, price=12.5))
    db.add(_item("shop-b", "OTHER-SHOP", age_days=90))
    db.commit()

    body = paperweight_queue(ctx=ShopContext(shop_id="shop-a"), db=db)
    assert set(body) == {"units", "items"}
    assert body["units"] == 4
    assert len(body["items"]) == 1
    row = body["items"][0]
    assert set(row) == {"id", "sku", "name", "stock", "price", "date_added"}
    assert row["sku"] == "ROUTE-1"
    assert row["price"] == 12.5
    assert isinstance(row["date_added"], str)
