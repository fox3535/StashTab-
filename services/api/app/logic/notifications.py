from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone
from queue import Empty, Queue
from threading import Thread
from typing import Iterable
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import String, cast, func, or_, true
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.inventory_truth.models_truth import InventoryException
from app.logic.push_endpoints import (
    PushEndpointError,
    no_redirect_session,
    validate_push_endpoint,
)
from app.models import ShopMember
from app.models.base import utcnow
from app.notifications_truth.models import (
    NotificationAudit,
    NotificationDelivery,
    NotificationDeliveryAttempt,
    NotificationEvent,
    NotificationOccurrence,
    NotificationOccurrenceTransition,
    NotificationPreference,
    NotificationRecoveryPark,
    NotificationSource,
    NotificationSourceObservation,
    PushSubscription,
    ShopNotificationPolicy,
)


SAFE_TEMPLATES = {
    "test": (
        "StashTab notifications are ready",
        "Phone alerts are connected to this shop.",
        "/admin/settings",
    ),
    "action_required": (
        "StashTab needs a review",
        "Open StashTab to resolve a blocked card or workflow item.",
        "/admin/staging",
    ),
    "critical": (
        "StashTab needs attention",
        "Open StashTab to review a critical workflow failure.",
        "/admin/reports",
    ),
    "routine": (
        "StashTab daily digest",
        "Open StashTab to review routine activity.",
        "/admin/settings",
    ),
}

NOTIFICATION_SEVERITIES = frozenset(("routine", "action_required", "critical"))
OPEN_DELIVERY_STATUSES = frozenset(("pending", "retry_scheduled"))
TERMINAL_DELIVERY_STATUSES = frozenset(
    ("sent", "failed_exhausted", "expired", "cancelled")
)
REOPEN_EVENT_STATUSES = frozenset(("acknowledged", "resolved", "cancelled"))
ACTIVE_EVENT_STATUSES = frozenset(("pending", "delivered", "failed"))
GONE_STATUS_CODES = frozenset((404, 410))
MAX_ATTEMPTS = 8
DELIVERY_BATCH_LIMIT = 50
MATERIALIZATION_BATCH_LIMIT = 100
RECOVERY_BATCH_LIMIT = 100
DELIVERY_CLAIM_LEASE_SECONDS = 120
PATTERN_B_OBSERVATION_TOKEN = "initial"
RECOVERY_PARK_LIMIT = 100
DUE_BATCH_LIMIT = 50
PROVIDER_DEADLINE_SECONDS = 20
DELIVERY_RETENTION_DAYS = 90
AUDIT_RETENTION_DAYS = 365
RECOVERABLE_EXCEPTION_KINDS = frozenset(("over_sale_short", "adjust_anomaly"))


class NotificationValidationError(ValueError):
    pass


def actor_id(clerk_user_id: str | None) -> str:
    if not clerk_user_id:
        raise NotificationValidationError("Authenticated user required")
    return clerk_user_id


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def safe_action_url(action_url: str) -> str:
    allowed = {template[2] for template in SAFE_TEMPLATES.values()}
    if action_url not in allowed:
        raise NotificationValidationError("action_url is not an approved application route")
    return action_url


def lock_screen_copy(
    category: str, severity: str, action_url: str
) -> tuple[str, str, str]:
    safe_action_url(action_url)
    template_key = "test" if category == "test" else severity
    template = SAFE_TEMPLATES.get(template_key)
    if template is None:
        raise NotificationValidationError("Unsupported notification severity")
    return template


def push_payload(event: NotificationEvent) -> dict[str, str]:
    return {
        "title": event.title,
        "body": event.body,
        "url": event.action_url,
        "tag": event.dedupe_key,
        "eventId": event.id,
    }


def _vapid_ready() -> bool:
    if not (
        settings.vapid_public_key.strip()
        and settings.vapid_private_key.strip()
    ):
        return False
    subject = settings.vapid_subject.strip()
    if not subject or subject.lower() == "mailto:ops@example.com":
        return False
    parsed = urlsplit(subject)
    if parsed.scheme == "mailto":
        return bool(parsed.path and "@" in parsed.path)
    return parsed.scheme == "https" and bool(parsed.netloc)


def _audit(
    db: Session,
    event: NotificationEvent,
    *,
    action: str,
    prior_state: str | None,
    new_state: str | None,
    actor_clerk_user_id: str = "system",
) -> None:
    db.add(
        NotificationAudit(
            shop_id=event.shop_id,
            actor_clerk_user_id=actor_clerk_user_id or "system",
            action=action,
            category=event.category,
            prior_state=prior_state,
            new_state=new_state,
            event_id=event.id,
        )
    )


def _lock_source(
    db: Session, shop_id: str, source_kind: str, source_key: str
) -> NotificationSource | None:
    query = db.query(NotificationSource).filter(
        NotificationSource.shop_id == shop_id,
        NotificationSource.source_kind == source_kind,
        NotificationSource.source_key == source_key,
    )
    if db.get_bind().dialect.name != "sqlite":
        query = query.with_for_update()
    return query.first()


def _existing_observation(
    db: Session,
    shop_id: str,
    source_kind: str,
    source_key: str,
    observation_token: str,
) -> NotificationSourceObservation | None:
    return (
        db.query(NotificationSourceObservation)
        .filter(
            NotificationSourceObservation.shop_id == shop_id,
            NotificationSourceObservation.source_kind == source_kind,
            NotificationSourceObservation.source_key == source_key,
            NotificationSourceObservation.observation_token == observation_token,
        )
        .first()
    )


