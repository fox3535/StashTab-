"""PostgreSQL proofs for frozen notification 1.1.2."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.inventory_truth.migrator import apply as apply_inventory
from app.inventory_truth.models_truth import InventoryEvent, InventoryException
from app.logic.notifications import (
    PATTERN_B_OBSERVATION_TOKEN,
    cancel_notification,
    create_notification,
    occurrence_status,
    process_pending_notifications,
    recover_notification_sources,
    _recover_stale_attempts,
)
import worker
from app.main import app
from app.models import PurchaseRecord, Sale, Shop, ShopMember
from app.models.base import utcnow
from app.notifications_truth.migrator import apply_notification_schema
from app.notifications_truth.models import (
    NOTIFICATION_TABLE_NAMES,
    NotificationAudit,
    NotificationDelivery,
    NotificationDeliveryAttempt,
    NotificationEvent,
    NotificationOccurrence,
    NotificationOccurrenceTransition,
    NotificationRecoveryPark,
    NotificationSourceObservation,
    PushSubscription,
)
from tests.test_notification_pg import _fresh_db

pytestmark = pytest.mark.skipif(
    not __import__("os").environ.get("STASHTAB_PG_URL"),
    reason="STASHTAB_PG_URL not set",
)


@pytest.fixture
def pg_engine():
    engine = _fresh_db()
    yield engine
    engine.dispose()


def _session(engine):
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)()


def _enable_push(monkeypatch):
    monkeypatch.setattr(settings, "vapid_public_key", "test-public")
    monkeypatch.setattr(settings, "vapid_private_key", "test-private")
    monkeypatch.setattr(settings, "vapid_subject", "mailto:tests@stashtab.invalid")


def _seed_shop(db, shop_id="shop-a"):
    db.add(Shop(id=shop_id, name=shop_id, slug=shop_id))
    db.add(
        ShopMember(
            id=f"member-{shop_id}",
            shop_id=shop_id,
            clerk_user_id="user-a",
            role="owner",
        )
    )
    db.commit()


def _subscribe(db, shop_id="shop-a", user="user-a", endpoint="https://fcm.googleapis.com/fcm/send/pg"):
    row = PushSubscription(
        shop_id=shop_id,
        clerk_user_id=user,
        endpoint=endpoint,
        p256dh="p256dh-key-value",
        auth="auth-key-value",
        enabled=True,
    )
    db.add(row)
    db.commit()
    return row


def test_pg_create_all_does_not_create_notification_tables(pg_engine):
    names = set(inspect(pg_engine).get_table_names())
    assert set(NOTIFICATION_TABLE_NAMES).isdisjoint(names)


def test_pg_upgrade_from_simulated_111_preserves_history(pg_engine):
    with pg_engine.begin() as conn:
        conn.execute(
            Shop.__table__.insert(),
            {"id": "shop-a", "name": "A", "slug": "a"},
        )
        conn.execute(
            text(
                """
                CREATE TABLE notification_event (
                    id VARCHAR(36) PRIMARY KEY,
                    shop_id VARCHAR(36) NOT NULL,
                    category VARCHAR(64) NOT NULL,
                    severity VARCHAR(24) NOT NULL,
                    title VARCHAR(160) NOT NULL,
                    body VARCHAR(500) NOT NULL,
                    action_url VARCHAR(500) NOT NULL,
                    dedupe_key VARCHAR(160) NOT NULL,
                    status VARCHAR(24) NOT NULL,
                    occurrence_seq INTEGER NOT NULL DEFAULT 1,
                    acknowledged_by VARCHAR(120),
                    acknowledged_at TIMESTAMPTZ,
                    resolved_at TIMESTAMPTZ,
                    cancelled_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    CONSTRAINT uq_notification_event_shop_id UNIQUE (shop_id, id),
                    CONSTRAINT uq_notification_event_shop_dedupe UNIQUE (shop_id, dedupe_key),
                    CONSTRAINT fk_notification_event_shop FOREIGN KEY (shop_id)
                        REFERENCES shops(id) ON DELETE RESTRICT,
                    CONSTRAINT ck_notification_event_severity
                        CHECK (severity IN ('routine','action_required','critical')),
                    CONSTRAINT ck_notification_event_status
                        CHECK (status IN ('pending','delivered','failed','acknowledged','resolved','cancelled','recorded')),
                    CONSTRAINT ck_notification_event_occurrence_seq CHECK (occurrence_seq >= 1)
                )
                """
            )
        )
        conn.execute(
            text(
                "CREATE INDEX ix_notification_event_shop_status_created "
                "ON notification_event (shop_id, status, created_at)"
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE notification_occurrence (
                    id VARCHAR(36) PRIMARY KEY,
                    shop_id VARCHAR(36) NOT NULL,
                    event_id VARCHAR(36) NOT NULL,
                    occurrence_seq INTEGER NOT NULL,
                    cause VARCHAR(255) NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    CONSTRAINT uq_notification_occurrence_shop_event_seq
                        UNIQUE (shop_id, event_id, occurrence_seq),
                    CONSTRAINT fk_notification_occurrence_shop FOREIGN KEY (shop_id)
                        REFERENCES shops(id) ON DELETE RESTRICT,
                    CONSTRAINT fk_notification_occurrence_shop_event
                        FOREIGN KEY (shop_id, event_id)
                        REFERENCES notification_event(shop_id, id) ON DELETE RESTRICT,
                    CONSTRAINT ck_notification_occurrence_seq CHECK (occurrence_seq >= 1)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE push_subscription (
                    id VARCHAR(36) PRIMARY KEY,
                    shop_id VARCHAR(36) NOT NULL,
                    clerk_user_id VARCHAR(120) NOT NULL,
                    endpoint TEXT NOT NULL,
                    p256dh TEXT NOT NULL,
                    auth TEXT NOT NULL,
                    enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    failure_count INTEGER NOT NULL DEFAULT 0,
                    last_success_at TIMESTAMPTZ,
                    replaced_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    CONSTRAINT uq_push_subscription_shop_id UNIQUE (shop_id, id),
                    CONSTRAINT uq_push_subscription_shop_endpoint UNIQUE (shop_id, endpoint),
                    CONSTRAINT fk_push_subscription_shop FOREIGN KEY (shop_id)
                        REFERENCES shops(id) ON DELETE RESTRICT,
                    CONSTRAINT ck_push_subscription_failure_count CHECK (failure_count >= 0)
                )
                """
            )
        )
        conn.execute(
            text(
                "CREATE INDEX ix_push_subscription_shop_user "
                "ON push_subscription (shop_id, clerk_user_id)"
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE notification_delivery (
                    id VARCHAR(36) PRIMARY KEY,
                    shop_id VARCHAR(36) NOT NULL,
                    event_id VARCHAR(36) NOT NULL,
                    occurrence_seq INTEGER NOT NULL,
                    subscription_id VARCHAR(36) NOT NULL,
                    delivery_generation INTEGER NOT NULL DEFAULT 1,
                    status VARCHAR(24) NOT NULL,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    next_retry_at TIMESTAMPTZ,
                    attempted_at TIMESTAMPTZ,
                    error VARCHAR(500),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    CONSTRAINT uq_notification_delivery_shop_id UNIQUE (shop_id, id),
                    CONSTRAINT uq_notification_delivery_identity UNIQUE (
                        shop_id, event_id, occurrence_seq, subscription_id, delivery_generation
                    ),
                    CONSTRAINT fk_notification_delivery_shop FOREIGN KEY (shop_id)
                        REFERENCES shops(id) ON DELETE RESTRICT,
                    CONSTRAINT fk_notification_delivery_shop_event
                        FOREIGN KEY (shop_id, event_id)
                        REFERENCES notification_event(shop_id, id) ON DELETE RESTRICT,
                    CONSTRAINT fk_notification_delivery_shop_occurrence
                        FOREIGN KEY (shop_id, event_id, occurrence_seq)
                        REFERENCES notification_occurrence(shop_id, event_id, occurrence_seq)
                        ON DELETE RESTRICT,
                    CONSTRAINT fk_notification_delivery_shop_subscription
                        FOREIGN KEY (shop_id, subscription_id)
                        REFERENCES push_subscription(shop_id, id) ON DELETE RESTRICT,
                    CONSTRAINT ck_notification_delivery_status
                        CHECK (status IN ('pending','retry_scheduled','sent','failed_exhausted','expired','cancelled')),
                    CONSTRAINT ck_notification_delivery_generation CHECK (delivery_generation >= 1),
                    CONSTRAINT ck_notification_delivery_attempt_count
                        CHECK (attempt_count >= 0 AND attempt_count <= 8)
                )
                """
            )
        )
        conn.execute(
            text(
                "CREATE INDEX ix_notification_delivery_shop_retry_created "
                "ON notification_delivery (shop_id, next_retry_at, created_at)"
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE notification_source (
                    id VARCHAR(36) PRIMARY KEY,
                    shop_id VARCHAR(36) NOT NULL,
                    source_kind VARCHAR(64) NOT NULL,
                    source_key VARCHAR(255) NOT NULL,
                    event_id VARCHAR(36) NOT NULL,
                    occurrence_seq INTEGER NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    CONSTRAINT uq_notification_source_identity
                        UNIQUE (shop_id, source_kind, source_key),
                    CONSTRAINT fk_notification_source_shop FOREIGN KEY (shop_id)
                        REFERENCES shops(id) ON DELETE RESTRICT,
                    CONSTRAINT fk_notification_source_shop_event
                        FOREIGN KEY (shop_id, event_id)
                        REFERENCES notification_event(shop_id, id) ON DELETE RESTRICT,
                    CONSTRAINT fk_notification_source_shop_occurrence
                        FOREIGN KEY (shop_id, event_id, occurrence_seq)
                        REFERENCES notification_occurrence(shop_id, event_id, occurrence_seq)
                        ON DELETE RESTRICT,
                    CONSTRAINT ck_notification_source_occurrence_seq CHECK (occurrence_seq >= 1)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE notification_preference (
                    id VARCHAR(36) PRIMARY KEY,
                    shop_id VARCHAR(36) NOT NULL,
                    clerk_user_id VARCHAR(120) NOT NULL,
                    web_push_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    action_required_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    critical_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    quiet_hours_start VARCHAR(5),
                    quiet_hours_end VARCHAR(5),
                    timezone VARCHAR(64) NOT NULL DEFAULT 'America/Toronto',
                    CONSTRAINT uq_notification_preference_shop_user
                        UNIQUE (shop_id, clerk_user_id),
                    CONSTRAINT fk_notification_preference_shop FOREIGN KEY (shop_id)
                        REFERENCES shops(id) ON DELETE RESTRICT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE shop_notification_policy (
                    shop_id VARCHAR(36) PRIMARY KEY,
                    critical_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    CONSTRAINT fk_shop_notification_policy_shop FOREIGN KEY (shop_id)
                        REFERENCES shops(id) ON DELETE RESTRICT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE notification_audit (
                    id VARCHAR(36) PRIMARY KEY,
                    shop_id VARCHAR(36) NOT NULL,
                    actor_clerk_user_id VARCHAR(120) NOT NULL,
                    action VARCHAR(32) NOT NULL,
                    category VARCHAR(64),
                    prior_state VARCHAR(64),
                    new_state VARCHAR(64),
                    event_id VARCHAR(36),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    CONSTRAINT fk_notification_audit_shop FOREIGN KEY (shop_id)
                        REFERENCES shops(id) ON DELETE RESTRICT,
                    CONSTRAINT ck_notification_audit_action CHECK (action IN (
                        'critical_disable','critical_enable','test_send','ack',
                        'resolve','cancel','reopen','occurrence_count_increment'
                    )),
                    CONSTRAINT fk_notification_audit_shop_event
                        FOREIGN KEY (shop_id, event_id)
                        REFERENCES notification_event(shop_id, id) ON DELETE RESTRICT
                )
                """
            )
        )
        conn.execute(
            text(
                "INSERT INTO push_subscription "
                "(id, shop_id, clerk_user_id, endpoint, p256dh, auth, enabled) "
                "VALUES ('sub-a','shop-a','user-a',"
                "'https://fcm.googleapis.com/fcm/send/a','k','s',TRUE)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO notification_event "
                "(id, shop_id, category, severity, title, body, action_url, "
                "dedupe_key, status, occurrence_seq) VALUES "
                "('event-a','shop-a','test','action_required',"
                "'StashTab notifications are ready',"
                "'Phone alerts are connected to this shop.','/admin/settings',"
                "'test:preserved','pending',1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO notification_occurrence "
                "(id, shop_id, event_id, occurrence_seq, cause) "
                "VALUES ('occ-a','shop-a','event-a',1,'created')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO notification_delivery "
                "(id, shop_id, event_id, occurrence_seq, subscription_id, "
                "delivery_generation, status, attempt_count) VALUES "
                "('delivery-a','shop-a','event-a',1,'sub-a',1,'pending',0)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO notification_source "
                "(id, shop_id, source_kind, source_key, event_id, occurrence_seq) "
                "VALUES ('source-a','shop-a','inventory_exception','exc-a','event-a',1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO notification_audit "
                "(id, shop_id, actor_clerk_user_id, action, event_id) "
                "VALUES ('audit-a','shop-a','user-a','test_send','event-a')"
            )
        )
    first = apply_notification_schema(pg_engine)
    second = apply_notification_schema(pg_engine)
    names = set(inspect(pg_engine).get_table_names())
    assert set(NOTIFICATION_TABLE_NAMES) <= names
    assert set(NOTIFICATION_TABLE_NAMES) <= set(first["tables"]).union(
        {
            "notification_event",
            "notification_occurrence",
            "notification_delivery",
            "notification_source",
            "push_subscription",
            "notification_preference",
            "shop_notification_policy",
            "notification_audit",
        }
    )
    assert second["tables"] == []
    with pg_engine.begin() as conn:
        event = conn.execute(
            text(
                "SELECT occurrence_count, last_seen_at, created_at "
                "FROM notification_event WHERE id='event-a'"
            )
        ).one()
        assert event.occurrence_count == 1
        assert event.last_seen_at.replace(tzinfo=None) == event.created_at.replace(tzinfo=None)
        assert conn.execute(
            text("SELECT id FROM notification_occurrence WHERE id='occ-a'")
        ).scalar_one() == "occ-a"
        assert conn.execute(
            text("SELECT id, status FROM notification_delivery WHERE id='delivery-a'")
        ).one() == ("delivery-a", "pending")
        assert conn.execute(
            text(
                "SELECT observation_token FROM notification_source_observation "
                "WHERE source_key='exc-a'"
            )
        ).scalar_one() == "initial"
        assert conn.execute(
            text(
                "SELECT transition_seq, to_status FROM notification_occurrence_transition "
                "WHERE event_id='event-a' ORDER BY transition_seq"
            )
        ).all() == [(1, "pending")]
        assert conn.execute(text("SELECT count(*) FROM notification_delivery_attempt")).scalar_one() == 0


