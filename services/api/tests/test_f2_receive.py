"""API-level acceptance for the F2 controlled receive (AMENDMENT-1.3.0 §13).

SQLite equivalents of the eight acceptance items, exercised through
`POST /api/v1/admin/inventory/receive` with a synthetic Clerk membership.
PostgreSQL-only concerns (role privileges, true multi-connection
concurrency, append-only at the DB level) live in
`tests/test_f2_receive_pg.py`.
"""

from __future__ import annotations

import os
import tempfile
import threading
import uuid as uuid_mod
from concurrent.futures import ThreadPoolExecutor

import pytest


def _ensure_pandas_importable() -> None:
    """Harness-only shim. On machines where Windows Application Control
    blocks numpy's native DLLs, `pandas` cannot be imported, which blocks
    importing the admin router (via app.logic.import_engine). This slice
    exercises no CSV logic, so a stub keeps the suite runnable. Strictly a
    no-op wherever real pandas imports."""
    try:
        import pandas  # noqa: F401

        return
    except ImportError:
        pass
    import sys
    import types

    def _unavailable(*_args, **_kwargs):
        raise RuntimeError("pandas unavailable in this test environment")

    stub = types.ModuleType("pandas")
    stub.DataFrame = object
    stub.Series = object
    stub.read_csv = _unavailable
    stub.to_datetime = _unavailable
    sys.modules.setdefault("pandas", stub)


_ensure_pandas_importable()

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import get_db
from app.errors import FeatureNotReadyError
from app.inventory_truth import core as truth_core
from app.inventory_truth.models_truth import AcquisitionLot, InventoryEvent, TruthBase
from app.main import (
    feature_not_ready_handler,
    operational_error_handler,
    programming_error_handler,
)
from app.models import Base, InventoryItem, PurchaseRecord, Shop, ShopMember
from app.models.base import new_uuid
from app.routers import admin as admin_router

RECEIVE_URL = "/api/v1/admin/inventory/receive"
CLIENT_KEY_INDEX_SQL = (
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_purchase_record_shop_client_key "
    "ON purchase_record (shop_id, client_idempotency_key) "
    "WHERE client_idempotency_key IS NOT NULL"
)


def _build_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TruthBase.metadata.create_all(engine)
    with engine.begin() as conn:
        # Partial unique is migrator-owned DDL on PostgreSQL; mirror it here
        # so replay/race semantics are exercised identically.
        conn.execute(text(CLIENT_KEY_INDEX_SQL))
    return engine


def _seed(engine):
    db = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    db.add(Shop(id="shop-a", name="A", slug="a"))
    db.add(Shop(id="shop-b", name="B", slug="b"))
    db.add(ShopMember(id=new_uuid(), shop_id="shop-a", clerk_user_id="user-owner", role="owner"))
    db.add(ShopMember(id=new_uuid(), shop_id="shop-a", clerk_user_id="user-staff", role="staff"))
    db.add(ShopMember(id=new_uuid(), shop_id="shop-b", clerk_user_id="user-other", role="owner"))
    db.commit()
    # shop-a completes cutover; shop-b deliberately has none (fail-closed).
    truth_core.run_cutover(db, "shop-a")
    db.commit()
    return db


def _decode(authorization):
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    return token


def _make_app(db):
    app = FastAPI()
    app.include_router(admin_router.router, prefix="/api/v1")
    app.add_exception_handler(FeatureNotReadyError, feature_not_ready_handler)
    app.add_exception_handler(OperationalError, operational_error_handler)
    app.add_exception_handler(ProgrammingError, programming_error_handler)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    return app


@pytest.fixture()
def env(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "local")
    monkeypatch.setattr(settings, "stashtab_allow_dev_identity", False)
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr("app.auth.identity.decode_bearer_user_id", _decode)
    monkeypatch.setattr("app.auth.clerk.decode_bearer_user_id", _decode)
    engine = _build_engine()
    db = _seed(engine)
    app = _make_app(db)
    return {
        "engine": engine,
        "db": db,
        "app": app,
        "client": TestClient(app),
        "client_500": TestClient(app, raise_server_exceptions=False),
    }


def _headers(user="user-owner", shop="shop-a"):
    return {"X-Shop-Id": shop, "Authorization": f"Bearer {user}"}


def _payload(**overrides):
    body = {
        "sku": "F2-TEST-0001",
        "name": "F2 Synthetic Test Card",
        "quantity": 2,
        "unit_cost": 0.01,
        "set_name": "Synthetic Set",
        "sequence_number": "1",
    }
    body.update(overrides)
    return body


def _counts(db):
    return {
        "items": db.query(InventoryItem).count(),
        "purchases": db.query(PurchaseRecord).count(),
        "lots": db.query(AcquisitionLot).count(),
        "events": db.query(InventoryEvent).count(),
    }