def _insert_transition(
    db: Session,
    event: NotificationEvent,
    occurrence_seq: int,
    *,
    from_status: str | None,
    to_status: str,
    cause: str,
) -> NotificationOccurrenceTransition | None:
    current = (
        db.query(NotificationOccurrenceTransition)
        .filter(
            NotificationOccurrenceTransition.shop_id == event.shop_id,
            NotificationOccurrenceTransition.event_id == event.id,
            NotificationOccurrenceTransition.occurrence_seq == occurrence_seq,
        )
        .order_by(NotificationOccurrenceTransition.transition_seq.desc())
        .first()
    )
    next_seq = 1 if current is None else current.transition_seq + 1
    if to_status in {"delivered", "failed", "cancelled"} and current is not None:
        if current.to_status in {"delivered", "failed", "cancelled"}:
            return None
    transition = NotificationOccurrenceTransition(
        shop_id=event.shop_id,
        event_id=event.id,
        occurrence_seq=occurrence_seq,
        transition_seq=next_seq,
        from_status=from_status,
        to_status=to_status,
        cause=cause[:255],
    )
    try:
        with db.begin_nested():
            db.add(transition)
            db.flush()
        return transition
    except IntegrityError:
        db.expire_all()
        return None


def occurrence_status(
    db: Session,
    shop_id: str,
    event_id: str,
    occurrence_seq: int,
) -> str | None:
    transition = (
        db.query(NotificationOccurrenceTransition)
        .filter(
            NotificationOccurrenceTransition.shop_id == shop_id,
            NotificationOccurrenceTransition.event_id == event_id,
            NotificationOccurrenceTransition.occurrence_seq == occurrence_seq,
        )
        .order_by(NotificationOccurrenceTransition.transition_seq.desc())
        .first()
    )
    if transition is not None:
        return transition.to_status
    return None


def _sanitize_attempt_error(error: str | None) -> str | None:
    if not error:
        return None
    lowered = error.lower()
    forbidden = ("http://", "https://", "p256dh", "vapid", "endpoint", "auth=")
    if any(token in lowered for token in forbidden):
        return "rejected"
    return error[:200]


def _member_for_shop(db: Session, shop_id: str, clerk_user_id: str) -> ShopMember | None:
    return (
        db.query(ShopMember)
        .filter(
            ShopMember.shop_id == shop_id,
            ShopMember.clerk_user_id == clerk_user_id,
        )
        .first()
    )


def _timezone_is_valid(name: str) -> bool:
    try:
        ZoneInfo(name)
        return True
    except ZoneInfoNotFoundError:
        return False


def _event_by_dedupe(
    db: Session, shop_id: str, dedupe_key: str, *, lock: bool = False
) -> NotificationEvent | None:
    query = db.query(NotificationEvent).filter(
        NotificationEvent.shop_id == shop_id,
        NotificationEvent.dedupe_key == dedupe_key,
    )
    if lock:
        query = query.with_for_update()
    return query.first()


def _preference_allows(
    preference: NotificationPreference | None, severity: str
) -> bool:
    if severity == "routine":
        return False
    if preference is not None and not preference.web_push_enabled:
        return False
    if severity == "action_required":
        return preference is None or preference.action_required_enabled
    if severity == "critical":
        return True
    return False


def _shop_policy_allows(
    db: Session, shop_id: str, severity: str
) -> bool:
    if severity != "critical":
        return True
    policy = db.query(ShopNotificationPolicy).filter(
        ShopNotificationPolicy.shop_id == shop_id
    ).first()
    return policy is None or policy.critical_enabled


def _eligible_subscriptions(
    db: Session,
    shop_id: str,
    severity: str,
    *,
    event: NotificationEvent | None = None,
    limit: int | None = None,
) -> list[PushSubscription]:
    if not _shop_policy_allows(db, shop_id, severity):
        return []
    query = db.query(PushSubscription).join(
        ShopMember,
        (
            (ShopMember.shop_id == PushSubscription.shop_id)
            & (ShopMember.clerk_user_id == PushSubscription.clerk_user_id)
        ),
    ).outerjoin(
        NotificationPreference,
        (
            (NotificationPreference.shop_id == PushSubscription.shop_id)
            & (
                NotificationPreference.clerk_user_id
                == PushSubscription.clerk_user_id
            )
        ),
    ).filter(
        PushSubscription.shop_id == shop_id,
        PushSubscription.enabled.is_(True),
        or_(
            NotificationPreference.id.is_(None),
            NotificationPreference.web_push_enabled.is_(True),
        ),
    )
    if severity == "action_required":
        query = query.filter(
            or_(
                NotificationPreference.id.is_(None),
                NotificationPreference.action_required_enabled.is_(True),
            )
        )
    if event is not None:
        existing_delivery = db.query(NotificationDelivery.id).filter(
            NotificationDelivery.shop_id == event.shop_id,
            NotificationDelivery.event_id == event.id,
            NotificationDelivery.occurrence_seq == event.occurrence_seq,
            NotificationDelivery.subscription_id == PushSubscription.id,
        ).exists()
        query = query.filter(~existing_delivery)
    query = query.order_by(PushSubscription.created_at.asc(), PushSubscription.id.asc())
    rows = query.all()
    eligible = []
    for subscription in rows:
        preference = db.query(NotificationPreference).filter(
            NotificationPreference.shop_id == subscription.shop_id,
            NotificationPreference.clerk_user_id == subscription.clerk_user_id,
        ).first()
        if preference is not None and not _timezone_is_valid(preference.timezone):
            continue
        eligible.append(subscription)
        if limit is not None and len(eligible) >= limit:
            break
    return eligible


def _subscription_is_eligible(
    db: Session,
    subscription: PushSubscription | None,
    severity: str,
) -> bool:
    if subscription is None or not subscription.enabled:
        return False
    if not _shop_policy_allows(db, subscription.shop_id, severity):
        return False
    preference = db.query(NotificationPreference).filter(
        NotificationPreference.shop_id == subscription.shop_id,
        NotificationPreference.clerk_user_id == subscription.clerk_user_id,
    ).first()
    return _preference_allows(preference, severity)


