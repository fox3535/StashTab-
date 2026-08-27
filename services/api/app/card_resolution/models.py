"""Migrator-owned card-resolution tables. Isolated from application Base."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.models.base import new_uuid, utcnow

CARD_RESOLUTION_TABLES = (
    "card_resolution_catalog",
    "card_resolution_intake",
    "card_resolution_evidence",
    "card_resolution_candidate",
    "card_resolution_review",
    "card_resolution_audit",
)


class CardResolutionBase(DeclarativeBase):
    pass


Table(
    "shops",
    CardResolutionBase.metadata,
    Column("id", String(36), primary_key=True),
)


class CardResolutionCatalog(CardResolutionBase):
    __tablename__ = "card_resolution_catalog"
    __table_args__ = (
        ForeignKeyConstraint(["shop_id"], ["shops.id"], name="fk_cr_catalog_shop_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    shop_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    game: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    set_name: Mapped[str | None] = mapped_column(String(120))
    set_code: Mapped[str | None] = mapped_column(String(40))
    collector_number: Mapped[str | None] = mapped_column(String(40))
    language: Mapped[str | None] = mapped_column(String(32))
    printing: Mapped[str | None] = mapped_column(String(64))
    justtcg_id: Mapped[str | None] = mapped_column(String(120))
    tcgplayer_id: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class CardResolutionIntake(CardResolutionBase):
    __tablename__ = "card_resolution_intake"
    __table_args__ = (
        UniqueConstraint("shop_id", "intake_id", name="uq_cr_intake_shop_intake"),
        UniqueConstraint("shop_id", "id", name="uq_cr_intake_shop_pk"),
        ForeignKeyConstraint(["shop_id"], ["shops.id"], name="fk_cr_intake_shop_id"),
        CheckConstraint(
            "result IN ('accepted', 'abstained', 'rejected')",
            name="ck_cr_intake_result",
        ),
        CheckConstraint(
            "state IN ('accepted', 'pending_human_review', 'rejected')",
            name="ck_cr_intake_state",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    shop_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    intake_id: Mapped[str] = mapped_column(String(120), nullable=False)
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_codes: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    identity_confidence_hundredths: Mapped[int | None] = mapped_column(Integer)
    price_confidence: Mapped[int | None] = mapped_column(Integer)
    confidence_components: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    ruleset_version: Mapped[str] = mapped_column(String(64), nullable=False)
    contract_version: Mapped[str] = mapped_column(String(16), nullable=False)
    decision_source: Mapped[str | None] = mapped_column(String(32))
    winner_identity_key: Mapped[str | None] = mapped_column(String(400))
    justtcg_invoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    actor_clerk_user_id: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class CardResolutionEvidence(CardResolutionBase):
    __tablename__ = "card_resolution_evidence"
    __table_args__ = (
        ForeignKeyConstraint(["shop_id"], ["shops.id"], name="fk_cr_evidence_shop_id"),
        ForeignKeyConstraint(
            ["intake_pk", "shop_id"],
            ["card_resolution_intake.id", "card_resolution_intake.shop_id"],
            name="fk_cr_evidence_intake",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    shop_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    intake_pk: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    intake_id: Mapped[str] = mapped_column(String(120), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class CardResolutionCandidate(CardResolutionBase):
    __tablename__ = "card_resolution_candidate"
    __table_args__ = (
        ForeignKeyConstraint(["shop_id"], ["shops.id"], name="fk_cr_candidate_shop_id"),
        ForeignKeyConstraint(
            ["intake_pk", "shop_id"],
            ["card_resolution_intake.id", "card_resolution_intake.shop_id"],
            name="fk_cr_candidate_intake",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    shop_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    intake_pk: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    identity_key: Mapped[str] = mapped_column(String(400), nullable=False)
    score_hundredths: Mapped[int] = mapped_column(Integer, nullable=False)
    components_json: Mapped[str] = mapped_column(Text, nullable=False)
    eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    retrieved_via_fuzzy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


class CardResolutionReview(CardResolutionBase):
    __tablename__ = "card_resolution_review"
    __table_args__ = (
        UniqueConstraint("shop_id", "intake_pk", name="uq_cr_review_shop_intake"),
        UniqueConstraint("shop_id", "id", name="uq_cr_review_shop_pk"),
        ForeignKeyConstraint(["shop_id"], ["shops.id"], name="fk_cr_review_shop_id"),
        ForeignKeyConstraint(
            ["intake_pk", "shop_id"],
            ["card_resolution_intake.id", "card_resolution_intake.shop_id"],
            name="fk_cr_review_intake",
        ),
        CheckConstraint(
            "status IN ('open', 'decided', 'deferred')",
            name="ck_cr_review_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    shop_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    intake_pk: Mapped[str] = mapped_column(String(36), nullable=False)
    intake_id: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    reason_codes: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    decision: Mapped[str | None] = mapped_column(String(32))
    decided_by: Mapped[str | None] = mapped_column(String(120))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class CardResolutionAudit(CardResolutionBase):
    __tablename__ = "card_resolution_audit"
    __table_args__ = (
        ForeignKeyConstraint(["shop_id"], ["shops.id"], name="fk_cr_audit_shop_id"),
        ForeignKeyConstraint(
            ["intake_pk", "shop_id"],
            ["card_resolution_intake.id", "card_resolution_intake.shop_id"],
            name="fk_cr_audit_intake",
        ),
        ForeignKeyConstraint(
            ["review_id", "shop_id"],
            ["card_resolution_review.id", "card_resolution_review.shop_id"],
            name="fk_cr_audit_review",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    shop_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    intake_pk: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    review_id: Mapped[str | None] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_clerk_user_id: Mapped[str | None] = mapped_column(String(120))
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
