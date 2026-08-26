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
- GET /shops/me, GET /shops/{id}, GET /shops/{id}/members: SELECT both
- POST /shops/{id}/members: SELECT both, INSERT shop_members
- get_shop_context / get_authenticated_user: SELECT only

No identity endpoint updates or deletes rows when owner membership is
written in the same transaction. stashtab_api therefore receives SELECT and
INSERT only. No sequence privileges. Worker and readonly get no DML.
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
        conn.execute(text(f"GRANT USAGE, CREATE ON SCHEMA public TO {migrator}"))
        conn.execute(text("REVOKE CREATE ON SCHEMA public FROM PUBLIC"))
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
        conn.execute(text("RESET ROLE"))
        for table in TABLES:
            conn.execute(text(f"REVOKE ALL ON TABLE {table} FROM PUBLIC"))
            if _role_exists(conn, api):
                conn.execute(text(f"GRANT SELECT, INSERT ON TABLE {table} TO {api}"))
                applied["grants"].append(f"{api}:{table}:select,insert")
            for extra in (WORKER_ROLE, READONLY_ROLE):
                if _role_exists(conn, extra):
                    conn.execute(text(f"REVOKE ALL ON TABLE {table} FROM {_ident(extra)}"))
        if _role_exists(conn, api):
            conn.execute(text(f"REVOKE CREATE ON SCHEMA public FROM {api}"))
            conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {api}"))
        if _role_exists(conn, api) and _role_exists(conn, migrator):
            conn.execute(text(f"REVOKE {migrator} FROM {api}"))
    with engine.connect() as probe:
        names = _public_tables(probe)
    if set(names) != set(TABLES):
        raise RuntimeError(f"identity schema verification failed: {names}")
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