def test_pg_definitions_are_structural(pg_engine):
    apply_notification_schema(pg_engine)
    with pg_engine.begin() as conn:
        fk = conn.execute(
            text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname='fk_notification_source_observation_shop_event'"
            )
        ).scalar_one()
        assert "FOREIGN KEY (shop_id, event_id)" in fk
        assert "REFERENCES notification_event(shop_id, id)" in fk
        assert "ON DELETE RESTRICT" in fk
        uniq = conn.execute(
            text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname='uq_notification_source_observation_identity'"
            )
        ).scalar_one()
        assert "shop_id" in uniq and "observation_token" in uniq
        trigger = conn.execute(
            text(
                "SELECT pg_get_triggerdef(t.oid) FROM pg_trigger t "
                "JOIN pg_class c ON c.oid=t.tgrelid "
                "WHERE t.tgname='trg_notification_occurrence_transition_no_update'"
            )
        ).scalar_one()
        assert "BEFORE UPDATE" in trigger
        assert "notification_reject_append_mutation" in trigger
        idx = conn.execute(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE indexname='uq_notification_occurrence_terminal_transition'"
            )
        ).scalar_one()
        assert "UNIQUE" in idx
        assert "to_status" in idx


def test_pg_cross_shop_observation_and_attempt_fail(pg_engine):
    apply_notification_schema(pg_engine)
    with pg_engine.begin() as conn:
        conn.execute(
            Shop.__table__.insert(),
            [
                {"id": "shop-a", "name": "A", "slug": "a"},
                {"id": "shop-b", "name": "B", "slug": "b"},
            ],
        )
        conn.execute(
            text(
                "INSERT INTO notification_event "
                "(id, shop_id, category, severity, title, body, action_url, "
                "dedupe_key, status, occurrence_seq, occurrence_count) VALUES "
                "('event-a','shop-a','test','action_required','t','b','/admin/settings',"
                "'d-a','pending',1,1), "
                "('event-b','shop-b','test','action_required','t','b','/admin/settings',"
                "'d-b','pending',1,1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO notification_occurrence "
                "(id, shop_id, event_id, occurrence_seq, cause) VALUES "
                "('occ-a','shop-a','event-a',1,'created'), "
                "('occ-b','shop-b','event-b',1,'created')"
            )
        )
    with pytest.raises(IntegrityError):
        with pg_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO notification_source_observation "
                    "(id, shop_id, source_kind, source_key, observation_token, "
                    "event_id, occurrence_seq) VALUES "
                    "('obs-x','shop-b','inventory_exception','1','tok','event-a',1)"
                )
            )


