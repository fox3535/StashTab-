"""Migrator-owned card-resolution schema. Startup create_all cannot see these tables."""

from __future__ import annotations

import argparse
import re
import sys

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.database import engine as default_engine
from app.card_resolution.models import CARD_RESOLUTION_TABLES, CardResolutionBase

TABLES = CARD_RESOLUTION_TABLES
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
_ROLE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_DROP_ORDER = (
    "card_resolution_audit",
    "card_resolution_review",
    "card_resolution_candidate",
    "card_resolution_evidence",
    "card_resolution_intake",
    "card_resolution_catalog",
)
_API_GRANTS = {
    "card_resolution_catalog": frozenset({"SELECT"}),
    "card_resolution_intake": frozenset({"SELECT", "INSERT", "UPDATE"}),
    "card_resolution_evidence": frozenset({"SELECT", "INSERT"}),
    "card_resolution_candidate": frozenset({"SELECT", "INSERT"}),
    "card_resolution_review": frozenset({"SELECT", "INSERT", "UPDATE"}),
    "card_resolution_audit": frozenset({"SELECT", "INSERT"}),
}

_PG_DDL = (
    """
CREATE TABLE IF NOT EXISTS card_resolution_catalog (
    id VARCHAR(36) NOT NULL,
    shop_id VARCHAR(36) NOT NULL,
    game VARCHAR(32) NOT NULL,
    name VARCHAR(200) NOT NULL,
    set_name VARCHAR(120),
    set_code VARCHAR(40),
    collector_number VARCHAR(40),
    language VARCHAR(32),
    printing VARCHAR(64),
    justtcg_id VARCHAR(120),
    tcgplayer_id VARCHAR(120),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT card_resolution_catalog_pkey PRIMARY KEY (id),
    CONSTRAINT fk_cr_catalog_shop_id FOREIGN KEY (shop_id) REFERENCES shops(id)
)
""",
    """
CREATE TABLE IF NOT EXISTS card_resolution_intake (
    id VARCHAR(36) NOT NULL,
    shop_id VARCHAR(36) NOT NULL,
    intake_id VARCHAR(120) NOT NULL,
    evidence_hash VARCHAR(64) NOT NULL,
    result VARCHAR(32) NOT NULL,
    state VARCHAR(32) NOT NULL,
    reason_codes TEXT NOT NULL,
    identity_confidence_hundredths INTEGER,
    price_confidence INTEGER,
    confidence_components TEXT NOT NULL,
    ruleset_version VARCHAR(64) NOT NULL,
    contract_version VARCHAR(16) NOT NULL,
    decision_source VARCHAR(32),
    winner_identity_key VARCHAR(400),
    justtcg_invoked BOOLEAN NOT NULL DEFAULT FALSE,
    actor_clerk_user_id VARCHAR(120),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT card_resolution_intake_pkey PRIMARY KEY (id),
    CONSTRAINT uq_cr_intake_shop_intake UNIQUE (shop_id, intake_id),
    CONSTRAINT uq_cr_intake_shop_pk UNIQUE (shop_id, id),
    CONSTRAINT fk_cr_intake_shop_id FOREIGN KEY (shop_id) REFERENCES shops(id),
    CONSTRAINT ck_cr_intake_result CHECK (result IN ('accepted', 'abstained', 'rejected')),
    CONSTRAINT ck_cr_intake_state CHECK (state IN ('accepted', 'pending_human_review', 'rejected'))
)
""",
    """
CREATE TABLE IF NOT EXISTS card_resolution_evidence (
    id VARCHAR(36) NOT NULL,
    shop_id VARCHAR(36) NOT NULL,
    intake_pk VARCHAR(36) NOT NULL,
    intake_id VARCHAR(120) NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT card_resolution_evidence_pkey PRIMARY KEY (id),
    CONSTRAINT fk_cr_evidence_shop_id FOREIGN KEY (shop_id) REFERENCES shops(id),
    CONSTRAINT fk_cr_evidence_intake FOREIGN KEY (intake_pk, shop_id)
        REFERENCES card_resolution_intake (id, shop_id)
)
""",
    """
CREATE TABLE IF NOT EXISTS card_resolution_candidate (
    id VARCHAR(36) NOT NULL,
    shop_id VARCHAR(36) NOT NULL,
    intake_pk VARCHAR(36) NOT NULL,
    rank INTEGER NOT NULL,
    identity_key VARCHAR(400) NOT NULL,
    score_hundredths INTEGER NOT NULL,
    components_json TEXT NOT NULL,
    eligible BOOLEAN NOT NULL,
    retrieved_via_fuzzy BOOLEAN NOT NULL DEFAULT FALSE,
    payload_json TEXT NOT NULL,
    CONSTRAINT card_resolution_candidate_pkey PRIMARY KEY (id),
    CONSTRAINT fk_cr_candidate_shop_id FOREIGN KEY (shop_id) REFERENCES shops(id),
    CONSTRAINT fk_cr_candidate_intake FOREIGN KEY (intake_pk, shop_id)
        REFERENCES card_resolution_intake (id, shop_id)
)
""",
    """
CREATE TABLE IF NOT EXISTS card_resolution_review (
    id VARCHAR(36) NOT NULL,
    shop_id VARCHAR(36) NOT NULL,
    intake_pk VARCHAR(36) NOT NULL,
    intake_id VARCHAR(120) NOT NULL,
    status VARCHAR(32) NOT NULL,
    reason_codes TEXT NOT NULL,
    decision VARCHAR(32),
    decided_by VARCHAR(120),
    decided_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT card_resolution_review_pkey PRIMARY KEY (id),
    CONSTRAINT uq_cr_review_shop_intake UNIQUE (shop_id, intake_pk),
    CONSTRAINT uq_cr_review_shop_pk UNIQUE (shop_id, id),
    CONSTRAINT fk_cr_review_shop_id FOREIGN KEY (shop_id) REFERENCES shops(id),
    CONSTRAINT fk_cr_review_intake FOREIGN KEY (intake_pk, shop_id)
        REFERENCES card_resolution_intake (id, shop_id),
    CONSTRAINT ck_cr_review_status CHECK (status IN ('open', 'decided', 'deferred'))
)
""",
    """
CREATE TABLE IF NOT EXISTS card_resolution_audit (
    id VARCHAR(36) NOT NULL,
    shop_id VARCHAR(36) NOT NULL,
    intake_pk VARCHAR(36) NOT NULL,
    review_id VARCHAR(36),
    action VARCHAR(64) NOT NULL,
    actor_clerk_user_id VARCHAR(120),
    payload_json TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT card_resolution_audit_pkey PRIMARY KEY (id),
    CONSTRAINT fk_cr_audit_shop_id FOREIGN KEY (shop_id) REFERENCES shops(id),
    CONSTRAINT fk_cr_audit_intake FOREIGN KEY (intake_pk, shop_id)
        REFERENCES card_resolution_intake (id, shop_id),
    CONSTRAINT fk_cr_audit_review FOREIGN KEY (review_id, shop_id)
        REFERENCES card_resolution_review (id, shop_id)
)
""",
)


