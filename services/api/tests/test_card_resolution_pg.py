from __future__ import annotations

import subprocess
import time
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DatabaseError, ProgrammingError

from app.card_resolution.migrator import TABLES as CR_TABLES
from app.card_resolution.migrator import apply as apply_card_resolution
from app.card_resolution.migrator import rollback as rollback_card_resolution
from app.identity_schema.migrator import apply as apply_identity
from app.inventory_live_schema.migrator import REHEARSAL_TABLES, apply_rehearsal
from app.models import Base

IMAGE = "postgres:16"
CONTAINER = f"stashtab-cr-schema-{uuid.uuid4().hex[:8]}"
PORT = "55437"
PASSWORD = "stashtab"
DB_NAME = "card_resolution"
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
                    "GRANT CONNECT ON DATABASE card_resolution TO "
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
        yield db_engine
        db_engine.dispose()
    finally:
        subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True, text=True)


@pytest.fixture
def migrator_engine(pg16):
    engine = create_engine(_role_url("stashtab_migrator"), pool_pre_ping=True)
    yield engine
    engine.dispose()


def _tables(engine) -> set[str]:
    with engine.connect() as conn:
        return set(conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'")).scalars())


def _priv(engine, role: str, table: str, priv: str) -> bool:
    with engine.connect() as conn:
        return bool(
            conn.execute(
                text("SELECT has_table_privilege(:role, :rel, :priv)"),
                {"role": role, "rel": f"public.{table}", "priv": priv},
            ).scalar()
        )


def test_apply_rollback_preserves_identity_and_inventory(pg16, migrator_engine):
    apply_identity(migrator_engine)
    apply_rehearsal(migrator_engine)
    required = IDENTITY | set(REHEARSAL_TABLES)
    assert len(required) == 13
    before = _tables(pg16)
    assert required <= before
    first = apply_card_resolution(migrator_engine)
    assert set(first["tables"]) == set(CR_TABLES)
    second = apply_card_resolution(migrator_engine)
    assert second["tables"] == []
    assert set(CR_TABLES) <= _tables(pg16)
    dropped = rollback_card_resolution(migrator_engine)
    assert set(dropped["dropped"]) == set(CR_TABLES)
    after = _tables(pg16)
    assert required <= after
    assert set(CR_TABLES).isdisjoint(after)
    assert after >= required


def test_api_cannot_rewrite_evidence_and_has_expected_grants(pg16, migrator_engine):
    if "shops" not in _tables(pg16):
        apply_identity(migrator_engine)
    apply_card_resolution(migrator_engine)
    for table in CR_TABLES:
        assert _priv(pg16, "stashtab_api", table, "SELECT") is True
        assert _priv(pg16, "stashtab_worker", table, "SELECT") is False
        assert _priv(pg16, "stashtab_readonly", table, "SELECT") is False
        for priv in ("DELETE", "TRUNCATE"):
            assert _priv(pg16, "stashtab_api", table, priv) is False
    assert _priv(pg16, "stashtab_api", "card_resolution_evidence", "UPDATE") is False
    assert _priv(pg16, "stashtab_api", "card_resolution_audit", "UPDATE") is False
    assert _priv(pg16, "stashtab_api", "card_resolution_catalog", "INSERT") is False
    api = create_engine(_role_url("stashtab_api"), pool_pre_ping=True)
    with pg16.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO shops (id, name, slug, created_at, updated_at) "
                "VALUES ('shop-a', 'A', 'a', NOW(), NOW()) ON CONFLICT (id) DO NOTHING"
            )
        )
    migrator = create_engine(_role_url("stashtab_migrator"), pool_pre_ping=True)
    with migrator.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO card_resolution_intake ("
                "id, shop_id, intake_id, evidence_hash, result, state, reason_codes, "
                "confidence_components, ruleset_version, contract_version, justtcg_invoked, created_at, updated_at"
                ") VALUES ("
                "'in-1', 'shop-a', 'req-1', 'abc', 'accepted', 'accepted', '[]', '{}', "
                "'identity-score-v0', '1.0.0', FALSE, NOW(), NOW())"
            )
        )
        conn.execute(
            text(
                "INSERT INTO card_resolution_evidence ("
                "id, shop_id, intake_pk, intake_id, payload_json, created_at"
                ") VALUES ('ev-1', 'shop-a', 'in-1', 'req-1', '{}', NOW())"
            )
        )
    with pytest.raises((ProgrammingError, DatabaseError)):
        with api.begin() as conn:
            conn.execute(text("UPDATE card_resolution_evidence SET payload_json='tamper' WHERE id='ev-1'"))
    with pytest.raises((ProgrammingError, DatabaseError)):
        with api.begin() as conn:
            conn.execute(text("DELETE FROM card_resolution_evidence WHERE id='ev-1'"))
    with pytest.raises((ProgrammingError, DatabaseError)):
        with api.begin() as conn:
            conn.execute(text("TRUNCATE card_resolution_evidence"))
    with migrator.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO card_resolution_audit ("
                "id, shop_id, intake_pk, action, payload_json, created_at"
                ") VALUES ('au-1', 'shop-a', 'in-1', 'intake_accepted', '{}', NOW())"
            )
        )
    with pytest.raises((ProgrammingError, DatabaseError)):
        with api.begin() as conn:
            conn.execute(text("UPDATE card_resolution_audit SET payload_json='tamper' WHERE id='au-1'"))
    with pytest.raises((ProgrammingError, DatabaseError)):
        with api.begin() as conn:
            conn.execute(text("DELETE FROM card_resolution_audit WHERE id='au-1'"))
    with pytest.raises((ProgrammingError, DatabaseError)):
        with api.begin() as conn:
            conn.execute(text("TRUNCATE card_resolution_audit"))
    with pg16.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO shops (id, name, slug, created_at, updated_at) "
                "VALUES ('shop-b', 'B', 'b', NOW(), NOW()) ON CONFLICT (id) DO NOTHING"
            )
        )
    with pytest.raises((ProgrammingError, DatabaseError)):
        with migrator.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO card_resolution_evidence ("
                    "id, shop_id, intake_pk, intake_id, payload_json, created_at"
                    ") VALUES ('ev-x', 'shop-b', 'in-1', 'req-1', '{}', NOW())"
                )
            )
    api.dispose()
    migrator.dispose()


def test_application_base_create_all_skips_card_resolution(pg16):
    names_before = _tables(pg16)
    Base.metadata.create_all(pg16)
    created = _tables(pg16) - names_before
    assert set(CR_TABLES).isdisjoint(created)
    assert set(CR_TABLES).isdisjoint(Base.metadata.tables)
