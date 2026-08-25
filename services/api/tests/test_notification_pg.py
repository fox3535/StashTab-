"""PostgreSQL acceptance for backend-notification-integration-v1."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import sessionmaker

from app.models import Base, Shop, ShopMember
from app.models.base import utcnow
from app.notifications_truth.models import NOTIFICATION_TABLE_NAMES

PG_URL = os.environ.get("STASHTAB_PG_URL", "")
pytestmark = pytest.mark.skipif(not PG_URL, reason="STASHTAB_PG_URL not set")


def _fresh_db():
    url = make_url(PG_URL)
    destructive_opt_in = os.environ.get(
        "STASHTAB_NOTIFICATION_PG_DESTRUCTIVE_OK", ""
    )
    allowed_ports = {55432, 55433}
    if (
        url.database != "stashtab_it"
        or url.host not in {"localhost", "127.0.0.1"}
        or url.port not in allowed_ports
        or destructive_opt_in != f"local-{url.database}-{url.port}"
    ):
        raise RuntimeError(
            "refusing destructive PostgreSQL test outside an explicitly "
            "approved local stashtab_it target on port 55432 or 55433"
        )
    engine = create_engine(PG_URL, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                DO $$ DECLARE r RECORD; BEGIN
                  FOR r IN (
                    SELECT tablename FROM pg_tables WHERE schemaname='public'
                  ) LOOP
                    EXECUTE 'DROP TABLE IF EXISTS public.'
                      || quote_ident(r.tablename) || ' CASCADE';
                  END LOOP;
                END $$;
                """
            )
        )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def pg_engine(monkeypatch):
    monkeypatch.setenv(
        "STASHTAB_NOTIFICATION_MIGRATOR_ROLE",
        "stashtab_notification_migrator",
    )
    engine = _fresh_db()
    yield engine
    engine.dispose()


def test_pg_migrator_atomic_idempotent_and_create_all_excluded(pg_engine):
    from app.notifications_truth.migrator import apply_notification_schema

    assert not any(inspect(pg_engine).has_table(name) for name in NOTIFICATION_TABLE_NAMES)
    with pytest.raises(RuntimeError, match="injected"):
        apply_notification_schema(pg_engine, fail_after="tables")
    assert not any(inspect(pg_engine).has_table(name) for name in NOTIFICATION_TABLE_NAMES)
    first = apply_notification_schema(pg_engine)
    second = apply_notification_schema(pg_engine)
    assert set(first["tables"]) == set(NOTIFICATION_TABLE_NAMES)
    assert second["tables"] == []
    Base.metadata.create_all(pg_engine)
    assert all(inspect(pg_engine).has_table(name) for name in NOTIFICATION_TABLE_NAMES)


@pytest.mark.parametrize("stage", ["triggers", "protections"])
def test_pg_migrator_rolls_back_late_failure_stages(pg_engine, stage):
    from app.notifications_truth.migrator import apply_notification_schema

    with pytest.raises(RuntimeError, match="injected"):
        apply_notification_schema(pg_engine, fail_after=stage)
    assert not any(inspect(pg_engine).has_table(name) for name in NOTIFICATION_TABLE_NAMES)


def test_pg_cross_shop_fks_and_unique_source(pg_engine):
    from app.notifications_truth.migrator import apply_notification_schema

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
                "dedupe_key, status, occurrence_seq) VALUES "
                "('event-a','shop-a','critical','critical','StashTab needs attention',"
                "'Open StashTab.','/admin/reports','critical:a','pending',1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO notification_occurrence "
                "(id, shop_id, event_id, occurrence_seq, cause) VALUES "
                "('occ-a','shop-a','event-a',1,'created')"
            )
        )
    with pytest.raises(IntegrityError):
        with pg_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO notification_occurrence "
                    "(id, shop_id, event_id, occurrence_seq, cause) VALUES "
                    "('occ-b','shop-b','event-a',1,'cross-shop')"
                )
            )
    with pg_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO notification_source "
                "(id, shop_id, source_kind, source_key, event_id, occurrence_seq) "
                "VALUES ('source-1','shop-a','inventory_exception','1','event-a',1)"
            )
        )
    with pytest.raises(IntegrityError):
        with pg_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO notification_source "
                    "(id, shop_id, source_kind, source_key, event_id, occurrence_seq) "
                    "VALUES ('source-2','shop-a','inventory_exception','1','event-a',1)"
                )
            )
    with pytest.raises(IntegrityError):
        with pg_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO notification_source "
                    "(id, shop_id, source_kind, source_key, event_id, occurrence_seq) "
                    "VALUES ('source-bad-seq','shop-a','inventory_exception','2',"
                    "'event-a',2)"
                )
            )