def test_pg_runtime_cannot_mutate_append_only_or_assume_migrator(pg_engine, monkeypatch):
    with pg_engine.begin() as conn:
        for role in ("stashtab_notification_runtime", "stashtab_notification_migrator"):
            exists = conn.execute(
                text("SELECT 1 FROM pg_roles WHERE rolname=:role"),
                {"role": role},
            ).first()
            if exists:
                conn.execute(text(f"DROP OWNED BY {role}"))
            conn.execute(text(f"DROP ROLE IF EXISTS {role}"))
        conn.execute(text("CREATE ROLE stashtab_notification_runtime NOLOGIN"))
        conn.execute(text("CREATE ROLE stashtab_notification_migrator NOLOGIN"))
    monkeypatch.setenv("STASHTAB_NOTIFICATION_RUNTIME_ROLE", "stashtab_notification_runtime")
    monkeypatch.setenv("STASHTAB_NOTIFICATION_MIGRATOR_ROLE", "stashtab_notification_migrator")
    apply_notification_schema(pg_engine)
    with pg_engine.begin() as conn:
        conn.execute(Shop.__table__.insert(), {"id": "shop-a", "name": "A", "slug": "a"})
        conn.execute(
            text(
                "INSERT INTO notification_event "
                "(id, shop_id, category, severity, title, body, action_url, "
                "dedupe_key, status) VALUES "
                "('event-a','shop-a','test','action_required','t','b','/admin/settings',"
                "'d','pending')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO notification_occurrence "
                "(id, shop_id, event_id, occurrence_seq, cause) "
                "VALUES ('occ-a','shop-a','event-a',1,'created')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO notification_occurrence_transition "
                "(id, shop_id, event_id, occurrence_seq, transition_seq, "
                "from_status, to_status, cause) VALUES "
                "('tr-1','shop-a','event-a',1,1,NULL,'pending','created')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO notification_source_observation "
                "(id, shop_id, source_kind, source_key, observation_token, "
                "event_id, occurrence_seq) VALUES "
                "('obs-1','shop-a','inventory_exception','1','initial','event-a',1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO notification_audit "
                "(id, shop_id, actor_clerk_user_id, action) "
                "VALUES ('audit-a','shop-a','user-a','test_send')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO notification_recovery_park "
                "(id, shop_id, source_kind, source_key, fail_count, next_at) "
                "VALUES ('park-a','shop-a','inventory_exception','later',1, now() + interval '1 hour')"
            )
        )
        conn.execute(text("GRANT USAGE ON SCHEMA public TO stashtab_notification_runtime"))
        conn.execute(
            text(
                "GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON "
                "notification_occurrence_transition, notification_delivery_attempt, "
                "notification_source_observation, notification_audit, "
                "notification_occurrence, notification_recovery_park "
                "TO stashtab_notification_runtime"
            )
        )
    apply_notification_schema(pg_engine)
    blocked = [
        "UPDATE notification_occurrence_transition SET cause='x' WHERE id='tr-1'",
        "DELETE FROM notification_source_observation WHERE id='obs-1'",
        "TRUNCATE notification_audit",
        "DELETE FROM notification_recovery_park WHERE id='park-a'",
        "TRUNCATE notification_recovery_park",
    ]
    for statement in blocked:
        with pytest.raises(DBAPIError):
            with pg_engine.begin() as conn:
                conn.execute(text("SET ROLE stashtab_notification_runtime"))
                conn.execute(text(statement))
    with pg_engine.begin() as conn:
        conn.execute(text("SET ROLE stashtab_notification_runtime"))
        conn.execute(
            text(
                "UPDATE notification_recovery_park SET fail_count=2 WHERE id='park-a'"
            )
        )
        membership = conn.execute(
            text(
                "SELECT 1 FROM pg_auth_members m "
                "JOIN pg_roles r ON r.oid=m.roleid "
                "JOIN pg_roles u ON u.oid=m.member "
                "WHERE r.rolname='stashtab_notification_migrator' "
                "AND u.rolname='stashtab_notification_runtime'"
            )
        ).first()
        assert membership is None
    with pg_engine.begin() as conn:
        assert conn.execute(
            text("SELECT fail_count FROM notification_recovery_park WHERE id='park-a'")
        ).scalar_one() == 2
        assert conn.execute(
            text("SELECT count(*) FROM notification_occurrence_transition")
        ).scalar_one() == 1