def _ident(role: str) -> str:
    if not _ROLE_RE.fullmatch(role):
        raise RuntimeError("invalid role name")
    return role


def _role_exists(conn, role: str) -> bool:
    return bool(
        conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": role}).scalar()
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
                    WHERE r.rolname = :role AND u.rolname = :member
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
        raise RuntimeError("prohibited membership: " + ",".join(blocked) + " can assume stashtab_migrator")


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


def _normalize_privileges(conn) -> list[str]:
    grants: list[str] = []
    conn.execute(text("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM PUBLIC"))
    for role in _RUNTIME_ROLES:
        if _role_exists(conn, role):
            conn.execute(
                text(
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                    f"REVOKE ALL ON TABLES FROM {_ident(role)}"
                )
            )
    api = _ident(API_ROLE)
    for table in TABLES:
        conn.execute(text(f"REVOKE ALL PRIVILEGES ON TABLE {table} FROM PUBLIC"))
        for role in _RUNTIME_ROLES:
            if _role_exists(conn, role):
                conn.execute(text(f"REVOKE ALL PRIVILEGES ON TABLE {table} FROM {_ident(role)}"))
        if _role_exists(conn, api):
            privs = ", ".join(sorted(_API_GRANTS[table]))
            conn.execute(text(f"GRANT {privs} ON TABLE {table} TO {api}"))
            grants.append(f"{api}:{table}:{privs.lower()}")
    return grants


def _assert_privileges(conn) -> None:
    for table in TABLES:
        for priv in _TABLE_PRIVS:
            if _public_has_table_privilege(conn, table, priv):
                raise RuntimeError(f"PUBLIC has {priv} on {table}")
        if _role_exists(conn, API_ROLE):
            allowed = {
                priv for priv in _TABLE_PRIVS if _has_table_privilege(conn, API_ROLE, table, priv)
            }
            if allowed != _API_GRANTS[table]:
                raise RuntimeError(
                    f"stashtab_api privileges on {table} are {sorted(allowed)}, "
                    f"expected {sorted(_API_GRANTS[table])}"
                )
        for role in (WORKER_ROLE, READONLY_ROLE):
            if not _role_exists(conn, role):
                continue
            held = {priv for priv in _TABLE_PRIVS if _has_table_privilege(conn, role, table, priv)}
            if held:
                raise RuntimeError(f"{role} has table privileges on {table}: {sorted(held)}")


def _install_postgres_triggers(conn) -> None:
    conn.execute(
        text(
            """
            CREATE OR REPLACE FUNCTION card_resolution_deny_mutation()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
              RAISE EXCEPTION 'append-only';
            END;
            $$
            """
        )
    )
    for table in ("card_resolution_evidence", "card_resolution_audit"):
        conn.execute(text(f"DROP TRIGGER IF EXISTS {table}_no_update ON {table}"))
        conn.execute(text(f"DROP TRIGGER IF EXISTS {table}_no_delete ON {table}"))
        conn.execute(
            text(
                f"""
                CREATE TRIGGER {table}_no_update
                BEFORE UPDATE ON {table}
                FOR EACH ROW EXECUTE FUNCTION card_resolution_deny_mutation()
                """
            )
        )
        conn.execute(
            text(
                f"""
                CREATE TRIGGER {table}_no_delete
                BEFORE DELETE ON {table}
                FOR EACH ROW EXECUTE FUNCTION card_resolution_deny_mutation()
                """
            )
        )


def _install_sqlite_triggers(conn) -> None:
    for table in ("card_resolution_evidence", "card_resolution_audit"):
        conn.execute(
            text(
                f"""
                CREATE TRIGGER IF NOT EXISTS {table}_no_update
                BEFORE UPDATE ON {table}
                BEGIN
                  SELECT RAISE(ABORT, 'append-only');
                END
                """
            )
        )
        conn.execute(
            text(
                f"""
                CREATE TRIGGER IF NOT EXISTS {table}_no_delete
                BEFORE DELETE ON {table}
                BEGIN
                  SELECT RAISE(ABORT, 'append-only');
                END
                """
            )
        )


def _owned_tables():
    return [
        table
        for name, table in CardResolutionBase.metadata.tables.items()
        if name != "shops"
    ]


def apply_sqlite(target_engine: Engine) -> dict[str, list[str]]:
    before = set()
    with target_engine.connect() as conn:
        before = set(conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).scalars())
    CardResolutionBase.metadata.create_all(target_engine, tables=_owned_tables())
    with target_engine.begin() as conn:
        _install_sqlite_triggers(conn)
    with target_engine.connect() as conn:
        after = set(conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).scalars())
    created = [name for name in TABLES if name in after and name not in before]
    return {"tables": created}


