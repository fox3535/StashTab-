from datetime import timedelta
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import get_db
from app.deps import ShopContext, get_notification_context
from app.inventory_truth.migrator import apply as apply_inventory_truth
from app.inventory_truth.models_truth import InventoryException
from app.logic import notifications as logic
from app.logic import push_endpoints
from app.logic.notifications import (
    NotificationValidationError,
    actor_id,
    cleanup_notification_history,
    create_notification,
    process_pending_notifications,
    push_payload,
    recover_notification_sources,
)
from app.logic.push_endpoints import PushEndpointError, validate_push_endpoint
from app.models import Base, Shop, ShopMember, SystemSettings
from app.models.base import new_uuid, utcnow
from app.notifications_truth.migrator import apply_notification_schema
from app.notifications_truth.models import (
    NotificationAudit,
    NotificationDelivery,
    NotificationEvent,
    NotificationOccurrence,
    NotificationPreference,
    NotificationSource,
    PushSubscription,
    ShopNotificationPolicy,
)
from app.routers import notifications as notifications_router

FCM_ENDPOINT = "https://fcm.googleapis.com/fcm/send/test-subscription"
MOZ_ENDPOINT = "https://updates.push.services.mozilla.com/wpush/v2/test"


@pytest.fixture(autouse=True)
def _forbid_live_web_push(monkeypatch):
    def blocked(*_args, **_kwargs):
        raise AssertionError("live Web Push is forbidden in tests")

    monkeypatch.setattr(logic, "_send_web_push_blocking", blocked)


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
    apply_inventory_truth(engine)
    apply_notification_schema(engine)
    return engine


def _session():
    db = sessionmaker(bind=_engine(), autocommit=False, autoflush=False)()
    db.add_all(
        [
            Shop(id="shop-a", name="A", slug="a"),
            Shop(id="shop-b", name="B", slug="b"),
            ShopMember(
                id=new_uuid(),
                shop_id="shop-a",
                clerk_user_id="user-a",
                role="owner",
            ),
            ShopMember(
                id=new_uuid(),
                shop_id="shop-a",
                clerk_user_id="staff-a",
                role="staff",
            ),
            ShopMember(
                id=new_uuid(),
                shop_id="shop-b",
                clerk_user_id="user-b",
                role="owner",
            ),
        ]
    )
    db.commit()
    return db


def _enable_push(monkeypatch):
    monkeypatch.setattr(settings, "vapid_public_key", "test-public")
    monkeypatch.setattr(settings, "vapid_private_key", "test-private")
    monkeypatch.setattr(settings, "vapid_subject", "mailto:tests@stashtab.invalid")


def _subscription(db, *, shop="shop-a", user="user-a", endpoint=FCM_ENDPOINT):
    row = PushSubscription(
        shop_id=shop,
        clerk_user_id=user,
        endpoint=endpoint,
        p256dh="p256dh-key-value",
        auth="auth-key-value",
        enabled=True,
    )
    db.add(row)
    db.commit()
    return row


def _create(db, *, shop="shop-a", key="event:1", severity="action_required"):
    return create_notification(
        db,
        shop,
        category="test" if key.startswith("test") else "ambiguous_card",
        severity=severity,
        action_url="/admin/settings" if key.startswith("test") else "/admin/staging",
        dedupe_key=key,
    )


def _client(db, *, shop="shop-a", user="user-a", role="owner"):
    app = FastAPI()
    app.include_router(notifications_router.router, prefix="/api/v1")

    def override_db():
        yield db

    def override_ctx():
        return ShopContext(shop_id=shop, clerk_user_id=user, role=role)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_notification_context] = override_ctx
    return TestClient(app)


def test_01_actor_requires_authenticated_user():
    assert actor_id("user-a") == "user-a"
    with pytest.raises(NotificationValidationError):
        actor_id(None)


def test_02_notification_deduplicates_pending_occurrence():
    db = _session()
    first = _create(db, key="card:1")
    second = _create(db, key="card:1")
    assert first.id == second.id
    assert second.occurrence_seq == 1
    assert db.query(NotificationOccurrence).count() == 1


