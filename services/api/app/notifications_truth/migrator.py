"""Controlled migrator for the frozen notification schema.

The application startup path does not import or apply this module. Operators
must call ``apply_notification_schema`` explicitly with an approved engine.
"""

from __future__ import annotations

import os
import re
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import (
    CheckConstraint,
    Connection,
    Engine,
    ForeignKeyConstraint,
    UniqueConstraint,
    inspect,
    text,
)

from app.database import engine
from app.notifications_truth.models import NOTIFICATION_TABLE_NAMES, NotificationBase


APPEND_ONLY_TABLES = (
    "notification_occurrence",
    "notification_audit",
    "notification_source_observation",
    "notification_occurrence_transition",
    "notification_delivery_attempt",
)
FAIL_STAGES = {"tables", "triggers", "protections"}
TERMINAL_DELIVERY_STATUSES = ("sent", "failed_exhausted", "expired", "cancelled")
OPEN_DELIVERY_STATUSES = ("pending", "retry_scheduled")


@contextmanager
def _atomic_connection(target_engine: Engine) -> Iterator[Connection]:
    """Use an explicit transaction, including for SQLite DDL."""
    conn = target_engine.connect()
    try:
        if target_engine.dialect.name == "sqlite":
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        else:
            conn.begin()
        try:
            yield conn
        except BaseException:
            conn.rollback()
            raise
        else:
            conn.commit()
    finally:
        conn.close()


def _safe_role(value: str, variable: str) -> str:
    role = value.strip()
    if role and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", role):
        raise RuntimeError(f"invalid {variable}: {role!r}")
    return role


def _trigger_exists(conn: Connection, name: str, table_name: str) -> bool:
    if conn.dialect.name == "sqlite":
        query = (
            "SELECT name FROM sqlite_master "
            "WHERE type='trigger' AND name=:name AND tbl_name=:table_name"
        )
    else:
        query = (
            "SELECT t.tgname FROM pg_trigger t "
            "JOIN pg_class c ON c.oid=t.tgrelid "
            "WHERE t.tgname=:name AND c.relname=:table_name AND NOT t.tgisinternal"
        )
    return (
        conn.execute(
            text(query),
            {"name": name, "table_name": table_name},
        ).first()
        is not None
    )


