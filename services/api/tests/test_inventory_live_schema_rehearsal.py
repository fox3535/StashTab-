"""Local PostgreSQL 16 rehearsal for slice-02 live parents plus inventory-truth."""

from __future__ import annotations

import subprocess
import time
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, ProgrammingError

from app.config import settings
from app.database import init_db, startup_schema_mutation_forbidden
from app.identity_schema.migrator import apply as apply_identity
from app.inventory_live_schema.migrator import (
    LIVE_TABLES,
    REHEARSAL_TABLES,
    apply,
    apply_rehearsal,
    rollback,
    rollback_rehearsal,
)
from app.inventory_truth.migrator import apply as apply_truth

IMAGE = "postgres:16"
CONTAINER = f"stashtab-inv-schema-{uuid.uuid4().hex[:8]}"
PORT = "55436"
PASSWORD = "stashtab"
DB_NAME = "inventory_rehearsal"
ROLES = {
    "stashtab_migrator": "mig",
    "stashtab_api": "api",
    "stashtab_worker": "wrk",
    "stashtab_readonly": "ro",
}
IDENTITY = {"shops", "shop_members"}
PRIVS = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")


def _admin_url(db: str = "postgres") -> str:
    return f"postgresql://postgres:{PASSWORD}@127.0.0.1:{PORT}/{db}"


def _role_url(role: str) -> str:
    return f"postgresql://{role}:{ROLES[role]}@127.0.0.1:{PORT}/{DB_NAME}"


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


@pytest.fixture(scope="module")
def pg16():
    _run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            CONTAINER,
            "-e",
            f"POSTGRES_PASSWORD={PASSWORD}",
            "-p",
            f"{PORT}:5432",
            IMAGE,
        ]
    )
    try:
        admin = create_engine(_admin_url(), pool_pre_ping=True)
        for _ in range(40):
            try:
                with admin.connect() as conn:
                    conn.execute(text("SELECT 1"))
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("postgres:16 did not become ready")
        with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text(f"CREATE DATABASE {DB_NAME}"))
        admin.dispose()
        db_engine = create_engine(_admin_url(DB_NAME), pool_pre_ping=True)
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
                    "GRANT CONNECT ON DATABASE inventory_rehearsal TO "
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
            conn.execute(text("SET ROLE stashtab_migrator"))
            conn.execute(
                text(
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                    "GRANT ALL ON TABLES TO PUBLIC"
                )
            )
            for role in ("stashtab_api", "stashtab_worker", "stashtab_readonly"):
                conn.execute(
                    text(
                        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                        f"GRANT ALL ON TABLES TO {role}"
                    )
                )
            conn.execute(text("RESET ROLE"))
        yield db_engine
        db_engine.dispose()
    finally:
        subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True, text=True)


@pytest.fixture
def migrator_engine():
    engine = create_engine(_role_url("stashtab_migrator"), pool_pre_ping=True)
    yield engine
    engine.dispose()


def _tables(engine) -> list[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' ORDER BY 1"
            )
        )
        return [r[0] for r in rows]


def _roles(engine) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT rolname FROM pg_roles WHERE rolname LIKE 'stashtab_%'")
        )
        return {r[0] for r in rows}


def _priv(engine, role: str, table: str, priv: str) -> bool:
    with engine.connect() as conn:
        return bool(
            conn.execute(
                text("SELECT has_table_privilege(:role, :rel, :priv)"),
                {"role": role, "rel": f"public.{table}", "priv": priv},
            ).scalar()
        )


def _shop_counts(engine) -> tuple[int, int]:
    with engine.connect() as conn:
        shops = conn.execute(text("SELECT COUNT(*) FROM shops")).scalar()
        members = conn.execute(text("SELECT COUNT(*) FROM shop_members")).scalar()
    return int(shops), int(members)


def _insert_shops(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO shops (id, name, slug, created_at, updated_at) VALUES "
                "('shop-a', 'Smoke Shop A', 'smoke-a', NOW(), NOW()), "
                "('shop-b', 'Smoke Shop B', 'smoke-b', NOW(), NOW()) "
                "ON CONFLICT (id) DO NOTHING"
            )
        )
        conn.execute(
            text(
                "INSERT INTO shop_members "
                "(id, shop_id, clerk_user_id, role, created_at, updated_at) VALUES "
                "('mem-a', 'shop-a', 'owner-a', 'owner', NOW(), NOW()), "
                "('mem-b', 'shop-b', 'owner-b', 'owner', NOW(), NOW()) "
                "ON CONFLICT (id) DO NOTHING"
            )
        )


def _reset(engine) -> None:
    names = set(_tables(engine))
    if any(name in names for name in REHEARSAL_TABLES):
        rollback_rehearsal(engine)
    apply_identity(engine)
    _insert_shops(engine)