# --- §13.2: first-SKU receive ---------------------------------------------


def test_first_sku_receive_creates_item_purchase_pair_and_reconciles(env):
    key = str(uuid_mod.uuid4())
    resp = env["client"].post(
        RECEIVE_URL, json=_payload(), headers={**_headers(), "Idempotency-Key": key}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["result"] == "created"
    assert body["sku"] == "F2-TEST-0001"
    assert body["stock"] == 2

    db = env["db"]
    item = db.query(InventoryItem).filter_by(shop_id="shop-a", sku="F2-TEST-0001").one()
    assert item.stock == 2
    assert item.cost == 0.01
    assert item.sync_status == "approved"
    assert body["inventory_item_id"] == item.id

    record = (
        db.query(PurchaseRecord)
        .filter_by(shop_id="shop-a", client_idempotency_key=key)
        .one()
    )
    assert body["purchase_record_id"] == record.id
    assert record.sku == "F2-TEST-0001"
    assert record.quantity == 2

    expected_key = truth_core.canonical_key("purchase_record", "shop-a", record.id)
    lot = db.query(AcquisitionLot).filter_by(shop_id="shop-a", idempotency_key=expected_key).one()
    event = (
        db.query(InventoryEvent).filter_by(shop_id="shop-a", idempotency_key=expected_key).one()
    )
    assert lot.quantity_acquired == 2
    assert event.event_type == "receive"
    assert event.quantity_delta == 2

    # Reconciliation proof (§6): event-derived remaining == snapshot stock.
    assert truth_core.reconcile_shop(db, "shop-a") == {}


def test_existing_item_receive_bumps_stock_and_weighted_cost(env):
    db = env["db"]
    db.add(
        InventoryItem(
            shop_id="shop-a", sku="WA-1", name="WA Card", cost=4.00, price=8.0, stock=2,
            game="Pokemon",
        )
    )
    db.commit()
    resp = env["client"].post(
        RECEIVE_URL,
        json=_payload(sku="WA-1", name="WA Card", quantity=2, unit_cost=2.00),
        headers={**_headers(), "Idempotency-Key": str(uuid_mod.uuid4())},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["result"] == "created"
    item = db.query(InventoryItem).filter_by(shop_id="shop-a", sku="WA-1").one()
    assert item.stock == 4
    assert item.cost == 3.0  # (4.00*2 + 2.00*2) / 4


# --- §13.3: idempotent replay and conflict ---------------------------------


def test_idempotent_replay_same_payload_is_no_op(env):
    key = str(uuid_mod.uuid4())
    headers = {**_headers(), "Idempotency-Key": key}
    first = env["client"].post(RECEIVE_URL, json=_payload(), headers=headers)
    assert first.status_code == 200
    before = _counts(env["db"])

    second = env["client"].post(RECEIVE_URL, json=_payload(), headers=headers)
    assert second.status_code == 200, second.text
    body = second.json()
    assert body["result"] == "no_op"
    assert body["purchase_record_id"] == first.json()["purchase_record_id"]
    assert _counts(env["db"]) == before


def test_conflicting_replay_different_payload_409_zero_writes(env):
    key = str(uuid_mod.uuid4())
    headers = {**_headers(), "Idempotency-Key": key}
    first = env["client"].post(RECEIVE_URL, json=_payload(), headers=headers)
    assert first.status_code == 200
    before = _counts(env["db"])

    conflict = env["client"].post(
        RECEIVE_URL, json=_payload(quantity=5), headers=headers
    )
    assert conflict.status_code == 409
    assert _counts(env["db"]) == before


def test_digest_recomputed_from_stored_columns_is_stable():
    from decimal import Decimal

    from app.logic.controlled_receive import canonical_cost, payload_digest

    stored_float = 0.1 + 0.2  # float round-trip like purchase_record.cost_per_unit
    assert payload_digest("SKU", 2, canonical_cost(stored_float)) == payload_digest(
        "SKU", 2, Decimal("0.30")
    )


# --- §13.4: concurrent identical receives → exactly one pair ---------------


def test_concurrent_identical_receives_yield_exactly_one_pair():
    tmp = tempfile.mkdtemp(prefix="stashtab-f2-")
    path = os.path.join(tmp, "f2.sqlite")
    engine = create_engine(
        f"sqlite:///{path}", connect_args={"check_same_thread": False, "timeout": 30}
    )
    Base.metadata.create_all(engine)
    TruthBase.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text(CLIENT_KEY_INDEX_SQL))
    maker = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = maker()
    db.add(Shop(id="shop-a", name="A", slug="a"))
    db.commit()
    truth_core.run_cutover(db, "shop-a")
    db.commit()
    db.close()

    key = str(uuid_mod.uuid4())
    barrier = threading.Barrier(2)

    def worker():
        session = maker()
        try:
            barrier.wait(timeout=20)
            from app.logic.controlled_receive import receive_controlled

            return receive_controlled(
                session,
                shop_id="shop-a",
                client_key=key,
                sku="RACE-1",
                name="Race Card",
                quantity=1,
                unit_cost=1.00,
            )
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: worker(), range(2)))

    outcomes = sorted(r.result for r in results)
    assert outcomes == ["created", "no_op"]
    assert results[0].purchase_record_id == results[1].purchase_record_id

    check = maker()
    assert check.query(PurchaseRecord).filter_by(client_idempotency_key=key).count() == 1
    assert check.query(AcquisitionLot).count() == 1
    assert check.query(InventoryEvent).count() == 1
    assert check.query(InventoryItem).filter_by(sku="RACE-1").count() == 1
    check.close()


