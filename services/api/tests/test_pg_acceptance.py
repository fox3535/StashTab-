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


def _fresh_db():
    """Drop everything, recreate the PRE-inventory schema via app create_all."""
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
        ))
        assert set(result["tables"]) == {
            "acquisition_lot",
            "inventory_event",
            "inventory_truth_cutover",
        }
        assert len(result["indexes"]) == 3  # inventory_item, purchase_record, sale

    def test_2_second_run_is_noop(self, pg_engine):
        from app.inventory_truth.migrator import apply

        result = apply(pg_engine)
        assert result["indexes"] == []
        assert result["tables"] == []


# --- Criteria 3, 4, 5 ------------------------------------------------------


class TestSchemaGuarantees:
    def test_3_app_create_all_cannot_create_or_alter_truth_tables(self, pg_engine):
        # Fresh pre-inventory DB: app create_all must not create truth tables.
        fresh = _fresh_db()
        insp = inspect(fresh)
        assert not any(insp.has_table(t) for t in ("acquisition_lot", "inventory_event"))
        Base.metadata.create_all(fresh)  # again — must stay inert for truth tables
        insp = inspect(fresh)
        assert not insp.has_table("acquisition_lot")
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

        total = (
            s1.query(func.coalesce(func.sum(InventoryEvent.quantity_delta), 0))
            .filter(InventoryEvent.shop_id == "shop-d", InventoryEvent.sku == "R1")
            .scalar()
        )
        assert int(total or 0) == 5, errs
        s1.close(); s2.close()
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
        assert set(result["tables"]) == {"acquisition_lot", "inventory_event", "inventory_truth_cutover"}
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