def _insert_item(conn, shop_id: str, sku: str):
    return conn.execute(
        text(
            "INSERT INTO inventory_item ("
            "shop_id, sku, name, cost, price, stock, date_added, needs_update, "
            "needs_review, image_locked, sync_status, paused_stock, game, "
            "created_at, updated_at"
            ") VALUES ("
            ":shop, :sku, 'Card', 1, 2, 1, NOW(), FALSE, FALSE, FALSE, "
            "'paused', 0, 'Pokemon', NOW(), NOW()) RETURNING id"
        ),
        {"shop": shop_id, "sku": sku},
    ).scalar()


def _insert_sale(conn, shop_id: str, sku: str):
    return conn.execute(
        text(
            "INSERT INTO sale ("
            "shop_id, sku, timestamp, trade_in_value, processing_fees, "
            "trade_credit_deduction, net_revenue, game, is_reconciled, "
            "created_at, updated_at"
            ") VALUES ("
            ":shop, :sku, NOW(), 0, 0, 0, 0, 'Pokemon', FALSE, NOW(), NOW()) "
            "RETURNING id"
        ),
        {"shop": shop_id, "sku": sku},
    ).scalar()


def test_live_apply_adds_only_three_parents(pg16, migrator_engine):
    _reset(migrator_engine)
    first = apply(migrator_engine)
    assert set(first["tables"]) == set(LIVE_TABLES)
    assert set(_tables(pg16)) == IDENTITY | set(LIVE_TABLES)
    second = apply(migrator_engine)
    assert second["tables"] == []
    assert set(_tables(pg16)) == IDENTITY | set(LIVE_TABLES)


def test_truth_apply_requires_live_parents(pg16, migrator_engine):
    _reset(migrator_engine)
    with pytest.raises(Exception):
        apply_truth(migrator_engine)
    assert set(_tables(pg16)) == IDENTITY


def test_rehearsal_table_index_fk_and_privilege_inventory(pg16, migrator_engine):
    _reset(migrator_engine)
    apply_rehearsal(migrator_engine)
    assert set(_tables(pg16)) == IDENTITY | set(REHEARSAL_TABLES)
    with pg16.connect() as conn:
        for table in LIVE_TABLES:
            owner = conn.execute(
                text("SELECT tableowner FROM pg_tables WHERE tablename = :t"),
                {"t": table},
            ).scalar()
            assert owner == "stashtab_migrator"
            unique = conn.execute(
                text(
                    "SELECT 1 FROM pg_indexes WHERE tablename = :t AND indexname = :n"
                ),
                {"t": table, "n": f"uq_{table}_shop_id"},
            ).first()
            assert unique is not None
            fk = conn.execute(
                text("SELECT 1 FROM pg_constraint WHERE conname = :n AND contype = 'f'"),
                {"n": f"fk_{table}_shop_id"},
            ).first()
            assert fk is not None
        show_fk = conn.execute(
            text(
                "SELECT 1 FROM pg_constraint c "
                "JOIN pg_class t ON t.oid = c.conrelid "
                "JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey) "
                "WHERE t.relname = 'sale' AND a.attname = 'show_session_id' AND c.contype = 'f'"
            )
        ).first()
        assert show_fk is None
    for table in REHEARSAL_TABLES:
        held = {priv for priv in PRIVS if _priv(pg16, "stashtab_api", table, priv)}
        assert held == {"SELECT"}
        for role in ("stashtab_worker", "stashtab_readonly"):
            assert {priv for priv in PRIVS if _priv(pg16, role, table, priv)} == set()


def test_api_select_only_and_cannot_write_or_ddl(pg16, migrator_engine):
    _reset(migrator_engine)
    apply_rehearsal(migrator_engine)
    with migrator_engine.begin() as conn:
        _insert_item(conn, "shop-a", "SKU-A-1")
    api = create_engine(_role_url("stashtab_api"), pool_pre_ping=True)
    with api.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM inventory_item")).scalar() == 1
    with api.connect() as conn:
        with pytest.raises((ProgrammingError, DBAPIError)):
            _insert_item(conn, "shop-a", "SKU-A-2")
            conn.commit()
    with api.connect() as conn:
        with pytest.raises((ProgrammingError, DBAPIError)):
            conn.execute(text("UPDATE inventory_item SET stock = 9"))
            conn.commit()
    with api.connect() as conn:
        with pytest.raises((ProgrammingError, DBAPIError)):
            conn.execute(text("DELETE FROM inventory_item"))
            conn.commit()
    with api.connect() as conn:
        with pytest.raises((ProgrammingError, DBAPIError)):
            conn.execute(text("TRUNCATE inventory_item"))
        with pytest.raises((ProgrammingError, DBAPIError)):
            conn.execute(text("CREATE TABLE extra_forbidden (id int)"))
        with pytest.raises((ProgrammingError, DBAPIError)):
            conn.execute(text("ALTER TABLE sale ADD COLUMN extra int"))
        with pytest.raises((ProgrammingError, DBAPIError)):
            conn.execute(text("SET ROLE stashtab_migrator"))
    worker = create_engine(_role_url("stashtab_worker"), pool_pre_ping=True)
    with worker.connect() as conn:
        with pytest.raises((ProgrammingError, DBAPIError)):
            conn.execute(text("SELECT COUNT(*) FROM inventory_item"))
    readonly = create_engine(_role_url("stashtab_readonly"), pool_pre_ping=True)
    with readonly.connect() as conn:
        with pytest.raises((ProgrammingError, DBAPIError)):
            conn.execute(text("SELECT COUNT(*) FROM sale"))
    api.dispose()
    worker.dispose()
    readonly.dispose()


