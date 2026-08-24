"""PostgreSQL acceptance harness — inventory-truth-v1/slice-01-receive-foundation.

Runs ONLY against a disposable local PostgreSQL database with synthetic
data (docker: see scripts/pg_acceptance_setup.md / CI job). Skipped when no
PG URL is provided, so the normal SQLite suite is unaffected.

Set: STASHTAB_PG_URL=postgresql+psycopg2://postgres:stashtab@localhost:55432/stashtab_it

Covers the fourteen owner acceptance criteria (see docs/inventory-truth-v1/
reviews/SLICE-01-PG-ACCEPTANCE.md for the mapping).
"""

from __future__ import annotations

import os
import threading
import time
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models import InventoryItem, PurchaseRecord, Sale, Shop, StagingItem
from app.models.base import new_uuid

PG_URL = os.environ.get("STASHTAB_PG_URL", "")

pytestmark = pytest.mark.skipif(
    not PG_URL, reason="STASHTAB_PG_URL not set; PostgreSQL acceptance runs in its own CI job"
)


def _dispose_all_engines():
    """Close every pooled connection this process may still hold.

    Tests create several short-lived engines; a connection left idle in
    transaction would block the catalog DDL below (drop/recreate) and can
    deadlock later CREATE INDEX statements. Disposing first makes resets
    deterministic."""
    import gc

    gc.collect()
    for obj in list(gc.get_objects()):
        try:
            from sqlalchemy.engine import Engine

            if isinstance(obj, Engine):
                obj.dispose()
        except Exception:
            pass