def test_pg_append_only_runtime_role_cannot_rewrite_audit(pg_engine, monkeypatch):
    from app.notifications_truth.migrator import apply_notification_schema

    with pg_engine.begin() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname='stashtab_notification_runtime'")
        ).first()
        if exists:
            conn.execute(text("DROP OWNED BY stashtab_notification_runtime"))
        conn.execute(text("DROP ROLE IF EXISTS stashtab_notification_runtime"))
        conn.execute(text("CREATE ROLE stashtab_notification_runtime NOLOGIN"))
    monkeypatch.setenv(
        "STASHTAB_NOTIFICATION_RUNTIME_ROLE",
        "stashtab_notification_runtime",
    )
    monkeypatch.setenv(
        "STASHTAB_NOTIFICATION_MIGRATOR_ROLE",
        make_url(PG_URL).username or "postgres",
    )
    apply_notification_schema(pg_engine)
    with pg_engine.begin() as conn:
        conn.execute(
            Shop.__table__.insert(),
            {"id": "shop-a", "name": "A", "slug": "a"},
        )
        conn.execute(
            text(
                "INSERT INTO notification_audit "
                "(id,shop_id,actor_clerk_user_id,action) "
                "VALUES ('audit-a','shop-a','user-a','test_send')"
            )
        )
        conn.execute(text("GRANT USAGE ON SCHEMA public TO stashtab_notification_runtime"))
        conn.execute(
            text(
                "GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE "
                "ON notification_audit, notification_occurrence "
                "TO stashtab_notification_runtime"
            )
        )
    apply_notification_schema(pg_engine)
    for statement in (
        "UPDATE notification_audit SET action='ack' WHERE id='audit-a'",
        "DELETE FROM notification_audit WHERE id='audit-a'",
        "TRUNCATE notification_audit",
    ):
        with pytest.raises(DBAPIError):
            with pg_engine.begin() as conn:
                conn.execute(text("SET ROLE stashtab_notification_runtime"))
                conn.execute(text(statement))
    with pg_engine.begin() as conn:
        assert conn.execute(
            text("SELECT count(*) FROM notification_audit WHERE id='audit-a'")
        ).scalar_one() == 1


def test_pg_concurrent_recovery_creates_one_occurrence(pg_engine):
    from app.inventory_truth.migrator import apply as apply_inventory
    from app.logic.notifications import recover_notification_sources
    from app.notifications_truth.migrator import apply_notification_schema
    from app.notifications_truth.models import NotificationOccurrence, NotificationSource

    apply_inventory(pg_engine)
    apply_notification_schema(pg_engine)
    with pg_engine.begin() as conn:
        conn.execute(
            Shop.__table__.insert(),
            {"id": "shop-a", "name": "A", "slug": "a"},
        )
        conn.execute(
            text(
                "INSERT INTO inventory_exception "
                "(shop_id,kind,exception_ref,status,created_at) "
                "VALUES ('shop-a','over_sale_short','order:1','open',CURRENT_TIMESTAMP)"
            )
        )
    Session = sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)

    def sweep():
        db = Session()
        try:
            result = recover_notification_sources(db, "shop-a")
            db.commit()
            return result
        except IntegrityError:
            db.rollback()
            return {"lost_race": 1}
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _index: sweep(), range(2)))
    check = Session()
    assert check.query(NotificationSource).count() == 1
    assert check.query(NotificationOccurrence).count() == 1
    check.close()