def test_concurrent_loser_rolls_back_and_re_resolves_to_no_op(env, monkeypatch):
    """Loser path: commit hits the partial unique, the ENTIRE transaction
    rolls back, and the request re-resolves by client key (§6/§4 binding)."""
    from app.logic import controlled_receive as cr

    key = str(uuid_mod.uuid4())
    headers = {**_headers(), "Idempotency-Key": key}
    first = env["client"].post(RECEIVE_URL, json=_payload(), headers=headers)
    assert first.status_code == 200

    db = env["db"]
    rolled_back = []
    original_rollback = db.rollback

    def fake_commit():
        raise IntegrityError(
            "INSERT INTO purchase_record ...",
            {},
            Exception(
                "UNIQUE constraint failed: purchase_record.shop_id, "
                "purchase_record.client_idempotency_key"
            ),
        )

    def tracking_rollback():
        rolled_back.append(True)
        return original_rollback()

    monkeypatch.setattr(db, "commit", fake_commit)
    monkeypatch.setattr(db, "rollback", tracking_rollback)

    result = cr.receive_controlled(
        db,
        shop_id="shop-a",
        client_key=key,
        sku="F2-TEST-0001",
        name="F2 Synthetic Test Card",
        quantity=2,
        unit_cost=0.01,
    )
    assert result.result == "no_op"
    assert rolled_back, "loser must roll back its entire transaction"
    assert result.purchase_record_id == first.json()["purchase_record_id"]


# --- §13.5: injected failure mid-transaction → zero rows -------------------


def test_injected_failure_mid_transaction_commits_zero_rows(env, monkeypatch):
    from app.logic import controlled_receive as cr

    def boom(*args, **kwargs):
        raise RuntimeError("injected failure after snapshot and purchase insert")

    monkeypatch.setattr(cr.truth, "record_purchase_receive", boom)
    key = str(uuid_mod.uuid4())
    resp = env["client_500"].post(
        RECEIVE_URL,
        json=_payload(sku="FAIL-1"),
        headers={**_headers(), "Idempotency-Key": key},
    )
    # Unclassified failure keeps the generic 500 path (never a controlled
    # 503, never a partial commit).
    assert resp.status_code == 500

    db = env["db"]
    assert db.query(InventoryItem).filter_by(sku="FAIL-1").count() == 0
    assert db.query(PurchaseRecord).filter_by(sku="FAIL-1").count() == 0
    assert db.query(AcquisitionLot).filter_by(sku="FAIL-1").count() == 0
    assert db.query(InventoryEvent).filter_by(sku="FAIL-1").count() == 0


# --- §13.6: cross-shop denial ----------------------------------------------


def test_cross_shop_denied_zero_data_leak(env):
    key = str(uuid_mod.uuid4())
    # user-other is a member of shop-b only; hint shop-a must be rejected.
    resp = env["client"].post(
        RECEIVE_URL,
        json=_payload(),
        headers={**_headers(user="user-other", shop="shop-a"), "Idempotency-Key": key},
    )
    assert resp.status_code in (403, 404)
    # Missing bearer entirely.
    resp2 = env["client"].post(
        RECEIVE_URL,
        json=_payload(),
        headers={"X-Shop-Id": "shop-a", "Idempotency-Key": str(uuid_mod.uuid4())},
    )
    assert resp2.status_code == 401

    db = env["db"]
    assert db.query(PurchaseRecord).filter_by(shop_id="shop-a").count() == 0
    assert db.query(PurchaseRecord).filter_by(shop_id="shop-b").count() == 0
    assert db.query(InventoryItem).count() == 0