def apply(target_engine: Engine | None = None) -> dict[str, list[str]]:
    engine = target_engine or default_engine
    if engine.dialect.name == "sqlite":
        return apply_sqlite(engine)
    migrator = _ident(MIGRATOR_ROLE)
    applied: dict[str, list[str]] = {"tables": [], "grants": []}
    with engine.begin() as conn:
        if not _role_exists(conn, migrator):
            raise RuntimeError("stashtab_migrator role is missing")
        _assert_runtime_cannot_assume_migrator(conn)
        names = set(_public_tables(conn))
        if "shops" not in names:
            raise RuntimeError("card-resolution apply requires shops")
        conn.execute(text(f"SET LOCAL ROLE {migrator}"))
        before = set(_public_tables(conn))
        for ddl in _PG_DDL:
            conn.execute(text(ddl))
        for table in TABLES:
            if table not in before:
                applied["tables"].append(table)
            conn.execute(text(f"ALTER TABLE {table} OWNER TO {migrator}"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_cr_catalog_shop_id ON card_resolution_catalog (shop_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_cr_intake_shop_id ON card_resolution_intake (shop_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_cr_evidence_shop_id ON card_resolution_evidence (shop_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_cr_review_shop_id ON card_resolution_review (shop_id)"))
        _install_postgres_triggers(conn)
        applied["grants"] = _normalize_privileges(conn)
        conn.execute(text("RESET ROLE"))
        _assert_privileges(conn)
    with engine.connect() as probe:
        missing = [name for name in TABLES if name not in set(_public_tables(probe))]
        if missing:
            raise RuntimeError(f"card-resolution schema verification failed, missing {missing}")
        _assert_privileges(probe)
    return applied


def rollback(target_engine: Engine | None = None) -> dict[str, list[str]]:
    engine = target_engine or default_engine
    if engine.dialect.name == "sqlite":
        dropped: list[str] = []
        with engine.begin() as conn:
            existing = set(conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).scalars())
            for table in _DROP_ORDER:
                conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
                if table in existing:
                    dropped.append(table)
        return {"dropped": dropped}
    migrator = _ident(MIGRATOR_ROLE)
    dropped: list[str] = []
    with engine.begin() as conn:
        if not _role_exists(conn, migrator):
            raise RuntimeError("stashtab_migrator role is missing")
        conn.execute(text(f"SET LOCAL ROLE {migrator}"))
        existing = set(_public_tables(conn))
        for table in _DROP_ORDER:
            conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
            if table in existing:
                dropped.append(table)
        conn.execute(text("DROP FUNCTION IF EXISTS card_resolution_deny_mutation() CASCADE"))
    with engine.connect() as probe:
        leftover = [name for name in _public_tables(probe) if name in TABLES]
    if leftover:
        raise RuntimeError(f"card-resolution rollback left tables: {leftover}")
    return {"dropped": dropped}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Card-resolution schema migrator")
    parser.add_argument("command", choices=("apply", "rollback"))
    args = parser.parse_args(argv)
    if args.command == "apply":
        print("card-resolution-schema apply:", apply())
    else:
        print("card-resolution-schema rollback:", rollback())
    return 0


if __name__ == "__main__":
    sys.exit(main())