def _quiet_until(
    preference: NotificationPreference | None, now: datetime
) -> datetime | None:
    if (
        preference is None
        or not preference.quiet_hours_start
        or not preference.quiet_hours_end
    ):
        return None
    try:
        start = time.fromisoformat(preference.quiet_hours_start)
        end = time.fromisoformat(preference.quiet_hours_end)
        zone = ZoneInfo(preference.timezone)
    except (ValueError, ZoneInfoNotFoundError):
        # Invalid user-supplied quiet-hour data fails closed for this tick.
        return now + timedelta(hours=1)
    if start == end:
        return None
    local_now = _as_utc(now).astimezone(zone)
    current = local_now.timetz().replace(tzinfo=None)
    end_date: date
    if start < end:
        if not start <= current < end:
            return None
        end_date = local_now.date()
    else:
        if current >= start:
            end_date = local_now.date() + timedelta(days=1)
        elif current < end:
            end_date = local_now.date()
        else:
            return None
    return datetime.combine(end_date, end, tzinfo=zone).astimezone(timezone.utc)


def _get_or_create_delivery(
    db: Session,
    event: NotificationEvent,
    subscription: PushSubscription,
) -> NotificationDelivery:
    if event.shop_id != subscription.shop_id:
        raise NotificationValidationError("Delivery shop_id must match parent rows")
    delivery = db.query(NotificationDelivery).filter(
        NotificationDelivery.shop_id == event.shop_id,
        NotificationDelivery.event_id == event.id,
        NotificationDelivery.occurrence_seq == event.occurrence_seq,
        NotificationDelivery.subscription_id == subscription.id,
        NotificationDelivery.delivery_generation == 1,
    ).first()
    if delivery is not None:
        return delivery
    delivery = NotificationDelivery(
        shop_id=event.shop_id,
        event_id=event.id,
        occurrence_seq=event.occurrence_seq,
        subscription_id=subscription.id,
        delivery_generation=1,
        status="pending",
        attempt_count=0,
    )
    try:
        with db.begin_nested():
            db.add(delivery)
            db.flush()
        return delivery
    except IntegrityError:
        existing = db.query(NotificationDelivery).filter(
            NotificationDelivery.shop_id == event.shop_id,
            NotificationDelivery.event_id == event.id,
            NotificationDelivery.occurrence_seq == event.occurrence_seq,
            NotificationDelivery.subscription_id == subscription.id,
            NotificationDelivery.delivery_generation == 1,
        ).first()
        if existing is None:
            raise
        return existing


def _seed_deliveries(db: Session, event: NotificationEvent) -> None:
    if event.severity == "routine":
        return
    for subscription in _eligible_subscriptions(
        db,
        event.shop_id,
        event.severity,
        limit=MATERIALIZATION_BATCH_LIMIT,
    ):
        try:
            with db.begin_nested():
                _get_or_create_delivery(db, event, subscription)
        except Exception:
            # One malformed/contended device cannot suppress later devices.
            continue


def _new_occurrence(
    db: Session, event: NotificationEvent, *, cause: str
) -> NotificationOccurrence:
    occurrence = NotificationOccurrence(
        shop_id=event.shop_id,
        event_id=event.id,
        occurrence_seq=event.occurrence_seq,
        cause=cause[:255],
    )
    db.add(occurrence)
    db.flush()
    _insert_transition(
        db,
        event,
        event.occurrence_seq,
        from_status=None,
        to_status="pending",
        cause=cause,
    )
    return occurrence


def _create_new_event(
    db: Session,
    shop_id: str,
    *,
    category: str,
    severity: str,
    action_url: str,
    dedupe_key: str,
    cause: str,
) -> NotificationEvent:
    title, body, safe_url = lock_screen_copy(category, severity, action_url)
    event = NotificationEvent(
        shop_id=shop_id,
        category=category,
        severity=severity,
        title=title,
        body=body,
        action_url=safe_url,
        dedupe_key=dedupe_key,
        status="recorded" if severity == "routine" else "pending",
        occurrence_seq=1,
        occurrence_count=1,
        last_seen_at=utcnow(),
    )
    db.add(event)
    db.flush()
    if severity != "routine":
        _new_occurrence(db, event, cause=cause)
        _seed_deliveries(db, event)
    return event


def _touch_or_reopen_event(
    db: Session,
    event: NotificationEvent,
    *,
    category: str,
    severity: str,
    action_url: str,
    cause: str,
) -> NotificationEvent:
    if event.category != category or event.severity != severity:
        raise NotificationValidationError(
            "A dedupe key cannot change notification category or severity"
        )
    title, body, safe_url = lock_screen_copy(category, severity, action_url)
    event.title = title
    event.body = body
    event.action_url = safe_url
    event.last_seen_at = utcnow()
    if event.status in REOPEN_EVENT_STATUSES and severity != "routine":
        prior_state = event.status
        event.occurrence_seq += 1
        event.occurrence_count = 1
        event.status = "pending"
        event.acknowledged_by = None
        event.acknowledged_at = None
        event.resolved_at = None
        event.cancelled_at = None
        _new_occurrence(db, event, cause=cause)
        _seed_deliveries(db, event)
        _audit(
            db,
            event,
            action="reopen",
            prior_state=prior_state,
            new_state="pending",
        )
    db.flush()
    return event