def _validate_table_shape(conn: Connection, table_name: str) -> None:
    inspector = inspect(conn)
    expected = NotificationBase.metadata.tables[table_name]
    inspected_columns = inspector.get_columns(table_name)
    actual_columns = {column["name"] for column in inspected_columns}
    expected_columns = set(expected.columns.keys())
    if actual_columns != expected_columns:
        raise RuntimeError(
            f"existing {table_name} has incompatible columns; "
            f"expected {sorted(expected_columns)}, got {sorted(actual_columns)}"
        )
    actual_by_name = {column["name"]: column for column in inspected_columns}
    for column in expected.columns:
        actual = actual_by_name[column.name]
        if bool(actual["nullable"]) != bool(column.nullable):
            raise RuntimeError(
                f"existing {table_name}.{column.name} has incompatible nullability"
            )
        actual_type = actual["type"]
        if actual_type._type_affinity is not column.type._type_affinity:
            raise RuntimeError(
                f"existing {table_name}.{column.name} has incompatible type"
            )
        expected_length = getattr(column.type, "length", None)
        actual_length = getattr(actual_type, "length", None)
        if expected_length is not None and actual_length != expected_length:
            raise RuntimeError(
                f"existing {table_name}.{column.name} has incompatible length"
            )

    expected_pk = {column.name for column in expected.primary_key.columns}
    actual_pk = set(inspector.get_pk_constraint(table_name).get("constrained_columns") or ())
    if actual_pk != expected_pk:
        raise RuntimeError(f"existing {table_name} has incompatible primary key")

    expected_unique = {
        constraint.name
        for constraint in expected.constraints
        if isinstance(constraint, UniqueConstraint) and constraint.name
    }
    expected_fks = {
        constraint.name
        for constraint in expected.constraints
        if isinstance(constraint, ForeignKeyConstraint) and constraint.name
    }
    expected_checks = {
        constraint.name
        for constraint in expected.constraints
        if isinstance(constraint, CheckConstraint) and constraint.name
    }
    actual_unique = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints(table_name)
        if constraint.get("name")
    }
    actual_fk_rows = inspector.get_foreign_keys(table_name)
    actual_fks = {
        constraint["name"]
        for constraint in actual_fk_rows
        if constraint.get("name")
    }
    actual_fk_by_name = {
        constraint["name"]: constraint
        for constraint in actual_fk_rows
        if constraint.get("name")
    }
    for constraint in expected.constraints:
        if not isinstance(constraint, ForeignKeyConstraint) or not constraint.name:
            continue
        actual = actual_fk_by_name.get(constraint.name)
        if actual is None:
            continue
        if list(constraint.column_keys) != list(actual.get("constrained_columns") or ()):
            raise RuntimeError(
                f"existing {table_name}.{constraint.name} has incompatible foreign-key columns"
            )
        referred = constraint.elements[0].column.table.name
        if actual.get("referred_table") != referred:
            raise RuntimeError(
                f"existing {table_name}.{constraint.name} points at the wrong parent"
            )
        ondelete = (
            (actual.get("options") or {}).get("ondelete")
            or actual.get("ondelete")
            or ""
        ).upper()
        if ondelete not in {"RESTRICT", "NO ACTION", ""}:
            raise RuntimeError(
                f"existing {table_name}.{constraint.name} has incompatible ON DELETE"
            )
    actual_unique_rows = inspector.get_unique_constraints(table_name)
    actual_unique_by_name = {
        constraint["name"]: constraint
        for constraint in actual_unique_rows
        if constraint.get("name")
    }
    for constraint in expected.constraints:
        if not isinstance(constraint, UniqueConstraint) or not constraint.name:
            continue
        actual = actual_unique_by_name.get(constraint.name)
        if actual is None:
            continue
        if set(constraint.columns.keys()) != set(actual.get("column_names") or ()):
            raise RuntimeError(
                f"existing {table_name}.{constraint.name} has incompatible unique columns"
            )
    actual_checks = {
        constraint["name"]
        for constraint in inspector.get_check_constraints(table_name)
        if constraint.get("name")
    }
    expected_indexes = {index.name for index in expected.indexes if index.name}
    actual_indexes = {
        index["name"]
        for index in inspector.get_indexes(table_name)
        if index.get("name")
    }
    missing_indexes = expected_indexes - actual_indexes
    if missing_indexes:
        raise RuntimeError(
            f"existing {table_name} is missing indexes: "
            + ", ".join(sorted(missing_indexes))
        )
    for label, required, actual in (
        ("unique", expected_unique, actual_unique),
        ("foreign key", expected_fks, actual_fks),
        ("check", expected_checks, actual_checks),
    ):
        missing = required - actual
        if missing:
            raise RuntimeError(
                f"existing {table_name} is missing {label} constraints: "
                + ", ".join(sorted(missing))
            )


def _column_names(conn: Connection, table_name: str) -> set[str]:
    return {column["name"] for column in inspect(conn).get_columns(table_name)}


def _add_column_if_missing(
    conn: Connection, table_name: str, column_name: str, ddl: str
) -> None:
    if column_name in _column_names(conn, table_name):
        return
    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}"))


def _ensure_112_columns(conn: Connection) -> None:
    if not inspect(conn).has_table("notification_event"):
        return
    _add_column_if_missing(
        conn,
        "notification_event",
        "occurrence_count",
        "occurrence_count INTEGER",
    )
    _add_column_if_missing(
        conn,
        "notification_event",
        "last_seen_at",
        "last_seen_at TIMESTAMP",
    )
    if inspect(conn).has_table("notification_delivery"):
        _add_column_if_missing(
            conn,
            "notification_delivery",
            "claimed_until",
            "claimed_until TIMESTAMP",
        )