def test_pg_same_token_concurrent_is_single_observation(pg_engine):
    apply_notification_schema(pg_engine)
    db = _session(pg_engine)
    _seed_shop(db)
    db.close()
    Session = sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)
    barrier = Barrier(2)

    def run():
        session = Session()
        try:
            barrier.wait(timeout=10)
            event = create_notification(
                session,
                "shop-a",
                category="test",
                severity="action_required",
                action_url="/admin/settings",
                dedupe_key="obs:same",
                source_kind="inventory_exception",
                source_key="exc-same",
                observation_token="tok-same",
            )
            session.commit()
            return event.id
        except IntegrityError:
            session.rollback()
            return "conflict"
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _index: run(), range(2)))
    check = _session(pg_engine)
    assert check.query(NotificationEvent).count() == 1
    assert check.query(NotificationSourceObservation).count() == 1
    assert check.query(NotificationEvent).one().occurrence_count == 1
    assert check.query(NotificationOccurrence).count() == 1
    check.close()


def test_pg_distinct_tokens_concurrent_increment_same_occurrence(pg_engine):
    apply_notification_schema(pg_engine)
    db = _session(pg_engine)
    _seed_shop(db)
    create_notification(
        db,
        "shop-a",
        category="test",
        severity="action_required",
        action_url="/admin/settings",
        dedupe_key="obs:distinct",
        source_kind="inventory_exception",
        source_key="exc-distinct",
        observation_token="tok-1",
    )
    db.commit()
    db.close()
    Session = sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)
    barrier = Barrier(2)

    def run(token):
        session = Session()
        try:
            barrier.wait(timeout=10)
            create_notification(
                session,
                "shop-a",
                category="test",
                severity="action_required",
                action_url="/admin/settings",
                dedupe_key="obs:distinct",
                source_kind="inventory_exception",
                source_key="exc-distinct",
                observation_token=token,
            )
            session.commit()
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(run, "tok-2")
        second = pool.submit(run, "tok-3")
        first.result(timeout=10)
        second.result(timeout=10)
    check = _session(pg_engine)
    event = check.query(NotificationEvent).one()
    assert event.occurrence_count == 3
    assert event.occurrence_seq == 1
    assert check.query(NotificationOccurrence).count() == 1
    assert check.query(NotificationSourceObservation).count() == 3
    check.close()