def create_notification(
    db: Session,
    shop_id: str,
    *,
    category: str,
    severity: str,
    title: str = "",
    body: str = "",
    action_url: str,
    dedupe_key: str,
    cause: str = "created",
    source_kind: str | None = None,
    source_key: str | None = None,
    observation_token: str | None = None,
) -> NotificationEvent:
    del title, body
    if not shop_id or not dedupe_key:
        raise NotificationValidationError("shop_id and dedupe_key are required")
    if severity not in NOTIFICATION_SEVERITIES:
        raise NotificationValidationError("Unsupported notification severity")
    if bool(source_kind) != bool(source_key):
        raise NotificationValidationError("source_kind and source_key must be provided together")
    if observation_token is not None and not observation_token.strip():
        raise NotificationValidationError("observation_token must not be empty")
    if source_kind and source_key:
        source = _lock_source(db, shop_id, source_kind, source_key)
        token = observation_token or PATTERN_B_OBSERVATION_TOKEN
        seen = _existing_observation(db, shop_id, source_kind, source_key, token)
        if seen is not None:
            return db.query(NotificationEvent).filter(
                NotificationEvent.shop_id == shop_id,
                NotificationEvent.id == seen.event_id,
            ).one()
        if source is not None:
            existing_event = db.query(NotificationEvent).filter(
                NotificationEvent.shop_id == shop_id,
                NotificationEvent.id == source.event_id,
            ).one()
            prior_status = existing_event.status
            event = _touch_or_reopen_event(
                db,
                existing_event,
                category=category,
                severity=severity,
                action_url=action_url,
                cause=cause,
            )
            if prior_status in ACTIVE_EVENT_STATUSES and token != PATTERN_B_OBSERVATION_TOKEN:
                event.occurrence_count = (event.occurrence_count or 1) + 1
                event.last_seen_at = utcnow()
                _audit(
                    db,
                    event,
                    action="occurrence_count_increment",
                    prior_state=prior_status,
                    new_state=event.status,
                )
            db.add(
                NotificationSourceObservation(
                    shop_id=shop_id,
                    source_kind=source_kind,
                    source_key=source_key,
                    observation_token=token,
                    event_id=event.id,
                    occurrence_seq=event.occurrence_seq,
                )
            )
            source.occurrence_seq = event.occurrence_seq
            db.flush()
            return event

    existing = _event_by_dedupe(db, shop_id, dedupe_key, lock=True)
    if existing is not None:
        event = _touch_or_reopen_event(
            db,
            existing,
            category=category,
            severity=severity,
            action_url=action_url,
            cause=cause,
        )
    else:
        try:
            if db.get_bind().dialect.name == "sqlite":
                event = _create_new_event(
                    db,
                    shop_id,
                    category=category,
                    severity=severity,
                    action_url=action_url,
                    dedupe_key=dedupe_key,
                    cause=cause,
                )
            else:
                with db.begin_nested():
                    event = _create_new_event(
                        db,
                        shop_id,
                        category=category,
                        severity=severity,
                        action_url=action_url,
                        dedupe_key=dedupe_key,
                        cause=cause,
                    )
        except IntegrityError:
            event = _event_by_dedupe(db, shop_id, dedupe_key, lock=True)
            if event is None:
                raise
            event = _touch_or_reopen_event(
                db,
                event,
                category=category,
                severity=severity,
                action_url=action_url,
                cause=cause,
            )

    if source_kind and source_key:
        token = observation_token or PATTERN_B_OBSERVATION_TOKEN
        source = db.query(NotificationSource).filter(
            NotificationSource.shop_id == shop_id,
            NotificationSource.source_kind == source_kind,
            NotificationSource.source_key == source_key,
        ).first()
        if source is None:
            db.add(
                NotificationSource(
                    shop_id=shop_id,
                    source_kind=source_kind,
                    source_key=source_key,
                    event_id=event.id,
                    occurrence_seq=event.occurrence_seq,
                )
            )
        if _existing_observation(db, shop_id, source_kind, source_key, token) is None:
            db.add(
                NotificationSourceObservation(
                    shop_id=shop_id,
                    source_kind=source_kind,
                    source_key=source_key,
                    observation_token=token,
                    event_id=event.id,
                    occurrence_seq=event.occurrence_seq,
                )
            )
        db.flush()
    return event


def recover_notification_sources(db: Session, shop_id: str) -> dict[str, int]:
    recovered = existing = 0
    source_exists = db.query(NotificationSource.id).filter(
        NotificationSource.shop_id == shop_id,
        NotificationSource.source_kind == "inventory_exception",
        NotificationSource.source_key == cast(InventoryException.id, String),
    ).exists()
    now = utcnow()
    park_not_due = db.query(NotificationRecoveryPark.id).filter(
        NotificationRecoveryPark.shop_id == shop_id,
        NotificationRecoveryPark.source_kind == "inventory_exception",
        NotificationRecoveryPark.source_key == cast(InventoryException.id, String),
        NotificationRecoveryPark.next_at > now,
    ).exists()
    exceptions = (
        db.query(InventoryException)
        .filter(
            InventoryException.shop_id == shop_id,
            InventoryException.status == "open",
            InventoryException.kind.in_(RECOVERABLE_EXCEPTION_KINDS),
            ~source_exists,
            ~park_not_due,
        )
        .order_by(InventoryException.kind.asc(), InventoryException.id.asc())
        .limit(RECOVERY_PARK_LIMIT)
        .all()
    )
    for exception in exceptions:
        source_key = str(exception.id)
        category = (
            "inventory_oversale"
            if exception.kind == "over_sale_short"
            else "adjustment_anomaly"
        )
        try:
            with db.begin_nested():
                create_notification(
                    db,
                    shop_id,
                    category=category,
                    severity="critical",
                    action_url="/admin/reports",
                    dedupe_key=f"inventory_exception:{source_key}",
                    cause=f"inventory_exception:{exception.kind}",
                    source_kind="inventory_exception",
                    source_key=source_key,
                    observation_token=PATTERN_B_OBSERVATION_TOKEN,
                )
                db.flush()
            recovered += 1
        except IntegrityError:
            # A concurrent sweep won the database uniqueness race.
            existing += 1
        except Exception:
            park = db.query(NotificationRecoveryPark).filter(
                NotificationRecoveryPark.shop_id == shop_id,
                NotificationRecoveryPark.source_kind == "inventory_exception",
                NotificationRecoveryPark.source_key == source_key,
            ).first()
            fail_count = 1 if park is None else park.fail_count + 1
            backoff = min(3600, 30 * (2 ** max(fail_count - 1, 0)))
            if park is None:
                db.add(
                    NotificationRecoveryPark(
                        shop_id=shop_id,
                        source_kind="inventory_exception",
                        source_key=source_key,
                        fail_count=fail_count,
                        next_at=utcnow() + timedelta(seconds=backoff),
                    )
                )
            else:
                park.fail_count = fail_count
                park.next_at = utcnow() + timedelta(seconds=backoff)
            db.flush()
            continue
    return {"recovered": recovered, "existing": existing}


