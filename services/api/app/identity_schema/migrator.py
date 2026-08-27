"""Explicit shops/shop_members migrator. Does not use metadata.create_all.

Types are taken from the live SQLAlchemy models compiled for PostgreSQL:

- id VARCHAR(36) PK, application UUID, no sequences
- name/slug VARCHAR(120); clerk_org_id VARCHAR(120) nullable
- clerk_user_id VARCHAR(120); role VARCHAR(32) NOT NULL (app default owner)
- timestamps TIMESTAMP WITH TIME ZONE NOT NULL, no database defaults
- unique slug as uq_shops_slug
- unique (shop_id, clerk_user_id) as uq_shop_members_shop_user
- indexes ix_shop_members_shop_id, ix_shop_members_clerk_user_id

Identity endpoint privilege map (verified against shops.py + deps.py):

- POST /shops, POST /shops/onboard: INSERT shops, INSERT shop_members
- GET /shops/me, GET /shops/me/memberships, GET /shops/{id}, GET /shops/{id}/members: SELECT both
- POST /shops/{id}/members: SELECT both, INSERT shop_members
- get_shop_context / get_authenticated_user: SELECT only

No identity endpoint updates or deletes rows when owner membership is
written in the same transaction. stashtab_api therefore receives SELECT and
INSERT only. No sequence privileges. Worker and readonly get no DML.

This migrator does not CREATE, ALTER, GRANT, or REVOKE database roles.
It fails closed before DDL if api, worker, or readonly can assume migrator.
It may change privileges on objects it owns and its own default privileges.
"""

from __future__ import annotations

import argparse
import re
import sys

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.database import engine as default_engine

TABLES = ("shops", "shop_members")
MIGRATOR_ROLE = "stashtab_migrator"
API_ROLE = "stashtab_api"
WORKER_ROLE = "stashtab_worker"
READONLY_ROLE = "stashtab_readonly"
_RUNTIME_ROLES = (API_ROLE, WORKER_ROLE, READONLY_ROLE)
_TABLE_PRIVS = (
    "SELECT",
    "INSERT",
    "UPDATE",
    "DELETE",
    "TRUNCATE",
    "REFERENCES",
    "TRIGGER",
)
_API_PRIVS = frozenset({"SELECT", "INSERT"})
_ROLE_RE = re.compile(r"^[a-z][a-z0-9_]*$")

_CREATE_SHOPS = """
CREATE TABLE IF NOT EXISTS shops (
    id VARCHAR(36) NOT NULL,
    name VARCHAR(120) NOT NULL,
    slug VARCHAR(120) NOT NULL,
    clerk_org_id VARCHAR(120),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT shops_pkey PRIMARY KEY (id),
    CONSTRAINT uq_shops_slug UNIQUE (slug)
)
"""

_CREATE_MEMBERS = """
CREATE TABLE IF NOT EXISTS shop_members (
    id VARCHAR(36) NOT NULL,
    shop_id VARCHAR(36) NOT NULL,
    clerk_user_id VARCHAR(120) NOT NULL,
    role VARCHAR(32) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT shop_members_pkey PRIMARY KEY (id),
    CONSTRAINT uq_shop_members_shop_user UNIQUE (shop_id, clerk_user_id),
    CONSTRAINT fk_shop_members_shop_id FOREIGN KEY (shop_id) REFERENCES shops(id),
    CONSTRAINT ck_shop_members_role CHECK (role IN ('owner', 'staff'))
)
"""


def _ident(role: str) -> str:
    if not _ROLE_RE.fullmatch(role):
        raise RuntimeError("invalid role name")
    return role


def _role_exists(conn, role: str) -> bool:
    return bool(
        conn.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = :r"),
            {"r": role},
        ).scalar()
    )


def _role_can_assume(conn, member: str, role: str) -> bool:
    return bool(
        conn.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_auth_members m
                    JOIN pg_roles r ON r.oid = m.roleid
                    JOIN pg_roles u ON u.oid = m.member
                    WHERE r.rolname = :role
                      AND u.rolname = :member
                )
                """
            ),
            {"member": member, "role": role},
        ).scalar()
    )


def _assert_runtime_cannot_assume_migrator(conn) -> None:
    migrator = _ident(MIGRATOR_ROLE)
    blocked = []
    for member in (API_ROLE, WORKER_ROLE, READONLY_ROLE):
        if not _role_exists(conn, member):
            continue
        if _role_can_assume(conn, member, migrator):
            blocked.append(member)
    if blocked:
        raise RuntimeError(
            "prohibited membership: "
            + ",".join(blocked)
            + " can assume stashtab_migrator"
        )


def _has_table_privilege(conn, role: str, table: str, priv: str) -> bool:
    return bool(
        conn.execute(
            text("SELECT has_table_privilege(:role, :rel, :priv)"),
            {"role": role, "rel": f"public.{table}", "priv": priv},
        ).scalar()
    )


def _public_has_table_privilege(conn, table: str, priv: str) -> bool:
    return bool(
        conn.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    CROSS JOIN LATERAL aclexplode(COALESCE(c.relacl, '{}'::aclitem[])) a
                    WHERE n.nspname = 'public'
                      AND c.relname = :table
                      AND a.grantee = 0
                      AND a.privilege_type = :priv
                )
                """
            ),
            {"table": table, "priv": priv},
        ).scalar()
    )


