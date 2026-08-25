"""Migrator-owned notification schema.

These tables deliberately use a dedicated ``NotificationBase``. Importing this
module performs no DDL, and application ``Base.metadata.create_all`` cannot see
or create any notification table.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import new_uuid, utcnow


class NotificationBase(DeclarativeBase):
    pass


# Resolve the application-owned parent in this isolated metadata. The migrator
# never includes this shadow table in its create list.
Table(
    "shops",
    NotificationBase.metadata,
    Column("id", String(36), primary_key=True),
)


EVENT_STATUSES = (
    "pending",
    "delivered",
    "failed",
    "acknowledged",
    "resolved",
    "cancelled",
    "recorded",
)
OCCURRENCE_STATUSES = ("pending", "delivered", "failed", "cancelled")
DELIVERY_STATUSES = (
    "pending",
    "retry_scheduled",
    "sent",
    "failed_exhausted",
    "expired",
    "cancelled",
)
SEVERITIES = ("routine", "action_required", "critical")
AUDIT_ACTIONS = (
    "critical_disable",
    "critical_enable",
    "test_send",
    "ack",
    "resolve",
    "cancel",
    "reopen",
    "occurrence_count_increment",
)
TRANSITION_STATUSES = ("pending", "delivered", "failed", "cancelled")
ATTEMPT_PHASES = ("started", "outcome")
ATTEMPT_OUTCOMES = (
    "sent",
    "retry_scheduled",
    "failed_exhausted",
    "expired",
    "provider_unknown",
    "cancelled",
)


def _values(values: tuple[str, ...]) -> str:
    return ",".join(f"'{value}'" for value in values)


class NotificationEvent(NotificationBase):
    __tablename__ = "notification_event"
    __table_args__ = (
        UniqueConstraint("shop_id", "id", name="uq_notification_event_shop_id"),
        UniqueConstraint(
            "shop_id", "dedupe_key", name="uq_notification_event_shop_dedupe"
        ),
        ForeignKeyConstraint(
            ["shop_id"], ["shops.id"], name="fk_notification_event_shop", ondelete="RESTRICT"
        ),
        CheckConstraint(
            f"severity IN ({_values(SEVERITIES)})", name="ck_notification_event_severity"
        ),
        CheckConstraint(
            f"status IN ({_values(EVENT_STATUSES)})", name="ck_notification_event_status"
        ),
        CheckConstraint("occurrence_seq >= 1", name="ck_notification_event_occurrence_seq"),
        CheckConstraint("occurrence_count >= 1", name="ck_notification_event_occurrence_count"),
        Index("ix_notification_event_shop_status_created", "shop_id", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    shop_id: Mapped[str] = mapped_column(String(36), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(24), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    body: Mapped[str] = mapped_column(String(500), nullable=False)
    action_url: Mapped[str] = mapped_column(String(500), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    occurrence_seq: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    occurrence_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )
    acknowledged_by: Mapped[str | None] = mapped_column(String(120))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )


class NotificationOccurrence(NotificationBase):
    __tablename__ = "notification_occurrence"
    __table_args__ = (
        UniqueConstraint(
            "shop_id",
            "event_id",
            "occurrence_seq",
            name="uq_notification_occurrence_shop_event_seq",
        ),
        ForeignKeyConstraint(
            ["shop_id"], ["shops.id"], name="fk_notification_occurrence_shop", ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(
            ["shop_id", "event_id"],
            ["notification_event.shop_id", "notification_event.id"],
            name="fk_notification_occurrence_shop_event",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "occurrence_seq >= 1", name="ck_notification_occurrence_seq"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    shop_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    occurrence_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    cause: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class PushSubscription(NotificationBase):
    __tablename__ = "push_subscription"
    __table_args__ = (
        UniqueConstraint("shop_id", "id", name="uq_push_subscription_shop_id"),
        UniqueConstraint("shop_id", "endpoint", name="uq_push_subscription_shop_endpoint"),
        ForeignKeyConstraint(
            ["shop_id"], ["shops.id"], name="fk_push_subscription_shop", ondelete="RESTRICT"
        ),
        CheckConstraint("failure_count >= 0", name="ck_push_subscription_failure_count"),
        Index("ix_push_subscription_shop_user", "shop_id", "clerk_user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    shop_id: Mapped[str] = mapped_column(String(36), nullable=False)
    clerk_user_id: Mapped[str] = mapped_column(String(120), nullable=False)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    p256dh: Mapped[str] = mapped_column(Text, nullable=False)
    auth: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class NotificationDelivery(NotificationBase):
    __tablename__ = "notification_delivery"
    __table_args__ = (
        UniqueConstraint("shop_id", "id", name="uq_notification_delivery_shop_id"),
        UniqueConstraint(
            "shop_id",
            "event_id",
            "occurrence_seq",
            "subscription_id",
            "delivery_generation",
            name="uq_notification_delivery_identity",
        ),
        ForeignKeyConstraint(
            ["shop_id"], ["shops.id"], name="fk_notification_delivery_shop", ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(
            ["shop_id", "event_id"],
            ["notification_event.shop_id", "notification_event.id"],
            name="fk_notification_delivery_shop_event",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["shop_id", "event_id", "occurrence_seq"],
            [
                "notification_occurrence.shop_id",
                "notification_occurrence.event_id",
                "notification_occurrence.occurrence_seq",
            ],
            name="fk_notification_delivery_shop_occurrence",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["shop_id", "subscription_id"],
            ["push_subscription.shop_id", "push_subscription.id"],
            name="fk_notification_delivery_shop_subscription",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            f"status IN ({_values(DELIVERY_STATUSES)})",
            name="ck_notification_delivery_status",
        ),
        CheckConstraint(
            "delivery_generation >= 1", name="ck_notification_delivery_generation"
        ),
        CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= 8",
            name="ck_notification_delivery_attempt_count",
        ),
        Index(
            "ix_notification_delivery_shop_retry_created",
            "shop_id",
            "next_retry_at",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    shop_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    occurrence_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    subscription_id: Mapped[str] = mapped_column(String(36), nullable=False)
    delivery_generation: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    claimed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class NotificationSource(NotificationBase):
    __tablename__ = "notification_source"
    __table_args__ = (
        UniqueConstraint(
            "shop_id", "source_kind", "source_key", name="uq_notification_source_identity"
        ),
        ForeignKeyConstraint(
            ["shop_id"], ["shops.id"], name="fk_notification_source_shop", ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(
            ["shop_id", "event_id"],
            ["notification_event.shop_id", "notification_event.id"],
            name="fk_notification_source_shop_event",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["shop_id", "event_id", "occurrence_seq"],
            [
                "notification_occurrence.shop_id",
                "notification_occurrence.event_id",
                "notification_occurrence.occurrence_seq",
            ],
            name="fk_notification_source_shop_occurrence",
            ondelete="RESTRICT",
        ),
        CheckConstraint("occurrence_seq >= 1", name="ck_notification_source_occurrence_seq"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    shop_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    occurrence_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class NotificationPreference(NotificationBase):
    __tablename__ = "notification_preference"
    __table_args__ = (
        UniqueConstraint(
            "shop_id", "clerk_user_id", name="uq_notification_preference_shop_user"
        ),
        ForeignKeyConstraint(
            ["shop_id"], ["shops.id"], name="fk_notification_preference_shop", ondelete="RESTRICT"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    shop_id: Mapped[str] = mapped_column(String(36), nullable=False)
    clerk_user_id: Mapped[str] = mapped_column(String(120), nullable=False)
    web_push_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    action_required_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    critical_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    quiet_hours_start: Mapped[str | None] = mapped_column(String(5))
    quiet_hours_end: Mapped[str | None] = mapped_column(String(5))
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="America/Toronto"
    )


class ShopNotificationPolicy(NotificationBase):
    __tablename__ = "shop_notification_policy"
    __table_args__ = (
        ForeignKeyConstraint(
            ["shop_id"],
            ["shops.id"],
            name="fk_shop_notification_policy_shop",
            ondelete="RESTRICT",
        ),
    )

    shop_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    critical_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )


class NotificationAudit(NotificationBase):
    __tablename__ = "notification_audit"
    __table_args__ = (
        ForeignKeyConstraint(
            ["shop_id"], ["shops.id"], name="fk_notification_audit_shop", ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(
            ["shop_id", "event_id"],
            ["notification_event.shop_id", "notification_event.id"],
            name="fk_notification_audit_shop_event",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            f"action IN ({_values(AUDIT_ACTIONS)})", name="ck_notification_audit_action"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    shop_id: Mapped[str] = mapped_column(String(36), nullable=False)
    actor_clerk_user_id: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str | None] = mapped_column(String(64))
    prior_state: Mapped[str | None] = mapped_column(String(64))
    new_state: Mapped[str | None] = mapped_column(String(64))
    event_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class NotificationSourceObservation(NotificationBase):
    __tablename__ = "notification_source_observation"
    __table_args__ = (
        UniqueConstraint("shop_id", "id", name="uq_notification_source_observation_shop_id"),
        UniqueConstraint(
            "shop_id",
            "source_kind",
            "source_key",
            "observation_token",
            name="uq_notification_source_observation_identity",
        ),
        ForeignKeyConstraint(
            ["shop_id"],
            ["shops.id"],
            name="fk_notification_source_observation_shop",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["shop_id", "event_id"],
            ["notification_event.shop_id", "notification_event.id"],
            name="fk_notification_source_observation_shop_event",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        ForeignKeyConstraint(
            ["shop_id", "event_id", "occurrence_seq"],
            [
                "notification_occurrence.shop_id",
                "notification_occurrence.event_id",
                "notification_occurrence.occurrence_seq",
            ],
            name="fk_notification_source_observation_shop_occurrence",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint(
            "length(observation_token) >= 1",
            name="ck_notification_source_observation_token",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    shop_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False)
    observation_token: Mapped[str] = mapped_column(String(255), nullable=False)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    occurrence_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class NotificationOccurrenceTransition(NotificationBase):
    __tablename__ = "notification_occurrence_transition"
    __table_args__ = (
        UniqueConstraint(
            "shop_id", "id", name="uq_notification_occurrence_transition_shop_id"
        ),
        UniqueConstraint(
            "shop_id",
            "event_id",
            "occurrence_seq",
            "transition_seq",
            name="uq_notification_occurrence_transition_identity",
        ),
        ForeignKeyConstraint(
            ["shop_id"],
            ["shops.id"],
            name="fk_notification_occurrence_transition_shop",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["shop_id", "event_id", "occurrence_seq"],
            [
                "notification_occurrence.shop_id",
                "notification_occurrence.event_id",
                "notification_occurrence.occurrence_seq",
            ],
            name="fk_notification_occurrence_transition_shop_occurrence",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "transition_seq >= 1", name="ck_notification_occurrence_transition_seq"
        ),
        CheckConstraint(
            f"to_status IN ({_values(TRANSITION_STATUSES)})",
            name="ck_notification_occurrence_transition_to_status",
        ),
        CheckConstraint(
            "("
            "transition_seq = 1 AND from_status IS NULL AND to_status = 'pending'"
            ") OR ("
            "transition_seq > 1 AND from_status = 'pending' AND "
            f"to_status IN ('delivered','failed','cancelled')"
            ")",
            name="ck_notification_occurrence_transition_pair",
        ),
        Index(
            "uq_notification_occurrence_initial_transition",
            "shop_id",
            "event_id",
            "occurrence_seq",
            unique=True,
            sqlite_where=text("transition_seq = 1"),
            postgresql_where=text("transition_seq = 1"),
        ),
        Index(
            "uq_notification_occurrence_terminal_transition",
            "shop_id",
            "event_id",
            "occurrence_seq",
            unique=True,
            sqlite_where=text("to_status IN ('delivered','failed','cancelled')"),
            postgresql_where=text("to_status IN ('delivered','failed','cancelled')"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    shop_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    occurrence_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    transition_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(24))
    to_status: Mapped[str] = mapped_column(String(24), nullable=False)
    cause: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class NotificationDeliveryAttempt(NotificationBase):
    __tablename__ = "notification_delivery_attempt"
    __table_args__ = (
        UniqueConstraint("shop_id", "id", name="uq_notification_delivery_attempt_shop_id"),
        UniqueConstraint(
            "shop_id",
            "delivery_id",
            "attempt_number",
            "phase",
            name="uq_notification_delivery_attempt_identity",
        ),
        ForeignKeyConstraint(
            ["shop_id"],
            ["shops.id"],
            name="fk_notification_delivery_attempt_shop",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["shop_id", "delivery_id"],
            ["notification_delivery.shop_id", "notification_delivery.id"],
            name="fk_notification_delivery_attempt_shop_delivery",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "attempt_number >= 1", name="ck_notification_delivery_attempt_number"
        ),
        CheckConstraint(
            f"phase IN ({_values(ATTEMPT_PHASES)})",
            name="ck_notification_delivery_attempt_phase",
        ),
        CheckConstraint(
            "phase <> 'started' OR (outcome IS NULL AND provider_status_code IS NULL AND error IS NULL)",
            name="ck_notification_delivery_attempt_started",
        ),
        CheckConstraint(
            f"phase <> 'outcome' OR outcome IN ({_values(ATTEMPT_OUTCOMES)})",
            name="ck_notification_delivery_attempt_outcome",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    shop_id: Mapped[str] = mapped_column(String(36), nullable=False)
    delivery_id: Mapped[str] = mapped_column(String(36), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    phase: Mapped[str] = mapped_column(String(16), nullable=False)
    outcome: Mapped[str | None] = mapped_column(String(24))
    provider_status_code: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class NotificationRecoveryPark(NotificationBase):
    __tablename__ = "notification_recovery_park"
    __table_args__ = (
        UniqueConstraint("shop_id", "id", name="uq_notification_recovery_park_shop_id"),
        UniqueConstraint(
            "shop_id",
            "source_kind",
            "source_key",
            name="uq_notification_recovery_park_identity",
        ),
        ForeignKeyConstraint(
            ["shop_id"],
            ["shops.id"],
            name="fk_notification_recovery_park_shop",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "fail_count >= 0", name="ck_notification_recovery_park_fail_count"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    shop_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False)
    fail_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    next_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


NOTIFICATION_TABLE_NAMES = (
    "notification_event",
    "notification_occurrence",
    "notification_delivery",
    "notification_source",
    "push_subscription",
    "notification_preference",
    "shop_notification_policy",
    "notification_audit",
    "notification_source_observation",
    "notification_occurrence_transition",
    "notification_delivery_attempt",
    "notification_recovery_park",
)