def test_pg_pattern_b_initial_stays_idempotent(pg_engine):
    apply_inventory(pg_engine)
    apply_notification_schema(pg_engine)
    db = _session(pg_engine)
    _seed_shop(db)
    db.add(
        InventoryException(
            shop_id="shop-a",
            kind="over_sale_short",
            exception_ref="order:pg-b",
            status="open",
        )
    )
    db.commit()
    recover_notification_sources(db, "shop-a")
    db.commit()
    event = db.query(NotificationEvent).one()
    event.status = "acknowledged"
    db.commit()
    recover_notification_sources(db, "shop-a")
    recover_notification_sources(db, "shop-a")
    db.commit()
    assert db.query(NotificationSourceObservation).count() == 1
    assert db.query(NotificationSourceObservation).one().observation_token == PATTERN_B_OBSERVATION_TOKEN
    assert db.query(NotificationOccurrence).count() == 1
    assert db.query(NotificationEvent).one().occurrence_seq == 1
    db.close()


def test_pg_concurrent_terminals_and_status_uses_transition_seq(pg_engine):
    apply_notification_schema(pg_engine)
    db = _session(pg_engine)
    _seed_shop(db)
    event = create_notification(
        db,
        "shop-a",
        category="test",
        severity="action_required",
        action_url="/admin/settings",
        dedupe_key="seq:status",
    )
    event_id = event.id
    db.commit()
    db.close()
    Session = sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)
    barrier = Barrier(2)

    def write(to_status, row_id):
        session = Session()
        try:
            barrier.wait(timeout=10)
            session.add(
                NotificationOccurrenceTransition(
                    id=row_id,
                    shop_id="shop-a",
                    event_id=event_id,
                    occurrence_seq=1,
                    transition_seq=2,
                    from_status="pending",
                    to_status=to_status,
                    cause="finalize",
                )
            )
            session.commit()
            return "ok"
        except IntegrityError:
            session.rollback()
            return "conflict"
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        delivered = pool.submit(write, "delivered", "tr-d")
        failed = pool.submit(write, "failed", "tr-f")
        results = [delivered.result(timeout=10), failed.result(timeout=10)]
    assert sorted(results) == ["conflict", "ok"]
    check = _session(pg_engine)
    assert check.query(NotificationOccurrenceTransition).filter_by(transition_seq=2).count() == 1
    terminal = check.query(NotificationOccurrenceTransition).filter_by(transition_seq=2).one()
    assert occurrence_status(check, "shop-a", event_id, 1) == terminal.to_status
    check.close()

    later = _session(pg_engine)
    _seed_shop(later, "shop-ts")
    stamped = create_notification(
        later,
        "shop-ts",
        category="test",
        severity="action_required",
        action_url="/admin/settings",
        dedupe_key="seq:created-at",
    )
    later.commit()
    later.add(
        NotificationOccurrenceTransition(
            shop_id="shop-ts",
            event_id=stamped.id,
            occurrence_seq=1,
            transition_seq=2,
            from_status="pending",
            to_status="delivered",
            cause="older-timestamp",
            created_at=utcnow() - timedelta(days=1),
        )
    )
    later.commit()
    assert occurrence_status(later, "shop-ts", stamped.id, 1) == "delivered"
    later.close()


