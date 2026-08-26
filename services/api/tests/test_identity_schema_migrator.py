"""Prove the identity kernel migrator on disposable PostgreSQL 16."""

from __future__ import annotations

import os
import subprocess
import time
import uuid
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.auth.clerk import ClerkAuthError
from app.config import settings
from app.database import get_db, init_db, startup_schema_mutation_forbidden
from app.identity_schema.migrator import apply, rollback
from app.models import Shop, ShopMember
from app.models.base import new_uuid
from app.routers import shops as shops_router

IMAGE = "postgres:16"
CONTAINER = f"stashtab-id-schema-{uuid.uuid4().hex[:8]}"
PORT = "55434"
PASSWORD = "stashtab"
DB_NAME = "identity_kernel"
ROLES = {
    "stashtab_migrator": "mig",
    "stashtab_api": "api",
    "stashtab_worker": "wrk",
    "stashtab_readonly": "ro",
}


def _admin_url(db: str = "postgres") -> str:
    return f"postgresql://postgres:{PASSWORD}@127.0.0.1:{PORT}/{db}"


def _role_url(role: str) -> str:
    return f"postgresql://{role}:{ROLES[role]}@127.0.0.1:{PORT}/{DB_NAME}"


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kwargs)


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
                    "GRANT CONNECT ON DATABASE identity_kernel TO "
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


@pytest.fixture(autouse=True)
def _reset_kernel(pg16):
    rollback(pg16)
    yield


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
        rows = conn.execute(text("SELECT rolname FROM pg_roles WHERE rolname LIKE 'stashtab_%'"))
        return {r[0] for r in rows}


def _decode(authorization):
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    if token == "invalid":
        raise ClerkAuthError("Invalid session")
    return token


def _has_priv(engine, role: str, table: str, priv: str) -> bool:
    with engine.connect() as conn:
        return bool(
            conn.execute(
                text("SELECT has_table_privilege(:role, :rel, :priv)"),
                {"role": role, "rel": f"public.{table}", "priv": priv},
            ).scalar()
        )


def _api_client(engine, monkeypatch):
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(settings, "app_env", "staging")
    monkeypatch.setattr(settings, "stashtab_allow_dev_identity", False)
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "clerk_jwt_issuer", "https://clerk.example")
    monkeypatch.setattr("app.auth.identity.decode_bearer_user_id", _decode)
    monkeypatch.setattr("app.auth.clerk.decode_bearer_user_id", _decode)
    app = FastAPI()
    app.include_router(shops_router.router, prefix="/api/v1")

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def test_permissive_defaults_are_reproduced(pg16, migrator_engine):
    with pg16.begin() as conn:
        conn.execute(text("SET ROLE stashtab_migrator"))
        conn.execute(
            text(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO PUBLIC"
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
    with migrator_engine.begin() as conn:
        conn.execute(text("CREATE TABLE privilege_probe (id int PRIMARY KEY)"))
    try:
        assert _has_priv(pg16, "stashtab_api", "privilege_probe", "UPDATE")
        assert _has_priv(pg16, "stashtab_api", "privilege_probe", "DELETE")
    finally:
        with migrator_engine.begin() as conn:
            conn.execute(text("DROP TABLE privilege_probe"))


def test_migrator_creates_two_tables_and_is_idempotent(pg16, migrator_engine):
    first = apply(migrator_engine)
    assert set(_tables(pg16)) == {"shop_members", "shops"}
    assert set(first["tables"]) == {"shop_members", "shops"}
    second = apply(migrator_engine)
    assert second["tables"] == []
    assert set(_tables(pg16)) == {"shop_members", "shops"}
    with pg16.connect() as conn:
        owner = conn.execute(
            text("SELECT tableowner FROM pg_tables WHERE tablename = 'shops'")
        ).scalar()
        assert owner == "stashtab_migrator"
        for table in ("shops", "shop_members"):
            held = {
                priv
                for priv in (
                    "SELECT",
                    "INSERT",
                    "UPDATE",
                    "DELETE",
                    "TRUNCATE",
                    "REFERENCES",
                    "TRIGGER",
                )
                if conn.execute(
                    text("SELECT has_table_privilege('stashtab_api', :rel, :priv)"),
                    {"rel": f"public.{table}", "priv": priv},
                ).scalar()
            }
            assert held == {"SELECT", "INSERT"}


def test_constraints_fk_unique_and_role_check(pg16, migrator_engine):
    apply(migrator_engine)
    migrator = create_engine(_role_url("stashtab_migrator"), pool_pre_ping=True)
    with migrator.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO shops (id, name, slug, created_at, updated_at) "
                "VALUES ('s1', 'A', 'alpha', NOW(), NOW())"
            )
        )
        conn.execute(
            text(
                "INSERT INTO shop_members (id, shop_id, clerk_user_id, role, created_at, updated_at) "
                "VALUES ('m1', 's1', 'user-a', 'owner', NOW(), NOW())"
            )
        )
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO shops (id, name, slug, created_at, updated_at) "
                    "VALUES ('s2', 'B', 'alpha', NOW(), NOW())"
                )
            )
    with migrator.begin() as conn:
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO shop_members (id, shop_id, clerk_user_id, role, created_at, updated_at) "
                    "VALUES ('m2', 's1', 'user-a', 'staff', NOW(), NOW())"
                )
            )
    with migrator.begin() as conn:
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO shop_members (id, shop_id, clerk_user_id, role, created_at, updated_at) "
                    "VALUES ('m3', 'missing', 'user-b', 'owner', NOW(), NOW())"
                )
            )
    with migrator.begin() as conn:
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO shop_members (id, shop_id, clerk_user_id, role, created_at, updated_at) "
                    "VALUES ('m4', 's1', 'user-c', 'admin', NOW(), NOW())"
                )
            )
    migrator.dispose()