def _send_web_push_blocking(
    subscription: PushSubscription, payload: dict[str, str]
) -> None:
    from pywebpush import webpush

    if not _vapid_ready():
        return
    validate_push_endpoint(subscription.endpoint, resolve_dns=True)
    webpush(
        subscription_info={
            "endpoint": subscription.endpoint,
            "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
        },
        data=json.dumps(payload),
        vapid_private_key=settings.vapid_private_key,
        vapid_claims={"sub": settings.vapid_subject},
        requests_session=no_redirect_session(),
    )


def _send_web_push(
    subscription: PushSubscription, payload: dict[str, str]
) -> None:
    result: Queue[Exception | None] = Queue(maxsize=1)

    def run() -> None:
        try:
            _send_web_push_blocking(subscription, payload)
        except Exception as exc:
            result.put(exc)
        else:
            result.put(None)

    Thread(target=run, daemon=True, name="notification-web-push").start()
    try:
        error = result.get(timeout=PROVIDER_DEADLINE_SECONDS)
    except Empty as exc:
        raise TimeoutError("Web Push provider deadline exceeded") from exc
    if error is not None:
        raise error


def _status_code(exc: BaseException) -> int | None:
    response = getattr(exc, "response", None)
    return getattr(response, "status_code", None)


def _backoff_seconds(attempt_count: int) -> int:
    return min(3600, 30 * (2 ** max(attempt_count - 1, 0)))


def _is_retryable_transport_error(error: BaseException) -> bool:
    if isinstance(error, PushEndpointError):
        return False
    status_code = _status_code(error)
    if status_code is None:
        return True
    return status_code in {408, 429} or status_code >= 500


def _current_occurrence(
    db: Session, event: NotificationEvent
) -> NotificationOccurrence | None:
    return db.query(NotificationOccurrence).filter(
        NotificationOccurrence.shop_id == event.shop_id,
        NotificationOccurrence.event_id == event.id,
        NotificationOccurrence.occurrence_seq == event.occurrence_seq,
    ).first()


def occurrence_status(
    db: Session,
    shop_id: str,
    event_id: str,
    occurrence_seq: int,
) -> str | None:
    """Derive occurrence state from the highest transition_seq, then deliveries."""
    db.flush()
    transition = (
        db.query(NotificationOccurrenceTransition)
        .filter(
            NotificationOccurrenceTransition.shop_id == shop_id,
            NotificationOccurrenceTransition.event_id == event_id,
            NotificationOccurrenceTransition.occurrence_seq == occurrence_seq,
        )
        .order_by(NotificationOccurrenceTransition.transition_seq.desc())
        .first()
    )
    if transition is not None and transition.to_status != "pending":
        return transition.to_status
    occurrence = db.query(NotificationOccurrence).filter(
        NotificationOccurrence.shop_id == shop_id,
        NotificationOccurrence.event_id == event_id,
        NotificationOccurrence.occurrence_seq == occurrence_seq,
    ).first()
    if occurrence is None:
        return None
    deliveries = db.query(NotificationDelivery).filter(
        NotificationDelivery.shop_id == shop_id,
        NotificationDelivery.event_id == event_id,
        NotificationDelivery.occurrence_seq == occurrence_seq,
    )
    if deliveries.filter(
        NotificationDelivery.status.in_(OPEN_DELIVERY_STATUSES)
    ).first() is not None:
        return "pending"
    if deliveries.filter(NotificationDelivery.status == "sent").first() is not None:
        return "delivered"
    first_delivery = deliveries.first()
    if first_delivery is None:
        event = db.query(NotificationEvent).filter(
            NotificationEvent.shop_id == shop_id,
            NotificationEvent.id == event_id,
        ).first()
        if (
            event is not None
            and event.occurrence_seq == occurrence_seq
            and event.status == "pending"
        ):
            return "pending"
        return "failed"
    if deliveries.filter(
        NotificationDelivery.status != "cancelled"
    ).first() is None:
        return "cancelled"
    return "failed"


def _finalize_occurrence(db: Session, event: NotificationEvent) -> None:
    status = occurrence_status(
        db,
        event.shop_id,
        event.id,
        event.occurrence_seq,
    )
    if status == "pending":
        if event.status not in {"acknowledged", "resolved", "cancelled"}:
            event.status = "pending"
        return
    if status in {"delivered", "failed", "cancelled"}:
        _insert_transition(
            db,
            event,
            event.occurrence_seq,
            from_status="pending",
            to_status=status,
            cause="finalized",
        )
    if event.status not in {"acknowledged", "resolved", "cancelled"}:
        event.status = status or "failed"