def test_03_same_dedupe_is_shop_scoped():
    db = _session()
    _create(db, shop="shop-a", key="card:1")
    _create(db, shop="shop-b", key="card:1")
    assert {row.shop_id for row in db.query(NotificationEvent)} == {"shop-a", "shop-b"}


def test_04_reopen_preserves_occurrence_and_delivery_history(monkeypatch):
    _enable_push(monkeypatch)
    db = _session()
    _subscription(db)
    event_row = _create(db, key="card:reopen")
    db.commit()
    with patch("app.logic.notifications._send_web_push"):
        process_pending_notifications(db, "shop-a")
    old_delivery = db.query(NotificationDelivery).one()
    assert old_delivery.status == "sent"
    event_row.status = "acknowledged"
    db.commit()
    reopened = _create(db, key="card:reopen")
    db.commit()
    assert reopened.occurrence_seq == 2
    assert db.query(NotificationOccurrence).count() == 2
    assert db.query(NotificationDelivery).count() == 2
    assert db.get(NotificationDelivery, old_delivery.id).status == "sent"


def test_05_missing_vapid_makes_no_provider_call():
    db = _session()
    _subscription(db)
    _create(db, key="test:no-vapid")
    db.commit()
    with patch("app.logic.notifications._send_web_push") as send:
        result = process_pending_notifications(db, "shop-a")
    assert result["enabled"] is False
    send.assert_not_called()


def test_06_retryable_failure_then_success(monkeypatch):
    _enable_push(monkeypatch)
    db = _session()
    _subscription(db)
    event_row = _create(db, key="test:retry")
    db.commit()
    error = Exception("unavailable")
    error.response = SimpleNamespace(status_code=503)
    with patch("app.logic.notifications._send_web_push", side_effect=error):
        process_pending_notifications(db, "shop-a")
    delivery = db.query(NotificationDelivery).one()
    assert delivery.status == "retry_scheduled"
    delivery.next_retry_at = utcnow() - timedelta(seconds=1)
    db.commit()
    with patch("app.logic.notifications._send_web_push"):
        process_pending_notifications(db, "shop-a")
    assert db.get(NotificationDelivery, delivery.id).status == "sent"
    assert db.get(NotificationEvent, event_row.id).status == "delivered"


@pytest.mark.parametrize("status_code", [404, 410])
def test_07_gone_subscription_expires(monkeypatch, status_code):
    _enable_push(monkeypatch)
    db = _session()
    subscription = _subscription(db)
    _create(db, key="test:gone")
    db.commit()
    error = Exception("gone")
    error.response = SimpleNamespace(status_code=status_code)
    with patch("app.logic.notifications._send_web_push", side_effect=error):
        process_pending_notifications(db, "shop-a")
    db.refresh(subscription)
    assert subscription.enabled is False
    assert db.query(NotificationDelivery).one().status == "expired"


def test_08_retry_exhaustion_is_terminal(monkeypatch):
    _enable_push(monkeypatch)
    db = _session()
    _subscription(db)
    event_row = _create(db, key="test:exhaust")
    db.commit()
    error = Exception("down")
    error.response = SimpleNamespace(status_code=503)
    with patch("app.logic.notifications._send_web_push", side_effect=error):
        for _ in range(8):
            process_pending_notifications(db, "shop-a")
            delivery = db.query(NotificationDelivery).one()
            if delivery.next_retry_at:
                delivery.next_retry_at = utcnow() - timedelta(seconds=1)
                db.commit()
    assert delivery.status == "failed_exhausted"
    assert db.get(NotificationEvent, event_row.id).status == "failed"