def test_unknown_shop_and_cross_shop_fks_fail(pg16, migrator_engine):
    _reset(migrator_engine)
    apply_rehearsal(migrator_engine)
    with migrator_engine.begin() as conn:
        with pytest.raises(Exception):
            _insert_item(conn, "missing-shop", "SKU-X")
    with migrator_engine.begin() as conn:
        item_a = _insert_item(conn, "shop-a", "SKU-A-1")
        _insert_item(conn, "shop-b", "SKU-B-1")
        sale_b = _insert_sale(conn, "shop-b", "SKU-B-1")
        conn.execute(
            text(
                "INSERT INTO purchase_record "
                "(shop_id, sku, quantity, cost_per_unit, timestamp, created_at, updated_at) "
                "VALUES ('shop-a', 'SKU-A-1', 1, 1, NOW(), NOW(), NOW())"
            )
        )
    with migrator_engine.begin() as conn:
        with pytest.raises(Exception):
            conn.execute(
                text(
                    "INSERT INTO acquisition_lot ("
                    "shop_id, sku, inventory_item_id, source_type, idempotency_key, "
                    "quantity_acquired, unit_cost, status, created_at"
                    ") VALUES ("
                    "'shop-b', 'SKU-B-1', :item, 'purchase_record', 'k-cross', 1, 1.00, "
                    "'active', NOW())"
                ),
                {"item": item_a},
            )
    with migrator_engine.begin() as conn:
        with pytest.raises(Exception):
            conn.execute(
                text(
                    "INSERT INTO inventory_event ("
                    "shop_id, sku, sale_id, event_type, quantity_delta, "
                    "idempotency_key, created_at"
                    ") VALUES ("
                    "'shop-a', 'SKU-A-1', :sale, 'sell', -1, 'e-cross', NOW())"
                ),
                {"sale": sale_b},
            )


def test_second_rehearsal_apply_is_noop(pg16, migrator_engine):
    _reset(migrator_engine)
    apply_rehearsal(migrator_engine)
    second = apply_rehearsal(migrator_engine)
    assert second["live"]["tables"] == []
    assert second["truth"].get("tables", []) == []
    assert set(_tables(pg16)) == IDENTITY | set(REHEARSAL_TABLES)


@pytest.mark.parametrize("stage", ["tables", "uniques", "fks"])
def test_live_injected_failure_leaves_identity_only(pg16, migrator_engine, stage):
    _reset(migrator_engine)
    with pytest.raises(RuntimeError, match="injected"):
        apply(migrator_engine, fail_after=stage)
    assert set(_tables(pg16)) == IDENTITY
    assert _shop_counts(migrator_engine) == (2, 2)


@pytest.mark.parametrize("stage", ["indexes", "tables", "triggers"])
def test_truth_injected_failure_keeps_live_parents(pg16, migrator_engine, stage):
    _reset(migrator_engine)
    apply(migrator_engine)
    with pytest.raises(RuntimeError, match="injected"):
        apply_truth(migrator_engine, fail_after=stage)
    assert set(_tables(pg16)) == IDENTITY | set(LIVE_TABLES)
    assert _shop_counts(migrator_engine) == (2, 2)


def test_rollback_removes_truth_then_live_and_keeps_identity(pg16, migrator_engine):
    _reset(migrator_engine)
    apply_rehearsal(migrator_engine)
    before_roles = _roles(pg16)
    shops_before, members_before = _shop_counts(migrator_engine)
    result = rollback_rehearsal(migrator_engine)
    dropped = result["dropped"]
    assert dropped.index("inventory_adjustment") < dropped.index("inventory_item")
    assert dropped.index("sale") < dropped.index("inventory_item")
    assert set(_tables(pg16)) == IDENTITY
    assert _shop_counts(migrator_engine) == (shops_before, members_before) == (2, 2)
    assert _roles(pg16) == before_roles


def test_startup_creates_no_tables(pg16, migrator_engine, monkeypatch):
    _reset(migrator_engine)
    apply_rehearsal(migrator_engine)
    before = set(_tables(pg16))
    monkeypatch.setattr(settings, "app_env", "staging")
    assert startup_schema_mutation_forbidden() is True
    with pytest.raises(RuntimeError, match="forbidden"):
        init_db()
    assert set(_tables(pg16)) == before


def test_live_rollback_blocked_until_truth_removed(pg16, migrator_engine):
    _reset(migrator_engine)
    apply_rehearsal(migrator_engine)
    with pytest.raises(RuntimeError, match="truth tables"):
        rollback(migrator_engine)
    assert set(REHEARSAL_TABLES).issubset(set(_tables(pg16)))