def _materialize_current_deliveries(db: Session, shop_id: str) -> set[str]:
    incomplete_event_ids: set[str] = set()
    events = db.query(NotificationEvent).filter(
        NotificationEvent.shop_id == shop_id,
        NotificationEvent.status.in_(("pending", "failed")),
        NotificationEvent.severity.in_(("action_required", "critical")),
    ).order_by(
        NotificationEvent.created_at.asc(), NotificationEvent.id.asc()
    ).limit(DELIVERY_BATCH_LIMIT).all()
    for event in events:
        missing = _eligible_subscriptions(
            db,
            shop_id,
            event.severity,
            event=event,
            limit=MATERIALIZATION_BATCH_LIMIT + 1,
        )
        if len(missing) > MATERIALIZATION_BATCH_LIMIT:
            incomplete_event_ids.add(event.id)
        for subscription in missing[:MATERIALIZATION_BATCH_LIMIT]:
            _get_or_create_delivery(db, event, subscription)
        db.flush()
        current_open = db.query(NotificationDelivery).filter(
            NotificationDelivery.shop_id == shop_id,
            NotificationDelivery.event_id == event.id,
            NotificationDelivery.occurrence_seq == event.occurrence_seq,
            NotificationDelivery.status.in_(OPEN_DELIVERY_STATUSES),
        ).order_by(
            NotificationDelivery.created_at.asc(),
            NotificationDelivery.id.asc(),
        ).limit(MATERIALIZATION_BATCH_LIMIT + 1).all()
        if len(current_open) > MATERIALIZATION_BATCH_LIMIT:
            incomplete_event_ids.add(event.id)
        for delivery in current_open[:MATERIALIZATION_BATCH_LIMIT]:
            if delivery.attempt_count >= MAX_ATTEMPTS:
                delivery.status = "failed_exhausted"
                delivery.next_retry_at = None
                continue
            subscription = db.query(PushSubscription).filter(
                PushSubscription.shop_id == shop_id,
                PushSubscription.id == delivery.subscription_id,
            ).first()
            if not _subscription_is_eligible(db, subscription, event.severity):
                delivery.status = "expired"
                delivery.next_retry_at = None
        if event.id in incomplete_event_ids:
            continue
        current_count = db.query(NotificationDelivery).filter(
            NotificationDelivery.shop_id == shop_id,
            NotificationDelivery.event_id == event.id,
            NotificationDelivery.occurrence_seq == event.occurrence_seq,
        ).count()
        if current_count == 0:
            event.status = "failed"
            _insert_transition(
                db,
                event,
                event.occurrence_seq,
                from_status="pending",
                to_status="failed",
                cause="no_devices",
            )
        else:
            _finalize_occurrence(db, event)
    db.flush()
    return incomplete_event_ids


def _claim_delivery(db: Session, shop_id: str, delivery_id: str) -> bool:
    now = utcnow()
    claimed = db.query(NotificationDelivery).filter(
        NotificationDelivery.shop_id == shop_id,
        NotificationDelivery.id == delivery_id,
        NotificationDelivery.status.in_(OPEN_DELIVERY_STATUSES),
        NotificationDelivery.attempt_count < MAX_ATTEMPTS,
        or_(
            NotificationDelivery.claimed_until.is_(None),
            NotificationDelivery.claimed_until < now,
        ),
        or_(
            NotificationDelivery.next_retry_at.is_(None),
            NotificationDelivery.next_retry_at <= now,
        ),
    ).update(
        {
            NotificationDelivery.attempt_count:
                NotificationDelivery.attempt_count + 1,
            NotificationDelivery.status: "retry_scheduled",
            NotificationDelivery.attempted_at: now,
            NotificationDelivery.claimed_until: now + timedelta(
                seconds=DELIVERY_CLAIM_LEASE_SECONDS
            ),
            NotificationDelivery.error: None,
        },
        synchronize_session=False,
    )
    if claimed != 1:
        db.commit()
        db.expire_all()
        return False
    db.expire_all()
    delivery = db.query(NotificationDelivery).filter(
        NotificationDelivery.shop_id == shop_id,
        NotificationDelivery.id == delivery_id,
    ).one()
    db.add(
        NotificationDeliveryAttempt(
            shop_id=shop_id,
            delivery_id=delivery_id,
            attempt_number=delivery.attempt_count,
            phase="started",
        )
    )
    db.commit()
    db.expire_all()
    return True


def _record_transport_result(
    db: Session,
    delivery: NotificationDelivery,
    event: NotificationEvent,
    subscription: PushSubscription,
    *,
    error: BaseException | None,
) -> str:
    outcome = "sent"
    if error is None:
        delivery.status = "sent"
        delivery.error = None
        delivery.next_retry_at = None
        delivery.claimed_until = None
        subscription.failure_count = 0
        subscription.last_success_at = utcnow()
    else:
        subscription.failure_count += 1
        delivery.error = _sanitize_attempt_error(str(error))
        status_code = _status_code(error)
        if status_code in GONE_STATUS_CODES:
            delivery.status = "expired"
            delivery.next_retry_at = None
            delivery.claimed_until = None
            subscription.enabled = False
            subscription.replaced_at = subscription.replaced_at or utcnow()
            outcome = "expired"
        elif (
            delivery.attempt_count >= MAX_ATTEMPTS
            or not _is_retryable_transport_error(error)
        ):
            delivery.status = "failed_exhausted"
            delivery.next_retry_at = None
            delivery.claimed_until = None
            outcome = "failed_exhausted"
        else:
            delivery.status = "retry_scheduled"
            delivery.next_retry_at = utcnow() + timedelta(
                seconds=_backoff_seconds(delivery.attempt_count)
            )
            delivery.claimed_until = None
            outcome = "retry_scheduled"
    started = db.query(NotificationDeliveryAttempt).filter(
        NotificationDeliveryAttempt.shop_id == delivery.shop_id,
        NotificationDeliveryAttempt.delivery_id == delivery.id,
        NotificationDeliveryAttempt.attempt_number == delivery.attempt_count,
        NotificationDeliveryAttempt.phase == "started",
    ).first()
    if started is not None:
        db.add(
            NotificationDeliveryAttempt(
                shop_id=delivery.shop_id,
                delivery_id=delivery.id,
                attempt_number=delivery.attempt_count,
                phase="outcome",
                outcome=outcome,
                error=delivery.error,
            )
        )
    # The delivery row is the durable transport audit: it retains attempt
    # count, timestamps, retry schedule, terminal outcome and bounded error.
    # NotificationAudit is reserved by the frozen schema for human actions.
    _finalize_occurrence(db, event)
    db.flush()
    return delivery.status


def _defer_for_quiet_hours(
    db: Session,
    delivery: NotificationDelivery,
    event: NotificationEvent | None,
    subscription: PushSubscription | None,
) -> bool:
    if event is None or subscription is None or event.category == "test":
        return False
    preference = db.query(NotificationPreference).filter(
        NotificationPreference.shop_id == subscription.shop_id,
        NotificationPreference.clerk_user_id == subscription.clerk_user_id,
    ).first()
    quiet_until = _quiet_until(preference, utcnow())
    if quiet_until is None:
        return False
    deferred = db.query(NotificationDelivery).filter(
        NotificationDelivery.shop_id == delivery.shop_id,
        NotificationDelivery.id == delivery.id,
        NotificationDelivery.status.in_(OPEN_DELIVERY_STATUSES),
        or_(
            NotificationDelivery.next_retry_at.is_(None),
            NotificationDelivery.next_retry_at <= utcnow(),
        ),
    ).update(
        {NotificationDelivery.next_retry_at: quiet_until},
        synchronize_session=False,
    )
    db.commit()
    db.expire_all()
    return deferred == 1