def test_shop_and_owner_commit_atomically(pg16, migrator_engine, monkeypatch):
    apply(migrator_engine)
    api = create_engine(_role_url("stashtab_api"), pool_pre_ping=True)
    client = _api_client(api, monkeypatch)
    res = client.post(
        "/api/v1/shops",
        json={"name": "Nova", "slug": "nova"},
        headers={"Authorization": "Bearer user-c"},
    )
    assert res.status_code == 200
    shop_id = res.json()["id"]
    with api.connect() as conn:
        shops = conn.execute(text("SELECT COUNT(*) FROM shops WHERE slug = 'nova'")).scalar()
        members = conn.execute(
            text(
                "SELECT COUNT(*) FROM shop_members "
                "WHERE shop_id = :id AND clerk_user_id = 'user-c' AND role = 'owner'"
            ),
            {"id": shop_id},
        ).scalar()
    assert shops == 1
    assert members == 1
    dup = client.post(
        "/api/v1/shops",
        json={"name": "Nova2", "slug": "nova"},
        headers={"Authorization": "Bearer user-d"},
    )
    assert dup.status_code == 409
    with api.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM shops WHERE slug = 'nova'")).scalar() == 1
        assert (
            conn.execute(
                text("SELECT COUNT(*) FROM shop_members WHERE shop_id = :id"),
                {"id": shop_id},
            ).scalar()
            == 1
        )
    api.dispose()


def test_api_has_only_required_dml(pg16, migrator_engine):
    apply(migrator_engine)
    api = create_engine(_role_url("stashtab_api"), pool_pre_ping=True)
    with api.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO shops (id, name, slug, created_at, updated_at) "
                "VALUES ('s-api', 'Api', 'api-shop', NOW(), NOW())"
            )
        )
        conn.execute(
            text(
                "INSERT INTO shop_members (id, shop_id, clerk_user_id, role, created_at, updated_at) "
                "VALUES ('m-api', 's-api', 'user-api', 'owner', NOW(), NOW())"
            )
        )
    with api.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM shops")).scalar() >= 1
        with pytest.raises(Exception):
            conn.execute(text("UPDATE shops SET name = 'x' WHERE id = 's-api'"))
            conn.commit()
    with api.connect() as conn:
        with pytest.raises(Exception):
            conn.execute(text("DELETE FROM shops WHERE id = 's-api'"))
            conn.commit()
    with api.connect() as conn:
        with pytest.raises(Exception):
            conn.execute(text("TRUNCATE shops"))
        with pytest.raises(Exception):
            conn.execute(text("CREATE TABLE extra_forbidden (id int)"))
        with pytest.raises(Exception):
            conn.execute(text("CREATE ROLE extra_role"))
        with pytest.raises(Exception):
            conn.execute(text("SET ROLE stashtab_migrator"))
    with pg16.connect() as conn:
        for table in ("shops", "shop_members"):
            for priv in ("UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"):
                assert not conn.execute(
                    text("SELECT has_table_privilege('stashtab_api', :rel, :priv)"),
                    {"rel": f"public.{table}", "priv": priv},
                ).scalar()
    worker = create_engine(_role_url("stashtab_worker"), pool_pre_ping=True)
    with worker.connect() as conn:
        with pytest.raises(Exception):
            conn.execute(text("SELECT COUNT(*) FROM shops"))
    readonly = create_engine(_role_url("stashtab_readonly"), pool_pre_ping=True)
    with readonly.connect() as conn:
        with pytest.raises(Exception):
            conn.execute(text("SELECT COUNT(*) FROM shops"))
    api.dispose()
    worker.dispose()
    readonly.dispose()


