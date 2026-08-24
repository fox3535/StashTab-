"""Approved migrator for the frozen inventory-truth schema.

The ONLY sanctioned path that creates `acquisition_lot`,
`inventory_event`, and `inventory_truth_cutover`, plus the additive
unique `(shop_id, id)` indexes required before composite FKs
(MIGRATION.md §Compatibility, §Order step 2; DESIGN.md §3).

Run:  python -m app.inventory_truth.migrator   (or import apply()).

Atomicity: everything runs in ONE transaction. On PostgreSQL a failure at
any point (including injected mid-point failures via `fail_after`) rolls
back completely — no partially accepted schema.
Idempotent: safe to re-run; existing objects are left untouched.
"""

from __future__ import annotations

import os
import re
import sys

from sqlalchemy import inspect, text

from app.database import engine

TRUTH_TABLE_NAMES = (
    "acquisition_lot",
    "inventory_event",
    "inventory_truth_cutover",
    "inventory_channel_observation",
    "refund_record",
    "return_record",
    "inventory_exception",
)
LIVE_TABLES = ("inventory_item", "purchase_record", "sale")

# Append-only enforcement (DIRECTIVE-SLICE-02 §5): BEFORE triggers reject
# UPDATE/DELETE at the DB level. SQLite has no role grants; triggers work
# on both backends and are created inside the same atomic migration.
_APPEND_ONLY_TABLES = ("refund_record", "return_record")