def _process_due_delivery(db: Session, shop_id: str, delivery_id: str) -> str | None:
    selected = db.query(NotificationDelivery).filter(
        NotificationDelivery.shop_id == shop_id,
        NotificationDelivery.id == delivery_id,
    ).populate_existing().first()
    if selected is None:
        return None
    event = db.query(NotificationEvent).filter(
        NotificationEvent.shop_id == shop_id,
        NotificationEvent.id == selected.event_id,
        NotificationEvent.occurrence_seq == selected.occurrence_seq,
    ).first()
    subscription = db.query(PushSubscription).filter(
        PushSubscription.shop_id == shop_id,
        PushSubscription.id == selected.subscription_id,
    ).first()
    if _defer_for_quiet_hours(db, selected, event, subscription):
        return None
    if not _claim_delivery(db, shop_id, delivery_id):
        return None

    delivery = db.query(NotificationDelivery).filter(
        NotificationDelivery.shop_id == shop_id,
        NotificationDelivery.id == delivery_id,
    ).populate_existing().one()
    event = db.query(NotificationEvent).filter(
        NotificationEvent.shop_id == shop_id,
        NotificationEvent.id == delivery.event_id,
        NotificationEvent.occurrence_seq == delivery.occurrence_seq,
    ).first()
    subscription = db.query(PushSubscription).filter(
        PushSubscription.shop_id == shop_id,
        PushSubscription.id == delivery.subscription_id,
    ).first()
    if (
        event is None
        or event.status in {"cancelled", "resolved"}
        or subscription is None
        or not subscription.enabled
        or _member_for_shop(db, shop_id, subscription.clerk_user_id) is None
    ):
        with db.begin_nested():
            started = db.query(NotificationDeliveryAttempt).filter(
                NotificationDeliveryAttempt.shop_id == shop_id,
                NotificationDeliveryAttempt.delivery_id == delivery.id,
                NotificationDeliveryAttempt.attempt_number == delivery.attempt_count,
                NotificationDeliveryAttempt.phase == "started",
            ).first()
            if started is not None:
                db.add(
                    NotificationDeliveryAttempt(
                        shop_id=shop_id,
                        delivery_id=delivery.id,
                        attempt_number=delivery.attempt_count,
                        phase="outcome",
                        outcome="expired",
                    )
                )
            delivery.status = "expired"
            delivery.next_retry_at = None
            delivery.claimed_until = None
            if event is not None:
                _finalize_occurrence(db, event)
            db.flush()
        db.commit()
        return "expired"

    transport_error: BaseException | None = None
    try:
        _send_web_push(subscription, push_payload(event))
    except Exception as exc:
        transport_error = exc

    with db.begin_nested():
        outcome = _record_transport_result(
            db,
            delivery,
            event,
            subscription,
            error=transport_error,
        )
    db.commit()
    return outcome


def cancel_notification(
    db: Session,
    shop_id: str,
    event_id: str,
    actor_clerk_user_id: str,
) -> NotificationEvent:
    event = db.query(NotificationEvent).filter(
        NotificationEvent.shop_id == shop_id,
        NotificationEvent.id == event_id,
    ).first()
    if event is None:
        raise LookupError("notification not found")
    member = _member_for_shop(db, shop_id, actor_clerk_user_id)
    if member is None or member.role != "owner":
        raise PermissionError("owner required")
    prior = event.status
    event.status = "cancelled"
    event.cancelled_at = utcnow()
    if occurrence_status(db, shop_id, event.id, event.occurrence_seq) == "pending":
        _insert_transition(
            db,
            event,
            event.occurrence_seq,
            from_status="pending",
            to_status="cancelled",
            cause="cancelled",
        )
    deliveries = db.query(NotificationDelivery).filter(
        NotificationDelivery.shop_id == shop_id,
        NotificationDelivery.event_id == event.id,
        NotificationDelivery.occurrence_seq == event.occurrence_seq,
        NotificationDelivery.status.in_(OPEN_DELIVERY_STATUSES),
    ).all()
    for delivery in deliveries:
        delivery.status = "cancelled"
        delivery.next_retry_at = None
        delivery.claimed_until = None
        started = db.query(NotificationDeliveryAttempt).filter(
            NotificationDeliveryAttempt.shop_id == shop_id,
            NotificationDeliveryAttempt.delivery_id == delivery.id,
            NotificationDeliveryAttempt.phase == "started",
        ).order_by(NotificationDeliveryAttempt.attempt_number.desc()).first()
        has_outcome = False
        if started is not None:
            has_outcome = (
                db.query(NotificationDeliveryAttempt)
                .filter(
                    NotificationDeliveryAttempt.shop_id == shop_id,
                    NotificationDeliveryAttempt.delivery_id == delivery.id,
                    NotificationDeliveryAttempt.attempt_number == started.attempt_number,
                    NotificationDeliveryAttempt.phase == "outcome",
                )
                .first()
                is not None
            )
            if not has_outcome:
                db.add(
                    NotificationDeliveryAttempt(
                        shop_id=shop_id,
                        delivery_id=delivery.id,
                        attempt_number=started.attempt_number,
                        phase="outcome",
                        outcome="cancelled",
                    )
                )
    _audit(
        db,
        event,
        action="cancel",
        prior_state=prior,
        new_state="cancelled",
        actor_clerk_user_id=actor_clerk_user_id,
    )
    db.flush()
    return event


