"""31 frozen acceptance tests for slice-03 adjustments."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, InventoryItem, Sale, Shop
from app.inventory_truth.core_adjust import (
    AdjustConflict,
    AdjustForbidden,
    AdjustFrozenError,
    AdjustRejected,
    apply_adjustment,
    apply_csv_adjustments,
    recon_by_reason,
    reverse_adjustment,
    sale_count,
)
from app.inventory_truth.models_truth import InventoryAdjustment, InventoryException


KEY1 = str(uuid.uuid4())
KEY2 = str(uuid.uuid4())
UPLOAD = str(uuid.uuid4())


def _engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def _db(shop_id="shop-a"):
    engine = _engine()
    Base.metadata.create_all(engine)
    from app.inventory_truth.migrator import apply

    apply(engine)
    s = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    s.add(Shop(id=shop_id, name=shop_id, slug=shop_id))
    s.commit()
    from app.inventory_truth import core as truth

    truth.run_cutover(s, shop_id)
    item = InventoryItem(
        shop_id=shop_id, sku="SKU-1", name="n", stock=10, cost=2.0, price=5.0, game="Pokemon"
    )
    s.add(item)
    s.commit()
    return s, item


def test_01_absolute_patch_writes_delta():
    s, item = _db()
    before_cost = item.cost
    before_sales = sale_count(s, "shop-a")
    result = apply_adjustment(
        s, shop_id="shop-a", item_id=item.id, input_mode="absolute", target=7,
        reason_code="count_correction", actor_clerk_user_id="user-a",
        source="admin_patch", client_idempotency_key=KEY1,
    )
    s.refresh(item)
    assert result["qty_before"] == 10 and result["qty_delta"] == -3 and result["qty_after"] == 7
    assert item.stock == 7 and item.cost == before_cost
    assert sale_count(s, "shop-a") == before_sales


def test_02_signed_patch_matches_absolute():
    s, item = _db()
    result = apply_adjustment(
        s, shop_id="shop-a", item_id=item.id, input_mode="signed", delta=-3,
        reason_code="count_correction", actor_clerk_user_id="user-a",
        source="admin_patch", client_idempotency_key=KEY1,
    )
    assert result["qty_before"] == 10 and result["qty_after"] == 7


def test_03_writer_never_assigns_client_absolute_directly():
    import inspect
    from app.inventory_truth import core_adjust as mod

    src = inspect.getsource(mod.apply_adjustment)
    assert "item.stock = target" not in src
    assert "item.stock = qty_after" in src


def test_04_idempotent_replay():
    s, item = _db()
    first = apply_adjustment(
        s, shop_id="shop-a", item_id=item.id, input_mode="signed", delta=-1,
        reason_code="count_correction", actor_clerk_user_id="user-a",
        source="admin_patch", client_idempotency_key=KEY1,
    )
    second = apply_adjustment(
        s, shop_id="shop-a", item_id=item.id, input_mode="signed", delta=-1,
        reason_code="count_correction", actor_clerk_user_id="user-a",
        source="admin_patch", client_idempotency_key=KEY1,
    )
    assert second["replayed"] is True
    assert second["event_id"] == first["event_id"]
    assert s.query(InventoryAdjustment).count() == 1
    assert s.query(InventoryException).filter(InventoryException.kind == "adjust_anomaly").count() <= 1


def test_05_same_key_different_payload_conflicts():
    s, item = _db()
    apply_adjustment(
        s, shop_id="shop-a", item_id=item.id, input_mode="signed", delta=-1,
        reason_code="count_correction", actor_clerk_user_id="user-a",
        source="admin_patch", client_idempotency_key=KEY1,
    )
    with pytest.raises(AdjustConflict):
        apply_adjustment(
            s, shop_id="shop-a", item_id=item.id, input_mode="signed", delta=-2,
            reason_code="count_correction", actor_clerk_user_id="user-a",
            source="admin_patch", client_idempotency_key=KEY1,
        )
    s.refresh(item)
    assert item.stock == 9


def test_06_missing_uuid_rejected():
    s, item = _db()
    with pytest.raises(AdjustRejected):
        apply_adjustment(
            s, shop_id="shop-a", item_id=item.id, input_mode="signed", delta=-1,
            reason_code="count_correction", actor_clerk_user_id="user-a",
            source="admin_patch", client_idempotency_key=None,
        )


def test_07_negative_remaining_rejected():
    s, item = _db()
    stock = item.stock
    with pytest.raises(AdjustRejected):
        apply_adjustment(
            s, shop_id="shop-a", item_id=item.id, input_mode="signed", delta=-99,
            reason_code="count_correction", actor_clerk_user_id="user-a",
            source="admin_patch", client_idempotency_key=KEY1,
        )
    s.refresh(item)
    assert item.stock == stock
    assert s.query(InventoryAdjustment).count() == 0


def test_08_loss_class_never_creates_sale():
    s, item = _db()
    sales = sale_count(s, "shop-a")
    apply_adjustment(
        s, shop_id="shop-a", item_id=item.id, input_mode="signed", delta=-2,
        reason_code="shrinkage", actor_clerk_user_id="user-a",
        source="admin_patch", client_idempotency_key=KEY1,
    )
    assert sale_count(s, "shop-a") == sales
    s.refresh(item)
    assert item.cost == 2.0


def test_09_found_is_not_a_lot():
    s, item = _db()
    result = apply_adjustment(
        s, shop_id="shop-a", item_id=item.id, input_mode="signed", delta=2,
        reason_code="found", actor_clerk_user_id="user-a",
        source="admin_patch", client_idempotency_key=KEY1,
    )
    from app.inventory_truth.models_truth import InventoryEvent

    ev = s.query(InventoryEvent).filter(InventoryEvent.id == result["event_id"]).one()
    assert ev.lot_id is None
    s.refresh(item)
    assert item.cost == 2.0


def test_10_reverse_records_both_actors():
    s, item = _db()
    first = apply_adjustment(
        s, shop_id="shop-a", item_id=item.id, input_mode="signed", delta=-2,
        reason_code="count_correction", actor_clerk_user_id="user-a",
        source="admin_patch", client_idempotency_key=KEY1,
    )
    rev = reverse_adjustment(
        s, shop_id="shop-a", original_event_id=first["event_id"],
        actor_clerk_user_id="user-b",
    )
    assert rev["qty_delta"] == 2
    assert rev["actor_clerk_user_id"] == "user-b"
    assert rev["original_actor_clerk_user_id"] == "user-a"
    s.refresh(item)
    assert item.stock == 10


def test_11_second_reverse_conflicts():
    s, item = _db()
    first = apply_adjustment(
        s, shop_id="shop-a", item_id=item.id, input_mode="signed", delta=-1,
        reason_code="count_correction", actor_clerk_user_id="user-a",
        source="admin_patch", client_idempotency_key=KEY1,
    )
    reverse_adjustment(
        s, shop_id="shop-a", original_event_id=first["event_id"],
        actor_clerk_user_id="user-b",
    )
    with pytest.raises(AdjustConflict):
        reverse_adjustment(
            s, shop_id="shop-a", original_event_id=first["event_id"],
            actor_clerk_user_id="user-b",
        )


def test_12_reverse_negative_rejected():
    s, item = _db()
    first = apply_adjustment(
        s, shop_id="shop-a", item_id=item.id, input_mode="signed", delta=5,
        reason_code="found", actor_clerk_user_id="user-a",
        source="admin_patch", client_idempotency_key=KEY1,
    )
    item.stock = 0
    s.commit()
    with pytest.raises(AdjustRejected):
        reverse_adjustment(
            s, shop_id="shop-a", original_event_id=first["event_id"],
            actor_clerk_user_id="user-b",
        )


def test_13_create_all_excludes_adjustment_table():
    engine = _engine()
    Base.metadata.create_all(engine)
    insp = inspect(engine)
    assert not insp.has_table("inventory_adjustment")


def test_14_csv_owner_only():
    s, item = _db()
    with pytest.raises(AdjustForbidden):
        apply_csv_adjustments(
            s, shop_id="shop-a", actor_clerk_user_id="staff-1", role="staff",
            upload_id=UPLOAD, rows=[{"row_identity": "SKU-1", "target": 8}],
        )


def test_15_csv_three_rows_atomic():
    s, item = _db()
    s.add(InventoryItem(shop_id="shop-a", sku="SKU-2", name="b", stock=4, cost=1, price=2, game="Pokemon"))
    s.add(InventoryItem(shop_id="shop-a", sku="SKU-3", name="c", stock=4, cost=1, price=2, game="Pokemon"))
    s.commit()
    result = apply_csv_adjustments(
        s, shop_id="shop-a", actor_clerk_user_id="owner-1", role="owner",
        upload_id=UPLOAD,
        rows=[
            {"row_identity": "SKU-1", "target": 9},
            {"row_identity": "SKU-2", "target": 3},
            {"row_identity": "SKU-3", "target": 1},
        ],
    )
    assert result["applied"] == 3


def test_16_csv_invalid_rolls_back():
    s, item = _db()
    with pytest.raises(AdjustRejected):
        apply_csv_adjustments(
            s, shop_id="shop-a", actor_clerk_user_id="owner-1", role="owner",
            upload_id=UPLOAD,
            rows=[
                {"row_identity": "SKU-1", "target": 9},
                {"row_identity": "NOPE", "target": 1},
            ],
        )
    s.refresh(item)
    assert item.stock == 10


def test_17_csv_conflicting_duplicate_sku():
    s, item = _db()
    with pytest.raises(AdjustRejected):
        apply_csv_adjustments(
            s, shop_id="shop-a", actor_clerk_user_id="owner-1", role="owner",
            upload_id=UPLOAD,
            rows=[
                {"row_identity": "SKU-1", "target": 8},
                {"row_identity": "SKU-1", "target": 3},
            ],
        )


def test_18_csv_identical_duplicate_collapses():
    s, item = _db()
    result = apply_csv_adjustments(
        s, shop_id="shop-a", actor_clerk_user_id="owner-1", role="owner",
        upload_id=UPLOAD,
        rows=[
            {"row_identity": "SKU-1", "target": 8},
            {"row_identity": "SKU-1", "target": 8},
        ],
    )
    assert result["applied"] == 1
    s.refresh(item)
    assert item.stock == 8


def test_19_csv_new_item_fails_file():
    s, item = _db()
    with pytest.raises(AdjustRejected, match="new-item"):
        apply_csv_adjustments(
            s, shop_id="shop-a", actor_clerk_user_id="owner-1", role="owner",
            upload_id=UPLOAD,
            rows=[{"row_identity": "BRAND-NEW", "target": 5}],
        )
    assert s.query(InventoryItem).filter(InventoryItem.sku == "BRAND-NEW").first() is None


def test_20_csv_replay_same_upload():
    s, item = _db()
    apply_csv_adjustments(
        s, shop_id="shop-a", actor_clerk_user_id="owner-1", role="owner",
        upload_id=UPLOAD, rows=[{"row_identity": "SKU-1", "target": 8}],
    )
    result = apply_csv_adjustments(
        s, shop_id="shop-a", actor_clerk_user_id="owner-1", role="owner",
        upload_id=UPLOAD, rows=[{"row_identity": "SKU-1", "target": 8}],
    )
    assert result["results"][0]["replayed"] is True
    s.refresh(item)
    assert item.stock == 8


def test_21_csv_new_upload_uses_live_qty():
    s, item = _db()
    apply_csv_adjustments(
        s, shop_id="shop-a", actor_clerk_user_id="owner-1", role="owner",
        upload_id=UPLOAD, rows=[{"row_identity": "SKU-1", "target": 8}],
    )
    result = apply_csv_adjustments(
        s, shop_id="shop-a", actor_clerk_user_id="owner-1", role="owner",
        upload_id=str(uuid.uuid4()), rows=[{"row_identity": "SKU-1", "target": 6}],
    )
    assert result["results"][0]["qty_before"] == 8
    s.refresh(item)
    assert item.stock == 6


def test_22_csv_cost_not_applied_via_writer():
    s, item = _db()
    cost = item.cost
    apply_csv_adjustments(
        s, shop_id="shop-a", actor_clerk_user_id="owner-1", role="owner",
        upload_id=UPLOAD, rows=[{"row_identity": "SKU-1", "target": 8}],
    )
    s.refresh(item)
    assert item.cost == cost


def test_23_header_identity_not_enough():
    s, item = _db()
    with pytest.raises(AdjustForbidden):
        apply_adjustment(
            s, shop_id="shop-a", item_id=item.id, input_mode="signed", delta=-1,
            reason_code="count_correction", actor_clerk_user_id="",
            source="admin_patch", client_idempotency_key=KEY1,
        )


def test_24_append_only_rejects_update(monkeypatch):
    s, item = _db()
    apply_adjustment(
        s, shop_id="shop-a", item_id=item.id, input_mode="signed", delta=-1,
        reason_code="count_correction", actor_clerk_user_id="user-a",
        source="admin_patch", client_idempotency_key=KEY1,
    )
    with pytest.raises(Exception):
        s.execute(text("UPDATE inventory_adjustment SET qty_delta = 99"))
        s.commit()
    s.rollback()


def test_25_recon_by_reason():
    s, item = _db()
    apply_adjustment(
        s, shop_id="shop-a", item_id=item.id, input_mode="signed", delta=-2,
        reason_code="shrinkage", actor_clerk_user_id="user-a",
        source="admin_patch", client_idempotency_key=KEY1,
    )
    recon = recon_by_reason(s, "shop-a")
    assert recon["shrinkage"] == -2


def test_26_anomaly_after_commit_no_stack():
    s, item = _db()
    item.stock = 200
    s.commit()
    apply_adjustment(
        s, shop_id="shop-a", item_id=item.id, input_mode="signed", delta=-100,
        reason_code="shrinkage", actor_clerk_user_id="user-a",
        source="admin_patch", client_idempotency_key=KEY2,
    )
    count = s.query(InventoryException).filter(InventoryException.kind == "adjust_anomaly").count()
    apply_adjustment(
        s, shop_id="shop-a", item_id=item.id, input_mode="signed", delta=-100,
        reason_code="shrinkage", actor_clerk_user_id="user-a",
        source="admin_patch", client_idempotency_key=KEY2,
    )
    assert s.query(InventoryException).filter(InventoryException.kind == "adjust_anomaly").count() == count


def test_27_frozen_shop_rejects_quantity():
    engine = _engine()
    Base.metadata.create_all(engine)
    from app.inventory_truth.migrator import apply

    apply(engine)
    s = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    s.add(Shop(id="shop-f", name="F", slug="f"))
    item = InventoryItem(shop_id="shop-f", sku="X", name="n", stock=3, cost=1, price=2, game="Pokemon")
    s.add(item)
    s.commit()
    with pytest.raises(AdjustFrozenError):
        apply_adjustment(
            s, shop_id="shop-f", item_id=item.id, input_mode="signed", delta=-1,
            reason_code="count_correction", actor_clerk_user_id="user-a",
            source="admin_patch", client_idempotency_key=KEY1,
        )


def test_28_theft_and_damage_are_adjustments_not_sales():
    s, item = _db()
    sales = sale_count(s, "shop-a")
    apply_adjustment(
        s, shop_id="shop-a", item_id=item.id, input_mode="signed", delta=-1,
        reason_code="theft", actor_clerk_user_id="user-a",
        source="admin_patch", client_idempotency_key=KEY1,
    )
    apply_adjustment(
        s, shop_id="shop-a", item_id=item.id, input_mode="signed", delta=-1,
        reason_code="damage", actor_clerk_user_id="user-a",
        source="admin_patch", client_idempotency_key=KEY2,
    )
    assert sale_count(s, "shop-a") == sales
    assert s.query(Sale).count() == 0


def test_29_zero_delta_rejected():
    s, item = _db()
    with pytest.raises(AdjustRejected):
        apply_adjustment(
            s, shop_id="shop-a", item_id=item.id, input_mode="absolute", target=10,
            reason_code="count_correction", actor_clerk_user_id="user-a",
            source="admin_patch", client_idempotency_key=KEY1,
        )


def test_30_cycle_count_variance_source():
    s, item = _db()
    result = apply_adjustment(
        s, shop_id="shop-a", item_id=item.id, input_mode="absolute", target=8,
        reason_code="cycle_count_variance", actor_clerk_user_id="user-a",
        source="cycle_count_variance", client_idempotency_key=KEY1,
    )
    assert result["source"] == "cycle_count_variance"
    assert result["qty_after"] == 8


def test_31_recon_matches_snapshot():
    s, item = _db()
    apply_adjustment(
        s, shop_id="shop-a", item_id=item.id, input_mode="signed", delta=-3,
        reason_code="count_correction", actor_clerk_user_id="user-a",
        source="admin_patch", client_idempotency_key=KEY1,
    )
    s.refresh(item)
    total = sum(recon_by_reason(s, "shop-a").values())
    opening = 10
    assert item.stock == opening + total