def test_09_mixed_device_terminalization_delivers_if_any_sent(monkeypatch):
    _enable_push(monkeypatch)
    db = _session()
    _subscription(db, endpoint=FCM_ENDPOINT)
    _subscription(db, user="staff-a", endpoint=MOZ_ENDPOINT)
    event_row = _create(db, key="test:mixed")
    db.commit()

    def send(subscription, _payload):
        if "mozilla" in subscription.endpoint:
            error = Exception("down")
            error.response = SimpleNamespace(status_code=503)
            raise error

    with patch("app.logic.notifications._send_web_push", side_effect=send):
        for _ in range(8):
            process_pending_notifications(db, "shop-a")
            for delivery in db.query(NotificationDelivery).filter(
                NotificationDelivery.status == "retry_scheduled"
            ):
                delivery.next_retry_at = utcnow() - timedelta(seconds=1)
            db.commit()
    assert {row.status for row in db.query(NotificationDelivery)} == {
        "sent",
        "failed_exhausted",
    }
    assert db.get(NotificationEvent, event_row.id).status == "delivered"
    assert logic.occurrence_status(db, "shop-a", event_row.id, 1) == "delivered"
    check = sessionmaker(bind=db.get_bind(), autocommit=False, autoflush=False)()
    assert logic.occurrence_status(check, "shop-a", event_row.id, 1) == "delivered"
    check.close()


def test_10_zero_devices_terminalizes_failed(monkeypatch):
    _enable_push(monkeypatch)
    db = _session()
    event_row = _create(db, key="test:no-devices")
    db.commit()
    assert logic.occurrence_status(db, "shop-a", event_row.id, 1) == "pending"
    process_pending_notifications(db, "shop-a")
    assert db.get(NotificationEvent, event_row.id).status == "failed"
    assert logic.occurrence_status(db, "shop-a", event_row.id, 1) == "failed"
    check = sessionmaker(bind=db.get_bind(), autocommit=False, autoflush=False)()
    assert logic.occurrence_status(check, "shop-a", event_row.id, 1) == "failed"
    check.close()


def test_11_future_retry_does_not_hide_due_work(monkeypatch):
    _enable_push(monkeypatch)
    db = _session()
    _subscription(db)
    first = _create(db, key="test:future")
    second = _create(db, key="test:due")
    db.commit()
    deliveries = db.query(NotificationDelivery).order_by(NotificationDelivery.created_at).all()
    deliveries[0].status = "retry_scheduled"
    deliveries[0].next_retry_at = utcnow() + timedelta(hours=1)
    db.commit()
    sent = []
    with patch(
        "app.logic.notifications._send_web_push",
        side_effect=lambda _sub, payload: sent.append(payload["eventId"]),
    ):
        process_pending_notifications(db, "shop-a")
    assert sent == [second.id]
    assert db.get(NotificationEvent, first.id).status == "pending"


def test_12_oldest_due_first_under_batch_limit(monkeypatch):
    _enable_push(monkeypatch)
    monkeypatch.setattr(logic, "DELIVERY_BATCH_LIMIT", 2)
    db = _session()
    _subscription(db)
    events = [_create(db, key=f"test:fair:{i}") for i in range(3)]
    db.commit()
    sent = []
    with patch(
        "app.logic.notifications._send_web_push",
        side_effect=lambda _sub, payload: sent.append(payload["eventId"]),
    ):
        process_pending_notifications(db, "shop-a")
    assert sent == [events[0].id, events[1].id]


def test_13_push_payload_is_generic_and_safe():
    db = _session()
    row = create_notification(
        db,
        "shop-a",
        category="ambiguous_card",
        severity="action_required",
        title="Customer Jane Charizard $999",
        body="sensitive",
        action_url="/admin/staging",
        dedupe_key="safe",
    )
    payload = push_payload(row)
    assert "Jane" not in str(payload)
    assert "$999" not in str(payload)
    assert set(payload) == {"title", "body", "url", "tag", "eventId"}


@pytest.mark.parametrize(
    "url",
    ["https://evil.invalid", "//evil.invalid", "/pos/checkout", "/admin/unknown"],
)
def test_14_rejects_unapproved_click_targets(url):
    db = _session()
    with pytest.raises(NotificationValidationError):
        create_notification(
            db,
            "shop-a",
            category="test",
            severity="action_required",
            action_url=url,
            dedupe_key=f"bad:{url}",
        )


