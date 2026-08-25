from datetime import timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import ShopContext, get_notification_context
from app.logic.notifications import (
    NotificationValidationError,
    cancel_notification,
    create_notification,
    process_pending_notifications,
)
from app.logic.push_endpoints import PushEndpointError, validate_push_endpoint
from app.models.base import utcnow
from app.notifications_truth.models import (
    NotificationAudit,
    NotificationEvent,
    NotificationPreference,
    PushSubscription,
    ShopNotificationPolicy,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])

TEST_SEND_LIMIT = 5
TEST_SEND_WINDOW = timedelta(hours=1)


class SubscriptionIn(BaseModel):
    endpoint: str = Field(min_length=10, max_length=4096)
    p256dh: str = Field(min_length=10, max_length=4096)
    auth: str = Field(min_length=4, max_length=4096)


class PreferencesIn(BaseModel):
    web_push_enabled: bool = True
    action_required_enabled: bool = True
    quiet_hours_start: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    quiet_hours_end: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    timezone: str = Field(default="America/Toronto", min_length=1, max_length=64)


class CriticalPolicyIn(BaseModel):
    enabled: bool
    confirm: bool = False


def _actor(ctx: ShopContext) -> str:
    if not ctx.clerk_user_id:
        raise HTTPException(status_code=401, detail="Authenticated user required")
    return ctx.clerk_user_id


def _audit(
    db: Session,
    ctx: ShopContext,
    action: str,
    *,
    category: str | None = None,
    prior_state: str | None = None,
    new_state: str | None = None,
    event_id: str | None = None,
) -> None:
    db.add(
        NotificationAudit(
            shop_id=ctx.shop_id,
            actor_clerk_user_id=_actor(ctx),
            action=action,
            category=category,
            prior_state=prior_state,
            new_state=new_state,
            event_id=event_id,
        )
    )


@router.get("/config")
def config() -> dict:
    return {
        "backend_enabled": settings.notifications_backend_enabled,
        "web_push_enabled": settings.web_push_enabled,
        "vapid_public_key": settings.vapid_public_key if settings.web_push_enabled else "",
    }


@router.get("/preferences")
def get_preferences(
    ctx: ShopContext = Depends(get_notification_context),
    db: Session = Depends(get_db),
) -> dict:
    actor = _actor(ctx)
    pref = (
        db.query(NotificationPreference)
        .filter(
            NotificationPreference.shop_id == ctx.shop_id,
            NotificationPreference.clerk_user_id == actor,
        )
        .first()
    )
    policy = db.get(ShopNotificationPolicy, ctx.shop_id)
    return {
        "web_push_enabled": True if pref is None else pref.web_push_enabled,
        "action_required_enabled": True if pref is None else pref.action_required_enabled,
        "quiet_hours_start": None if pref is None else pref.quiet_hours_start,
        "quiet_hours_end": None if pref is None else pref.quiet_hours_end,
        "timezone": "America/Toronto" if pref is None else pref.timezone,
        "critical_enabled": True if policy is None else policy.critical_enabled,
    }


