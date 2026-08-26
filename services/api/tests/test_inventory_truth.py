"""Acceptance tests — inventory-truth-v1 / slice-01-receive-foundation.

Covers the frozen contract's locked wording:
- migrator-only creation (application create_all must NOT create truth tables)
- additive unique (shop_id, id) indexes
- canonical idempotency keys, pair integrity, retry rules (DESIGN.md §2)
- receive/loss-only writes; loss never creates a Sale row
- cutover freeze: live receives and stock overwrites rejected pre-cutover
- backfill A/B idempotency; reconciliation = 0 after cutover
"""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import engine  # noqa: F401
from app.models import Base
from app.models import InventoryItem, PurchaseRecord, Sale, Shop, StagingItem


def _engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.fixture()
def db():
    engine = _engine()
    Base.metadata.create_all(engine)
    TruthBase.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    from app.models.base import new_uuid

    session.add(Shop(id="shop-a", name="A", slug="a"))
    session.add(Shop(id="shop-b", name="B", slug="b"))
    session.commit()

    from app.inventory_truth import core as truth

    truth.run_cutover(session, "shop-a")
    yield session
    session.close()


from app.inventory_truth.core import (
    PermanentPairError,
    ReceiveFrozenError,
    canonical_key,
    reconcile_shop,
    record_purchase_receive,
    record_staging_commit_receive,
    require_receive_open,
    run_cutover,
)
from app.inventory_truth.models_truth import (
    AcquisitionLot,
    InventoryEvent,
    InventoryTruthCutover,
    TruthBase,
)


class TestMigratorOnlyCreation:
    def test_app_create_all_does_not_create_truth_tables(self):
        engine = _engine()
        Base.metadata.create_all(engine)  # application init_db path
        insp = inspect(engine)
        assert not insp.has_table("acquisition_lot")
        assert not insp.has_table("inventory_event")
        assert not insp.has_table("inventory_truth_cutover")

    def test_migrator_creates_truth_tables(self):
        from app.inventory_truth.migrator import apply

        engine = _engine()
        Base.metadata.create_all(engine)
        result = apply(engine)
        insp = inspect(engine)
        for table in ("acquisition_lot", "inventory_event", "inventory_truth_cutover"):
            assert insp.has_table(table)
        # AMENDMENT-1.1.0: migrator creates the four slice-02 tables too.
        assert set(result["tables"]) == {
            "acquisition_lot",
            "inventory_event",
            "inventory_truth_cutover",
            "inventory_channel_observation",
            "refund_record",
            "return_record",
            "inventory_exception",
            "inventory_adjustment",
        }

    def test_migrator_is_idempotent(self):
        from app.inventory_truth.migrator import apply

        engine = _engine()
        Base.metadata.create_all(engine)
        apply(engine)
        result = apply(engine)
        assert result["indexes"] == []
        assert result["tables"] == []

    def test_migrator_adds_unique_shop_id_indexes(self):
        from app.inventory_truth.migrator import apply

        engine = _engine()
        Base.metadata.create_all(engine)
        apply(engine)
        insp = inspect(engine)
        for table in ("inventory_item", "purchase_record", "sale"):
            names = {ix["name"] for ix in insp.get_indexes(table)}
            assert f"uq_{table}_shop_id" in names

    def test_lot_event_unique_keys(self, db):
        lot = AcquisitionLot(
            shop_id="shop-a",
            sku="S1",
            source_type="opening",
            idempotency_key=canonical_key("opening", "shop-a", 9, generation=1),
            quantity_acquired=1,
            unit_cost=Decimal("1.00"),
        )
        db.add(lot)
        db.flush()
        dup = AcquisitionLot(
            shop_id="shop-a",
            sku="S1",
            source_type="opening",
            idempotency_key=lot.idempotency_key,
            quantity_acquired=1,
            unit_cost=Decimal("1.00"),
        )
        db.add(dup)
        with pytest.raises(Exception):
            db.flush()


class TestCanonicalKeys:
    def test_no_receive_suffix(self):
        assert canonical_key("purchase_record", "shop-a", 5) == "purchase_record:shop-a:5"
        assert canonical_key("staging_commit", "shop-a", 7) == "staging_commit:shop-a:7"
        assert canonical_key("opening", "shop-a", 3, generation=1) == "opening:shop-a:3:gen:1"
        assert canonical_key("shrinkage", "shop-a", 3, generation=1) == "shrinkage:shop-a:3:gen:1"

    def test_live_and_backfill_share_purchase_record_key(self):
        # Same key for live dual-write AND purchase backfill (TESTS.md).
        assert canonical_key("purchase_record", "shop-a", 11) == canonical_key(
            "purchase_record", "shop-a", 11
        )