def test_15_push_endpoint_safety():
    validate_push_endpoint(FCM_ENDPOINT)
    validate_push_endpoint(MOZ_ENDPOINT)
    for endpoint in (
        "http://fcm.googleapis.com/x",
        "https://127.0.0.1/x",
        "https://169.254.169.254/x",
        "https://localhost/x",
        "https://evil.invalid/x",
        "https://user:pass@fcm.googleapis.com/x",
        "https://fcm.googleapis.com:444/x",
    ):
        with pytest.raises(PushEndpointError):
            validate_push_endpoint(endpoint)


def test_16_configured_provider_suffix_is_accepted(monkeypatch):
    monkeypatch.setattr(settings, "web_push_allowed_host_suffixes", "push.partner.test")
    validate_push_endpoint("https://eu.push.partner.test/v1/sub")


def test_16b_dns_validation_has_a_deadline(monkeypatch):
    release = Event()
    monkeypatch.setattr(push_endpoints, "DNS_RESOLUTION_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(
        push_endpoints.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: release.wait(timeout=0.2) or [],
    )
    with pytest.raises(PushEndpointError, match="timed out"):
        validate_push_endpoint(FCM_ENDPOINT, resolve_dns=True)
    release.set()


def test_17_create_notification_does_not_commit_caller_transaction():
    db = _session()
    _create(db, key="test:rollback")
    db.rollback()
    assert db.query(NotificationEvent).count() == 0


@pytest.mark.parametrize("kind", ["over_sale_short", "adjust_anomaly"])
def test_18_recovery_sweep_creates_from_durable_exception(kind):
    db = _session()
    exception = InventoryException(
        shop_id="shop-a",
        kind=kind,
        exception_ref=f"{kind}:1",
        status="open",
    )
    db.add(exception)
    db.commit()
    result = recover_notification_sources(db, "shop-a")
    db.commit()
    assert result["recovered"] == 1
    source = db.query(NotificationSource).one()
    assert source.source_key == str(exception.id)


@pytest.mark.parametrize(
    "terminal_status",
    ["delivered", "failed", "acknowledged", "resolved", "cancelled"],
)
def test_19_recovery_replay_cannot_duplicate_occurrence(terminal_status):
    db = _session()
    db.add(
        InventoryException(
            shop_id="shop-a",
            kind="over_sale_short",
            exception_ref="oversale:1",
            status="open",
        )
    )
    db.commit()
    recover_notification_sources(db, "shop-a")
    db.commit()
    event_row = db.query(NotificationEvent).one()
    event_row.status = terminal_status
    db.commit()
    recover_notification_sources(db, "shop-a")
    db.commit()
    assert db.query(NotificationSource).count() == 1
    assert db.query(NotificationOccurrence).count() == 1
    assert db.query(NotificationEvent).one().status == terminal_status


def test_20_acknowledge_does_not_resolve_inventory_exception():
    db = _session()
    exception = InventoryException(
        shop_id="shop-a",
        kind="over_sale_short",
        exception_ref="oversale:ack",
        status="open",
    )
    db.add(exception)
    db.commit()
    recover_notification_sources(db, "shop-a")
    db.commit()
    event_row = db.query(NotificationEvent).one()
    response = _client(db).post(
        f"/api/v1/notifications/events/{event_row.id}/acknowledge"
    )
    assert response.status_code == 200
    assert _client(db).post(
        f"/api/v1/notifications/events/{event_row.id}/resolve"
    ).status_code == 200
    db.refresh(exception)
    assert exception.status == "open"
    assert {
        row.action for row in db.query(NotificationAudit).order_by(
            NotificationAudit.created_at
        )
    } == {"ack", "resolve"}


