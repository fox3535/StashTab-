"""PostgreSQL acceptance for the F2 controlled receive (AMENDMENT-1.3.0 §13).

Items the SQLite suite cannot prove: role privileges (§13.1), true
multi-connection concurrency (§13.4), atomic failure on a real WAL
backend (§13.5), and append-only containment at the DB level.

Each test runs on a FRESH disposable docker postgres:16 database; the
core receive flow is parametrized to run twice on two fresh databases,
as required by the acceptance list. Skipped when docker is unavailable.
Local-only: no staging, no cloud services, no production contact.
"""

from __future__ import annotations

import shutil
import socket
import subprocess
import threading
import time
import uuid as uuid_mod
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, OperationalError, ProgrammingError

from app.config import settings

DOCKER_MISSING = shutil.which("docker") is None

pytestmark = pytest.mark.skipif(DOCKER_MISSING, reason="docker CLI unavailable")

IMAGE = "postgres:16"
PASSWORD = "stashtab"
DB_NAME = "f2_receive"
ROLES = {
    "stashtab_migrator": "mig",
    "stashtab_api": "api",
    "stashtab_worker": "wrk",
    "stashtab_readonly": "ro",
}
PRIVS = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")


def _ensure_pandas_importable() -> None:
    """Harness-only shim (see tests/test_f2_receive.py for rationale)."""
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


def _free_port() -> str:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return str(sock.getsockname()[1])


def _admin_url(port: str, db: str = "postgres") -> str:
    return f"postgresql://postgres:{PASSWORD}@127.0.0.1:{port}/{db}"


def _role_url(role: str, port: str) -> str:
    return f"postgresql://{role}:{ROLES[role]}@127.0.0.1:{port}/{DB_NAME}"


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


@pytest.fixture()
def f2_pg():
    """One fresh disposable postgres:16 database with the four roles,
    identity schema, live parents + truth tables (SELECT-only default),
    and the opt-in F2 envelope applied — everything via the reviewed
    migrators under stashtab_migrator."""
    from app.identity_schema.migrator import apply as apply_identity
    from app.inventory_live_schema.migrator import (
        F2_CLIENT_KEY_COLUMN,
        apply_f2_receive,
        apply_rehearsal,
    )

    port = _free_port()
    container = f"stashtab-f2-{uuid_mod.uuid4().hex[:8]}"
    try:
        _run(
            [
                "docker", "run", "-d", "--name", container,
                "-e", f"POSTGRES_PASSWORD={PASSWORD}",
                "-p", f"{port}:5432",
                IMAGE,
            ]
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        pytest.skip(f"docker container could not start: {exc}")

    engines: dict = {}
    try:
        admin = create_engine(_admin_url(port), pool_pre_ping=True)
        for _ in range(60):
            try:
                with admin.connect() as conn:
                    conn.execute(text("SELECT 1"))
                break
            except Exception:
                time.sleep(0.5)
        else:
            pytest.skip("postgres:16 did not become ready")
        with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text(f"CREATE DATABASE {DB_NAME}"))
        admin.dispose()

        db_engine = create_engine(_admin_url(port, DB_NAME), pool_pre_ping=True)
        with db_engine.begin() as conn:
            for role, secret in ROLES.items():
                conn.execute(
                    text(
                        f"CREATE ROLE {role} LOGIN PASSWORD '{secret}' "
                        "NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT"
                    )
                )
            conn.execute(
                text(
                    f"GRANT CONNECT ON DATABASE {DB_NAME} TO "
                    "stashtab_migrator, stashtab_api, stashtab_worker, stashtab_readonly"
                )
            )
            conn.execute(
                text(
                    "GRANT USAGE ON SCHEMA public TO "
                    "stashtab_migrator, stashtab_api, stashtab_worker, stashtab_readonly"
                )
            )
            conn.execute(text("REVOKE CREATE ON SCHEMA public FROM PUBLIC"))
            conn.execute(text("GRANT CREATE ON SCHEMA public TO stashtab_migrator"))
            conn.execute(
                text(
                    "REVOKE CREATE ON SCHEMA public FROM "
                    "stashtab_api, stashtab_worker, stashtab_readonly"
                )
            )
        db_engine.dispose()

        mig = create_engine(_role_url("stashtab_migrator", port), pool_pre_ping=True)
        apply_identity(mig)
        with mig.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO shops (id, name, slug, created_at, updated_at) VALUES "
                    "('shop-a', 'F2 Shop A', 'f2-a', NOW(), NOW()), "
                    "('shop-b', 'F2 Shop B', 'f2-b', NOW(), NOW())"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO shop_members "
                    "(id, shop_id, clerk_user_id, role, created_at, updated_at) VALUES "
                    "('mem-a', 'shop-a', 'owner-a', 'owner', NOW(), NOW()), "
                    "('mem-s', 'shop-a', 'staff-a', 'staff', NOW(), NOW()), "
                    "('mem-b', 'shop-b', 'owner-b', 'owner', NOW(), NOW())"
                )
            )
        apply_rehearsal(mig)
        applied = apply_f2_receive(mig)
        assert applied["columns"] == [f"purchase_record.{F2_CLIENT_KEY_COLUMN}"]
        assert applied["indexes"] == ["uq_purchase_record_shop_client_key"]
        assert applied["grants"]

        # Cutover seed for shop-a (api role is SELECT-only on the cutover
        # table; the staging cutover procedure itself is a separate unlock).
        # shop-b deliberately has NO cutover row (fail-closed).
        with mig.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO inventory_truth_cutover "
                    "(shop_id, generation, status, frozen_at, opened_at, created_at) "
                    "VALUES ('shop-a', 1, 'complete', NOW(), NOW(), NOW())"
                )
            )
        engines["mig"] = mig
        engines["api"] = create_engine(_role_url("stashtab_api", port), pool_pre_ping=True)
        engines["admin"] = create_engine(_admin_url(port, DB_NAME), pool_pre_ping=True)
        engines["worker"] = create_engine(_role_url("stashtab_worker", port), pool_pre_ping=True)
        engines["readonly"] = create_engine(
            _role_url("stashtab_readonly", port), pool_pre_ping=True
        )
        yield engines
        for engine in engines.values():
            engine.dispose()
    finally:
        subprocess.run(["docker", "rm", "-f", container], capture_output=True, text=True)