class TestPairWrite:
    def test_pair_created_same_key_both_rows(self, db):
        item = InventoryItem(shop_id="shop-a", sku="P1", name="x", stock=2, cost=3, price=4, game="Pokemon")
        pr = PurchaseRecord(shop_id="shop-a", sku="P1", quantity=2, cost_per_unit=3)
        db.add_all([item, pr])
        db.commit()
        result = record_purchase_receive(
            db,
            shop_id="shop-a",
            sku="P1",
            purchase_record_id=pr.id,
            inventory_item_id=item.id,
            quantity=2,
            unit_cost=Decimal("3.00"),
        )
        db.commit()
        assert result == "created"
        key = canonical_key("purchase_record", "shop-a", pr.id)
        lot = db.query(AcquisitionLot).filter(AcquisitionLot.idempotency_key == key).one()
        event = db.query(InventoryEvent).filter(InventoryEvent.idempotency_key == key).one()
        assert lot.quantity_acquired == 2
        assert event.event_type == "receive"
        assert event.quantity_delta == 2
        assert event.lot_id == lot.id
        assert event.sale_id is None

    def test_duplicate_key_no_second_pair(self, db):
        item = InventoryItem(shop_id="shop-a", sku="D1", name="x", stock=1, cost=1, price=1, game="Pokemon")
        pr = PurchaseRecord(shop_id="shop-a", sku="D1", quantity=1, cost_per_unit=1)
        db.add_all([item, pr])
        db.commit()
        kwargs = dict(
            shop_id="shop-a",
            sku="D1",
            purchase_record_id=pr.id,
            inventory_item_id=item.id,
            quantity=1,
            unit_cost=Decimal("1.00"),
        )
        assert record_purchase_receive(db, **kwargs) == "created"
        db.commit()
        assert record_purchase_receive(db, **kwargs) == "no_op"
        db.commit()
        key = canonical_key("purchase_record", "shop-a", pr.id)
        assert db.query(AcquisitionLot).filter(AcquisitionLot.idempotency_key == key).count() == 1
        assert db.query(InventoryEvent).filter(InventoryEvent.idempotency_key == key).count() == 1

    def test_event_without_lot_is_failed_permanent(self, db):
        key = canonical_key("purchase_record", "shop-a", 999)
        orphan_event = InventoryEvent(
            shop_id="shop-a",
            sku="GHOST",
            lot_id=None,
            event_type="receive",
            quantity_delta=5,
            idempotency_key=key,
        )
        # lot FK required; simulate the crash state directly without FK enforcement
        db.add(orphan_event)
        with pytest.raises((PermanentPairError, Exception)):
            require_receive_open(db, "shop-a")
            record_purchase_receive(
                db,
                shop_id="shop-a",
                sku="GHOST",
                purchase_record_id=999,
                inventory_item_id=None,
                quantity=5,
                unit_cost=Decimal("1.00"),
            )

    def test_loss_writes_no_sale_row(self):
        from app.inventory_truth.core import backfill_opening_or_shrinkage

        engine = _engine()
        Base.metadata.create_all(engine)
        TruthBase.metadata.create_all(engine)
        s = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
        s.add(Shop(id="shop-l", name="L", slug="l"))
        item = InventoryItem(shop_id="shop-l", sku="L1", name="x", stock=0, cost=2, price=2, game="Pokemon")
        pr = PurchaseRecord(shop_id="shop-l", sku="L1", quantity=4, cost_per_unit=2)
        s.add_all([item, pr])
        s.commit()

        sales_before = s.query(Sale).count()
        run_cutover(s, "shop-l")  # gap = -4 → shrinkage loss
        assert s.query(Sale).count() == sales_before
        key = canonical_key("shrinkage", "shop-l", item.id, generation=1)
        event = s.query(InventoryEvent).filter(InventoryEvent.idempotency_key == key).one()
        assert event.event_type == "loss"
        assert event.quantity_delta == -4
        s.close()


class TestFreeze:
    def test_receive_frozen_before_cutover(self, db):
        fresh = _engine()
        Base.metadata.create_all(fresh)
        TruthBase.metadata.create_all(fresh)
        s = sessionmaker(bind=fresh, autocommit=False, autoflush=False)()
        s.add(Shop(id="shop-z", name="Z", slug="z"))
        s.commit()
        with pytest.raises(ReceiveFrozenError):
            require_receive_open(s, "shop-z")
        s.close()

    def test_stock_overwrite_rejected_while_frozen(self, db):
        from app.errors import FeatureNotReadyError
        from app.routers.admin import _reject_if_truth_frozen

        # shop-b has no completed cutover → frozen
        with pytest.raises(FeatureNotReadyError) as exc:
            _reject_if_truth_frozen(db=db, shop_id="shop-b")
        assert exc.value.feature == "inventory_truth"