def _reconstruct_112_history(conn: Connection) -> None:
    if not inspect(conn).has_table("notification_event"):
        return
    columns = _column_names(conn, "notification_event")
    if "created_at" not in columns or "shop_id" not in columns:
        return
    if "occurrence_count" in columns:
        conn.execute(
            text(
                "UPDATE notification_event SET occurrence_count = 1 "
                "WHERE occurrence_count IS NULL"
            )
        )
    if "created_at" in columns and "last_seen_at" in columns:
        conn.execute(
            text(
                "UPDATE notification_event SET last_seen_at = created_at "
                "WHERE last_seen_at IS NULL"
            )
        )
    if inspect(conn).has_table("notification_source") and inspect(conn).has_table(
        "notification_source_observation"
    ):
        conn.execute(
            text(
                "INSERT INTO notification_source_observation ("
                "id, shop_id, source_kind, source_key, observation_token, "
                "event_id, occurrence_seq, created_at"
                ") SELECT "
                "source.id, source.shop_id, source.source_kind, source.source_key, "
                "'initial', source.event_id, source.occurrence_seq, source.created_at "
                "FROM notification_source AS source "
                "WHERE NOT EXISTS ("
                "SELECT 1 FROM notification_source_observation AS observation "
                "WHERE observation.shop_id = source.shop_id "
                "AND observation.source_kind = source.source_kind "
                "AND observation.source_key = source.source_key "
                "AND observation.observation_token = 'initial'"
                ")"
            )
        )
    if inspect(conn).has_table("notification_occurrence") and inspect(conn).has_table(
        "notification_occurrence_transition"
    ):
        conn.execute(
            text(
                "INSERT INTO notification_occurrence_transition ("
                "id, shop_id, event_id, occurrence_seq, transition_seq, "
                "from_status, to_status, cause, created_at"
                ") SELECT occurrence.id, occurrence.shop_id, occurrence.event_id, "
                "occurrence.occurrence_seq, 1, NULL, 'pending', 'reconstructed', "
                "occurrence.created_at "
                "FROM notification_occurrence AS occurrence "
                "WHERE NOT EXISTS ("
                "SELECT 1 FROM notification_occurrence_transition AS transition "
                "WHERE transition.shop_id = occurrence.shop_id "
                "AND transition.event_id = occurrence.event_id "
                "AND transition.occurrence_seq = occurrence.occurrence_seq "
                "AND transition.transition_seq = 1"
                ")"
            )
        )
        conn.execute(
            text(
                "INSERT INTO notification_occurrence_transition ("
                "id, shop_id, event_id, occurrence_seq, transition_seq, "
                "from_status, to_status, cause, created_at"
                ") SELECT "
                "occurrence.id || '-terminal', occurrence.shop_id, occurrence.event_id, "
                "occurrence.occurrence_seq, 2, 'pending', "
                "CASE WHEN event.status = 'cancelled' THEN 'cancelled' "
                "WHEN EXISTS ("
                "SELECT 1 FROM notification_delivery AS delivery "
                "WHERE delivery.shop_id = occurrence.shop_id "
                "AND delivery.event_id = occurrence.event_id "
                "AND delivery.occurrence_seq = occurrence.occurrence_seq "
                "AND delivery.status = 'sent'"
                ") THEN 'delivered' ELSE 'failed' END, "
                "'reconstructed', occurrence.created_at "
                "FROM notification_occurrence AS occurrence "
                "JOIN notification_event AS event "
                "ON event.shop_id = occurrence.shop_id "
                "AND event.id = occurrence.event_id "
                "AND event.occurrence_seq = occurrence.occurrence_seq "
                "WHERE NOT EXISTS ("
                "SELECT 1 FROM notification_occurrence_transition AS transition "
                "WHERE transition.shop_id = occurrence.shop_id "
                "AND transition.event_id = occurrence.event_id "
                "AND transition.occurrence_seq = occurrence.occurrence_seq "
                "AND transition.transition_seq = 2"
                ") AND NOT EXISTS ("
                "SELECT 1 FROM notification_delivery AS delivery "
                "WHERE delivery.shop_id = occurrence.shop_id "
                "AND delivery.event_id = occurrence.event_id "
                "AND delivery.occurrence_seq = occurrence.occurrence_seq "
                "AND delivery.status IN ('pending','retry_scheduled')"
                ") AND ("
                "event.status = 'cancelled' OR EXISTS ("
                "SELECT 1 FROM notification_delivery AS delivery "
                "WHERE delivery.shop_id = occurrence.shop_id "
                "AND delivery.event_id = occurrence.event_id "
                "AND delivery.occurrence_seq = occurrence.occurrence_seq"
                ")"
                ") AND event.status NOT IN ('acknowledged','resolved','recorded')"
            )
        )


def _postgres_constraint_exists(conn: Connection, name: str) -> bool:
    return (
        conn.execute(
            text("SELECT 1 FROM pg_constraint WHERE conname=:name"),
            {"name": name},
        ).first()
        is not None
    )


def _finalize_112_columns(conn: Connection) -> None:
    if conn.dialect.name != "postgresql":
        return
    if not inspect(conn).has_table("notification_event"):
        return
    columns = _column_names(conn, "notification_event")
    if "occurrence_count" in columns:
        conn.execute(
            text(
                "ALTER TABLE notification_event "
                "ALTER COLUMN occurrence_count SET DEFAULT 1"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE notification_event "
                "ALTER COLUMN occurrence_count SET NOT NULL"
            )
        )
        if not _postgres_constraint_exists(conn, "ck_notification_event_occurrence_count"):
            conn.execute(
                text(
                    "ALTER TABLE notification_event ADD CONSTRAINT "
                    "ck_notification_event_occurrence_count CHECK (occurrence_count >= 1)"
                )
            )
    if "last_seen_at" in columns:
        conn.execute(
            text(
                "ALTER TABLE notification_event "
                "ALTER COLUMN last_seen_at SET DEFAULT now()"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE notification_event "
                "ALTER COLUMN last_seen_at SET NOT NULL"
            )
        )