def _priv(engine, role: str, obj: str, priv: str) -> bool:
    with engine.connect() as conn:
        return bool(
            conn.execute(
                text("SELECT has_table_privilege(:role, :rel, :priv)"),
                {"role": role, "rel": f"public.{obj}", "priv": priv},
            ).scalar()
        )


# --- §13.1: runtime role boundary ------------------------------------------


class TestPrivilegeEnvelope:
    def test_envelope_grants_exact(self, f2_pg):
        admin = f2_pg["admin"]
        expected = {
            "inventory_item": {"SELECT", "INSERT", "UPDATE"},
            "purchase_record": {"SELECT", "INSERT"},
            "acquisition_lot": {"SELECT", "INSERT"},
            "inventory_event": {"SELECT", "INSERT"},
        }
        for table, want in expected.items():
            held = {p for p in PRIVS if _priv(admin, "stashtab_api", table, p)}
            assert held == want, table
        # Everything else stays SELECT-only (evidence of the per-table assert).
        for table in ("sale", "inventory_adjustment", "inventory_truth_cutover"):
            held = {p for p in PRIVS if _priv(admin, "stashtab_api", table, p)}
            assert held == {"SELECT"}, table
        for role in ("stashtab_worker", "stashtab_readonly"):
            for table in expected:
                assert {p for p in PRIVS if _priv(admin, role, table, p)} == set()

    def test_column_scoped_update_containment(self, f2_pg):
        api = f2_pg["api"]
        mig = f2_pg["mig"]
        with mig.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO inventory_item (shop_id, sku, name, cost, price, stock, "
                    "date_added, needs_update, needs_review, image_locked, sync_status, "
                    "paused_stock, game, created_at, updated_at) VALUES "
                    "('shop-a', 'PRIV-1', 'Priv Card', 1, 2, 1, NOW(), FALSE, FALSE, "
                    "FALSE, 'approved', 0, 'Pokemon', NOW(), NOW())"
                )
            )
        with api.begin() as conn:
            conn.execute(
                text("UPDATE inventory_item SET stock = 3, cost = 1.50 "
                     "WHERE shop_id = 'shop-a' AND sku = 'PRIV-1'")
            )
        for column in ("price", "sticker_price", "name", "sync_status"):
            with api.connect() as conn:
                with pytest.raises(DBAPIError):
                    conn.execute(
                        text(
                            f"UPDATE inventory_item SET {column} = NULL "
                            "WHERE shop_id = 'shop-a' AND sku = 'PRIV-1'"
                        )
                    )
                    conn.commit()

    def test_api_delete_truncate_and_assume_denied(self, f2_pg):
        api = f2_pg["api"]
        for table in ("inventory_item", "purchase_record", "acquisition_lot", "inventory_event"):
            with api.connect() as conn:
                with pytest.raises(DBAPIError):
                    conn.execute(text(f"DELETE FROM {table}"))
                    conn.commit()
            with api.connect() as conn:
                with pytest.raises(DBAPIError):
                    conn.execute(text(f"TRUNCATE {table}"))
        with api.connect() as conn:
            with pytest.raises(DBAPIError):
                conn.execute(text("SET ROLE stashtab_migrator"))
        # Append-only containment: truth rows are INSERT+SELECT only.
        with api.connect() as conn:
            with pytest.raises(DBAPIError):
                conn.execute(text("UPDATE acquisition_lot SET status = 'closed'"))
                conn.commit()

    def test_sequences_usage_granted(self, f2_pg):
        admin = f2_pg["admin"]
        for seq in (
            "inventory_item_id_seq",
            "purchase_record_id_seq",
            "acquisition_lot_id_seq",
            "inventory_event_id_seq",
        ):
            with admin.connect() as conn:
                assert bool(
                    conn.execute(
                        text("SELECT has_sequence_privilege('stashtab_api', :s, 'USAGE')"),
                        {"s": f"public.{seq}"},
                    ).scalar()
                ), seq

    def test_rerun_noop_and_injected_failure_leaves_nothing_partial(self):
        """fail_after + rerun semantics on their own fresh database."""
        from app.identity_schema.migrator import apply as apply_identity
        from app.inventory_live_schema.migrator import apply_f2_receive, apply_rehearsal

        port = _free_port()
        container = f"stashtab-f2fail-{uuid_mod.uuid4().hex[:8]}"
        try:
            _run(
                [
                    "docker", "run", "-d", "--name", container,
                    "-e", f"POSTGRES_PASSWORD={PASSWORD}",
                    "-p", f"{port}:5432",
                    IMAGE,
                ]
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            pytest.skip(f"docker container could not start: {exc}")
        try:
            admin = create_engine(_admin_url(port), pool_pre_ping=True)
            for _ in range(60):
                try:
                    with admin.connect() as conn:
                        conn.execute(text("SELECT 1"))
                    break
                except Exception:
                    time.sleep(0.5)
            with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                conn.execute(text(f"CREATE DATABASE {DB_NAME}"))
            admin.dispose()
            db_engine = create_engine(_admin_url(port, DB_NAME), pool_pre_ping=True)
            with db_engine.begin() as conn:
                for role, secret in ROLES.items():
                    conn.execute(
                        text(
                            f"CREATE ROLE {role} LOGIN PASSWORD '{secret}' "
                            "NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT"
                        )
                    )
                conn.execute(
                    text(
                        f"GRANT CONNECT ON DATABASE {DB_NAME} TO "
                        "stashtab_migrator, stashtab_api, stashtab_worker, stashtab_readonly"
                    )
                )
                conn.execute(
                    text(
                        "GRANT USAGE ON SCHEMA public TO "
                        "stashtab_migrator, stashtab_api, stashtab_worker, stashtab_readonly"
                    )
                )
                conn.execute(text("REVOKE CREATE ON SCHEMA public FROM PUBLIC"))
                conn.execute(text("GRANT CREATE ON SCHEMA public TO stashtab_migrator"))
            db_engine.dispose()

            mig = create_engine(_role_url("stashtab_migrator", port), pool_pre_ping=True)
            apply_identity(mig)
            apply_rehearsal(mig)

            with pytest.raises(RuntimeError, match="injected f2 failure"):
                apply_f2_receive(mig, fail_after="grants")
            # All-or-nothing: no column, no index, grants unchanged.
            with mig.connect() as conn:
                assert conn.execute(
                    text(
                        "SELECT COUNT(*) FROM information_schema.columns "
                        "WHERE table_name = 'purchase_record' "
                        "AND column_name = 'client_idempotency_key'"
                    )
                ).scalar() == 0
                assert conn.execute(
                    text(
                        "SELECT COUNT(*) FROM pg_indexes "
                        "WHERE indexname = 'uq_purchase_record_shop_client_key'"
                    )
                ).scalar() == 0
                assert not _priv(mig, "stashtab_api", "purchase_record", "INSERT")

            first = apply_f2_receive(mig)
            assert first["columns"] and first["indexes"] and first["grants"]
            second = apply_f2_receive(mig)
            assert second["columns"] == []
            assert second["indexes"] == []
            mig.dispose()
        finally:
            subprocess.run(["docker", "rm", "-f", container], capture_output=True, text=True)

    def test_rollback_grants_restores_select_only_and_preserves_evidence(self, f2_pg):
        from app.inventory_live_schema.migrator import rollback_f2_receive_grants

        api = f2_pg["api"]
        mig = f2_pg["mig"]
        with api.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO purchase_record "
                    "(shop_id, sku, quantity, cost_per_unit, timestamp, created_at, "
                    "updated_at, client_idempotency_key) VALUES "
                    "('shop-a', 'EVIDENCE-1', 1, 1.00, NOW(), NOW(), NOW(), :key)"
                ),
                {"key": str(uuid_mod.uuid4())},
            )
        rollback_f2_receive_grants(mig)
        # SELECT survives; every write is denied again.
        with api.connect() as conn:
            assert conn.execute(
                text("SELECT COUNT(*) FROM purchase_record WHERE sku = 'EVIDENCE-1'")
            ).scalar() == 1
        with api.connect() as conn:
            with pytest.raises(DBAPIError):
                conn.execute(
                    text(
                        "INSERT INTO purchase_record (shop_id, sku, quantity, "
                        "cost_per_unit, timestamp, created_at, updated_at) VALUES "
                        "('shop-a', 'DENIED-1', 1, 1, NOW(), NOW(), NOW())"
                    )
                )
                conn.commit()
        # Evidence preserved: column stays, row stays (§12 rollback policy).
        with mig.connect() as conn:
            assert conn.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_name = 'purchase_record' "
                    "AND column_name = 'client_idempotency_key'"
                )
            ).scalar() == 1