def test_21_provider_success_crash_can_only_duplicate_transport(monkeypatch):
    _enable_push(monkeypatch)
    db = _session()
    _subscription(db)
    exception = InventoryException(
        shop_id="shop-a",
        kind="over_sale_short",
        exception_ref="oversale:crash",
        status="open",
    )
    db.add(exception)
    db.commit()
    recover_notification_sources(db, "shop-a")
    db.commit()
    sends = []
    real_record = logic._record_transport_result
    with patch(
        "app.logic.notifications._send_web_push",
        side_effect=lambda _sub, payload: sends.append(payload["eventId"]),
    ), patch(
        "app.logic.notifications._record_transport_result",
        side_effect=RuntimeError("crash after provider success"),
    ):
        process_pending_notifications(db, "shop-a")
        delivery = db.query(NotificationDelivery).one()
        delivery.next_retry_at = utcnow() - timedelta(seconds=1)
        delivery.claimed_until = utcnow() - timedelta(seconds=1)
        db.commit()
    with patch(
        "app.logic.notifications._send_web_push",
        side_effect=lambda _sub, payload: sends.append(payload["eventId"]),
    ), patch("app.logic.notifications._record_transport_result", real_record):
        process_pending_notifications(db, "shop-a")
    assert len(sends) == 2
    assert db.query(NotificationSource).count() == 1
    assert db.query(NotificationOccurrence).count() == 1
    db.refresh(exception)
    assert exception.status == "open"


def test_22_retention_holds_delete_nothing():
    db = _session()
    result = cleanup_notification_history(db, "shop-a", legal_hold=True)
    assert result == {"deliveries": 0, "subscriptions": 0, "audits": 0}
    result = cleanup_notification_history(
        db,
        "shop-a",
        legal_hold=False,
        open_investigation=True,
    )
    assert result == {"deliveries": 0, "subscriptions": 0, "audits": 0}


def test_23_retention_preserves_unresolved_critical_delivery():
    db = _session()
    subscription = _subscription(db)
    event_row = create_notification(
        db,
        "shop-a",
        category="inventory_oversale",
        severity="critical",
        action_url="/admin/reports",
        dedupe_key="critical:retain",
    )
    db.commit()
    delivery = db.query(NotificationDelivery).one()
    delivery.status = "failed_exhausted"
    delivery.created_at = utcnow() - timedelta(days=100)
    db.commit()
    cleanup_notification_history(
        db,
        "shop-a",
        legal_hold=False,
        now=utcnow(),
    )
    db.flush()
    assert db.get(NotificationDelivery, delivery.id) is not None
    assert db.get(PushSubscription, subscription.id) is not None
    assert event_row.status == "pending"


def test_24_preferences_are_per_user():
    db = _session()
    owner = _client(db)
    staff = _client(db, user="staff-a", role="staff")
    assert owner.put(
        "/api/v1/notifications/preferences",
        json={"web_push_enabled": True, "action_required_enabled": False},
    ).status_code == 200
    assert staff.put(
        "/api/v1/notifications/preferences",
        json={"web_push_enabled": True, "action_required_enabled": True},
    ).status_code == 200
    assert owner.get("/api/v1/notifications/preferences").json()[
        "action_required_enabled"
    ] is False


def test_25_only_owner_can_disable_critical_policy():
    db = _session()
    staff = _client(db, user="staff-a", role="staff")
    assert staff.put(
        "/api/v1/notifications/policy/critical",
        json={"enabled": False, "confirm": True},
    ).status_code == 403
    owner = _client(db)
    assert owner.put(
        "/api/v1/notifications/policy/critical",
        json={"enabled": False, "confirm": False},
    ).status_code == 400
    assert owner.put(
        "/api/v1/notifications/policy/critical",
        json={"enabled": False, "confirm": True},
    ).status_code == 200
    assert db.get(ShopNotificationPolicy, "shop-a").critical_enabled is False
    assert db.query(NotificationAudit).filter(
        NotificationAudit.action == "critical_disable"
    ).count() == 1


def test_26_test_send_is_labeled_audited_and_rate_limited():
    db = _session()
    client = _client(db)
    for _ in range(5):
        assert client.post("/api/v1/notifications/test").status_code == 200
    assert client.post("/api/v1/notifications/test").status_code == 429
    assert db.query(NotificationAudit).filter(
        NotificationAudit.action == "test_send"
    ).count() == 5
    assert db.query(NotificationEvent).count() == 5
    assert {row.category for row in db.query(NotificationEvent)} == {"test"}