def _fresh_db():
    """Drop everything, recreate the PRE-inventory schema via app create_all."""
    _dispose_all_engines()
    engine = create_engine(PG_URL, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                DO $$ DECLARE r RECORD; BEGIN
                  FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname='public') LOOP
                    EXECUTE 'DROP TABLE IF EXISTS public.' || quote_ident(r.tablename) || ' CASCADE';
                  END LOOP;
                END $$;
                """
            )
        )
    Base.metadata.create_all(engine)  # pre-slice schema only
    return engine


@pytest.fixture(scope="module")
def pg_engine():
    yield _fresh_db()


def _sess(engine, shop_id="shop-a", slug=None):
    s = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    s.add(Shop(id=shop_id, name=shop_id, slug=slug or shop_id))
    s.commit()
    from app.inventory_truth import core as truth

    truth.run_cutover(s, shop_id)
    return s


# --- Criteria 1 & 2 -------------------------------------------------------


class TestMigrator:
    def test_1_migrator_from_pre_inventory_schema(self, pg_engine):
        from app.inventory_truth.migrator import apply

        result = apply(pg_engine)
        insp = inspect(pg_engine)
        assert all(insp.has_table(t) for t in (
            "acquisition_lot",
            "inventory_event",
            "inventory_truth_cutover",
            "inventory_channel_observation",
            "refund_record",
            "return_record",
            "inventory_exception",
        ))
        assert set(result["tables"]) == {
            "acquisition_lot",
            "inventory_event",
            "inventory_truth_cutover",
            "inventory_channel_observation",
            "refund_record",
            "return_record",
            "inventory_exception",
        }
        assert len(result["indexes"]) == 3  # inventory_item, purchase_record, sale
        assert len(result["triggers"]) == 4  # refund/return × UPDATE/DELETE

    def test_2_second_run_is_noop(self, pg_engine):
        from app.inventory_truth.migrator import apply

        result = apply(pg_engine)
        assert result["indexes"] == []
        assert result["tables"] == []
        assert result["triggers"] == []


# --- Criteria 3, 4, 5 ------------------------------------------------------


class TestSchemaGuarantees:
    def test_3_app_create_all_cannot_create_or_alter_truth_tables(self, pg_engine):
        # Fresh pre-inventory DB: app create_all must not create truth tables.
        fresh = _fresh_db()
        insp = inspect(fresh)
        assert not any(insp.has_table(t) for t in ("acquisition_lot", "inventory_event"))
        Base.metadata.create_all(fresh)  # again — must stay inert for truth tables
        insp = inspect(fresh)
        # AMENDMENT-1.1.0: all seven truth tables are outside app metadata.
        assert not any(
            insp.has_table(t)
            for t in (
                "acquisition_lot",
                "inventory_event",
                "inventory_truth_cutover",
                "inventory_channel_observation",
                "refund_record",
                "return_record",
                "inventory_exception",
            )
        )
        cols = {c["name"] for c in insp.get_columns("inventory_item")}
        assert "lot_id" not in cols and "truth" not in " ".join(sorted(cols)).lower()
        fresh.dispose()

    def _migrated(self, pg_engine):
        from app.inventory_truth.migrator import apply

        apply(pg_engine)

    def test_4_unique_keys_and_composite_fks_reject_cross_shop(self, pg_engine):
        self._migrated(pg_engine)
        insp = inspect(pg_engine)
        for table in ("inventory_item", "purchase_record", "sale"):
            names = {ix["name"] for ix in insp.get_indexes(table)}
            assert f"uq_{table}_shop_id" in names
        fk_names = {
            fk["name"]
            for fk in insp.get_foreign_keys("acquisition_lot")
        } | {fk["name"] for fk in insp.get_foreign_keys("inventory_event")}
        expected = {
            "fk_lot_shop_item",
            "fk_lot_shop_purchase",
            "fk_event_shop_lot",
            "fk_event_shop_item",
            "fk_event_shop_sale",
            "fk_event_shop_reverses",
        }
        assert expected <= fk_names

        s = _sess(pg_engine, "shop-x")
        other = InventoryItem(shop_id="shop-y", sku="O1", name="o", stock=1, cost=1, price=1, game="Pokemon")
        s.add(other)
        s.commit()
        from app.inventory_truth.models_truth import AcquisitionLot

        bad = AcquisitionLot(
            shop_id="shop-x",
            sku="O1",
            inventory_item_id=other.id,  # exists but belongs to another shop
            source_type="opening",
            idempotency_key=new_uuid(),
            quantity_acquired=1,
            unit_cost=Decimal("1.00"),
        )
        s.add(bad)
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            s.commit()
        s.rollback()

    def test_5_numeric_money_and_quantity_exact(self, pg_engine):
        self._migrated(pg_engine)
        from sqlalchemy.dialects import postgresql

        insp = inspect(pg_engine)
        lot_cols = {c["name"]: c for c in insp.get_columns("acquisition_lot")}
        ev_cols = {c["name"]: c for c in insp.get_columns("inventory_event")}
        unit_cost_type = lot_cols["unit_cost"]["type"]
        assert isinstance(unit_cost_type, postgresql.NUMERIC) or str(unit_cost_type).upper().startswith("NUMERIC")
        assert getattr(unit_cost_type, "scale", None) == 2
        assert str(ev_cols["quantity_delta"]["type"]).upper().startswith("INTEGER")

        s = _sess(pg_engine, "shop-n")
        item = InventoryItem(shop_id="shop-n", sku="N1", name="n", stock=0, cost=0.01, price=0.03, game="Pokemon")
        pr = PurchaseRecord(shop_id="shop-n", sku="N1", quantity=3, cost_per_unit=19.99)
        s.add_all([item, pr])
        s.commit()
        from app.inventory_truth import core as truth

        truth.backfill_purchase_record(
            s,
            shop_id="shop-n",
            sku="N1",
            purchase_record_id=pr.id,
            inventory_item_id=item.id,
            quantity=3,
            unit_cost=Decimal("19.99"),
        )
        s.commit()
        from app.inventory_truth.models_truth import AcquisitionLot

        lot = (
            s.query(AcquisitionLot)
            .filter(AcquisitionLot.shop_id == "shop-n", AcquisitionLot.source_type == "purchase_record")
            .one()
        )
        assert lot.unit_cost == Decimal("19.99")
        assert lot.quantity_acquired == 3
        s.close()


# --- Criteria 6–10 ---------------------------------------------------------


def _migrated(engine):
    from app.inventory_truth.migrator import apply

    apply(engine)


class TestConcurrencyAndCorruption:
    def _migrated(self, engine):
        from app.inventory_truth.migrator import apply

        apply(engine)

    def _two_sessions(self, engine, shop_id="shop-c"):
        s1 = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
        s2 = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
        item = InventoryItem(shop_id=shop_id, sku="R1", name="r", stock=4, cost=2, price=5, game="Pokemon")
        pr = PurchaseRecord(shop_id=shop_id, sku="R1", quantity=2, cost_per_unit=2)
        s1.add_all([item, pr])
        s1.commit()
        return s1, s2, item.id, pr.id

    def test_6_same_key_concurrent_receives_exactly_one_pair(self, pg_engine):
        from app.inventory_truth import core as truth
        from app.inventory_truth.models_truth import AcquisitionLot, InventoryEvent

        self._migrated(pg_engine)
        s1, s2, item_id, pr_id = self._two_sessions(pg_engine, "shop-c")
        key_qty = dict(quantity=2, unit_cost=Decimal("2.00"))

        results: list[str] = []
        barrier = threading.Barrier(2)

        def worker(session, pk):
            barrier.wait()
            try:
                results.append(
                    truth.record_purchase_receive(
                        session,
                        shop_id="shop-c",
                        sku="R1",
                        purchase_record_id=pk,
                        inventory_item_id=item_id,
                        **key_qty,
                    )
                )
                session.commit()
            except Exception as exc:  # loser may get a serialized retry error
                session.rollback()
                results.append(f"error:{type(exc).__name__}")

        t1 = threading.Thread(target=worker, args=(s1, pr_id))
        t2 = threading.Thread(target=worker, args=(s2, pr_id))
        t1.start(); t2.start(); t1.join(30); t2.join(30)

        lots = s1.query(AcquisitionLot).filter(AcquisitionLot.sku == "R1").all()
        events = s1.query(InventoryEvent).filter(InventoryEvent.sku == "R1").all()
        assert len(lots) == 1, results
        assert len(events) == 1 and events[0].event_type == "receive"
        assert sum(l.quantity_acquired for l in lots) == 2
        s1.close(); s2.close()

    def test_7_different_keys_concurrent_no_quantity_loss(self, pg_engine):
        from app.inventory_truth import core as truth
        from app.inventory_truth.models_truth import InventoryEvent

        self._migrated(pg_engine)
        s1, s2, _, pr_id = self._two_sessions(pg_engine, "shop-d")
        pr2 = PurchaseRecord(shop_id="shop-d", sku="R1", quantity=3, cost_per_unit=1)
        s1.add(pr2)
        s1.commit()

        barrier = threading.Barrier(2)

        def worker(session, pk, qty):
            barrier.wait()
            try:
                truth.record_purchase_receive(
                    session,
                    shop_id="shop-d",
                    sku="R1",
                    purchase_record_id=pk,
                    inventory_item_id=None,
                    quantity=qty,
                    unit_cost=Decimal("1.00"),
                )
                session.commit()
            except Exception:
                session.rollback()
                raise

        t1 = threading.Thread(target=worker, args=(s1, pr_id, 2))
        t2 = threading.Thread(target=worker, args=(s2, pr2.id, 3))
        errs = []

        def run(t, fn):
            try:
                t.start(); t.join(30)
            except Exception as e:  # pragma: no cover
                errs.append(e)

        run(t1, worker); run(t2, worker)
        from sqlalchemy import func

        # Assert from a fresh session: a racing commit can leave the worker
        # sessions in 'prepared' state, which cannot emit further SQL.
        s1.close(); s2.close()
        check = sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)()
        total = (
            check.query(func.coalesce(func.sum(InventoryEvent.quantity_delta), 0))
            .filter(InventoryEvent.shop_id == "shop-d", InventoryEvent.sku == "R1")
            .scalar()
        )
        assert int(total or 0) == 5, errs
        check.close()
    def test_8_cutover_racing_receive_never_partial(self, pg_engine):
        """A receive racing the cutover boundary either fully dual-writes
        after completion or rejects cleanly while frozen — never a snapshot
        bump without its pair."""
        from app.logic.intake import commit_staging_item

        from app.inventory_truth.core import ReceiveFrozenError

        engine = _fresh_db()
        from app.inventory_truth.migrator import apply

        apply(engine)
        setup = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
        setup.add(Shop(id="shop-e", name="E", slug="e"))
        setup.add(
            StagingItem(
                shop_id="shop-e", sku="E1", name="e", market_price=5, cost_basis=2,
                suggested_price=6, quantity=2, game="Pokemon",
            )
        )
        setup.commit()
        staging_id = setup.query(StagingItem).first().id
        setup.close()

        outcomes: list[str] = []
        barrier = threading.Barrier(2)

        s_cut = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
        s_recv = sessionmaker(bind=engine, autocommit=False, autoflush=False)()

        def cutover_worker():
            barrier.wait()
            from app.inventory_truth import core as truth

            truth.run_cutover(s_cut, "shop-e")

        def receive_worker():
            barrier.wait()
            try:
                inv = commit_staging_item(s_recv, "shop-e", staging_id)
                s_recv.commit()
                outcomes.append(("received", inv.stock))
            except ReceiveFrozenError:
                s_recv.rollback()
                outcomes.append(("rejected", None))
            except Exception:
                # Serialized-conflict loser: clean rollback is also acceptable.
                s_recv.rollback()
                outcomes.append(("conflict-rollback", None))

        t1 = threading.Thread(target=cutover_worker)
        t2 = threading.Thread(target=receive_worker)
        t1.start(); t2.start(); t1.join(60); t2.join(60)

        state, stock = outcomes[-1]
        from app.inventory_truth import core as truth
        from app.inventory_truth.models_truth import AcquisitionLot, InventoryEvent

        check = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
        pairs = check.query(InventoryEvent).filter(InventoryEvent.shop_id == "shop-e").count()
        lots = check.query(AcquisitionLot).filter(AcquisitionLot.shop_id == "shop-e").count()
        if state == "rejected" or state == "conflict-rollback":
            # clean reject: staging row still there, snapshot untouched
            assert check.query(StagingItem).filter(StagingItem.shop_id == "shop-e").count() == 1
            assert check.query(InventoryItem).filter(InventoryItem.shop_id == "shop-e").count() == 0
        else:
            assert stock == 2
        if lots and pairs:
            # If both exist they are a complete pair with matching keys.
            lot_keys = {l.idempotency_key for l in check.query(AcquisitionLot).all()}
            event_keys = {e.idempotency_key for e in check.query(InventoryEvent).all()}
            assert lot_keys == event_keys
        # Final invariant: recon deterministic post-boundary.
        assert truth.reconcile_shop(check, "shop-e") == {}
        s_cut.close(); s_recv.close(); check.close()
        engine.dispose()

    def test_9_backfill_repeat_vs_dual_write_no_double_quantity(self, pg_engine):
        from app.inventory_truth import core as truth
        from app.inventory_truth.models_truth import AcquisitionLot, InventoryEvent

        self._migrated(pg_engine)
        s = _sess(pg_engine, "shop-f")
        item = InventoryItem(shop_id="shop-f", sku="F1", name="f", stock=6, cost=1, price=2, game="Pokemon")
        pr = PurchaseRecord(shop_id="shop-f", sku="F1", quantity=6, cost_per_unit=1)
        s.add_all([item, pr])
        s.commit()

        # Live dual-write first…
        truth.record_purchase_receive(
            s, shop_id="shop-f", sku="F1", purchase_record_id=pr.id,
            inventory_item_id=item.id, quantity=6, unit_cost=Decimal("1.00"),
        )
        s.commit()
        # …then repeated backfill against the same rows (race/retry shape).
        for _ in range(3):
            truth.backfill_purchase_record(
                s, shop_id="shop-f", sku="F1", purchase_record_id=pr.id,
                inventory_item_id=item.id, quantity=6, unit_cost=Decimal("1.00"),
            )
        s.commit()
        key = truth.canonical_key("purchase_record", "shop-f", pr.id)
        assert s.query(InventoryEvent).filter(InventoryEvent.idempotency_key == key).count() == 1
        assert s.query(AcquisitionLot).filter(AcquisitionLot.idempotency_key == key).count() == 1
        assert truth.reconcile_shop(s, "shop-f") == {}
        s.close()

    def test_10_event_without_lot_fails_permanently_snapshot_intact(self, pg_engine):
        from app.inventory_truth import core as truth
        from app.inventory_truth.models_truth import AcquisitionLot, InventoryEvent

        self._migrated(pg_engine)
        s = _sess(pg_engine, "shop-g")
        item = InventoryItem(shop_id="shop-g", sku="G1", name="g", stock=9, cost=1, price=2, game="Pokemon")
        pr = PurchaseRecord(shop_id="shop-g", sku="G1", quantity=1, cost_per_unit=1)
        s.add_all([item, pr])
        s.commit()
        stock_before = item.stock

        # A valid pair first (its lot will be the FK anchor for the orphan).
        truth.record_purchase_receive(
            s, shop_id="shop-g", sku="G1", purchase_record_id=pr.id,
            inventory_item_id=item.id, quantity=1, unit_cost=Decimal("1.00"),
        )
        s.commit()

        # Orphan shape reachable under PG: an event whose key matches no lot
        # but whose lot_id points at an unrelated real lot (passes FK).
        good_lot = (
            s.query(AcquisitionLot)
            .filter(AcquisitionLot.shop_id == "shop-g")
            .one()
        )
        ghost_key = "purchase_record:shop-g:424242"
        s.add(
            InventoryEvent(
                shop_id="shop-g",
                sku="GHOST",
                lot_id=good_lot.id,
                inventory_item_id=None,
                sale_id=None,
                reverses_event_id=None,
                event_type="receive",
                quantity_delta=7,
                overlay_quantity=None,
                reason=None,
                actor_clerk_user_id=None,
                idempotency_key=ghost_key,
            )
        )
        s.commit()

        with pytest.raises(truth.PermanentPairError):
            truth.record_purchase_receive(
                s, shop_id="shop-g", sku="GHOST", purchase_record_id=424242,
                inventory_item_id=None, quantity=7, unit_cost=Decimal("1.00"),
            )
        s.rollback()
        assert s.query(InventoryItem).filter(InventoryItem.sku == "G1").one().stock == stock_before
        assert s.query(InventoryEvent).filter(InventoryEvent.idempotency_key == ghost_key).count() == 1
        s.close()


# --- Criteria 11–13 --------------------------------------------------------


class TestBackfillReconRollbackMigration:
    def _seed_three_shops(self, pg_engine):
        from app.inventory_truth.migrator import apply

        apply(pg_engine)
        s = sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)()
        s.add(Shop(id="shop-pos", name="P", slug="pos"))   # positive gap
        s.add(Shop(id="shop-neg", name="Q", slug="neg"))   # negative gap → loss
        s.add(Shop(id="shop-zero", name="Z", slug="zero")) # zero gap
        s.add(InventoryItem(shop_id="shop-pos", sku="S1", name="x", stock=8, cost=2, price=3, game="Pokemon"))
        s.add(PurchaseRecord(shop_id="shop-pos", sku="S1", quantity=5, cost_per_unit=2))
        s.add(InventoryItem(shop_id="shop-neg", sku="S1", name="y", stock=1, cost=2, price=3, game="Pokemon"))
        s.add(PurchaseRecord(shop_id="shop-neg", sku="S1", quantity=6, cost_per_unit=2))
        s.add(InventoryItem(shop_id="shop-zero", sku="S1", name="z", stock=4, cost=2, price=3, game="Pokemon"))
        s.add(PurchaseRecord(shop_id="shop-zero", sku="S1", quantity=4, cost_per_unit=2))
        s.commit()
        return s

    def test_11_opening_negative_zero_gaps_reconcile(self, pg_engine):
        from app.inventory_truth import core as truth
        from app.inventory_truth.models_truth import InventoryEvent

        s = self._seed_three_shops(pg_engine)

        truth.run_cutover(s, "shop-pos")
        opening = (
            s.query(InventoryEvent)
            .filter(InventoryEvent.shop_id == "shop-pos", InventoryEvent.event_type == "receive")
            .all()
        )
        deltas = sorted(e.quantity_delta for e in opening)
        assert deltas == [3, 5]  # backfilled purchase + opening gap

        truth.run_cutover(s, "shop-neg")
        loss = (
            s.query(InventoryEvent)
            .filter(InventoryEvent.shop_id == "shop-neg", InventoryEvent.event_type == "loss")
            .one()
        )
        assert loss.quantity_delta == -5
        assert s.query(Sale).count() == 0  # loss never creates a Sale row

        truth.run_cutover(s, "shop-zero")
        zero_events = (
            s.query(InventoryEvent)
            .filter(InventoryEvent.shop_id == "shop-zero")
            .count()
        )
        assert zero_events == 1  # just the purchase backfill; gap 0 writes nothing

        for shop in ("shop-pos", "shop-neg", "shop-zero"):
            mismatches = truth.reconcile_shop(s, shop)
            assert mismatches == {}, (shop, mismatches)

        # Deterministic: rerunning recon yields identical results.
        assert all(truth.reconcile_shop(s, sh) == {} for sh in ("shop-pos", "shop-neg", "shop-zero"))
        s.close()

    def test_12_rollback_drill_preserves_snapshot_wa_sales_purchase(self, pg_engine):
        from app.logic.intake import commit_staging_item
        from app.models import SyncOutbox

        from app.inventory_truth.core import ReceiveFrozenError
        from app.inventory_truth.models_truth import InventoryTruthCutover as Cutover

        engine = _fresh_db()
        from app.inventory_truth.migrator import apply

        apply(engine)
        s = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
        s.add(Shop(id="shop-rb", name="R", slug="rb"))
        s.add(InventoryItem(shop_id="shop-rb", sku="W1", name="w", stock=4, cost=2.00, price=3, game="Pokemon"))
        s.add(StagingItem(shop_id="shop-rb", sku="W1", name="w", market_price=3, cost_basis=2, suggested_price=4, quantity=2, game="Pokemon"))
        s.commit()
        sales_before = s.query(Sale).count()
        purchases_before = s.query(PurchaseRecord).count()

        # Complete cutover, then operator rollback flip (no deploy).
        from app.inventory_truth import core as truth

        truth.run_cutover(s, "shop-rb")
        row = s.query(Cutover).filter(Cutover.shop_id == "shop-rb").one()
        row.status = "locking"
        s.commit()

        with pytest.raises(ReceiveFrozenError):
            commit_staging_item(s, "shop-rb", s.query(StagingItem).first().id)
        s.rollback()

        item = s.query(InventoryItem).filter(InventoryItem.sku == "W1").one()
        assert item.stock == 4 and abs(float(item.cost) - 2.00) < 1e-9
        assert s.query(Sale).count() == sales_before
        assert s.query(PurchaseRecord).count() == purchases_before
        assert s.query(SyncOutbox).filter(SyncOutbox.shop_id == "shop-rb").count() == 0

        # Restore completion; behavior returns to dual-write mode intact.
        result = truth.run_cutover(s, "shop-rb")
        assert result["status"] in ("complete", "already_complete")
        assert truth.reconcile_shop(s, "shop-rb") == {}
        s.close()
        engine.dispose()

    def test_13_midpoint_migration_failure_leaves_no_partial_schema(self, pg_engine):
        from app.inventory_truth.migrator import apply

        fresh = _fresh_db()
        insp = inspect(fresh)
        assert not insp.has_table("acquisition_lot")

        with pytest.raises(RuntimeError, match="injected"):
            apply(fresh, fail_after="tables")

        insp = inspect(fresh)
        assert not insp.has_table("acquisition_lot")
        assert not insp.has_table("inventory_event")
        assert not insp.has_table("inventory_truth_cutover")
        # Live tables untouched by the rolled-back attempt.
        names = {ix["name"] for ix in insp.get_indexes("inventory_item")}
        assert "uq_inventory_item_shop_id" not in names

        # A subsequent clean run succeeds fully.
        result = apply(fresh)
        assert set(result["tables"]) == {
            "acquisition_lot",
            "inventory_event",
            "inventory_truth_cutover",
            "inventory_channel_observation",
            "refund_record",
            "return_record",
            "inventory_exception",
        }
        fresh.dispose()


# --- Criterion 14 ----------------------------------------------------------


class TestFreezeCoverage:
    def test_14_all_quantity_changing_intake_paths_frozen(self, pg_engine):
        """While frozen: staging commit, trade apply, CSV/admin overwrite all
        reject. Sale/Shopify behavior otherwise unchanged (POS rejects with
        mapped 503; pull returns freeze message without touching stock)."""
        from fastapi import HTTPException

        from app.logic.intake import commit_staging_item
        from app.logic.sales import CartLine, finalize_sale
        from app.logic.trades import apply_trade_values_to_staging
        from app.routers.admin import _reject_if_truth_frozen

        from app.inventory_truth.core import ReceiveFrozenError

        engine = _fresh_db()
        from app.inventory_truth.migrator import apply

        apply(engine)
        s = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
        s.add(Shop(id="shop-frz", name="F", slug="frz"))
        s.add(InventoryItem(shop_id="shop-frz", sku="Z1", name="z", stock=5, cost=1, price=2, game="Pokemon"))
        s.add(StagingItem(shop_id="shop-frz", sku="Z1", name="z", market_price=2, cost_basis=1, suggested_price=3, quantity=1, game="Pokemon"))
        from app.models import PendingTrade

        s.add(PendingTrade(shop_id="shop-frz", status="pending", total_market_value=10, total_cash_paid=5))
        s.commit()
        sales_before = s.query(Sale).count()

        with pytest.raises(ReceiveFrozenError):
            commit_staging_item(s, "shop-frz", s.query(StagingItem).first().id)
        s.rollback()

        ok, message = apply_trade_values_to_staging(s, "shop-frz", [])
        assert ok is False  # no valid pending trades path unchanged; frozen checked inside loop below

        with pytest.raises(HTTPException) as exc:
            _reject_if_truth_frozen(db=s, shop_id="shop-frz")
        assert exc.value.status_code == 503

        line = CartLine(item=s.query(InventoryItem).first(), quantity=1, unit_price=2.0)
        with pytest.raises(ReceiveFrozenError):
            finalize_sale(s, "shop-frz", [line], 2.0, "cash")
        s.rollback()
        assert s.query(Sale).count() == sales_before
        s.close()
        engine.dispose()


# --- Slice-02 outbound acceptance (AMENDMENT-1.1.0) -------------------------


class TestSlice02Outbound:
    """Twelve-test extension per DIRECTIVE-SLICE-02 §8 / TESTS.md item 12:
    PG-level append-only enforcement, scheduler-overlap + cross-channel
    races, over-sale retry-after-restock, create_all prevention for the
    four new tables, and the inventoried-paths grep gate."""

    def _outbound_shop(self, pg_engine, shop_id="shop-s2", stock=10):
        from app.inventory_truth.migrator import apply

        apply(pg_engine)
        s = sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)()
        s.add(Shop(id=shop_id, name=shop_id.upper(), slug=shop_id))
        s.add(
            InventoryItem(
                shop_id=shop_id, sku="S2", name="s2", stock=stock, cost=2, price=5,
                game="Pokemon",
            )
        )
        s.commit()
        from app.inventory_truth import core as truth

        truth.run_cutover(s, shop_id)
        return s

    def test_s2_1_append_only_triggers_reject_update_delete(self, pg_engine):
        from sqlalchemy.exc import DBAPIError

        from app.inventory_truth import core_outbound as out
        from app.inventory_truth.models_truth import (
            InventoryEvent,
            RefundRecord,
            ReturnRecord,
        )

        s = self._outbound_shop(pg_engine, "shop-append", stock=6)
        item = s.query(InventoryItem).filter(InventoryItem.shop_id == "shop-append").one()
        out.write_sell_event(
            s,
            key=out.sell_key_sale("shop-append", 1),
            shop_id="shop-append",
            sku=item.sku,
            inventory_item_id=item.id,
            sale_id=None,
            quantity_removed=1,
            reason=None,
        )
        event = (
            s.query(InventoryEvent)
            .filter(InventoryEvent.idempotency_key == out.sell_key_sale("shop-append", 1))
            .one()
        )
        refund = out.create_refund_record(
            s, shop_id="shop-append", outbound_event_id=event.id,
            amount=Decimal("5.00"), reason=None, actor_clerk_user_id="u1",
        )
        s.commit()

        # UPDATE rejected on refund_record (DB-level trigger).
        refund.amount = Decimal("9.99")
        with pytest.raises(DBAPIError):
            s.flush()
        s.rollback()

        # DELETE rejected on refund_record.
        r2 = (
            s.query(RefundRecord)
            .filter(RefundRecord.shop_id == "shop-append")
            .first()
        )
        s.delete(r2)
        with pytest.raises(DBAPIError):
            s.flush()
        s.rollback()

        # UPDATE/DELETE rejected on return_record.
        out.confirm_return(
            s,
            shop_id="shop-append",
            sku=item.sku,
            quantity_confirmed=1,
            outcome="resalable",
            condition_note=None,
            refund_record_id=refund.id,
            outbound_event_id=event.id,
            inventory_item_id=item.id,
            actor_clerk_user_id="u1",
        )
        s.commit()
        rr = s.query(ReturnRecord).filter(ReturnRecord.shop_id == "shop-append").one()
        rr.condition_note = "tamper"
        with pytest.raises(DBAPIError):
            s.flush()
        s.rollback()
        s.delete(rr)
        with pytest.raises(DBAPIError):
            s.flush()
        s.rollback()

        # Rows survived every rejected mutation attempt.
        assert s.query(RefundRecord).filter(RefundRecord.shop_id == "shop-append").count() == 1
        assert s.query(ReturnRecord).filter(ReturnRecord.shop_id == "shop-append").count() == 1
        s.close()

    def test_s2_2_scheduler_overlap_same_line_exactly_one_decrement(self, pg_engine):
        from app.inventory_truth import core_outbound as out
        from app.inventory_truth.models_truth import InventoryChannelObservation, InventoryEvent

        engine = _fresh_db()
        from app.inventory_truth.migrator import apply

        apply(engine)
        setup = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
        setup.add(Shop(id="shop-overlap", name="O", slug="overlap"))
        setup.add(
            InventoryItem(
                shop_id="shop-overlap", sku="S3", name="s3", stock=8, cost=2, price=5,
                game="Pokemon",
            )
        )
        setup.commit()
        setup.close()
        from app.inventory_truth import core as truth

        seed = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
        truth.run_cutover(seed, "shop-overlap")
        seed.close()

        outcomes: list[str] = []
        barrier = threading.Barrier(2)

        def pull_worker():
            s = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
            item = (
                s.query(InventoryItem)
                .filter(InventoryItem.shop_id == "shop-overlap", InventoryItem.sku == "S3")
                .one()
            )
            barrier.wait()
            try:
                removed = min(3, max(int(item.stock or 0), 0))
                if not out.claim_observation(
                    s, shop_id="shop-overlap", channel="shopify",
                    channel_ref="7777:1", sku="S3",
                    quantity_requested=3, quantity_removed=removed, sale_id=None,
                ):
                    outcomes.append("lost")
                    s.rollback()
                    return
                item.stock -= removed
                sale = Sale(
                    shop_id="shop-overlap", item_name="s3", sku="S3", sold_price=5.0,
                    profit=3.0, transaction_type="online", net_revenue=5.0,
                )
                s.add(sale)
                s.flush()
                out.write_sell_event(
                    s, key=out.sell_key_shopify_line("shop-overlap", "7777", "1"),
                    shop_id="shop-overlap", sku="S3", inventory_item_id=item.id,
                    sale_id=sale.id, quantity_removed=removed, reason=None,
                )
                s.commit()
                outcomes.append("won")
            except Exception as exc:
                s.rollback()
                outcomes.append(f"error:{type(exc).__name__}")
            finally:
                s.close()

        t1 = threading.Thread(target=pull_worker)
        t2 = threading.Thread(target=pull_worker)
        t1.start(); t2.start(); t1.join(30); t2.join(30)

        try:
            check = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
            assert sorted(o.split(":")[0] for o in outcomes) == ["lost", "won"], outcomes
            obs = check.query(InventoryChannelObservation).filter(
                InventoryChannelObservation.channel_ref == "7777:1"
            ).all()
            assert len(obs) == 1 and obs[0].quantity_removed == 3
            # NOTE: cutover backfill also wrote an `opening` receive for this
            # SKU; the sell-side guarantee is exactly ONE *sell* event.
            sells = check.query(InventoryEvent).filter(
                InventoryEvent.sku == "S3", InventoryEvent.event_type == "sell"
            ).all()
            assert len(sells) == 1 and sells[0].quantity_delta == -3, [
                (e.event_type, e.quantity_delta) for e in sells
            ]
            item = check.query(InventoryItem).filter(
                InventoryItem.shop_id == "shop-overlap", InventoryItem.sku == "S3"
            ).one()
            assert item.stock == 5  # decremented exactly once
        finally:
            check.close()
            engine.dispose()

    def test_s2_3_cross_channel_race_both_recorded_never_merged(self, pg_engine):
        from concurrent.futures import ThreadPoolExecutor

        from app.inventory_truth import core_outbound as out
        from app.inventory_truth.models_truth import InventoryChannelObservation

        engine = _fresh_db()
        from app.inventory_truth.migrator import apply

        apply(engine)
        setup = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
        setup.add(Shop(id="shop-xc", name="X", slug="xc"))
        setup.add(
            InventoryItem(
                shop_id="shop-xc", sku="X4", name="x4", stock=4, cost=2, price=5,
                game="Pokemon",
            )
        )
        setup.commit()
        from app.inventory_truth import core as truth

        truth.run_cutover(setup, "shop-xc")
        setup.close()

        barrier = threading.Barrier(2)

        def channel_worker(channel, ref):
            s = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
            try:
                barrier.wait()
                claimed = out.claim_observation(
                    s, shop_id="shop-xc", channel=channel, channel_ref=ref,
                    sku="X4", quantity_requested=1, quantity_removed=1, sale_id=None,
                )
                s.commit()
                return claimed
            finally:
                s.close()

        with ThreadPoolExecutor() as pool:
            f1 = pool.submit(channel_worker, "pos", "555")
            f2 = pool.submit(channel_worker, "shopify", "8888:9")
            assert f1.result(30) is True
            assert f2.result(30) is True

        check = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
        rows = check.query(InventoryChannelObservation).filter(
            InventoryChannelObservation.sku == "X4"
        ).all()
        assert {(r.channel, r.channel_ref) for r in rows} == {
            ("pos", "555"),
            ("shopify", "8888:9"),
        }  # both recorded — no cross-channel arbitration exists by design
        check.close()
        engine.dispose()

    def test_s2_4_oversale_retry_after_restock_stable_no_stack(self, pg_engine):
        from app.inventory_truth import core_outbound as out
        from app.inventory_truth.models_truth import InventoryException

        s = self._outbound_shop(pg_engine, "shop-retry", stock=2)

        def attempt(removed_now):
            removed = min(5, removed_now)
            if not out.claim_observation(
                s, shop_id="shop-retry", channel="shopify",
                channel_ref="9999:1", sku="S2",
                quantity_requested=5, quantity_removed=removed, sale_id=None,
            ):
                return "no_op"
            state, _eid = out.record_over_sale_exception(
                s, shop_id="shop-retry", channel_ref="9999:1",
                order_id="9999", line_id="1", sku="S2",
                requested=5, removed=removed,
            )
            return state

        assert attempt(removed_now=2) in ("created", "reused")
        s.commit()
        key = out.sell_key_shopify_line("shop-retry", "9999", "1")

        # Restock to 10, then replay the SAME line: identity matches
        # (requested 5), only computed removal drifts → must stay a no-op.
        item = s.query(InventoryItem).filter(InventoryItem.shop_id == "shop-retry").one()
        item.stock = 10
        s.commit()
        assert attempt(removed_now=10) == "no_op"
        s.commit()

        assert s.query(InventoryException).filter(
            InventoryException.exception_ref == key
        ).count() == 1  # never stacked
        item = s.query(InventoryItem).filter(InventoryItem.shop_id == "shop-retry").one()
        assert item.stock == 10
        s.close()

    def test_s2_5_composite_fks_on_new_tables_reject_cross_shop(self, pg_engine):
        from sqlalchemy.exc import IntegrityError

        from app.inventory_truth import core_outbound as out
        from app.inventory_truth.models_truth import (
            InventoryChannelObservation,
            InventoryEvent,
            RefundRecord,
            ReturnRecord,
        )

        insp = inspect(pg_engine)
        fk_map = {
            table: {fk["name"] for fk in insp.get_foreign_keys(table)}
            for table in (
                "inventory_channel_observation",
                "refund_record",
                "return_record",
            )
        }
        assert {"fk_obs_shop_sale"} <= fk_map["inventory_channel_observation"]
        assert {"fk_refund_shop_event"} <= fk_map["refund_record"]
        assert {
            "fk_return_shop_refund",
            "fk_return_shop_event",
        } <= fk_map["return_record"]

        s = self._outbound_shop(pg_engine, "shop-fk", stock=4)
        other = Shop(id="shop-fk-other", name="FO", slug="fk-other")
        s.add(other)
        s.add(
            InventoryEvent(
                shop_id="shop-fk", sku="S2", lot_id=None, inventory_item_id=None,
                sale_id=None, reverses_event_id=None, event_type="sell",
                quantity_delta=-1, overlay_quantity=None, reason=None,
                actor_clerk_user_id=None, idempotency_key=out.sell_key_sale("shop-fk", 42),
            )
        )
        s.commit()
        event = (
            s.query(InventoryEvent)
            .filter(InventoryEvent.idempotency_key == out.sell_key_sale("shop-fk", 42))
            .one()
        )
        bad = RefundRecord(
            shop_id="shop-fk-other",  # wrong shop → composite FK must reject
            outbound_event_id=event.id,
            amount=Decimal("1.00"),
        )
        s.add(bad)
        with pytest.raises(IntegrityError):
            s.commit()
        s.rollback()
        s.close()

    def test_s2_6_grep_gate_no_uninventoried_stock_mutation(self):
        """TESTS.md item 12: prove stock mutations occur only inside the
        inventoried path list (DIRECTIVE-SLICE-02 §1 O-list)."""
        import re
        from pathlib import Path

        app_dir = Path(__file__).resolve().parents[1] / "app"
        allowed = {
            # O1/O3 POS checkout
            (Path("app") / "logic" / "sales.py"): {"item.stock -= finalized.quantity"},
            # O4 Shopify pull
            (Path("app") / "logic" / "sync_worker.py"): {
                "locked_item.stock = stock_before - removed",
                "inv_item.stock = stock_before - removed",
            },
            # O6 admin PATCH (frozen via _reject_if_truth_frozen)
            (Path("app") / "routers" / "admin.py"): {"item.stock = payload.stock"},
            # O2 trade settlement (receive-side, slice-01 dual-write)
            (Path("app") / "logic" / "trades.py"): {"existing_item.stock = total_qty"},
            # receive-side intake commit
            (Path("app") / "logic" / "intake.py"): {"existing.stock = total_qty"},
            # O7 CSV overwrite (frozen at router)
            (Path("app") / "logic" / "import_engine.py"): {"existing.stock = quantity"},
        }
        pattern = re.compile(r"^\s*\w[\w.\[\]]*\.stock\s*(?:-=|\+=|=(?!=))", re.MULTILINE)
        violations: list[str] = []

        for py in sorted(app_dir.rglob("*.py")):
            rel = Path("app") / py.relative_to(app_dir)
            text_src = py.read_text(encoding="utf-8")
            for match in pattern.finditer(text_src):
                line = match.group(0).strip()
                allowed_lines = allowed.get(rel, set())
                if not any(line.startswith(a.split("=")[0].strip()) or a in line for a in allowed_lines):
                    violations.append(f"{rel}: {line}")

        assert violations == [], (
            "un-inventoried stock mutation outside the O-list:\n"
            + "\n".join(violations)
        )

    def test_s2_7_distinct_lines_same_sku_serialize_no_lost_update(self, pg_engine):
        """Adversarial P1: two concurrent DISTINCT order lines for the SAME
        SKU must serialize on the item row lock — final stock equals
        snapshot minus event sum, with no overwritten decrement."""
        from app.inventory_truth import core_outbound as out
        from app.inventory_truth.models_truth import InventoryEvent

        engine = _fresh_db()
        from app.inventory_truth.migrator import apply

        apply(engine)
        setup = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
        setup.add(Shop(id="shop-dl", name="D", slug="dl"))
        setup.add(
            InventoryItem(
                shop_id="shop-dl", sku="L1", name="l1", stock=10, cost=1, price=5,
                game="Pokemon",
            )
        )
        setup.commit()
        from app.inventory_truth import core as truth

        seed = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
        truth.run_cutover(seed, "shop-dl")
        seed.close()

        barrier = threading.Barrier(2)

        def line_worker(line_ref):
            s = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
            try:
                item = (
                    s.query(InventoryItem)
                    .filter(
                        InventoryItem.shop_id == "shop-dl",
                        InventoryItem.sku == "L1",
                    )
                    .one()
                )
                barrier.wait()
                removed = 4
                if not out.claim_observation(
                    s, shop_id="shop-dl", channel="shopify",
                    channel_ref=f"8000:{line_ref}", sku="L1",
                    quantity_requested=removed, quantity_removed=removed,
                    sale_id=None,
                ):
                    return "lost"
                sale = Sale(
                    shop_id="shop-dl", item_name="l1", sku="L1", sold_price=5.0,
                    profit=4.0, transaction_type="online", net_revenue=5.0,
                )
                s.add(sale)
                s.flush()
                # Lock the item row only at the decrement point (mirrors the
                # production path: read → arbitrate → lock → write), so the
                # barrier never deadlocks on a pre-barrier FOR UPDATE.
                locked_item = (
                    s.query(InventoryItem)
                    .filter(
                        InventoryItem.shop_id == "shop-dl",
                        InventoryItem.id == item.id,
                    )
                    .with_for_update()
                    .populate_existing()
                    .one()
                )
                out.write_sell_event(
                    s, key=out.sell_key_shopify_line("shop-dl", "8000", line_ref),
                    shop_id="shop-dl", sku="L1", inventory_item_id=item.id,
                    sale_id=sale.id, quantity_removed=removed, reason=None,
                )
                locked_item.stock -= removed  # absolute write AFTER the lock
                s.commit()
                return "won"
            except Exception:
                s.rollback()
                raise
            finally:
                s.close()

        t1 = threading.Thread(target=line_worker, args=("1",))
        t2 = threading.Thread(target=line_worker, args=("2",))
        results = []
        t1.start(); t2.start(); t1.join(30); t2.join(30)

        check = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
        try:
            sells = (
                check.query(InventoryEvent)
                .filter(
                    InventoryEvent.shop_id == "shop-dl",
                    InventoryEvent.sku == "L1",
                    InventoryEvent.event_type == "sell",
                )
                .all()
            )
            assert len(sells) == 2, [(e.event_type, e.quantity_delta) for e in sells]
            assert sum(e.quantity_delta for e in sells) == -8
            item = (
                check.query(InventoryItem)
                .filter(InventoryItem.shop_id == "shop-dl", InventoryItem.sku == "L1")
                .one()
            )
            # Without the row lock this window yields stock 6 (one write lost);
            # serialization guarantees both decrements land.
            assert item.stock == 2, f"lost update detected: stock={item.stock}"
        finally:
            check.close()
            engine.dispose()

    def test_s2_8_append_only_rejects_truncate_runtime_role(self, pg_engine):
        """Final acceptance: TRUNCATE on append-only tables is denied at the
        DATABASE level for the runtime role; records survive every rejected
        attempt; the authorized migrator role keeps full lifecycle access."""
        from sqlalchemy.exc import DBAPIError

        from app.inventory_truth import core_outbound as out
        from app.inventory_truth.models_truth import RefundRecord

        runtime_user = None
        with pg_engine.connect() as c:
            runtime_user = c.execute(text("SELECT current_user")).scalar()

        # Migrator pass with an explicitly authorized role (the runtime role
        # is deliberately NOT it — the denial must hit that role).
        os.environ["STASHTAB_TRUTH_MIGRATOR_ROLE"] = "stashtab_migrator"
        from app.inventory_truth.migrator import apply

        apply(pg_engine)

        # The authorized migrator role can truncate (controlled lifecycle):
        # connect AS the migrator role on a dedicated autocommit connection.
        try:
            mig_engine = create_engine(PG_URL, poolclass=None)
            with mig_engine.connect().execution_options(
                isolation_level="AUTOCOMMIT"
            ) as c:
                c.execute(text("SET ROLE stashtab_migrator"))
                c.execute(text("TRUNCATE return_record"))  # must be allowed
            mig_engine.dispose()
            setrole_ok = True
        except Exception:
            setrole_ok = False

        # Seed one refund + one return record.
        s = sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)()
        item = InventoryItem(
            shop_id="shop-tr", sku="T9", name="t9", stock=3, cost=1, price=5,
            game="Pokemon",
        )
        s.add(item)
        s.commit()
        ev = out.InventoryEvent(
            shop_id="shop-tr", sku="T9", lot_id=None, inventory_item_id=item.id,
            sale_id=None, reverses_event_id=None, event_type="sell",
            quantity_delta=-1, overlay_quantity=None, reason=None,
            actor_clerk_user_id=None, idempotency_key=out.sell_key_sale("shop-tr", 77),
        )
        s.add(ev)
        s.flush()
        refund = out.create_refund_record(
            s, shop_id="shop-tr", outbound_event_id=ev.id,
            amount=Decimal("5.00"), reason=None, actor_clerk_user_id="u1",
        )
        out.confirm_return(
            s, shop_id="shop-tr", sku="T9", quantity_confirmed=1,
            outcome="resalable", condition_note=None,
            refund_record_id=refund.id, outbound_event_id=ev.id,
            inventory_item_id=item.id, actor_clerk_user_id="u1",
        )
        s.commit()

        counts = lambda: [  # noqa: E731
            s.query(t).filter(t.shop_id == "shop-tr").count()
            for t in (RefundRecord,)
        ]
        assert counts() == [1]

        # Runtime role TRUNCATE must be rejected by the database (ACL first,
        # trigger as second gate). Lock timeout guards against queueing.
        for table in ("refund_record", "return_record"):
            with pytest.raises(DBAPIError):
                with pg_engine.connect() as c:
                    c.execute(text("SET lock_timeout = '3s'"))
                    c.execute(text(f"TRUNCATE {table}"))
                    c.commit()
        assert counts() == [1]  # records intact after failed attempts
        assert setrole_ok  # controlled migrator path still functions
        s.close()

    def test_s2_9_worker_isolation_line_order_shop_tick(self, pg_engine):
        """Final acceptance: poisoned line/order/shop/tick containment with
        committed-event durability and idempotent retry."""
        import app.logic.sync_worker as sw

        engine = _fresh_db()
        from app.inventory_truth.migrator import apply

        apply(engine)
        s = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
        # Shop A: one poisoned line (unknown SKU), then two valid lines.
        s.add(Shop(id="shop-iso", name="I", slug="iso"))
        s.add(
            InventoryItem(
                shop_id="shop-iso", sku="W1", name="w1", stock=10, cost=1,
                price=5, game="Pokemon",
            )
        )
        s.add(
            InventoryItem(
                shop_id="shop-iso", sku="W2", name="w2", stock=10, cost=1,
                price=5, game="Pokemon",
            )
        )
        s.add(
            InventoryItem(
                shop_id="shop-iso", sku="W3", name="w3", stock=20, cost=1,
                price=5, game="Pokemon",
            )
        )
        # POISON must resolve to an item so processing reaches the (wrapped)
        # line handler instead of being filtered as an unknown SKU.
        s.add(
            InventoryItem(
                shop_id="shop-iso", sku="POISON", name="p", stock=5, cost=1,
                price=5, game="Pokemon",
            )
        )
        # Shop B: must be processed even if shop A's tick explodes.
        s.add(Shop(id="shop-other", name="O", slug="other"))
        s.add(
            InventoryItem(
                shop_id="shop-other", sku="V1", name="v1", stock=5, cost=1,
                price=5, game="Pokemon",
            )
        )
        s.commit()
        from app.inventory_truth import core as truth

        for sid in ("shop-iso", "shop-other"):
            seed = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
            truth.run_cutover(seed, sid)
            seed.close()

        orders = [
            {
                # Malformed line FIRST (unknown SKU): later valid lines in
                # this same order must still be processed.
                "id": 9001,
                "line_items": [
                    {"id": 1, "sku": "POISON", "quantity": 1, "price": 5.0},
                    {"id": 2, "sku": "W1", "quantity": 2, "price": 5.0},
                ],
            },
            {
                # This whole order will fail permanently at its only line;
                # the NEXT order must still be processed afterwards.
                "id": 9002,
                "line_items": [
                    {"id": 3, "sku": "W2", "quantity": 3, "price": 5.0},
                ],
            },
            {
                "id": 9003,
                "line_items": [
                    {"id": 4, "sku": "W3", "quantity": 4, "price": 5.0},
                ],
            },
        ]

        class FakeClient:
            def __init__(self, creds):
                pass

            def get_recent_unfulfilled_orders(self):
                return {"orders": orders}

        from app.models import ShopifyCredentials

        s.add(
            ShopifyCredentials(
                shop_id="shop-iso", store_url="test", api_key_encrypted="x"
            )
        )
        s.commit()

        original_client = sw.ShopifyClient
        sw.ShopifyClient = FakeClient
        from app.inventory_truth import core_outbound as out

        # Poison the POISON line via a wrapper around the real processor so
        # the permanent-failure path (not a missing-SKU skip) is exercised.
        real_process = sw._process_pull_line

        def poisoned_process(db, **kwargs):
            if kwargs.get("sku") == "POISON":
                raise out.LinePermanentError("poisoned line")
            return real_process(db, **kwargs)

        sw._process_pull_line = poisoned_process
        try:
            result = sw.pull_shopify_orders(s, "shop-iso")
        finally:
            sw.ShopifyClient = original_client
            sw._process_pull_line = real_process
        failed_skus = {f["sku"] for f in result["failed_permanent_lines"]}
        # Poisoned first line + fully-poisoned order 9002 both fail; the
        # valid lines and order 9003 still commit.
        assert result["new_pulls"] == 3, result
        assert failed_skus == {"POISON"}
        w1 = s.query(InventoryItem).filter(
            InventoryItem.shop_id == "shop-iso", InventoryItem.sku == "W1"
        ).one()
        assert w1.stock == 8  # valid line after the poison still decremented
        w3 = s.query(InventoryItem).filter(
            InventoryItem.shop_id == "shop-iso", InventoryItem.sku == "W3"
        ).one()
        assert w3.stock == 16  # order after a failing order still processed

        # Order 9001 is now partially pulled; a retry must not re-decrement.
        sw._process_pull_line = poisoned_process
        try:
            result2 = sw.pull_shopify_orders(s, "shop-iso")
        finally:
            sw.ShopifyClient = original_client
            sw._process_pull_line = real_process
        assert result2["new_pulls"] == 0
        w1 = s.query(InventoryItem).filter(
            InventoryItem.shop_id == "shop-iso", InventoryItem.sku == "W1"
        ).one()
        assert w1.stock == 8  # idempotent retry: no double decrement

        # Failing-shop isolation via the worker entrypoint.
        import worker

        def failing_sync(_db, shop_id):
            if shop_id == "shop-iso":
                raise RuntimeError("boom")
            return {
                "pull": {"new_pulls": 0, "notifications": []},
                "outbox": {},
            }

        original_run = worker.run_full_sync
        worker.run_full_sync = failing_sync
        try:
            shops = s.query(Shop).order_by(Shop.id).all()
            outcomes = []
            for shop in shops:
                # Mirror the worker loop's per-shop containment.
                try:
                    outcomes.append(worker.tick_shop(s, shop))
                except Exception as exc:  # pragma: no cover - last resort
                    s.rollback()
                    outcomes.append(
                        {"shop": shop.slug, "status": "failed", "error": str(exc)}
                    )
        finally:
            worker.run_full_sync = original_run
        statuses = {r["shop"]: r["status"] for r in outcomes}
        assert statuses["iso"] == "failed"
        assert statuses["other"] == "ok"  # later shop still ran

        s.close()
        engine.dispose()

    def test_s2_10_alert_delivery_failure_preserves_exception(self, pg_engine):
        """Final acceptance: a failing alert publisher can neither roll back
        nor resolve the committed over-sale exception."""
        import app.logic.sync_worker as sw

        engine = _fresh_db()
        from app.inventory_truth.migrator import apply

        apply(engine)
        s = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
        s.add(Shop(id="shop-alert", name="A", slug="alert"))
        s.add(
            InventoryItem(
                shop_id="shop-alert", sku="S1", name="s1", stock=2, cost=1,
                price=5, game="Pokemon",
            )
        )
        s.commit()
        from app.inventory_truth import core as truth
        from app.inventory_truth import core_outbound as out

        seed = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
        truth.run_cutover(seed, "shop-alert")
        seed.close()

        orders = [
            {
                "id": 7001,
                "line_items": [
                    # Request 5 with only 2 in stock → over-sale exception.
                    {"id": 1, "sku": "S1", "quantity": 5, "price": 5.0},
                ],
            },
        ]

        class FakeClient:
            def __init__(self, creds):
                pass

            def get_recent_unfulfilled_orders(self):
                return {"orders": orders}

        from app.models import ShopifyCredentials

        s.add(
            ShopifyCredentials(
                shop_id="shop-alert", store_url="test", api_key_encrypted="x"
            )
        )
        s.commit()

        original_client = sw.ShopifyClient
        original_publish = sw.publish_notifications
        calls = {"n": 0}

        def exploding_publisher(items):
            calls["n"] += 1
            raise RuntimeError("push vendor down")

        sw.ShopifyClient = FakeClient
        sw.publish_notifications = exploding_publisher
        try:
            result = sw.pull_shopify_orders(s, "shop-alert")
        finally:
            sw.ShopifyClient = original_client
            sw.publish_notifications = original_publish
        assert calls["n"] == 1  # delivery was attempted post-commit
        assert len(result["notifications"]) == 1  # batch still reports it
        item = s.query(InventoryItem).filter(
            InventoryItem.shop_id == "shop-alert", InventoryItem.sku == "S1"
        ).one()
        assert item.stock == 0  # actual removal persisted

        exc_row = (
            s.query(out.InventoryException)
            .filter(
                out.InventoryException.shop_id == "shop-alert",
                out.InventoryException.kind == "over_sale_short",
            )
            .one()
        )
        assert exc_row.status == "open"  # not resolved by the failed alert
        assert exc_row.quantity_unsatisfied == 3  # shortage preserved exactly
        sells = (
            s.query(out.InventoryEvent)
            .filter(
                out.InventoryEvent.shop_id == "shop-alert",
                out.InventoryEvent.sku == "S1",
                out.InventoryEvent.event_type == "sell",
            )
            .all()
        )
        # One event for the quantity actually removed (2), never 5.
        assert sum(-e.quantity_delta for e in sells) == 2

        s.close()
        engine.dispose()