# --- §13.2/3/5/8 through the endpoint as stashtab_api ----------------------


def _decode(authorization):
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return authorization.split(" ", 1)[1].strip()


def _client(f2_pg, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    from app.database import get_db
    from app.errors import FeatureNotReadyError
    from app.main import (
        feature_not_ready_handler,
        operational_error_handler,
        programming_error_handler,
    )
    from app.routers import admin as admin_router

    monkeypatch.setattr(settings, "app_env", "local")
    monkeypatch.setattr(settings, "stashtab_allow_dev_identity", False)
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr("app.auth.identity.decode_bearer_user_id", _decode)
    monkeypatch.setattr("app.auth.clerk.decode_bearer_user_id", _decode)

    session_factory = sessionmaker(bind=f2_pg["api"], autocommit=False, autoflush=False)
    app = FastAPI()
    app.include_router(admin_router.router, prefix="/api/v1")
    app.add_exception_handler(FeatureNotReadyError, feature_not_ready_handler)
    app.add_exception_handler(OperationalError, operational_error_handler)
    app.add_exception_handler(ProgrammingError, programming_error_handler)

    def override_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    return TestClient(app, raise_server_exceptions=False)


def _headers(user="owner-a", shop="shop-a"):
    return {"X-Shop-Id": shop, "Authorization": f"Bearer {user}"}


def _payload(**overrides):
    body = {
        "sku": "F2-TEST-0001",
        "name": "F2 Synthetic Test Card — staging proof",
        "quantity": 2,
        "unit_cost": 0.01,
        "set_name": "Synthetic Set",
        "sequence_number": "1",
    }
    body.update(overrides)
    return body


RECEIVE_URL = "/api/v1/admin/inventory/receive"


@pytest.mark.parametrize("fresh_db", ["first-fresh-db", "second-fresh-db"])
class TestReceiveFlowPG:
    """§13 requires the PostgreSQL proof twice on fresh disposable databases."""

    def test_receive_replay_conflict_and_fail_closed(self, f2_pg, monkeypatch, fresh_db):
        client = _client(f2_pg, monkeypatch)
        key = str(uuid_mod.uuid4())
        headers = {**_headers(), "Idempotency-Key": key}

        first = client.post(RECEIVE_URL, json=_payload(), headers=headers)
        assert first.status_code == 200, first.text
        body = first.json()
        assert body["result"] == "created"

        admin = f2_pg["admin"]
        record_id = body["purchase_record_id"]
        expected_key = f"purchase_record:shop-a:{record_id}"
        with admin.connect() as conn:
            assert conn.execute(
                text(
                    "SELECT COUNT(*) FROM acquisition_lot "
                    "WHERE shop_id = 'shop-a' AND idempotency_key = :k"
                ),
                {"k": expected_key},
            ).scalar() == 1
            assert conn.execute(
                text(
                    "SELECT COUNT(*) FROM inventory_event "
                    "WHERE shop_id = 'shop-a' AND idempotency_key = :k"
                ),
                {"k": expected_key},
            ).scalar() == 1
            remaining = conn.execute(
                text(
                    "SELECT COALESCE(SUM(quantity_delta), 0) FROM inventory_event "
                    "WHERE shop_id = 'shop-a' AND event_type = 'receive'"
                )
            ).scalar()
            stock = conn.execute(
                text(
                    "SELECT stock FROM inventory_item "
                    "WHERE shop_id = 'shop-a' AND sku = 'F2-TEST-0001'"
                )
            ).scalar()
        assert int(remaining) == int(stock)  # reconciliation proof

        replay = client.post(RECEIVE_URL, json=_payload(), headers=headers)
        assert replay.status_code == 200
        assert replay.json()["result"] == "no_op"

        conflict = client.post(RECEIVE_URL, json=_payload(quantity=9), headers=headers)
        assert conflict.status_code == 409
        with admin.connect() as conn:
            assert conn.execute(
                text("SELECT COUNT(*) FROM purchase_record WHERE shop_id = 'shop-a'")
            ).scalar() == 1

        # Missing Idempotency-Key → 422, zero writes.
        missing = client.post(RECEIVE_URL, json=_payload(sku="NOKEY-1"), headers=_headers())
        assert missing.status_code == 422

        # shop-b has no cutover row → controlled 503, fail-closed.
        gated = client.post(
            RECEIVE_URL,
            json=_payload(),
            headers={**_headers(user="owner-b", shop="shop-b"),
                     "Idempotency-Key": str(uuid_mod.uuid4())},
        )
        assert gated.status_code == 503
        assert gated.json()["error"] == "FEATURE_NOT_READY"

    def test_injected_failure_commits_zero_rows(self, f2_pg, monkeypatch, fresh_db):
        from app.logic import controlled_receive as cr

        client = _client(f2_pg, monkeypatch)

        def boom(*_args, **_kwargs):
            raise RuntimeError("injected failure mid-transaction")

        monkeypatch.setattr(cr.truth, "record_purchase_receive", boom)
        resp = client.post(
            RECEIVE_URL,
            json=_payload(sku="FAIL-PG-1"),
            headers={**_headers(), "Idempotency-Key": str(uuid_mod.uuid4())},
        )
        assert resp.status_code == 500
        with f2_pg["admin"].connect() as conn:
            for table in ("inventory_item", "purchase_record", "acquisition_lot",
                          "inventory_event"):
                assert conn.execute(
                    text(f"SELECT COUNT(*) FROM {table} WHERE sku = 'FAIL-PG-1'")
                ).scalar() == 0, table

    def test_concurrent_identical_receives_exactly_one_pair(
        self, f2_pg, monkeypatch, fresh_db
    ):
        from sqlalchemy.orm import sessionmaker

        from app.logic.controlled_receive import receive_controlled

        maker = sessionmaker(bind=f2_pg["api"], autocommit=False, autoflush=False)
        key = str(uuid_mod.uuid4())
        barrier = threading.Barrier(2)

        def worker():
            session = maker()
            try:
                barrier.wait(timeout=30)
                return receive_controlled(
                    session,
                    shop_id="shop-a",
                    client_key=key,
                    sku="RACE-PG-1",
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
        with f2_pg["admin"].connect() as conn:
            assert conn.execute(
                text(
                    "SELECT COUNT(*) FROM purchase_record "
                    "WHERE client_idempotency_key = :k"
                ),
                {"k": key},
            ).scalar() == 1
            assert conn.execute(
                text("SELECT COUNT(*) FROM acquisition_lot WHERE sku = 'RACE-PG-1'")
            ).scalar() == 1
            assert conn.execute(
                text("SELECT COUNT(*) FROM inventory_event WHERE sku = 'RACE-PG-1'")
            ).scalar() == 1