def test_27_cross_shop_event_access_is_404():
    db = _session()
    event_row = _create(db, key="test:tenant")
    db.commit()
    other = _client(db, shop="shop-b", user="user-b")
    assert other.post(
        f"/api/v1/notifications/events/{event_row.id}/acknowledge"
    ).status_code == 404
    subscription = _subscription(db)
    assert other.request(
        "DELETE",
        "/api/v1/notifications/subscriptions",
        json={
            "endpoint": subscription.endpoint,
            "p256dh": subscription.p256dh,
            "auth": subscription.auth,
        },
    ).status_code == 200
    db.refresh(subscription)
    assert subscription.enabled is True


def test_28_subscription_takeover_requires_disable_first():
    db = _session()
    owner = _client(db)
    payload = {
        "endpoint": FCM_ENDPOINT,
        "p256dh": "p256dh-key-value",
        "auth": "auth-key-value",
    }
    assert owner.post("/api/v1/notifications/subscriptions", json=payload).status_code == 200
    staff = _client(db, user="staff-a", role="staff")
    assert staff.post("/api/v1/notifications/subscriptions", json=payload).status_code == 409
    assert owner.request(
        "DELETE", "/api/v1/notifications/subscriptions", json=payload
    ).status_code == 200
    assert staff.post("/api/v1/notifications/subscriptions", json=payload).status_code == 200


def test_29_worker_runs_notifications_when_auto_sync_is_off(monkeypatch):
    import worker

    db = _session()
    db.add(SystemSettings(shop_id="shop-a", auto_sync_enabled=False))
    db.commit()
    shop = db.query(Shop).filter(Shop.id == "shop-a").one()
    calls = []
    Session = sessionmaker(bind=db.get_bind(), autocommit=False, autoflush=False)
    monkeypatch.setattr(settings, "notifications_backend_enabled", True)
    monkeypatch.setattr(worker, "SessionLocal", Session)
    monkeypatch.setattr(
        worker,
        "run_full_sync",
        lambda *_args: calls.append("sync") or {},
    )
    monkeypatch.setattr(
        worker,
        "recover_notification_sources",
        lambda _db, shop_id: calls.append(f"recover:{shop_id}") or {"recovered": 0},
    )
    monkeypatch.setattr(
        worker,
        "process_pending_notifications",
        lambda _db, shop_id: calls.append(f"notify:{shop_id}") or {"sent": 0},
    )
    result = worker.tick_shop(db, shop)
    assert result["status"] == "ok"
    assert calls == ["recover:shop-a", "notify:shop-a"]


def test_30_worker_notification_failure_does_not_stop_later_shop(monkeypatch):
    import worker

    db = _session()
    exception = InventoryException(
        shop_id="shop-a",
        kind="over_sale_short",
        exception_ref="notification-db-failure",
        status="open",
    )
    db.add(exception)
    db.commit()
    shops = db.query(Shop).order_by(Shop.id).all()
    Session = sessionmaker(bind=db.get_bind(), autocommit=False, autoflush=False)
    seen = []
    monkeypatch.setattr(settings, "notifications_backend_enabled", True)
    monkeypatch.setattr(worker, "SessionLocal", Session)
    monkeypatch.setattr(worker, "_shop_auto_sync", lambda *_args: False)

    def recover(_db, shop_id):
        if shop_id == "shop-a":
            raise RuntimeError("poisoned shop")
        seen.append(shop_id)
        return {"recovered": 0}

    monkeypatch.setattr(worker, "recover_notification_sources", recover)
    monkeypatch.setattr(
        worker,
        "process_pending_notifications",
        lambda _db, shop_id: {"sent": 0},
    )
    results = [worker.tick_shop(db, shop) for shop in shops]
    assert results[0]["status"] == "failed"
    assert results[1]["status"] == "ok"
    assert seen == ["shop-b"]
    db.refresh(exception)
    assert exception.status == "open"