def test_pg_attempts_lease_and_single_claim(pg_engine, monkeypatch):
    _enable_push(monkeypatch)
    apply_notification_schema(pg_engine)
    db = _session(pg_engine)
    _seed_shop(db)
    _subscribe(db)
    event = create_notification(
        db,
        "shop-a",
        category="test",
        severity="action_required",
        action_url="/admin/settings",
        dedupe_key="attempt:lease",
    )
    db.commit()
    delivery = db.query(NotificationDelivery).one()
    delivery.attempt_count = 1
    delivery.status = "retry_scheduled"
    delivery.claimed_until = utcnow() + timedelta(seconds=60)
    db.add(
        NotificationDeliveryAttempt(
            shop_id="shop-a",
            delivery_id=delivery.id,
            attempt_number=1,
            phase="started",
        )
    )
    db.commit()
    _recover_stale_attempts(db, "shop-a")
    db.commit()
    assert db.query(NotificationDeliveryAttempt).filter_by(phase="outcome").count() == 0
    delivery.claimed_until = utcnow() - timedelta(seconds=1)
    db.commit()
    _recover_stale_attempts(db, "shop-a")
    db.commit()
    outcomes = [
        row.outcome
        for row in db.query(NotificationDeliveryAttempt).filter_by(phase="outcome")
    ]
    assert outcomes == ["provider_unknown"]
    db.close()

    Session = sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)
    db = Session()
    other = create_notification(
        db,
        "shop-a",
        category="test",
        severity="action_required",
        action_url="/admin/settings",
        dedupe_key="attempt:send",
    )
    other_id = other.id
    db.commit()
    db.close()
    barrier = Barrier(2)
    sends = []

    def send(_subscription, payload):
        sends.append(payload["eventId"])

    def run():
        session = Session()
        try:
            barrier.wait(timeout=10)
            return process_pending_notifications(session, "shop-a")
        finally:
            session.close()

    with patch("app.logic.notifications._send_web_push", side_effect=send):
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(run)
            second = pool.submit(run)
            first.result(timeout=15)
            second.result(timeout=15)
    assert sends.count(other_id) == 1
    check = _session(pg_engine)
    started = check.query(NotificationDeliveryAttempt).filter_by(
        phase="started",
    ).join(
        NotificationDelivery,
        NotificationDelivery.id == NotificationDeliveryAttempt.delivery_id,
    ).filter(NotificationDelivery.event_id == other_id)
    assert started.count() == 1
    outcomes = check.query(NotificationDeliveryAttempt).filter_by(phase="outcome").join(
        NotificationDelivery,
        NotificationDelivery.id == NotificationDeliveryAttempt.delivery_id,
    ).filter(NotificationDelivery.event_id == other_id)
    assert outcomes.count() == 1
    check.close()