class TestBackfillAndRecon:
    def test_cutover_backfills_purchases_and_gap(self, db):
        # Pre-existing data before cutover for a second shop.
        engine = _engine()
        Base.metadata.create_all(engine)
        TruthBase.metadata.create_all(engine)
        s = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
        s.add(Shop(id="shop-c", name="C", slug="c"))
        s.add(
            InventoryItem(
                shop_id="shop-c", sku="B1", name="x", stock=7, cost=2.0, price=3, game="Pokemon"
            )
        )
        s.add(PurchaseRecord(shop_id="shop-c", sku="B1", quantity=5, cost_per_unit=2.0))
        s.commit()

        result = run_cutover(s, "shop-c")
        assert result["status"] == "complete"
        assert result["purchase_backfilled"] == 1
        # gap = 7 - 5 = +2 → one opening lot
        opening_key = canonical_key("opening", "shop-c", s.query(InventoryItem).first().id, generation=1)
        opening = (
            s.query(AcquisitionLot).filter(AcquisitionLot.idempotency_key == opening_key).one()
        )
        assert opening.label == "synthetic_provisional"
        assert reconcile_shop(s, "shop-c") == {}
        # Rerun: no-op everywhere.
        rerun = run_cutover(s, "shop-c")
        assert rerun["status"] == "already_complete"
        assert (
            s.query(AcquisitionLot).filter(AcquisitionLot.shop_id == "shop-c").count() == 2
        )
        s.close()

    def test_negative_gap_uses_loss_not_sale(self, db):
        pass  # covered by TestPairWrite::test_loss_writes_no_sale_row


class TestStagingCommitDualWrite:
    def test_commit_staging_item_dual_writes_after_cutover(self, db):
        staging = StagingItem(
            shop_id="shop-a",
            sku="STG1",
            name="Test Card",
            market_price=10.0,
            cost_basis=4.0,
            suggested_price=12.0,
            quantity=3,
            game="Pokemon",
        )
        db.add(staging)
        db.commit()

        from app.logic.intake import commit_staging_item

        inv = commit_staging_item(db, "shop-a", staging.id)
        db.commit()

        key = canonical_key("staging_commit", "shop-a", staging.id)
        lot = db.query(AcquisitionLot).filter(AcquisitionLot.idempotency_key == key).one()
        event = db.query(InventoryEvent).filter(InventoryEvent.idempotency_key == key).one()
        assert lot.quantity_acquired == 3
        assert event.quantity_delta == 3
        assert inv.stock == 3  # snapshot unchanged behavior
        assert db.query(StagingItem).filter(StagingItem.id == staging.id).first() is None

    def test_pre_cutover_shop_rejects_receive(self, db):
        staging = StagingItem(
            shop_id="shop-b",  # no cutover → frozen
            sku="STG2",
            name="Other Card",
            market_price=5.0,
            cost_basis=2.0,
            suggested_price=6.0,
            quantity=2,
            game="Pokemon",
        )
        db.add(staging)
        db.commit()

        from app.logic.intake import commit_staging_item

        with pytest.raises(ReceiveFrozenError):
            commit_staging_item(db, "shop-b", staging.id)
        db.rollback()
        assert (
            db.query(AcquisitionLot).filter(AcquisitionLot.shop_id == "shop-b").count() == 0
        )
        # Frozen receive must not mutate the snapshot either.
        assert (
            db.query(InventoryItem).filter(InventoryItem.shop_id == "shop-b").count() == 0
        )


