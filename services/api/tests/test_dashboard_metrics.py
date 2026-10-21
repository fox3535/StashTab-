"""Contract tests for GET /admin/dashboard (dashboard_kpis).

Pins every field's meaning before the dashboard renders any of them
(slice-14 plan §2.1), including fields the UI deliberately does not show:
- inventory_count: inventory rows (SKUs) with stock > 0, not units;
- inventory_value: sum of price x stock over all of the shop's rows;
- staging_count: staging rows;
- pending_sync: sync_outbox rows with status 'pending';
- total_revenue / sale_count: all-time sums (no date filter), where a
  trade-paid sale contributes net_revenue 0;
- paperweight_units: same number as the paperweight report;
- every figure is scoped to the caller's shop.

All rows are synthetic fixtures on in-memory SQLite.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.deps import ShopContext
from app.logic.pricing import calculate_net_revenue
from app.models import Base, InventoryItem, Sale, Shop, StagingItem, SyncOutbox
from app.routers.admin import dashboard_kpis, paperweight_queue

EXPECTED_KEYS = {
    "inventory_count",
    "inventory_value",
    "staging_count",
    "pending_sync",
    "total_revenue",
    "sale_count",
    "paperweight_units",
}


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


def _item(shop_id, sku, *, price, stock, age_days=1):
    return InventoryItem(
        shop_id=shop_id, sku=sku, name=f"FIXTURE {sku}", price=price, stock=stock,
        date_added=_days_ago(age_days),
    )


def _kpis(db, shop_id="shop-a"):
    return dashboard_kpis(ctx=ShopContext(shop_id=shop_id), db=db)


def test_empty_shop_returns_real_zeros_and_exact_keys(db):
    body = _kpis(db)
    assert set(body) == EXPECTED_KEYS
    assert body == {
        "inventory_count": 0,
        "inventory_value": 0.0,
        "staging_count": 0,
        "pending_sync": 0,
        "total_revenue": 0.0,
        "sale_count": 0,
        "paperweight_units": 0,
    }


def test_inventory_count_is_skus_with_stock_not_units(db):
    db.add_all([
        _item("shop-a", "MANY", price=1.0, stock=10),
        _item("shop-a", "ONE", price=1.0, stock=1),
        _item("shop-a", "NONE", price=1.0, stock=0),
    ])
    db.commit()

    assert _kpis(db)["inventory_count"] == 2


def test_inventory_value_is_sell_price_times_stock(db):
    db.add_all([
        _item("shop-a", "V1", price=12.50, stock=2),   # 25.00
        _item("shop-a", "V2", price=3.00, stock=5),    # 15.00
        _item("shop-a", "V0", price=99.00, stock=0),   # 0
    ])
    db.commit()

    assert _kpis(db)["inventory_value"] == pytest.approx(40.0)


def test_paperweight_units_match_the_report(db):
    db.add_all([
        _item("shop-a", "OLD", price=5.0, stock=3, age_days=90),
        _item("shop-a", "NEW", price=5.0, stock=7, age_days=5),
    ])
    db.commit()

    report = paperweight_queue(ctx=ShopContext(shop_id="shop-a"), db=db)
    assert _kpis(db)["paperweight_units"] == report["units"] == 3


def test_staging_and_pending_sync_counts(db):
    db.add_all([
        StagingItem(shop_id="shop-a", sku="STG-1", name="FIXTURE staging"),
        StagingItem(shop_id="shop-a", sku="STG-2", name="FIXTURE staging"),
        SyncOutbox(shop_id="shop-a", sku="SYNC-1", action_type="update", quantity_change=0, sync_status="pending"),
        SyncOutbox(shop_id="shop-a", sku="SYNC-2", action_type="update", quantity_change=0, sync_status="synced"),
    ])
    db.commit()

    body = _kpis(db)
    assert body["staging_count"] == 2
    assert body["pending_sync"] == 1


def test_revenue_and_sale_count_are_all_time_and_trade_sales_add_zero(db):
    _fees, _deduction, trade_net = calculate_net_revenue(30.0, "trade")
    assert trade_net == 0.0
    db.add_all([
        Sale(shop_id="shop-a", sku="S-CASH", sold_price=20.0, net_revenue=20.0,
             timestamp=_days_ago(400)),
        Sale(shop_id="shop-a", sku="S-TRADE", sold_price=30.0, net_revenue=trade_net,
             timestamp=_days_ago(1)),
    ])
    db.commit()

    body = _kpis(db)
    assert body["sale_count"] == 2
    assert body["total_revenue"] == pytest.approx(20.0)


def test_every_figure_is_shop_isolated(db):
    db.add_all([
        _item("shop-b", "B-ITEM", price=100.0, stock=4, age_days=120),
        StagingItem(shop_id="shop-b", sku="B-STG", name="FIXTURE"),
        SyncOutbox(shop_id="shop-b", sku="B-SYNC", action_type="update", quantity_change=0, sync_status="pending"),
        Sale(shop_id="shop-b", sku="B-SALE", sold_price=50.0, net_revenue=50.0),
    ])
    db.commit()

    body = _kpis(db, "shop-a")
    assert all(body[key] == 0 for key in EXPECTED_KEYS)
    other = _kpis(db, "shop-b")
    assert other["inventory_count"] == 1
    assert other["inventory_value"] == pytest.approx(400.0)
    assert other["paperweight_units"] == 4