def test_pg_mixed_device_reopen_batch_park_cancel_revoke_and_flag(pg_engine, monkeypatch):
    _enable_push(monkeypatch)
    apply_inventory(pg_engine)
    apply_notification_schema(pg_engine)
    db = _session(pg_engine)
    _seed_shop(db)
    _subscribe(db, endpoint="https://fcm.googleapis.com/fcm/send/one")
    db.add(
        ShopMember(
            id="member-staff",
            shop_id="shop-a",
            clerk_user_id="staff-a",
            role="staff",
        )
    )
    db.commit()
    _subscribe(db, user="staff-a", endpoint="https://updates.push.services.mozilla.com/wpush/v2/two")
    mixed = create_notification(
        db,
        "shop-a",
        category="test",
        severity="action_required",
        action_url="/admin/settings",
        dedupe_key="mixed:1",
    )
    db.commit()
    deliveries = db.query(NotificationDelivery).filter_by(event_id=mixed.id).all()
    deliveries[0].status = "sent"
    deliveries[1].status = "failed_exhausted"
    db.commit()
    process_pending_notifications(db, "shop-a")
    db.commit()
    assert occurrence_status(db, "shop-a", mixed.id, 1) == "delivered"
    assert db.get(NotificationEvent, mixed.id).status == "delivered"

    mixed.status = "acknowledged"
    db.commit()
    reopened = create_notification(
        db,
        "shop-a",
        category="test",
        severity="action_required",
        action_url="/admin/settings",
        dedupe_key="mixed:1",
        source_kind="inventory_exception",
        source_key="reopen-1",
        observation_token="tok-reopen",
    )
    db.commit()
    assert reopened.occurrence_seq == 2
    assert db.query(NotificationOccurrence).filter_by(event_id=mixed.id).count() == 2
    assert db.query(NotificationDelivery).filter_by(
        event_id=mixed.id, occurrence_seq=1, status="sent"
    ).count() == 1

    monkeypatch.setattr("app.logic.notifications.DELIVERY_BATCH_LIMIT", 1)
    first = create_notification(
        db, "shop-a", category="test", severity="action_required",
        action_url="/admin/settings", dedupe_key="batch:1",
    )
    second = create_notification(
        db, "shop-a", category="test", severity="action_required",
        action_url="/admin/settings", dedupe_key="batch:2",
    )
    db.commit()
    sent = []
    with patch(
        "app.logic.notifications._send_web_push",
        side_effect=lambda _sub, payload: sent.append(payload["eventId"]),
    ):
        for _ in range(8):
            process_pending_notifications(db, "shop-a")
    assert first.id in sent and second.id in sent

    db.add(
        NotificationRecoveryPark(
            shop_id="shop-a",
            source_kind="inventory_exception",
            source_key="parked-old",
            fail_count=4,
            next_at=utcnow() + timedelta(hours=1),
        )
    )
    db.add(
        InventoryException(
            shop_id="shop-a",
            kind="over_sale_short",
            exception_ref="healthy-later",
            status="open",
        )
    )
    db.commit()
    recover_notification_sources(db, "shop-a")
    db.commit()
    assert db.query(NotificationSourceObservation).filter_by(
        source_key=str(db.query(InventoryException).filter_by(exception_ref="healthy-later").one().id)
    ).count() == 1

    cancel_target = create_notification(
        db, "shop-a", category="test", severity="action_required",
        action_url="/admin/settings", dedupe_key="cancel:1",
    )
    db.commit()
    cancel_notification(db, "shop-a", cancel_target.id, "user-a")
    db.commit()
    assert db.get(NotificationEvent, cancel_target.id).status == "cancelled"
    assert db.query(NotificationAudit).filter_by(action="cancel", event_id=cancel_target.id).count() == 1
    assert all(
        row.status == "cancelled"
        for row in db.query(NotificationDelivery).filter_by(
            event_id=cancel_target.id, occurrence_seq=cancel_target.occurrence_seq
        )
    )

    revoked = create_notification(
        db, "shop-a", category="test", severity="action_required",
        action_url="/admin/settings", dedupe_key="revoke:1",
    )
    db.commit()
    db.query(ShopMember).delete()
    db.commit()
    with patch("app.logic.notifications._send_web_push") as send:
        process_pending_notifications(db, "shop-a")
    send.assert_not_called()
    assert db.get(NotificationEvent, revoked.id).id == revoked.id
    db.close()

    monkeypatch.setattr(settings, "notifications_backend_enabled", False)
    db = _session(pg_engine)
    shop = db.query(Shop).filter_by(id="shop-a").one()
    with patch.object(worker, "recover_notification_sources") as recover, patch.object(
        worker, "run_full_sync", return_value={"pull": {}, "outbox": {}}
    ):
        worker.tick_shop(db, shop)
    recover.assert_not_called()
    db.close()
    client = TestClient(app)
    assert client.get("/api/v1/notifications/config").status_code == 404


