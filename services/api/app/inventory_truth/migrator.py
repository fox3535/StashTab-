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

import sys

from sqlalchemy import inspect, text

from app.database import engine

TRUTH_TABLE_NAMES = ("acquisition_lot", "inventory_event", "inventory_truth_cutover")
LIVE_TABLES = ("inventory_item", "purchase_record", "sale")


def apply(target_engine=engine, *, fail_after: str | None = None) -> dict[str, list[str]]:
    """Apply additive indexes, then truth tables (with composite FKs).

    fail_after: optional test hook ("indexes" | "tables") that raises after
    that stage to exercise mid-migration rollback.
    """
    from app.inventory_truth.models_truth import TruthBase, register_composite_fks

    applied: dict[str, list[str]] = {"indexes": [], "tables": []}
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

    return applied


def main() -> int:
    result = apply()
    print("inventory-truth migrator:", result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
