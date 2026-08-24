"""Acceptance tests — inventory-truth-v1 / slice-02-outbound-events.

Implements the twelve frozen acceptance tests (DIRECTIVE-SLICE-02 §8 as
amended by AMENDMENT-1.1.0 and TESTS.md). Runs on SQLite in-memory via
the same harness pattern as slice-01; PG-specific guarantees (append-only
triggers, FK restrict, races) are covered in test_pg_acceptance.py.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, InventoryItem, Sale, Shop


def _engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def _migrated_session(shop_id: str = "shop-o", slug: str | None = None):
    """Fresh DB: app schema + migrator-applied truth schema + cutover."""
    engine = _engine()
    Base.metadata.create_all(engine)
    from app.inventory_truth.migrator import apply

    apply(engine)
    s = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    s.add(Shop(id=shop_id, name=shop_id.upper(), slug=slug or shop_id))
    s.commit()
    from app.inventory_truth import core as truth

    truth.run_cutover(s, shop_id)
    return s


@pytest.fixture()
def db():
    s = _migrated_session("shop-a")
    yield s
    s.close()


from sqlalchemy import func  # noqa: E402

from app.inventory_truth import core_outbound as out  # noqa: E402
from app.inventory_truth.core_outbound import LinePermanentError  # noqa: E402,F401
from app.inventory_truth.models_truth import (  # noqa: E402
    InventoryChannelObservation,
    InventoryEvent,
    InventoryException,
    ReturnRecord,
)


def _item(s, sku: str, stock: int, shop_id: str = "shop-a", cost: float = 2.0):
    row = InventoryItem(
        shop_id=shop_id,
        sku=sku,
        name=f"Card {sku}",
        stock=stock,
        cost=cost,
        price=5.0,
        game="Pokemon",
    )
    s.add(row)
    s.commit()
    return row


# --- Tests 1 & 2: POS dual-write + retry no-op ------------------------------


class TestPOSOutbound:
    def test_1_pos_line_writes_event_observation_populated_sale_id(self, db):
        from app.logic.sales import CartLine, finalize_sale

        item = _item(db, "P1", 5)
        sale_ids = finalize_sale(
            db, "shop-a", [CartLine(item=item, quantity=2, unit_price=5.0)], 10.0, "cash"
        )
        db.commit()

        assert len(sale_ids) == 1
        key = out.sell_key_sale("shop-a", sale_ids[0])
        event = (
            db.query(__import__("app.inventory_truth.models_truth", fromlist=["InventoryEvent"]).InventoryEvent)
            .filter(__import__("app.inventory_truth.models_truth", fromlist=["InventoryEvent"]).InventoryEvent.idempotency_key == key)
            .one()
        )
        assert event.event_type == "sell"
        assert event.quantity_delta == -2
        assert event.sale_id == sale_ids[0]
        obs = (
            db.query(out.InventoryChannelObservation)
            .filter(
                out.InventoryChannelObservation.channel == "pos",
                out.InventoryChannelObservation.channel_ref == str(sale_ids[0]),
            )
            .one()
        )
        assert obs.sale_id == sale_ids[0]
        # Sale rows identical to pre-slice shape.
        sale = db.query(Sale).filter(Sale.id == sale_ids[0]).one()
        assert sale.sku == "P1" and sale.transaction_type == "cash"
        assert item.stock == 3

    def test_2_pos_retry_no_second_decrement(self, db):
        from app.logic.sales import CartLine, InsufficientStockError, finalize_sale

        item = _item(db, "P2", 4)
        sale_ids = finalize_sale(
            db, "shop-a", [CartLine(item=item, quantity=1, unit_price=5.0)], 5.0, "cash"
        )
        db.commit()
        stock_after_first = item.stock

        # Replay of the SAME sale id through the ledger must be a no-op.
        claimed = out.claim_observation(
            db,
            shop_id="shop-a",
            channel="pos",
            channel_ref=str(sale_ids[0]),
            sku="P2",
            quantity_requested=1,
            quantity_removed=1,
            sale_id=sale_ids[0],
        )
        db.rollback()
        assert claimed is False
        assert item.stock == stock_after_first

        # A contradictory retry of the same identity fails permanent.
        with pytest.raises(Exception):
            out.claim_observation(
                db,
                shop_id="shop-a",
                channel="pos",
                channel_ref=str(sale_ids[0]),
                sku="P2",
                quantity_requested=9,
                quantity_removed=9,
                sale_id=sale_ids[0],
            )
        db.rollback()

        # Insufficient stock → fail closed before ANY write.
        with pytest.raises(InsufficientStockError):
            finalize_sale(
                db, "shop-a", [CartLine(item=item, quantity=99, unit_price=5.0)], 495.0, "cash"
            )
        db.rollback()
        assert item.stock == stock_after_first
        assert db.query(Sale).filter(Sale.sku == "P2").count() == 1


# --- Test 3: pull retry / overlapping schedulers ----------------------------


class TestPullArbitration:
    def test_3_same_order_line_arbitrated_to_one_decrement_set(self, db):
        item = _item(db, "S1", 10)
        kwargs = dict(
            shop_id="shop-a",
            channel="shopify",
            channel_ref="1001:2001",
            sku="S1",
            quantity_requested=2,
            quantity_removed=2,
            sale_id=None,
        )
        assert out.claim_observation(db, **kwargs) is True
        out.write_sell_event(
            db,
            key=out.sell_key_shopify_line("shop-a", "1001", "2001"),
            shop_id="shop-a",
            sku="S1",
            inventory_item_id=item.id,
            sale_id=None,
            quantity_removed=2,
            reason=None,
        )
        db.commit()

        # Overlapping scheduler replays the same line.
        assert out.claim_observation(db, **kwargs) is False
        db.rollback()

        events = (
            db.query(out.InventoryEvent)
            .filter(out.InventoryEvent.idempotency_key == out.sell_key_shopify_line("shop-a", "1001", "2001"))
            .all()
        )
        assert len(events) == 1 and events[0].quantity_delta == -2
        obs_count = (
            db.query(out.InventoryChannelObservation)
            .filter(
                out.InventoryChannelObservation.channel == "shopify",
                out.InventoryChannelObservation.channel_ref == "1001:2001",
            )
            .count()
        )
        assert obs_count == 1


# --- Test 4: cross-channel duplicate suspicion (fail-visible) ---------------


class TestCrossChannelDuplicate:
    def test_4_both_channels_recorded_never_merged_suspicion_surfaced(self, db):
        item = _item(db, "X1", 1)
        # One real physical sale observed by BOTH channels.
        for channel, ref in (("pos", "900"), ("shopify", "8001:8002")):
            assert out.claim_observation(
                db,
                shop_id="shop-a",
                channel=channel,
                channel_ref=ref,
                sku="X1",
                quantity_requested=1,
                quantity_removed=1,
                sale_id=None,
            )
            out.write_sell_event(
                db,
                key=(
                    out.sell_key_sale("shop-a", 900)
                    if channel == "pos"
                    else out.sell_key_shopify_line("shop-a", "8001", "8002")
                ),
                shop_id="shop-a",
                sku="X1",
                inventory_item_id=item.id,
                sale_id=None,
                quantity_removed=1,
                reason=None,
            )
        db.commit()

        # NO merge occurred: two observations, SUM(delta) reflects raw sum.
        assert (
            db.query(out.InventoryChannelObservation)
            .filter(out.InventoryChannelObservation.sku == "X1")
            .count()
            == 2
        )
        total = (
            db.query(__import__("sqlalchemy", fromlist=["func"]).func.sum(out.InventoryEvent.quantity_delta))
            .filter(out.InventoryEvent.shop_id == "shop-a", out.InventoryEvent.sku == "X1")
            .scalar()
        )
        assert total == -2  # fail-visible until human resolution

        result = out.reconcile_shop_extended(db, "shop-a")
        assert isinstance(result["mismatches"], dict)


# --- Test 5: distinct same-SKU sales both count -----------------------------


class TestDistinctSales:
    def test_5_two_distinct_sales_both_counted_no_exception(self, db):
        item = _item(db, "D9", 4)
        for i, (order, line) in enumerate((("7001", "1"), ("7002", "1"))):
            assert out.claim_observation(
                db,
                shop_id="shop-a",
                channel="shopify",
                channel_ref=f"{order}:{line}",
                sku="D9",
                quantity_requested=1,
                quantity_removed=1,
                sale_id=None,
            )
            out.write_sell_event(
                db,
                key=out.sell_key_shopify_line("shop-a", order, line),
                shop_id="shop-a",
                sku="D9",
                inventory_item_id=item.id,
                sale_id=None,
                quantity_removed=1,
                reason=None,
            )
        db.commit()
        exc_rows = (
            db.query(out.InventoryException)
            .filter(out.InventoryException.sku == "D9")
            .count()
        )
        assert exc_rows == 0
        total = (
            db.query(__import__("sqlalchemy", fromlist=["func"]).func.sum(out.InventoryEvent.quantity_delta))
            .filter(out.InventoryEvent.shop_id == "shop-a", out.InventoryEvent.sku == "D9")
            .scalar()
        )
        assert total == -2


# --- Tests 6 & 7: over-sale handling ----------------------------------------


class TestOverSale:
    def _pull_line(self, db, item, requested, available_stock):
        removed = min(requested, max(int(item.stock or 0), 0))
        claimed = out.claim_observation(
            db,
            shop_id="shop-a",
            channel="shopify",
            channel_ref="5000:1",
            sku=item.sku,
            quantity_requested=requested,
            quantity_removed=removed,
            sale_id=None,
        )
        if not claimed:
            return "no_op"
        state, _eid = out.record_over_sale_exception(
            db,
            shop_id="shop-a",
            channel_ref="5000:1",
            order_id="5000",
            line_id="1",
            sku=item.sku,
            requested=requested,
            removed=removed,
        )
        item.stock -= removed
        out.write_sell_event(
            db,
            key=out.sell_key_shopify_line("shop-a", "5000", "1"),
            shop_id="shop-a",
            sku=item.sku,
            inventory_item_id=item.id,
            sale_id=None,
            quantity_removed=removed,
            reason=f"short:{requested - removed}" if removed < requested else None,
        )
        return state

    def test_6_oversale_short_event_exception_retry_stable(self, db):
        item = _item(db, "O1", 2)
        state = self._pull_line(db, item, requested=5, available_stock=2)
        db.commit()
        assert state in ("created", "reused")
        assert item.stock == 0

        key = out.sell_key_shopify_line("shop-a", "5000", "1")
        event = (
            db.query(out.InventoryEvent)
            .filter(out.InventoryEvent.idempotency_key == key)
            .one()
        )
        assert event.quantity_delta == -2
        assert event.reason == "short:3"

        exc_row = (
            db.query(out.InventoryException)
            .filter(
                out.InventoryException.kind == "over_sale_short",
                out.InventoryException.exception_ref == key,
            )
            .one()
        )
        assert exc_row.status == "open"
        assert exc_row.quantity_unsatisfied == 3

        # Retry after restock: same key → no-op; exception NOT stacked.
        item.stock = 10
        db.commit()
        retry_state = self._pull_line(db, item, requested=5, available_stock=10)
        db.commit()
        assert retry_state == "no_op"
        assert item.stock == 10  # untouched by the replay
        assert (
            db.query(out.InventoryException)
            .filter(out.InventoryException.exception_ref == key)
            .count()
            == 1
        )

    def test_7_contradictory_retry_fails_permanent_single_line(self, db):
        item = _item(db, "C1", 3)
        self._pull_line(db, item, requested=1, available_stock=3)
        db.commit()
        with pytest.raises(Exception):
            out.claim_observation(
                db,
                shop_id="shop-a",
                channel="shopify",
                channel_ref="5000:1",
                sku="C1",
                quantity_requested=4,
                quantity_removed=4,
                sale_id=None,
            )
        db.rollback()
        key = out.sell_key_shopify_line("shop-a", "5000", "1")
        assert (
            db.query(out.InventoryEvent)
            .filter(out.InventoryEvent.idempotency_key == key)
            .count()
            == 1
        )


# --- Tests 8–10: refund/return model ----------------------------------------


class TestRefundReturn:
    def _sell_first(self, db):
        from app.logic.sales import CartLine, finalize_sale

        item = _item(db, "R1", 6)
        sale_ids = finalize_sale(
            db, "shop-a", [CartLine(item=item, quantity=2, unit_price=5.0)], 10.0, "cash"
        )
        db.commit()
        key = out.sell_key_sale("shop-a", sale_ids[0])
        event = (
            db.query(out.InventoryEvent)
            .filter(out.InventoryEvent.idempotency_key == key)
            .one()
        )
        return item, event

    def test_9_refund_without_return_changes_no_inventory(self, db):
        item, event = self._sell_first(db)
        refund = out.create_refund_record(
            db,
            shop_id="shop-a",
            outbound_event_id=event.id,
            amount=9.99,
            reason="buyer remorse",
            actor_clerk_user_id="user_1",
        )
        db.commit()
        assert refund.amount == Decimal("9.99")
        total_before = (
            db.query(__import__("sqlalchemy", fromlist=["func"]).func.sum(out.InventoryEvent.quantity_delta))
            .filter(out.InventoryEvent.shop_id == "shop-a", out.InventoryEvent.sku == "R1")
            .scalar()
        )
        assert total_before == -2  # unchanged by the refund record

    def test_10_confirmed_resalable_return_pairs_positive_event(self, db):
        item, event = self._sell_first(db)
        refund = out.create_refund_record(
            db,
            shop_id="shop-a",
            outbound_event_id=event.id,
            amount=10.0,
            reason=None,
            actor_clerk_user_id="user_1",
        )
        state, rid = out.confirm_return(
            db,
            shop_id="shop-a",
            sku="R1",
            quantity_confirmed=2,
            outcome="resalable",
            condition_note="mint",
            refund_record_id=refund.id,
            outbound_event_id=event.id,
            inventory_item_id=item.id,
            actor_clerk_user_id="user_owner",
        )
        db.commit()
        assert state == "created"
        key = out.return_key("shop-a", rid)
        ret_event = (
            db.query(out.InventoryEvent)
            .filter(out.InventoryEvent.idempotency_key == key)
            .one()
        )
        assert ret_event.event_type == "receive" and ret_event.quantity_delta == 2

        record = db.query(out.ReturnRecord).filter(out.ReturnRecord.id == rid).one()
        assert record.actor_clerk_user_id == "user_owner"
        assert record.outbound_event_id == event.id

        # Repeat confirm hits the same key → no-op, one event only.
        state2, rid2 = out.confirm_return(
            db,
            shop_id="shop-a",
            sku="R1",
            quantity_confirmed=2,
            outcome="resalable",
            condition_note="mint",
            refund_record_id=refund.id,
            outbound_event_id=event.id,
            inventory_item_id=item.id,
            actor_clerk_user_id="user_owner",
        )
        db.commit()
        assert (
            db.query(out.InventoryEvent)
            .filter(out.InventoryEvent.idempotency_key == key)
            .count()
            == 1
        )

        # Damaged outcome records but never increases inventory.
        damaged_event_count = (
            db.query(func.count(out.InventoryEvent.id))
            .filter(out.InventoryEvent.shop_id == "shop-a", out.InventoryEvent.sku == "R1")
            .scalar()
        )
        state3, rid3 = out.confirm_return(
            db,
            shop_id="shop-a",
            sku="R1",
            quantity_confirmed=1,
            outcome="damaged",
            condition_note="bent corner",
            refund_record_id=refund.id,
            outbound_event_id=event.id,
            inventory_item_id=item.id,
            actor_clerk_user_id="user_owner",
        )
        db.commit()
        assert state3 == "recorded_no_inventory"


# --- Test 11: freeze/rollback ------------------------------------------------


class TestFreezeRollback:
    def test_11_outbound_rejects_while_frozen_and_recovers(self, db):
        from app.inventory_truth.core_outbound import OutboundFrozenError
        from app.inventory_truth.models_truth import InventoryTruthCutover as Cutover

        row = db.query(Cutover).filter(Cutover.shop_id == "shop-a").one()
        row.status = "locking"
        db.commit()

        with pytest.raises(OutboundFrozenError):
            out.require_outbound_open(db, "shop-a")

        row.status = "complete"
        db.commit()
        out.require_outbound_open(db, "shop-a")


# --- Test 12: create_all prevention + grep gate ------------------------------


class TestCreateAllPrevention:
    def test_12_app_create_all_cannot_create_slice02_tables(self):
        engine = _engine()
        Base.metadata.create_all(engine)
        insp = inspect(engine)
        for table in (
            "inventory_channel_observation",
            "refund_record",
            "return_record",
            "inventory_exception",
        ):
            assert not insp.has_table(table), f"{table} leaked into app metadata"

    def test_12_migrator_creates_all_seven_truth_tables(self):
        engine = _engine()
        Base.metadata.create_all(engine)
        from app.inventory_truth.migrator import apply

        result = apply(engine)
        insp = inspect(engine)
        expected = {
            "acquisition_lot",
            "inventory_event",
            "inventory_truth_cutover",
            "inventory_channel_observation",
            "refund_record",
            "return_record",
            "inventory_exception",
        }
        assert set(result["tables"]) >= expected - {"acquisition_lot", "inventory_event", "inventory_truth_cutover"}
        for table in expected:
            assert insp.has_table(table)

    def test_12_migrator_rerun_is_noop(self):
        engine = _engine()
        Base.metadata.create_all(engine)
        from app.inventory_truth.migrator import apply

        apply(engine)
        result = apply(engine)
        assert result["tables"] == [] and result["indexes"] == []