def test_pg_failed_migration_preserves_identity_inventory_and_sales(pg_engine):
    apply_inventory(pg_engine)
    db = _session(pg_engine)
    _seed_shop(db)
    db.add(Sale(shop_id="shop-a", sku="SKU-1", sold_price=10.0))
    db.add(PurchaseRecord(shop_id="shop-a", sku="SKU-1", quantity=1, cost_per_unit=4.0))
    db.add(
        InventoryEvent(
            shop_id="shop-a",
            sku="SKU-1",
            event_type="receive",
            quantity_delta=1,
            idempotency_key="pg-112-preserve",
        )
    )
    db.commit()
    db.close()
    with pytest.raises(RuntimeError, match="injected"):
        apply_notification_schema(pg_engine, fail_after="tables")
    with pg_engine.begin() as conn:
        assert conn.execute(text("SELECT count(*) FROM shops")).scalar_one() == 1
        assert conn.execute(text("SELECT count(*) FROM shop_members")).scalar_one() == 1
        assert conn.execute(text("SELECT count(*) FROM sale")).scalar_one() == 1
        assert conn.execute(text("SELECT count(*) FROM purchase_record")).scalar_one() == 1
        assert conn.execute(text("SELECT count(*) FROM inventory_event")).scalar_one() == 1
        remaining = [
            name
            for name in NOTIFICATION_TABLE_NAMES
            if inspect(conn).has_table(name)
        ]
        assert remaining == []
