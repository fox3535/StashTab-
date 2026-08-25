"""Focused acceptance tests for the migrator-owned notification schema."""

import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.pool import StaticPool

from app.models import Base, Shop
from app.notifications_truth.migrator import apply_notification_schema
from app.notifications_truth.models import (
    AUDIT_ACTIONS,
    DELIVERY_STATUSES,
    EVENT_STATUSES,
    NOTIFICATION_TABLE_NAMES,
    OCCURRENCE_STATUSES,
    SEVERITIES,
    NotificationAudit,
    NotificationBase,
    NotificationEvent,
    NotificationOccurrence,
)


def _engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _foreign_keys(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            Shop.__table__.insert(),
            [
                {"id": "shop-a", "name": "A", "slug": "a"},
                {"id": "shop-b", "name": "B", "slug": "b"},
            ],
        )
    return engine


def _migrated():
    engine = _engine()
    apply_notification_schema(engine)
    return engine


def _event(conn, event_id="event-a", shop_id="shop-a", dedupe_key="source:1"):
    conn.execute(
        NotificationEvent.__table__.insert(),
        {
            "id": event_id,
            "shop_id": shop_id,
            "category": "test",
            "severity": "action_required",
            "title": "StashTab needs a review",
            "body": "Open StashTab.",
            "action_url": "/admin/settings",
            "dedupe_key": dedupe_key,
            "status": "pending",
            "occurrence_seq": 1,
        },
    )


def test_application_base_excludes_notification_schema():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    assert set(NOTIFICATION_TABLE_NAMES).isdisjoint(inspect(engine).get_table_names())
    assert set(NOTIFICATION_TABLE_NAMES).isdisjoint(Base.metadata.tables)
    assert set(NOTIFICATION_TABLE_NAMES) <= set(NotificationBase.metadata.tables)


def test_migrator_creates_canonical_tables_and_is_idempotent():
    engine = _engine()
    first = apply_notification_schema(engine)
    second = apply_notification_schema(engine)
    assert set(first["tables"]) == set(NOTIFICATION_TABLE_NAMES)
    assert len(first["triggers"]) >= 10
    assert second == {"tables": [], "triggers": [], "protections": []}


def test_migrator_rejects_preexisting_malformed_canonical_table():
    engine = _engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE notification_event (id TEXT PRIMARY KEY)"))
    with pytest.raises(RuntimeError, match="incompatible columns"):
        apply_notification_schema(engine)


@pytest.mark.parametrize("stage", ["tables", "triggers", "protections"])
def test_migrator_failure_rolls_back_atomically(stage):
    engine = _engine()
    with pytest.raises(RuntimeError, match="injected"):
        apply_notification_schema(engine, fail_after=stage)
    assert set(NOTIFICATION_TABLE_NAMES).isdisjoint(inspect(engine).get_table_names())


def test_exact_state_sets_are_frozen():
    assert SEVERITIES == ("routine", "action_required", "critical")
    assert EVENT_STATUSES == (
        "pending",
        "delivered",
        "failed",
        "acknowledged",
        "resolved",
        "cancelled",
        "recorded",
    )
    assert OCCURRENCE_STATUSES == ("pending", "delivered", "failed", "cancelled")
    assert DELIVERY_STATUSES == (
        "pending",
        "retry_scheduled",
        "sent",
        "failed_exhausted",
        "expired",
        "cancelled",
    )
    assert AUDIT_ACTIONS == (
        "critical_disable",
        "critical_enable",
        "test_send",
        "ack",
        "resolve",
        "cancel",
        "reopen",
        "occurrence_count_increment",
    )


@pytest.mark.parametrize("table_name", ["notification_occurrence", "notification_audit"])
@pytest.mark.parametrize("action", ["UPDATE", "DELETE"])
def test_append_only_tables_reject_mutation(table_name, action):
    engine = _migrated()
    with engine.begin() as conn:
        _event(conn)
        if table_name == "notification_occurrence":
            conn.execute(
                NotificationOccurrence.__table__.insert(),
                {
                    "id": "occ-1",
                    "shop_id": "shop-a",
                    "event_id": "event-a",
                    "occurrence_seq": 1,
                    "cause": "created",
                },
            )
            statement = (
                "UPDATE notification_occurrence SET cause='changed' WHERE id='occ-1'"
                if action == "UPDATE"
                else "DELETE FROM notification_occurrence WHERE id='occ-1'"
            )
        else:
            conn.execute(
                NotificationAudit.__table__.insert(),
                {
                    "id": "audit-1",
                    "shop_id": "shop-a",
                    "actor_clerk_user_id": "user-a",
                    "action": "ack",
                    "event_id": "event-a",
                },
            )
            statement = (
                "UPDATE notification_audit SET action='resolve' WHERE id='audit-1'"
                if action == "UPDATE"
                else "DELETE FROM notification_audit WHERE id='audit-1'"
            )
        with pytest.raises(DBAPIError, match="append-only"):
            conn.execute(text(statement))


def test_cross_shop_occurrence_and_delivery_are_rejected():
    engine = _migrated()
    with engine.begin() as conn:
        _event(conn)
        with pytest.raises(IntegrityError):
            conn.execute(
                NotificationOccurrence.__table__.insert(),
                {
                    "id": "occ-b",
                    "shop_id": "shop-b",
                    "event_id": "event-a",
                    "occurrence_seq": 1,
                    "cause": "cross-shop",
                },
            )
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO push_subscription "
                "(id, shop_id, clerk_user_id, endpoint, p256dh, auth, enabled, failure_count) "
                "VALUES ('sub-b', 'shop-b', 'user-b', 'https://push/b', 'p', 'a', 1, 0)"
            )
        )
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO notification_delivery "
                    "(id, shop_id, event_id, occurrence_seq, subscription_id, "
                    "delivery_generation, status, attempt_count) "
                    "VALUES ('delivery-cross', 'shop-a', 'event-a', 1, 'sub-b', 1, "
                    "'pending', 0)"
                )
            )


def test_delivery_identity_and_source_identity_are_database_unique():
    engine = _migrated()
    with engine.begin() as conn:
        _event(conn)
        conn.execute(
            NotificationOccurrence.__table__.insert(),
            {
                "id": "occ-a",
                "shop_id": "shop-a",
                "event_id": "event-a",
                "occurrence_seq": 1,
                "cause": "created",
            },
        )
        conn.execute(
            text(
                "INSERT INTO push_subscription "
                "(id, shop_id, clerk_user_id, endpoint, p256dh, auth, enabled, failure_count) "
                "VALUES ('sub-a', 'shop-a', 'user-a', 'https://push/a', 'p', 'a', 1, 0)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO notification_delivery "
                "(id, shop_id, event_id, occurrence_seq, subscription_id, "
                "delivery_generation, status, attempt_count) "
                "VALUES ('delivery-1', 'shop-a', 'event-a', 1, 'sub-a', 1, 'pending', 0)"
            )
        )
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO notification_delivery "
                    "(id, shop_id, event_id, occurrence_seq, subscription_id, "
                    "delivery_generation, status, attempt_count) "
                    "VALUES ('delivery-2', 'shop-a', 'event-a', 1, 'sub-a', 1, "
                    "'pending', 0)"
                )
            )
