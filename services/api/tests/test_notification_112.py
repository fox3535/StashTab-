"""Acceptance proofs for AMENDMENT-1.1.2 observation, transition, and attempt rules."""

from datetime import timedelta
from unittest.mock import patch

from app.logic.notifications import (
    cancel_notification,
    create_notification,
    occurrence_status,
    process_pending_notifications,
    recover_notification_sources,
)
from app.models.base import utcnow
from app.notifications_truth.models import (
    NOTIFICATION_TABLE_NAMES,
    NotificationDelivery,
    NotificationDeliveryAttempt,
    NotificationEvent,
    NotificationOccurrence,
    NotificationOccurrenceTransition,
    NotificationRecoveryPark,
    NotificationSourceObservation,
)
from tests.test_notifications import (
    _create,
    _enable_push,
    _session,
    _subscription,
)


def test_canonical_table_count_is_twelve():
    assert len(NOTIFICATION_TABLE_NAMES) == 12


def test_same_observation_token_is_noop():
    db = _session()
    first = create_notification(
        db,
        "shop-a",
        category="ambiguous_card",
        severity="action_required",
        action_url="/admin/staging",
        dedupe_key="obs:1",
        source_kind="inventory_exception",
        source_key="exc-1",
        observation_token="tok-a",
    )
    db.commit()
    second = create_notification(
        db,
        "shop-a",
        category="ambiguous_card",
        severity="action_required",
        action_url="/admin/staging",
        dedupe_key="obs:1",
        source_kind="inventory_exception",
        source_key="exc-1",
        observation_token="tok-a",
    )
    db.commit()
    assert first.id == second.id
    assert db.query(NotificationEvent).one().occurrence_count == 1
    assert db.query(NotificationOccurrence).count() == 1
    assert db.query(NotificationSourceObservation).count() == 1


def test_distinct_tokens_increment_count_without_new_occurrence():
    db = _session()
    create_notification(
        db,
        "shop-a",
        category="ambiguous_card",
        severity="action_required",
        action_url="/admin/staging",
        dedupe_key="obs:2",
        source_kind="inventory_exception",
        source_key="exc-2",
        observation_token="tok-1",
    )
    create_notification(
        db,
        "shop-a",
        category="ambiguous_card",
        severity="action_required",
        action_url="/admin/staging",
        dedupe_key="obs:2",
        source_kind="inventory_exception",
        source_key="exc-2",
        observation_token="tok-2",
    )
    db.commit()
    event = db.query(NotificationEvent).one()
    assert event.occurrence_count == 2
    assert event.occurrence_seq == 1
    assert db.query(NotificationOccurrence).count() == 1


def test_pattern_b_initial_token_does_not_reopen():
    db = _session()
    event = create_notification(
        db,
        "shop-a",
        category="ambiguous_card",
        severity="action_required",
        action_url="/admin/staging",
        dedupe_key="obs:3",
        source_kind="inventory_exception",
        source_key="exc-3",
        observation_token="initial",
    )
    event.status = "acknowledged"
    db.commit()
    again = create_notification(
        db,
        "shop-a",
        category="ambiguous_card",
        severity="action_required",
        action_url="/admin/staging",
        dedupe_key="obs:3",
        source_kind="inventory_exception",
        source_key="exc-3",
        observation_token="initial",
    )
    db.commit()
    assert again.occurrence_seq == 1
    assert again.status == "acknowledged"


def test_transition_current_status_is_max_seq():
    db = _session()
    event = _create(db)
    db.commit()
    assert occurrence_status(db, "shop-a", event.id, 1) == "pending"
    assert db.query(NotificationOccurrenceTransition).one().transition_seq == 1


def test_owner_cancel_is_terminal(monkeypatch):
    _enable_push(monkeypatch)
    db = _session()
    _subscription(db)
    event = _create(db, key="cancel:1")
    db.commit()
    cancel_notification(db, "shop-a", event.id, "user-a")
    db.commit()
    assert db.query(NotificationEvent).one().status == "cancelled"
    assert db.query(NotificationDelivery).one().status == "cancelled"
    with patch("app.logic.notifications._send_web_push") as send:
        process_pending_notifications(db, "shop-a")
    send.assert_not_called()


def test_attempt_log_started_then_outcome(monkeypatch):
    _enable_push(monkeypatch)
    db = _session()
    _subscription(db)
    _create(db, key="attempt:1")
    db.commit()
    with patch("app.logic.notifications._send_web_push"):
        process_pending_notifications(db, "shop-a")
    phases = [
        row.phase for row in db.query(NotificationDeliveryAttempt).order_by(
            NotificationDeliveryAttempt.created_at.asc()
        )
    ]
    assert phases == ["started", "outcome"]
    assert db.query(NotificationDeliveryAttempt).filter_by(phase="outcome").one().outcome == "sent"


def test_stale_lease_recovers_as_provider_unknown(monkeypatch):
    _enable_push(monkeypatch)
    db = _session()
    _subscription(db)
    _create(db, key="lease:1")
    db.commit()
    delivery = db.query(NotificationDelivery).one()
    delivery.attempt_count = 1
    delivery.status = "retry_scheduled"
    delivery.claimed_until = utcnow() - timedelta(seconds=1)
    db.add(
        NotificationDeliveryAttempt(
            shop_id="shop-a",
            delivery_id=delivery.id,
            attempt_number=1,
            phase="started",
        )
    )
    db.commit()
    with patch("app.logic.notifications._send_web_push"):
        process_pending_notifications(db, "shop-a")
    outcomes = [
        row.outcome
        for row in db.query(NotificationDeliveryAttempt).filter_by(phase="outcome")
    ]
    assert "provider_unknown" in outcomes


def test_parked_sources_do_not_hide_later_healthy_source(monkeypatch):
    db = _session()
    now = utcnow()
    for index in range(3):
        db.add(
            NotificationRecoveryPark(
                shop_id="shop-a",
                source_kind="inventory_exception",
                source_key=f"parked-{index}",
                fail_count=1,
                next_at=now + timedelta(hours=1),
            )
        )
    db.commit()
    from app.inventory_truth.models_truth import InventoryException

    db.add(
        InventoryException(
            shop_id="shop-a",
            kind="over_sale_short",
            exception_ref="healthy",
            status="open",
        )
    )
    db.commit()
    recover_notification_sources(db, "shop-a")
    db.commit()
    assert db.query(NotificationEvent).count() == 1