def apply(target_engine=engine, *, fail_after: str | None = None) -> dict[str, list[str]]:
    """Apply additive indexes, then truth tables (with composite FKs),
    then append-only triggers on refund/return records.

    fail_after: optional test hook ("indexes" | "tables" | "triggers") that
    raises after that stage to exercise mid-migration rollback.
    """
    from app.inventory_truth.models_truth import TruthBase, register_composite_fks

    applied: dict[str, list] = {"indexes": [], "tables": [], "triggers": [], "rules": []}
    insp = inspect(target_engine)
    register_composite_fks()
    metadata = TruthBase.metadata

    # Everything below commits or rolls back as one unit.
    with target_engine.begin() as conn:
        # Step 1 — additive unique (shop_id, id) on live tables (indexes only).
        for table in LIVE_TABLES:
            if not insp.has_table(table):
                continue  # empty schema: application create_all owns these later
            existing = {ix["name"] for ix in insp.get_indexes(table)}
            ix_name = f"uq_{table}_shop_id"
            if ix_name not in existing:
                conn.execute(
                    text(
                        f"CREATE UNIQUE INDEX IF NOT EXISTS {ix_name} "
                        f"ON {table} (shop_id, id)"
                    )
                )
                applied["indexes"].append(ix_name)

        if fail_after == "indexes":
            raise RuntimeError("injected migration failure after indexes")

        # Steps 2–3 — truth tables ONLY; shadow parents are never emitted.
        missing = [
            metadata.tables[name] for name in TRUTH_TABLE_NAMES if not insp.has_table(name)
        ]
        if missing:
            metadata.create_all(bind=conn, tables=missing)
            applied["tables"] = [t.name for t in missing]

        if fail_after == "tables":
            raise RuntimeError("injected migration failure after tables")

        # Step 4b — slice-02 forward migration: outbound events are lotless
        # (AMENDMENT-1.1.0), so a database created under slice-01 with the
        # original NOT NULL lot_id must be relaxed. No-op on fresh databases
        # and on SQLite (dynamic typing). Verified post-apply below.
        if target_engine.dialect.name != "sqlite":
            nullable = (
                conn.execute(
                    text(
                        "SELECT is_nullable FROM information_schema.columns "
                        "WHERE table_name = 'inventory_event' AND column_name = 'lot_id'"
                    )
                ).scalar()
            )
            if nullable == "NO":
                conn.execute(
                    text("ALTER TABLE inventory_event ALTER COLUMN lot_id DROP NOT NULL")
                )
                applied["column_relaxations"] = ["inventory_event.lot_id"]

        # Step 4 — append-only triggers for refund/return records.
        if target_engine.dialect.name != "sqlite":
            # Self-contained migration: create (or replace) the shared
            # rejection function inside the same atomic transaction.
            # Trigger functions take no declared args; the message is read
            # from TG_ARGV[0] at fire time.
            conn.execute(
                text(
                    "CREATE OR REPLACE FUNCTION raise_append_only() "
                    "RETURNS trigger AS $$ BEGIN "
                    "RAISE EXCEPTION '%', TG_ARGV[0]; END; "
                    "$$ LANGUAGE plpgsql"
                )
            )
        for table in _APPEND_ONLY_TABLES:
            for action in ("UPDATE", "DELETE"):
                trg = f"trg_{table.lower()}_no_{action.lower()}"
                exists = conn.execute(
                    text(
                        "SELECT name FROM sqlite_master WHERE type='trigger' AND name=:n"
                        if target_engine.dialect.name == "sqlite"
                        else "SELECT tgname FROM pg_trigger WHERE tgname = :n"
                    ),
                    {"n": trg},
                ).first()
                if exists is None:
                    conn.execute(
                        text(
                            f"CREATE TRIGGER {trg} BEFORE {action} ON {table} "
                            "FOR EACH ROW BEGIN SELECT RAISE(ABORT, "
                            f"'{table} is append-only: {action} rejected'); END"
                            if target_engine.dialect.name == "sqlite"
                            else (
                                f"CREATE TRIGGER {trg} BEFORE {action} ON {table} "
                                "FOR EACH ROW EXECUTE FUNCTION raise_append_only("
                                f"'{table} is append-only: {action} rejected')"
                            )
                        )
                    )
                    applied["triggers"].append(trg)

        if fail_after == "triggers":
            raise RuntimeError("injected migration failure after triggers")

        # Step 5 — TRUNCATE protection. Row triggers cannot intercept
        # TRUNCATE on PostgreSQL; a statement-level BEFORE TRUNCATE trigger
        # rejects it at the database level unless the session runs as the
        # authorized migrator role (STASHTAB_TRUTH_MIGRATOR_ROLE). With no
        # role configured the trigger denies every TRUNCATE — fail closed.
        if target_engine.dialect.name != "sqlite":
            migrator_role = os.environ.get("STASHTAB_TRUTH_MIGRATOR_ROLE", "").strip()
            if migrator_role and not re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_]*", migrator_role
            ):
                raise RuntimeError(
                    f"invalid STASHTAB_TRUTH_MIGRATOR_ROLE: {migrator_role!r}"
                )
            if migrator_role:
                conn.execute(
                    text(
                        "DO $$ BEGIN IF NOT EXISTS "
                        "(SELECT FROM pg_roles WHERE rolname = :r) THEN "
                        f'CREATE ROLE "{migrator_role}" NOLOGIN; '
                        "END IF; END $$;"
                    ).bindparams(r=migrator_role)
                )
            allow_expr = (
                f"(current_user = '{migrator_role}' "
                f"or session_user = '{migrator_role}')"
                if migrator_role
                else "false"
            )
            conn.execute(
                text(
                    "CREATE OR REPLACE FUNCTION truth_deny_truncate() "
                    "RETURNS trigger AS $$ BEGIN "
                    f"IF NOT {allow_expr} THEN "
                    "RAISE EXCEPTION 'TRUNCATE denied on %: append-only "
                    "(authorized migrator role only)', TG_TABLE_NAME; "
                    "END IF; RETURN NULL; END; "
                    "$$ LANGUAGE plpgsql"
                )
            )
            for table in _APPEND_ONLY_TABLES:
                trg = f"trg_{table.lower()}_no_truncate"
                exists = conn.execute(
                    text("SELECT tgname FROM pg_trigger WHERE tgname = :n"),
                    {"n": trg},
                ).first()
                if not exists:
                    conn.execute(
                        text(
                            f"CREATE TRIGGER {trg} BEFORE TRUNCATE ON {table} "
                            "FOR EACH STATEMENT EXECUTE FUNCTION "
                            "truth_deny_truncate()"
                        )
                    )
                    applied["rules"].append(trg)
                # ACL layer: TRUNCATE privilege is revoked from PUBLIC and
                # from every role except the authorized migrator (and the
                # table owner, whom PostgreSQL cannot fully bind). The
                # privilege check runs BEFORE the ACCESS EXCLUSIVE lock is
                # taken, so unauthorized attempts fail fast instead of
                # queueing behind other transactions; the trigger remains
                # as a second gate for owner/superuser sessions.
                conn.execute(text(f"REVOKE ALL ON {table} FROM PUBLIC"))
                roles = conn.execute(
                    text(
                        "SELECT rolname FROM pg_roles WHERE rolname NOT LIKE 'pg\\_%'"
                    )
                ).fetchall()
                for (rolname,) in roles:
                    if rolname == migrator_role:
                        conn.execute(
                            text(f'GRANT TRUNCATE ON {table} TO "{rolname}"')
                        )
                    else:
                        conn.execute(
                            text(f'REVOKE TRUNCATE ON {table} FROM "{rolname}"')
                        )

    # Post-apply verification: fail loudly if expected objects are absent.
    insp2 = inspect(target_engine)
    for name in TRUTH_TABLE_NAMES:
        if not insp2.has_table(name):
            raise RuntimeError(f"migrator verification failed: table {name} missing")
    for table in LIVE_TABLES:
        if not insp2.has_table(table):
            continue
        names = {ix["name"] for ix in insp2.get_indexes(table)}
        if f"uq_{table}_shop_id" not in names:
            raise RuntimeError(
                f"migrator verification failed: uq_{table}_shop_id index missing"
            )
    if insp2.has_table("inventory_event"):
        lot_nullable = (
            (insp2.get_columns("inventory_event") or [])
            and next(
                c["nullable"]
                for c in insp2.get_columns("inventory_event")
                if c["name"] == "lot_id"
            )
        )
        if not lot_nullable:
            raise RuntimeError(
                "migrator verification failed: inventory_event.lot_id must be "
                "nullable for lotless outbound events"
            )

    return applied


def main() -> int:
    result = apply()
    print("inventory-truth migrator:", result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