def test_31_local_ack_failure_for_one_event_does_not_stop_next(monkeypatch):
    _enable_push(monkeypatch)
    db = _session()
    _subscription(db)
    first = _create(db, key="test:ack-fail")
    second = _create(db, key="test:ack-next")
    db.commit()
    real_record = logic._record_transport_result

    def record(db_arg, delivery, event_row, subscription, *, error):
        if event_row.id == first.id:
            raise RuntimeError("local acknowledgement failed")
        return real_record(
            db_arg,
            delivery,
            event_row,
            subscription,
            error=error,
        )

    with patch("app.logic.notifications._send_web_push"), patch(
        "app.logic.notifications._record_transport_result",
        side_effect=record,
    ):
        process_pending_notifications(db, "shop-a")
    assert db.get(NotificationEvent, first.id).status == "pending"
    assert db.get(NotificationEvent, second.id).status == "delivered"


def test_32_poisoned_recovery_source_does_not_stop_later_source(monkeypatch):
    db = _session()
    db.add_all(
        [
            InventoryException(
                shop_id="shop-a",
                kind="over_sale_short",
                exception_ref="poison",
                status="open",
            ),
            InventoryException(
                shop_id="shop-a",
                kind="adjust_anomaly",
                exception_ref="healthy",
                status="open",
            ),
        ]
    )
    db.commit()
    real_create = logic.create_notification

    def create(db_arg, shop_id, **kwargs):
        if kwargs["dedupe_key"].endswith(":1"):
            raise RuntimeError("poisoned source")
        return real_create(db_arg, shop_id, **kwargs)

    with patch("app.logic.notifications.create_notification", side_effect=create):
        recover_notification_sources(db, "shop-a")
    db.commit()
    assert db.query(NotificationSource).count() == 1
    assert db.query(NotificationEvent).one().category == "adjustment_anomaly"


def test_33_test_send_bypasses_quiet_hours_but_background_event_waits(monkeypatch):
    _enable_push(monkeypatch)
    db = _session()
    _subscription(db)
    now = utcnow()
    db.add(
        NotificationPreference(
            shop_id="shop-a",
            clerk_user_id="user-a",
            quiet_hours_start=(now - timedelta(minutes=1)).strftime("%H:%M"),
            quiet_hours_end=(now + timedelta(minutes=1)).strftime("%H:%M"),
            timezone="UTC",
        )
    )
    background = _create(db, key="card:quiet")
    test_event = _create(db, key="test:quiet")
    db.commit()
    sent = []
    with patch(
        "app.logic.notifications._send_web_push",
        side_effect=lambda _sub, payload: sent.append(payload["eventId"]),
    ):
        process_pending_notifications(db, "shop-a")
    assert sent == [test_event.id]
    background_delivery = db.query(NotificationDelivery).filter(
        NotificationDelivery.event_id == background.id
    ).one()
    assert background_delivery.next_retry_at is not None


def test_34_due_retry_is_not_starved_by_full_fresh_backlog(monkeypatch):
    _enable_push(monkeypatch)
    db = _session()
    _subscription(db)
    retry_event = _create(db, key="test:old-retry")
    db.commit()
    retry = db.query(NotificationDelivery).filter(
        NotificationDelivery.event_id == retry_event.id
    ).one()
    retry.status = "retry_scheduled"
    retry.created_at = utcnow() - timedelta(days=1)
    retry.next_retry_at = utcnow() - timedelta(hours=1)
    for index in range(logic.DELIVERY_BATCH_LIMIT + 5):
        _create(db, key=f"test:fresh-{index}")
    db.commit()
    sent = []
    with patch(
        "app.logic.notifications._send_web_push",
        side_effect=lambda _sub, payload: sent.append(payload["eventId"]),
    ):
        process_pending_notifications(db, "shop-a")
    assert retry_event.id in sent