def test_receive_role_fail_closed(env, monkeypatch):
    # staff IS allowed (ordinary operation per DIRECTIVE §3).
    resp = env["client"].post(
        RECEIVE_URL,
        json=_payload(sku="STAFF-1"),
        headers={**_headers(user="user-staff"), "Idempotency-Key": str(uuid_mod.uuid4())},
    )
    assert resp.status_code == 200, resp.text

    # Dev-bypass context carries role=None and must be denied (fail-closed).
    monkeypatch.setattr(settings, "stashtab_allow_dev_identity", True)
    resp2 = env["client"].post(
        RECEIVE_URL,
        json=_payload(sku="BYPASS-1"),
        headers={"X-Shop-Id": "shop-a", "Idempotency-Key": str(uuid_mod.uuid4())},
    )
    assert resp2.status_code == 403
    db = env["db"]
    assert db.query(PurchaseRecord).filter_by(sku="BYPASS-1").count() == 0
    assert db.query(PurchaseRecord).count() == 1  # only the staff receive


# --- §13.7 equivalent: controlled-503 handler mapping -----------------------


def test_controlled_503_handler_mappings_never_leak_details():
    app = FastAPI()
    app.add_exception_handler(FeatureNotReadyError, feature_not_ready_handler)
    app.add_exception_handler(OperationalError, operational_error_handler)
    app.add_exception_handler(ProgrammingError, programming_error_handler)

    @app.get("/probe/privilege")
    def probe_privilege():
        # SQLSTATE 42501 — how SQLAlchemy 2.x surfaces a privilege denial.
        orig = Exception("permission denied for table inventory_adjustment")
        orig.pgcode = "42501"
        raise OperationalError(
            "INSERT INTO inventory_adjustment (shop_id) VALUES ('x')", {}, orig
        )

    @app.get("/probe/other-operational")
    def probe_other_operational():
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    @app.get("/probe/missing-table")
    def probe_missing_table():
        orig = Exception("relation \"sync_outbox\" does not exist")
        orig.pgcode = "42P01"
        raise ProgrammingError("SELECT * FROM sync_outbox", {}, orig)

    @app.get("/probe/other")
    def probe_other():
        raise ProgrammingError("SELECT bogus", {}, Exception("syntax error at end"))

    client = TestClient(app, raise_server_exceptions=False)

    priv = client.get("/probe/privilege")
    assert priv.status_code == 503
    assert priv.json()["error"] == "FEATURE_NOT_READY"
    assert "inventory_adjustment" not in priv.text
    assert "permission" not in priv.text
    assert "stashtab" not in priv.text

    missing = client.get("/probe/missing-table")
    assert missing.status_code == 503
    assert missing.json()["error"] == "FEATURE_NOT_READY"
    assert "sync_outbox" not in missing.text

    other_op = client.get("/probe/other-operational")
    assert other_op.status_code == 500  # unrelated operational errors stay generic

    other = client.get("/probe/other")
    assert other.status_code == 500  # unrelated programming errors stay generic


# --- §13.8: missing cutover fail-closed + Idempotency-Key validation --------


def test_missing_cutover_receive_503_fail_closed(env):
    resp = env["client"].post(
        RECEIVE_URL,
        json=_payload(),
        headers={**_headers(user="user-other", shop="shop-b"),
                 "Idempotency-Key": str(uuid_mod.uuid4())},
    )
    assert resp.status_code == 503
    assert resp.json()["error"] == "FEATURE_NOT_READY"
    db = env["db"]
    assert db.query(PurchaseRecord).filter_by(shop_id="shop-b").count() == 0
    assert db.query(InventoryItem).filter_by(shop_id="shop-b").count() == 0


@pytest.mark.parametrize("bad_key", [None, "", "not-a-uuid", "12345", str(uuid_mod.uuid1())])
def test_missing_or_invalid_idempotency_key_422_zero_writes(env, bad_key):
    headers = _headers()
    if bad_key is not None:
        headers["Idempotency-Key"] = bad_key
    resp = env["client"].post(RECEIVE_URL, json=_payload(), headers=headers)
    assert resp.status_code == 422
    db = env["db"]
    assert _counts(db) == {"items": 0, "purchases": 0, "lots": 0, "events": 0}


def test_validation_rules_422(env):
    headers = {**_headers(), "Idempotency-Key": str(uuid_mod.uuid4())}
    for bad in (
        _payload(sku=""),
        _payload(quantity=0),
        _payload(quantity=1001),
        _payload(unit_cost=-0.01),
        _payload(unit_cost=100000.00),
        _payload(name="x" * 101),
    ):
        resp = env["client"].post(RECEIVE_URL, json=bad, headers=headers)
        assert resp.status_code == 422, bad
    assert _counts(env["db"]) == {"items": 0, "purchases": 0, "lots": 0, "events": 0}