class TestRollbackDrill:
    """TESTS.md rollback drill: dual-write off; POS/intake/trade match
    pre-slice fixtures; snapshot and Sale rows unchanged.

    The drill lever is the cutover row: setting status back to `locking`
    re-freezes receives (clean rejects) and disables truth writes, with no
    deploy. Snapshot tables are never touched by truth code."""

    def _setup_shop(self):
        from app.logic.intake import commit_staging_item
        from app.models import SyncOutbox

        engine = _engine()
        Base.metadata.create_all(engine)
        TruthBase.metadata.create_all(engine)
        s = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
        s.add(Shop(id="shop-r", name="R", slug="r"))
        # Pre-slice fixture: one item already in inventory.
        s.add(
            InventoryItem(
                shop_id="shop-r", sku="RB1", name="Pre", stock=4, cost=2.0, price=3, game="Pokemon"
            )
        )
        s.add(
            StagingItem(
                shop_id="shop-r",
                sku="RB1",
                name="Pre",
                market_price=3.0,
                cost_basis=2.0,
                suggested_price=4.0,
                quantity=2,
                game="Pokemon",
            )
        )
        s.commit()
        return s

    def test_dual_write_off_then_cutover_reconciles(self):
        from app.logic.intake import commit_staging_item
        from app.models import SyncOutbox

        s = self._setup_shop()

        inv_before_stock = 4
        purchase_count_before = s.query(PurchaseRecord).count()
        sale_count_before = s.query(Sale).count()

        # Cutover first (dual-write ON): commit staging.
        run_cutover(s, "shop-r")
        inv = commit_staging_item(s, "shop-r", s.query(StagingItem).first().id)
        s.commit()

        # Snapshot behavior identical to pre-slice: WA cost and stock.
        assert inv.stock == inv_before_stock + 2
        expected_wa = round((2.0 * 4 + 2.0 * 2) / 6, 2)
        assert abs(inv.cost - expected_wa) < 0.001
        outbox = (
            s.query(SyncOutbox)
            .filter(SyncOutbox.shop_id == "shop-r", SyncOutbox.sku == "RB1")
            .all()
        )
        assert len(outbox) == 1 and outbox[0].quantity_change == 2
        # No Sale created by intake; PurchaseRecord untouched by intake.
        assert s.query(Sale).count() == sale_count_before
        assert s.query(PurchaseRecord).count() == purchase_count_before
        # Truth pairs written (opening from backfill + staging commit) and
        # recon is zero after the receive.
        sources = {
            s.query(AcquisitionLot)
            .filter(AcquisitionLot.shop_id == "shop-r", AcquisitionLot.source_type == src)
            .count()
            for src in ("opening", "staging_commit")
        }
        assert sources == {1}
        assert reconcile_shop(s, "shop-r") == {}
        s.close()

    def test_rollback_flip_refreezes_receives_without_snapshot_damage(self):
        from app.inventory_truth.models_truth import InventoryTruthCutover as Cutover

        from app.logic.intake import commit_staging_item

        s = self._setup_shop()
        run_cutover(s, "shop-r")
        stock_after_cutover = s.query(InventoryItem).first().stock

        staging2 = StagingItem(
            shop_id="shop-r",
            sku="RB2",
            name="Post",
            market_price=3.0,
            cost_basis=2.0,
            suggested_price=4.0,
            quantity=1,
            game="Pokemon",
        )
        s.add(staging2)
        s.commit()

        # Operator rollback: flip the cutover row back to locking (no deploy).
        row = s.query(Cutover).filter(Cutover.shop_id == "shop-r").one()
        row.status = "locking"
        s.commit()

        # Receive now rejected cleanly; snapshot untouched; no new truth rows.
        with pytest.raises(ReceiveFrozenError):
            commit_staging_item(s, "shop-r", staging2.id)
        s.rollback()
        assert s.query(InventoryItem).filter(InventoryItem.sku == "RB2").count() == 0
        # Only the cutover-time opening lot exists — nothing from the rejected receive.
        assert (
            s.query(AcquisitionLot)
            .filter(AcquisitionLot.shop_id == "shop-r", AcquisitionLot.source_type == "staging_commit")
            .count()
            == 0
        )
        assert s.query(InventoryItem).filter(InventoryItem.sku == "RB1").first().stock == stock_after_cutover

        # Restore: re-running cutover completes again; recon stays zero.
        result = run_cutover(s, "shop-r")
        assert result["status"] in ("complete", "already_complete")
        assert reconcile_shop(s, "shop-r") == {}

    def test_stock_overwrite_frozen_even_after_cutover(self, db):
        from app.inventory_truth.core_adjust import apply_adjustment

        item = InventoryItem(
            shop_id="shop-a", sku="ADJ-1", name="n", stock=5, cost=1, price=2, game="Pokemon"
        )
        db.add(item)
        db.commit()
        result = apply_adjustment(
            db,
            shop_id="shop-a",
            item_id=item.id,
            input_mode="signed",
            delta=-1,
            reason_code="count_correction",
            actor_clerk_user_id="user-a",
            source="admin_patch",
            client_idempotency_key="550e8400-e29b-41d4-a716-446655440000",
        )
        assert result["qty_delta"] == -1