def test_identity_http_cases_on_migrated_schema(pg16, migrator_engine, monkeypatch):
    apply(migrator_engine)
    api = create_engine(_role_url("stashtab_api"), pool_pre_ping=True)
    Session = sessionmaker(bind=api, autocommit=False, autoflush=False)
    db = Session()
    db.add(Shop(id="shop-a", name="A", slug="a"))
    db.add(Shop(id="shop-b", name="B", slug="b"))
    db.add(ShopMember(id=new_uuid(), shop_id="shop-a", clerk_user_id="user-a", role="owner"))
    db.add(ShopMember(id=new_uuid(), shop_id="shop-b", clerk_user_id="user-b", role="owner"))
    db.commit()
    db.close()
    client = _api_client(api, monkeypatch)
    assert client.get("/api/v1/shops/shop-a", headers={"X-Shop-Id": "shop-a"}).status_code == 401
    assert (
        client.post("/api/v1/shops", json={"name": "N", "slug": "n"}).status_code == 401
    )
    missing = client.get(
        "/api/v1/shops/shop-a",
        headers={"Authorization": "Bearer user-z", "X-Shop-Id": "shop-a"},
    )
    assert missing.status_code == 403
    cross = client.get(
        "/api/v1/shops/shop-a",
        headers={"Authorization": "Bearer user-b", "X-Shop-Id": "shop-a"},
    )
    assert cross.status_code == 403
    ok = client.get(
        "/api/v1/shops/shop-a",
        headers={"Authorization": "Bearer user-a", "X-Shop-Id": "shop-a"},
    )
    assert ok.status_code == 200
    dup = client.post(
        "/api/v1/shops/shop-a/members",
        json={"clerk_user_id": "user-a"},
        headers={"Authorization": "Bearer user-a", "X-Shop-Id": "shop-a"},
    )
    assert dup.status_code == 409
    api.dispose()


def test_future_tables_do_not_inherit_broad_api_dml(pg16, migrator_engine):
    apply(migrator_engine)
    with migrator_engine.begin() as conn:
        conn.execute(text("CREATE TABLE privilege_probe (id int PRIMARY KEY)"))
    try:
        assert _has_priv(pg16, "stashtab_api", "privilege_probe", "SELECT") is False
        assert _has_priv(pg16, "stashtab_api", "privilege_probe", "INSERT") is False
        assert _has_priv(pg16, "stashtab_api", "privilege_probe", "UPDATE") is False
        assert _has_priv(pg16, "stashtab_api", "privilege_probe", "DELETE") is False
        with migrator_engine.begin() as conn:
            conn.execute(text("INSERT INTO privilege_probe VALUES (1)"))
    finally:
        with migrator_engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS privilege_probe"))


def test_rollback_keeps_safe_default_privileges(pg16, migrator_engine):
    apply(migrator_engine)
    rollback(pg16)
    assert _tables(pg16) == []
    with migrator_engine.begin() as conn:
        conn.execute(text("CREATE TABLE privilege_probe (id int PRIMARY KEY)"))
    try:
        assert _has_priv(pg16, "stashtab_api", "privilege_probe", "UPDATE") is False
        assert _has_priv(pg16, "stashtab_api", "privilege_probe", "DELETE") is False
        with migrator_engine.begin() as conn:
            conn.execute(text("INSERT INTO privilege_probe VALUES (1)"))
    finally:
        with migrator_engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS privilege_probe"))


def test_rollback_drops_only_kernel_tables_and_keeps_roles(pg16, migrator_engine):
    apply(migrator_engine)
    before_roles = _roles(pg16)
    result = rollback(pg16)
    assert set(result["dropped"]) == {"shop_members", "shops"}
    assert _tables(pg16) == []
    assert _roles(pg16) == before_roles == set(ROLES)


def test_injected_failure_leaves_zero_tables(pg16, migrator_engine):
    rollback(pg16)
    with pytest.raises(RuntimeError, match="injected"):
        apply(migrator_engine, fail_after="shops")
    assert _tables(pg16) == []


def test_prohibited_membership_fails_before_ddl(pg16, migrator_engine):
    with pg16.begin() as conn:
        conn.execute(text("GRANT stashtab_migrator TO stashtab_api"))
        conn.execute(text("GRANT stashtab_migrator TO stashtab_worker"))
        conn.execute(text("GRANT stashtab_migrator TO stashtab_readonly"))
    try:
        with pytest.raises(RuntimeError, match="prohibited membership"):
            apply(migrator_engine)
        assert _tables(pg16) == []
    finally:
        with pg16.begin() as conn:
            conn.execute(text("REVOKE stashtab_migrator FROM stashtab_api"))
            conn.execute(text("REVOKE stashtab_migrator FROM stashtab_worker"))
            conn.execute(text("REVOKE stashtab_migrator FROM stashtab_readonly"))


def test_staging_startup_still_creates_no_schema(pg16, monkeypatch):
    rollback(pg16)
    monkeypatch.setattr(settings, "app_env", "staging")
    assert startup_schema_mutation_forbidden() is True
    with pytest.raises(RuntimeError, match="forbidden"):
        init_db()
    assert _tables(pg16) == []