@router.put("/preferences")
def update_preferences(
    payload: PreferencesIn,
    ctx: ShopContext = Depends(get_notification_context),
    db: Session = Depends(get_db),
) -> dict:
    actor = _actor(ctx)
    pref = (
        db.query(NotificationPreference)
        .filter(
            NotificationPreference.shop_id == ctx.shop_id,
            NotificationPreference.clerk_user_id == actor,
        )
        .first()
    )
    if pref is None:
        pref = NotificationPreference(shop_id=ctx.shop_id, clerk_user_id=actor)
        db.add(pref)
    data = payload.model_dump()
    try:
        ZoneInfo(data["timezone"])
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=400, detail="Invalid timezone") from exc
    for field, value in data.items():
        setattr(pref, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Preference update conflicted")
    return {"success": True}


@router.put("/policy/critical")
def update_critical_policy(
    payload: CriticalPolicyIn,
    ctx: ShopContext = Depends(get_notification_context),
    db: Session = Depends(get_db),
) -> dict:
    if ctx.role != "owner":
        raise HTTPException(status_code=403, detail="Shop owner required")
    if not payload.enabled and not payload.confirm:
        raise HTTPException(status_code=400, detail="Explicit confirmation required")
    policy = db.get(ShopNotificationPolicy, ctx.shop_id)
    if policy is None:
        policy = ShopNotificationPolicy(shop_id=ctx.shop_id, critical_enabled=True)
        db.add(policy)
    prior = bool(policy.critical_enabled)
    policy.critical_enabled = payload.enabled
    policy.updated_at = utcnow()
    _audit(
        db,
        ctx,
        "critical_enable" if payload.enabled else "critical_disable",
        category="critical",
        prior_state=str(prior).lower(),
        new_state=str(payload.enabled).lower(),
    )
    db.commit()
    return {"success": True, "critical_enabled": payload.enabled}


@router.post("/subscriptions")
def save_subscription(
    payload: SubscriptionIn,
    ctx: ShopContext = Depends(get_notification_context),
    db: Session = Depends(get_db),
) -> dict:
    actor = _actor(ctx)
    try:
        validate_push_endpoint(payload.endpoint, resolve_dns=False)
    except PushEndpointError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    subscription = (
        db.query(PushSubscription)
        .filter(
            PushSubscription.shop_id == ctx.shop_id,
            PushSubscription.endpoint == payload.endpoint,
        )
        .first()
    )
    if subscription is None:
        subscription = PushSubscription(
            shop_id=ctx.shop_id,
            clerk_user_id=actor,
            endpoint=payload.endpoint,
            p256dh=payload.p256dh,
            auth=payload.auth,
        )
        db.add(subscription)
    elif subscription.clerk_user_id != actor and subscription.enabled:
        raise HTTPException(status_code=409, detail="Push subscription is owned by another user")
    else:
        subscription.clerk_user_id = actor
        subscription.p256dh = payload.p256dh
        subscription.auth = payload.auth
        subscription.enabled = True
        subscription.replaced_at = None
        subscription.failure_count = 0
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Subscription update conflicted")
    return {"success": True}


@router.delete("/subscriptions")
def remove_subscription(
    payload: SubscriptionIn,
    ctx: ShopContext = Depends(get_notification_context),
    db: Session = Depends(get_db),
) -> dict:
    subscription = (
        db.query(PushSubscription)
        .filter(
            PushSubscription.shop_id == ctx.shop_id,
            PushSubscription.endpoint == payload.endpoint,
            PushSubscription.clerk_user_id == _actor(ctx),
        )
        .first()
    )
    if subscription is not None:
        subscription.enabled = False
        subscription.replaced_at = utcnow()
        db.commit()
    return {"success": True}


@router.get("/events")
def list_events(
    ctx: ShopContext = Depends(get_notification_context),
    db: Session = Depends(get_db),
) -> dict:
    rows = (
        db.query(NotificationEvent)
        .filter(NotificationEvent.shop_id == ctx.shop_id)
        .order_by(NotificationEvent.created_at.desc())
        .limit(100)
        .all()
    )
    return {
        "items": [
            {
                "id": row.id,
                "category": row.category,
                "severity": row.severity,
                "title": row.title,
                "body": row.body,
                "action_url": row.action_url,
                "status": row.status,
                "occurrence_seq": row.occurrence_seq,
                "created_at": row.created_at,
            }
            for row in rows
        ]
    }


def _event_for_shop(db: Session, shop_id: str, event_id: str) -> NotificationEvent:
    event = (
        db.query(NotificationEvent)
        .filter(NotificationEvent.shop_id == shop_id, NotificationEvent.id == event_id)
        .first()
    )
    if event is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return event


@router.post("/events/{event_id}/acknowledge")
def acknowledge(
    event_id: str,
    ctx: ShopContext = Depends(get_notification_context),
    db: Session = Depends(get_db),
) -> dict:
    event = _event_for_shop(db, ctx.shop_id, event_id)
    if event.status not in {"pending", "delivered", "failed"}:
        raise HTTPException(status_code=409, detail="Notification cannot be acknowledged")
    prior = event.status
    event.status = "acknowledged"
    event.acknowledged_by = _actor(ctx)
    event.acknowledged_at = utcnow()
    _audit(db, ctx, "ack", category=event.category, prior_state=prior, new_state=event.status, event_id=event.id)
    db.commit()
    return {"success": True}


@router.post("/events/{event_id}/resolve")
def resolve_event(
    event_id: str,
    ctx: ShopContext = Depends(get_notification_context),
    db: Session = Depends(get_db),
) -> dict:
    event = _event_for_shop(db, ctx.shop_id, event_id)
    if event.status != "acknowledged":
        raise HTTPException(status_code=409, detail="Acknowledge notification first")
    prior = event.status
    event.status = "resolved"
    event.resolved_at = utcnow()
    _audit(db, ctx, "resolve", category=event.category, prior_state=prior, new_state=event.status, event_id=event.id)
    db.commit()
    return {"success": True}


@router.post("/test")
def send_test(
    ctx: ShopContext = Depends(get_notification_context),
    db: Session = Depends(get_db),
) -> dict:
    actor = _actor(ctx)
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:rate_limit_key))"),
            {"rate_limit_key": f"notification-test:{ctx.shop_id}:{actor}"},
        )
    cutoff = utcnow() - TEST_SEND_WINDOW
    recent = (
        db.query(NotificationAudit)
        .filter(
            NotificationAudit.shop_id == ctx.shop_id,
            NotificationAudit.actor_clerk_user_id == actor,
            NotificationAudit.action == "test_send",
            NotificationAudit.created_at >= cutoff,
        )
        .count()
    )
    if recent >= TEST_SEND_LIMIT:
        raise HTTPException(status_code=429, detail="Test-send rate limit exceeded")
    request_id = str(uuid4())
    try:
        event = create_notification(
            db,
            ctx.shop_id,
            category="test",
            severity="action_required",
            action_url="/admin/settings",
            dedupe_key=f"test:{actor}:{request_id}",
            source_kind="test",
            source_key=f"test:{actor}:{request_id}",
            observation_token=request_id,
        )
    except NotificationValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _audit(db, ctx, "test_send", category="test", event_id=event.id)
    db.commit()
    result = process_pending_notifications(db, ctx.shop_id)
    return {"success": True, "event_id": event.id, "delivery": result}


@router.post("/events/{event_id}/cancel")
def cancel_event(
    event_id: str,
    ctx: ShopContext = Depends(get_notification_context),
    db: Session = Depends(get_db),
) -> dict:
    actor = _actor(ctx)
    if ctx.role != "owner":
        raise HTTPException(status_code=403, detail="Shop owner required")
    try:
        event = cancel_notification(db, ctx.shop_id, event_id, actor)
    except LookupError:
        raise HTTPException(status_code=404, detail="Notification not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Shop owner required")
    db.commit()
    return {"success": True, "event_id": event.id, "status": event.status}