def _recover_stale_attempts(db: Session, shop_id: str) -> None:
    now = utcnow()
    started_rows = (
        db.query(NotificationDeliveryAttempt)
        .filter(
            NotificationDeliveryAttempt.shop_id == shop_id,
            NotificationDeliveryAttempt.phase == "started",
        )
        .all()
    )
    for started in started_rows:
        has_outcome = (
            db.query(NotificationDeliveryAttempt)
            .filter(
                NotificationDeliveryAttempt.shop_id == shop_id,
                NotificationDeliveryAttempt.delivery_id == started.delivery_id,
                NotificationDeliveryAttempt.attempt_number == started.attempt_number,
                NotificationDeliveryAttempt.phase == "outcome",
            )
            .first()
        )
        if has_outcome is not None:
            continue
        delivery = db.query(NotificationDelivery).filter(
            NotificationDelivery.shop_id == shop_id,
            NotificationDelivery.id == started.delivery_id,
        ).first()
        claimed_until = _as_utc(delivery.claimed_until) if delivery is not None else None
        if delivery is None or claimed_until is None or claimed_until >= now:
            continue
        db.add(
            NotificationDeliveryAttempt(
                shop_id=shop_id,
                delivery_id=delivery.id,
                attempt_number=started.attempt_number,
                phase="outcome",
                outcome="provider_unknown",
            )
        )
        delivery.claimed_until = None
        if delivery.status not in TERMINAL_DELIVERY_STATUSES:
            delivery.status = "retry_scheduled"
    db.flush()


def process_pending_notifications(
    db: Session, shop_id: str
) -> dict[str, int | bool]:
    if not _vapid_ready():
        return {
            "enabled": False,
            "sent": 0,
            "failed": 0,
            "retry_scheduled": 0,
        }

    now = utcnow()
    _recover_stale_attempts(db, shop_id)
    incomplete_event_ids = _materialize_current_deliveries(db, shop_id)
    db.commit()
    due = (
        db.query(NotificationDelivery)
        .join(
            NotificationEvent,
            (NotificationEvent.shop_id == NotificationDelivery.shop_id)
            & (NotificationEvent.id == NotificationDelivery.event_id),
        )
        .filter(
            NotificationDelivery.shop_id == shop_id,
            NotificationEvent.status.notin_(("cancelled", "resolved")),
            NotificationDelivery.status.in_(OPEN_DELIVERY_STATUSES),
            NotificationDelivery.attempt_count < MAX_ATTEMPTS,
            ~NotificationDelivery.event_id.in_(incomplete_event_ids)
            if incomplete_event_ids
            else true(),
            or_(
                NotificationDelivery.claimed_until.is_(None),
                NotificationDelivery.claimed_until < now,
            ),
            or_(
                NotificationDelivery.next_retry_at.is_(None),
                NotificationDelivery.next_retry_at <= now,
            ),
        )
        .order_by(
            func.coalesce(
                NotificationDelivery.next_retry_at,
                NotificationDelivery.created_at,
            ).asc(),
            NotificationDelivery.created_at.asc(),
            NotificationDelivery.id.asc(),
        )
        .limit(DELIVERY_BATCH_LIMIT)
        .all()
    )
    counts = {"sent": 0, "failed": 0, "retry_scheduled": 0}
    for selected in due:
        try:
            outcome = _process_due_delivery(db, shop_id, selected.id)
        except Exception:
            db.rollback()
            counts["failed"] += 1
            continue
        if outcome is None:
            continue
        if outcome == "sent":
            counts["sent"] += 1
        elif outcome == "retry_scheduled":
            counts["retry_scheduled"] += 1
            counts["failed"] += 1
        else:
            counts["failed"] += 1
    return {"enabled": True, **counts}


def cleanup_notification_history(
    db: Session,
    shop_id: str,
    *,
    legal_hold: bool,
    open_investigation: bool = False,
    required_audit_ids: Iterable[str] = (),
    now: datetime | None = None,
) -> dict[str, int]:
    """Conservative, explicit cleanup job; never called by the worker tick."""
    if legal_hold or open_investigation:
        return {"deliveries": 0, "subscriptions": 0, "audits": 0}
    cutoff_now = _as_utc(now) or _as_utc(utcnow())
    delivery_cutoff = cutoff_now - timedelta(days=DELIVERY_RETENTION_DAYS)
    audit_cutoff = cutoff_now - timedelta(days=AUDIT_RETENTION_DAYS)

    terminal_deliveries = db.query(NotificationDelivery).filter(
        NotificationDelivery.shop_id == shop_id,
        NotificationDelivery.status.in_(TERMINAL_DELIVERY_STATUSES),
        NotificationDelivery.created_at < delivery_cutoff,
    ).all()
    delivery_count = 0
    for delivery in terminal_deliveries:
        event = db.query(NotificationEvent).filter(
            NotificationEvent.shop_id == shop_id,
            NotificationEvent.id == delivery.event_id,
        ).first()
        if event is not None and event.status not in {"resolved", "cancelled"}:
            continue
        db.delete(delivery)
        delivery_count += 1
    db.flush()

    subscriptions = db.query(PushSubscription).filter(
        PushSubscription.shop_id == shop_id,
        PushSubscription.enabled.is_(False),
        PushSubscription.replaced_at.is_not(None),
        PushSubscription.replaced_at < delivery_cutoff,
    ).all()
    subscription_count = 0
    for subscription in subscriptions:
        retained_delivery = db.query(NotificationDelivery).filter(
            NotificationDelivery.shop_id == shop_id,
            NotificationDelivery.subscription_id == subscription.id,
        ).first()
        if retained_delivery is None:
            db.delete(subscription)
            subscription_count += 1

    required = set(required_audit_ids)
    # Audit rows are append-only at the database layer. This runtime helper
    # deliberately never attempts to bypass that protection; an approved,
    # migrator-owned retention job may archive eligible rows after 365 days.
    del audit_cutoff, required
    audit_count = 0
    db.flush()
    return {
        "deliveries": delivery_count,
        "subscriptions": subscription_count,
        "audits": audit_count,
    }