def _create_terminal_reopen_guard(conn: Connection, applied: dict[str, list[str]]) -> None:
    trigger_name = "trg_notification_delivery_no_reopen"
    if _trigger_exists(conn, trigger_name, "notification_delivery"):
        return
    if conn.dialect.name == "sqlite":
        conn.execute(
            text(
                f"CREATE TRIGGER {trigger_name} BEFORE UPDATE ON notification_delivery "
                "FOR EACH ROW WHEN OLD.status IN "
                "('sent','failed_exhausted','expired','cancelled') "
                "AND NEW.status IN ('pending','retry_scheduled') "
                "BEGIN SELECT RAISE(ABORT, 'terminal delivery cannot reopen'); END"
            )
        )
    else:
        conn.execute(
            text(
                "CREATE OR REPLACE FUNCTION notification_reject_terminal_reopen() "
                "RETURNS trigger AS $$ BEGIN "
                "IF OLD.status IN ('sent','failed_exhausted','expired','cancelled') "
                "AND NEW.status IN ('pending','retry_scheduled') THEN "
                "RAISE EXCEPTION 'terminal delivery cannot reopen'; "
                "END IF; RETURN NEW; END; $$ LANGUAGE plpgsql"
            )
        )
        conn.execute(
            text(
                f"CREATE TRIGGER {trigger_name} BEFORE UPDATE ON notification_delivery "
                "FOR EACH ROW EXECUTE FUNCTION notification_reject_terminal_reopen()"
            )
        )
    applied["triggers"].append(trigger_name)


def _grant_runtime_privileges(conn: Connection) -> None:
    if conn.dialect.name == "sqlite":
        return
    runtime_role = _safe_role(
        os.environ.get("STASHTAB_NOTIFICATION_RUNTIME_ROLE", ""),
        "STASHTAB_NOTIFICATION_RUNTIME_ROLE",
    )
    if not runtime_role:
        return
    append_only = (
        "notification_occurrence",
        "notification_audit",
        "notification_source_observation",
        "notification_occurrence_transition",
        "notification_delivery_attempt",
    )
    for table_name in NOTIFICATION_TABLE_NAMES:
        conn.execute(text(f'REVOKE TRUNCATE, DELETE ON {table_name} FROM "{runtime_role}"'))
    for table_name in append_only:
        conn.execute(text(f'GRANT SELECT, INSERT ON {table_name} TO "{runtime_role}"'))
        conn.execute(text(f'REVOKE UPDATE ON {table_name} FROM "{runtime_role}"'))
    conn.execute(
        text(
            'GRANT SELECT, INSERT, UPDATE ON notification_recovery_park '
            f'TO "{runtime_role}"'
        )
    )


def _create_append_only_triggers(conn: Connection, applied: dict[str, list[str]]) -> None:
    if conn.dialect.name != "sqlite":
        conn.execute(
            text(
                "CREATE OR REPLACE FUNCTION notification_reject_append_mutation() "
                "RETURNS trigger AS $$ BEGIN "
                "RAISE EXCEPTION '%', TG_ARGV[0]; END; "
                "$$ LANGUAGE plpgsql"
            )
        )

    for table_name in APPEND_ONLY_TABLES:
        for action in ("UPDATE", "DELETE"):
            trigger_name = f"trg_{table_name}_no_{action.lower()}"
            if _trigger_exists(conn, trigger_name, table_name):
                continue
            if conn.dialect.name == "sqlite":
                ddl = (
                    f"CREATE TRIGGER {trigger_name} BEFORE {action} ON {table_name} "
                    "FOR EACH ROW BEGIN SELECT RAISE(ABORT, "
                    f"'{table_name} is append-only: {action} rejected'); END"
                )
            else:
                ddl = (
                    f"CREATE TRIGGER {trigger_name} BEFORE {action} ON {table_name} "
                    "FOR EACH ROW EXECUTE FUNCTION notification_reject_append_mutation("
                    f"'{table_name} is append-only: {action} rejected')"
                )
            conn.execute(text(ddl))
            applied["triggers"].append(trigger_name)