def _normalize_owned_privileges(conn, api: str) -> list[str]:
    grants: list[str] = []
    conn.execute(
        text("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM PUBLIC")
    )
    for role in _RUNTIME_ROLES:
        if _role_exists(conn, role):
            conn.execute(
                text(
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                    f"REVOKE ALL ON TABLES FROM {_ident(role)}"
                )
            )
    for table in TABLES:
        conn.execute(text(f"REVOKE ALL PRIVILEGES ON TABLE {table} FROM PUBLIC"))
        for role in _RUNTIME_ROLES:
            if _role_exists(conn, role):
                conn.execute(
                    text(f"REVOKE ALL PRIVILEGES ON TABLE {table} FROM {_ident(role)}")
                )
        if _role_exists(conn, api):
            conn.execute(text(f"GRANT SELECT, INSERT ON TABLE {table} TO {api}"))
            grants.append(f"{api}:{table}:select,insert")
    return grants


def _assert_contract_privileges(conn) -> None:
    for table in TABLES:
        for priv in _TABLE_PRIVS:
            if _public_has_table_privilege(conn, table, priv):
                raise RuntimeError(f"PUBLIC has {priv} on {table}")
        if _role_exists(conn, API_ROLE):
            allowed = {
                priv for priv in _TABLE_PRIVS if _has_table_privilege(conn, API_ROLE, table, priv)
            }
            if allowed != _API_PRIVS:
                raise RuntimeError(
                    f"stashtab_api privileges on {table} are {sorted(allowed)}, "
                    f"expected {sorted(_API_PRIVS)}"
                )
        for role in (WORKER_ROLE, READONLY_ROLE):
            if not _role_exists(conn, role):
                continue
            held = {
                priv for priv in _TABLE_PRIVS if _has_table_privilege(conn, role, table, priv)
            }
            if held:
                raise RuntimeError(f"{role} has table privileges on {table}: {sorted(held)}")


def _public_tables(conn) -> list[str]:
    rows = conn.execute(
        text(
            """
            SELECT c.relname FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind = 'r'
            ORDER BY 1
            """
        )
    )
    return [r[0] for r in rows]


def apply(target_engine: Engine | None = None, *, fail_after: str | None = None) -> dict[str, list[str]]:
    """Create shops and shop_members in one transaction. Idempotent."""
    engine = target_engine or default_engine
    migrator = _ident(MIGRATOR_ROLE)
    api = _ident(API_ROLE)
    applied: dict[str, list[str]] = {"tables": [], "grants": []}
    with engine.begin() as conn:
        if not _role_exists(conn, migrator):
            raise RuntimeError("stashtab_migrator role is missing")
        _assert_runtime_cannot_assume_migrator(conn)
        conn.execute(text(f"SET LOCAL ROLE {migrator}"))
        before = set(_public_tables(conn))
        conn.execute(text(_CREATE_SHOPS))
        if "shops" not in before:
            applied["tables"].append("shops")
        if fail_after == "shops":
            raise RuntimeError("injected migration failure after shops")
        conn.execute(text(_CREATE_MEMBERS))
        if "shop_members" not in before:
            applied["tables"].append("shop_members")
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_shop_members_shop_id ON shop_members (shop_id)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_shop_members_clerk_user_id "
                "ON shop_members (clerk_user_id)"
            )
        )
        for table in TABLES:
            conn.execute(text(f"ALTER TABLE {table} OWNER TO {migrator}"))
        applied["grants"] = _normalize_owned_privileges(conn, api)
        conn.execute(text("RESET ROLE"))
        _assert_contract_privileges(conn)
    with engine.connect() as probe:
        names = _public_tables(probe)
        if set(names) != set(TABLES):
            raise RuntimeError(f"identity schema verification failed: {names}")
        _assert_contract_privileges(probe)
    return applied


def rollback(target_engine: Engine | None = None) -> dict[str, list[str]]:
    """Drop shop_members, then shops. Does not drop roles."""
    engine = target_engine or default_engine
    migrator = _ident(MIGRATOR_ROLE)
    dropped: list[str] = []
    with engine.begin() as conn:
        if not _role_exists(conn, migrator):
            raise RuntimeError("stashtab_migrator role is missing")
        conn.execute(text(f"SET LOCAL ROLE {migrator}"))
        existing = set(_public_tables(conn))
        conn.execute(text("DROP TABLE IF EXISTS shop_members"))
        if "shop_members" in existing:
            dropped.append("shop_members")
        conn.execute(text("DROP TABLE IF EXISTS shops"))
        if "shops" in existing:
            dropped.append("shops")
    with engine.connect() as probe:
        leftover = [n for n in _public_tables(probe) if n in TABLES]
    if leftover:
        raise RuntimeError(f"identity rollback left tables: {leftover}")
    return {"dropped": dropped}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Identity kernel migrator")
    parser.add_argument("command", choices=("apply", "rollback"))
    args = parser.parse_args(argv)
    if args.command == "apply":
        print("identity-schema apply:", apply())
    else:
        print("identity-schema rollback:", rollback())
    return 0


if __name__ == "__main__":
    sys.exit(main())