def test_35_worker_loop_survives_whole_tick_failure(monkeypatch):
    import worker

    calls = []

    def tick():
        calls.append("tick")
        if len(calls) == 1:
            raise RuntimeError("database unavailable")
        return []

    monkeypatch.setattr(worker, "tick_all_shops", tick)
    monkeypatch.setattr(worker.time, "sleep", lambda _seconds: None)
    worker.run_worker_loop(0, max_ticks=2)
    assert calls == ["tick", "tick"]


def test_36_provider_deadline_does_not_stop_later_device(monkeypatch):
    _enable_push(monkeypatch)
    monkeypatch.setattr(logic, "PROVIDER_DEADLINE_SECONDS", 0.01)
    db = _session()
    _subscription(db, endpoint=FCM_ENDPOINT)
    _subscription(db, user="staff-a", endpoint=MOZ_ENDPOINT)
    event_row = _create(db, key="test:provider-deadline")
    db.commit()
    release = Event()
    sent = []

    def blocking_send(subscription, payload):
        if "fcm.googleapis.com" in subscription.endpoint:
            release.wait(timeout=0.2)
            return
        sent.append(payload["eventId"])

    with patch(
        "app.logic.notifications._send_web_push_blocking",
        side_effect=blocking_send,
    ):
        process_pending_notifications(db, "shop-a")
    release.set()
    assert sent == [event_row.id]
    assert db.get(NotificationEvent, event_row.id).status == "pending"
    assert {row.status for row in db.query(NotificationDelivery)} == {
        "retry_scheduled",
        "sent",
    }


def test_37_shopify_failure_still_runs_notification_tick(monkeypatch):
    import worker

    db = _session()
    shop = db.query(Shop).filter(Shop.id == "shop-a").one()
    Session = sessionmaker(bind=db.get_bind(), autocommit=False, autoflush=False)
    calls = []
    monkeypatch.setattr(settings, "notifications_backend_enabled", True)
    monkeypatch.setattr(worker, "SessionLocal", Session)
    monkeypatch.setattr(
        worker,
        "run_full_sync",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("Shopify unavailable")),
    )
    monkeypatch.setattr(
        worker,
        "recover_notification_sources",
        lambda _db, shop_id: calls.append(shop_id) or {"recovered": 0},
    )
    monkeypatch.setattr(
        worker,
        "process_pending_notifications",
        lambda *_args: {"sent": 0},
    )
    result = worker.tick_shop(db, shop)
    assert calls == ["shop-a"]
    assert result["sync"]["status"] == "failed"
    assert result["notifications"]["enabled"] is True


def test_38_real_shop_loop_contains_unexpected_shop_failure(monkeypatch):
    import worker

    db = _session()
    Session = sessionmaker(bind=db.get_bind(), autocommit=False, autoflush=False)
    seen = []
    monkeypatch.setattr(worker, "SessionLocal", Session)

    def tick(_db, shop):
        seen.append(shop.id)
        if shop.id == "shop-a":
            raise RuntimeError("poisoned shop")
        return {"shop": shop.slug, "status": "ok"}

    monkeypatch.setattr(worker, "tick_shop", tick)
    results = worker.tick_all_shops()
    assert seen == ["shop-a", "shop-b"]
    assert [row["status"] for row in results] == ["failed", "ok"]


def test_39_retention_removes_only_eligible_terminal_transport():
    db = _session()
    subscription = _subscription(db)
    event_row = _create(db, key="test:retention-eligible")
    db.commit()
    delivery = db.query(NotificationDelivery).one()
    event_row.status = "resolved"
    delivery.status = "sent"
    delivery.created_at = utcnow() - timedelta(days=91)
    subscription.enabled = False
    subscription.replaced_at = utcnow() - timedelta(days=91)
    db.commit()
    result = cleanup_notification_history(
        db,
        "shop-a",
        legal_hold=False,
        now=utcnow(),
    )
    assert result == {"deliveries": 1, "subscriptions": 1, "audits": 0}
    assert db.get(NotificationDelivery, delivery.id) is None
    assert db.get(PushSubscription, subscription.id) is None