def _create_postgres_truncate_protection(
    conn: Connection, applied: dict[str, list[str]]
) -> None:
    if conn.dialect.name == "sqlite":
        return

    migrator_role = _safe_role(
        os.environ.get("STASHTAB_NOTIFICATION_MIGRATOR_ROLE", ""),
        "STASHTAB_NOTIFICATION_MIGRATOR_ROLE",
    )
    runtime_role = _safe_role(
        os.environ.get("STASHTAB_NOTIFICATION_RUNTIME_ROLE", ""),
        "STASHTAB_NOTIFICATION_RUNTIME_ROLE",
    )
    allow_expression = (
        f"(current_user = '{migrator_role}')"
        if migrator_role
        else "false"
    )
    conn.execute(
        text(
            "CREATE OR REPLACE FUNCTION notification_deny_truncate() "
            "RETURNS trigger AS $$ BEGIN "
            f"IF NOT {allow_expression} THEN "
            "RAISE EXCEPTION 'TRUNCATE denied on %: append-only "
            "(controlled migrator role only)', TG_TABLE_NAME; "
            "END IF; RETURN NULL; END; "
            "$$ LANGUAGE plpgsql"
        )
    )

    for table_name in APPEND_ONLY_TABLES:
        trigger_name = f"trg_{table_name}_no_truncate"
        if not _trigger_exists(conn, trigger_name, table_name):
            conn.execute(
                text(
                    f"CREATE TRIGGER {trigger_name} BEFORE TRUNCATE ON {table_name} "
                    "FOR EACH STATEMENT EXECUTE FUNCTION notification_deny_truncate()"
                )
            )
            applied["protections"].append(trigger_name)
        conn.execute(text(f"REVOKE TRUNCATE ON {table_name} FROM PUBLIC"))
        if runtime_role:
            exists = conn.execute(
                text("SELECT 1 FROM pg_roles WHERE rolname=:role"),
                {"role": runtime_role},
            ).first()
            if exists is None:
                raise RuntimeError(
                    "configured STASHTAB_NOTIFICATION_RUNTIME_ROLE does not exist"
                )
            conn.execute(
                text(
                    f'REVOKE UPDATE, DELETE, TRUNCATE ON {table_name} '
                    f'FROM "{runtime_role}"'
                )
            )


def apply_notification_schema(
    target_engine: Engine = engine, *, fail_after: str | None = None
) -> dict[str, list[str]]:
    """Atomically create and protect the twelve canonical notification tables.

    ``fail_after`` is a test-only hook accepting ``tables``, ``triggers``, or
    ``protections``. Any injected failure rolls back the entire migration.
    """
    if fail_after is not None and fail_after not in FAIL_STAGES:
        raise ValueError(f"unknown fail_after stage: {fail_after}")

    applied: dict[str, list[str]] = {
        "tables": [],
        "triggers": [],
        "protections": [],
    }
    with _atomic_connection(target_engine) as conn:
        _ensure_112_columns(conn)
        inspector = inspect(conn)
        missing = [
            NotificationBase.metadata.tables[name]
            for name in NOTIFICATION_TABLE_NAMES
            if not inspector.has_table(name)
        ]
        if missing:
            NotificationBase.metadata.create_all(bind=conn, tables=missing)
            applied["tables"] = [table.name for table in missing]
        _reconstruct_112_history(conn)
        _finalize_112_columns(conn)
        for table_name in NOTIFICATION_TABLE_NAMES:
            _validate_table_shape(conn, table_name)

        if fail_after == "tables":
            raise RuntimeError("injected notification migration failure after tables")

        _create_append_only_triggers(conn, applied)
        _create_terminal_reopen_guard(conn, applied)
        if fail_after == "triggers":
            raise RuntimeError("injected notification migration failure after triggers")

        _create_postgres_truncate_protection(conn, applied)
        _grant_runtime_privileges(conn)
        if fail_after == "protections":
            raise RuntimeError(
                "injected notification migration failure after protections"
            )

        verify = inspect(conn)
        missing_after = [
            name for name in NOTIFICATION_TABLE_NAMES if not verify.has_table(name)
        ]
        if missing_after:
            raise RuntimeError(
                "notification migrator verification failed; missing: "
                + ", ".join(missing_after)
            )
        for table_name in APPEND_ONLY_TABLES:
            for action in ("update", "delete"):
                name = f"trg_{table_name}_no_{action}"
                if not _trigger_exists(conn, name, table_name):
                    raise RuntimeError(
                        f"notification migrator verification failed; trigger {name} missing"
                    )

    return applied


# Short alias for consistency with the inventory-truth migrator.
apply = apply_notification_schema