def test_pg_concurrent_delivery_claim_sends_once(pg_engine, monkeypatch):
    from app.config import settings
    from app.logic import notifications as notification_logic
    from app.logic.notifications import create_notification, process_pending_notifications
    from app.models import ShopMember
    from app.notifications_truth.migrator import apply_notification_schema
    from app.notifications_truth.models import PushSubscription

    apply_notification_schema(pg_engine)
    Session = sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)
    db = Session()
    db.add_all(
        [
            Shop(id="shop-a", name="A", slug="a"),
            ShopMember(
                id="member-a",
                shop_id="shop-a",
                clerk_user_id="user-a",
                role="owner",
            ),
            PushSubscription(
                id="sub-a",
                shop_id="shop-a",
                clerk_user_id="user-a",
                endpoint="https://fcm.googleapis.com/fcm/send/claim",
                p256dh="p256dh-key-value",
                auth="auth-key-value",
                enabled=True,
            ),
        ]
    )
    db.commit()
    create_notification(
        db,
        "shop-a",
        category="test",
        severity="action_required",
        action_url="/admin/settings",
        dedupe_key="test:concurrent-claim",
    )
    db.commit()
    from app.notifications_truth.models import NotificationDelivery

    delivery_id = db.query(NotificationDelivery).one().id
    db.close()
    monkeypatch.setattr(settings, "vapid_public_key", "test-public")
    monkeypatch.setattr(settings, "vapid_private_key", "test-private")
    monkeypatch.setattr(settings, "vapid_subject", "mailto:tests@stashtab.invalid")
    barrier = Barrier(2)

    def run():
        session = Session()
        try:
            barrier.wait(timeout=5)
            return notification_logic._claim_delivery(session, "shop-a", delivery_id)
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(run)
        second = pool.submit(run)
        results = [first.result(timeout=10), second.result(timeout=10)]
    assert sorted(results) == [False, True]


def test_pg_concurrent_create_and_reopen_keep_one_occurrence(pg_engine):
    from app.logic.notifications import create_notification
    from app.notifications_truth.migrator import apply_notification_schema
    from app.notifications_truth.models import NotificationEvent, NotificationOccurrence

    apply_notification_schema(pg_engine)
    with pg_engine.begin() as conn:
        conn.execute(
            Shop.__table__.insert(),
            {"id": "shop-a", "name": "A", "slug": "a"},
        )
    Session = sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)

    def create(barrier):
        session = Session()
        try:
            barrier.wait(timeout=10)
            event = create_notification(
                session,
                "shop-a",
                category="test",
                severity="action_required",
                action_url="/admin/settings",
                dedupe_key="test:concurrent-event",
            )
            session.commit()
            return event.id
        finally:
            session.close()

    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(lambda _index: create(barrier), range(2)))
    assert len(set(ids)) == 1

    session = Session()
    event = session.query(NotificationEvent).one()
    event.status = "acknowledged"
    session.commit()
    session.close()

    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _index: create(barrier), range(2)))
    check = Session()
    assert check.query(NotificationEvent).one().occurrence_seq == 2
    assert check.query(NotificationOccurrence).count() == 2
    check.close()


def test_pg_concurrent_test_send_rate_limit_is_atomic(pg_engine):
    from fastapi import HTTPException

    from app.deps import ShopContext
    from app.models import ShopMember
    from app.notifications_truth.migrator import apply_notification_schema
    from app.notifications_truth.models import NotificationAudit
    from app.routers.notifications import send_test

    apply_notification_schema(pg_engine)
    Session = sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)
    db = Session()
    db.add_all(
        [
            Shop(id="shop-a", name="A", slug="a"),
            ShopMember(
                id="member-a",
                shop_id="shop-a",
                clerk_user_id="user-a",
                role="owner",
            ),
            *[
                NotificationAudit(
                    id=f"audit-{index}",
                    shop_id="shop-a",
                    actor_clerk_user_id="user-a",
                    action="test_send",
                    category="test",
                )
                for index in range(4)
            ],
        ]
    )
    db.commit()
    db.close()
    barrier = Barrier(2)
    context = ShopContext(
        shop_id="shop-a",
        clerk_user_id="user-a",
        role="owner",
    )

    def run():
        session = Session()
        try:
            barrier.wait(timeout=10)
            try:
                send_test(context, session)
                return 200
            except HTTPException as exc:
                session.rollback()
                return exc.status_code
        finally:
            session.close()

    with patch("app.logic.notifications._send_web_push"), ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _index: run(), range(2)))
    assert sorted(statuses) == [200, 429]
    check = Session()
    assert check.query(NotificationAudit).filter(
        NotificationAudit.action == "test_send"
    ).count() == 5
    check.close()
