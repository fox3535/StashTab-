"""Frozen inventory-truth schema (STASHTAB-INVENTORY-TRUTH-001 v1.1.0).

This module defines the truth tables on a dedicated `TruthBase` that is
NOT part of the application metadata, so `init_db()` / `create_all` can
never create them. Importing this module runs no DDL. Only
`app.inventory_truth.migrator` applies its DDL (MIGRATION.md §4).

Locked wording (DESIGN.md §3, as extended by AMENDMENT-1.1.0):
- created_at only; no TimestampMixin / onupdate.
- money on lots: Numeric(12,2).
- UNIQUE (shop_id, id) on lot and event; UNIQUE (shop_id, generation) on cutover.
- composite FKs ON DELETE RESTRICT.
- lot FK is REQUIRED for receive/loss only (DESIGN.md §3); outbound sell /
  return events are LOTLESS (lot_id NULL) — never linked to invented lots.
- Slice-02 additions: inventory_channel_observation, refund_record,
  return_record, inventory_exception — migrator-only, append-only where
  specified; observation ledger arbitrates same-channel retries.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.models.base import utcnow


class TruthBase(DeclarativeBase):
    pass


class AcquisitionLot(TruthBase):
    __tablename__ = "acquisition_lot"
    __table_args__ = (
        UniqueConstraint("shop_id", "id", name="uq_acquisition_lot_shop_id"),
        UniqueConstraint("shop_id", "idempotency_key", name="uq_lot_shop_idemkey"),
        CheckConstraint("quantity_acquired > 0", name="ck_lot_qty_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    inventory_item_id: Mapped[int | None] = mapped_column(Integer)
    purchase_record_id: Mapped[int | None] = mapped_column(Integer)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity_acquired: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    label: Mapped[str | None] = mapped_column(String(40))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class InventoryEvent(TruthBase):
    __tablename__ = "inventory_event"
    __table_args__ = (
        UniqueConstraint("shop_id", "id", name="uq_inventory_event_shop_id"),
        UniqueConstraint("shop_id", "idempotency_key", name="uq_event_shop_idemkey"),
        # receive-first slice inserts only receive / loss / reverse-of-those.
        CheckConstraint(
            "event_type IN ('receive','sell','loss','return','damage','adjust',"
            "'reverse','reserve','release','move','channel_commit','quarantine')",
            name="ck_event_type",
        ),
        CheckConstraint(
            "(event_type NOT IN ('reserve','release','move','channel_commit','quarantine'))"
            " OR (quantity_delta = 0)",
            name="ck_overlay_zero_delta",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # Lot FK is required for receive/loss only (DESIGN.md §3); outbound
    # sell/return events are lotless (NULL) — never invented stock.
    lot_id: Mapped[int | None] = mapped_column(Integer)
    inventory_item_id: Mapped[int | None] = mapped_column(Integer)
    sale_id: Mapped[int | None] = mapped_column(Integer)  # always null receive-first
    reverses_event_id: Mapped[int | None] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    overlay_quantity: Mapped[int | None] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(String(60))
    actor_clerk_user_id: Mapped[str | None] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class InventoryTruthCutover(TruthBase):
    __tablename__ = "inventory_truth_cutover"
    __table_args__ = (
        UniqueConstraint("shop_id", "generation", name="uq_cutover_shop_generation"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    generation: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="locking")
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


# --- Slice-02 outbound structures (AMENDMENT-1.1.0) ------------------------


class InventoryChannelObservation(TruthBase):
    """Per-line observation ledger (DIRECTIVE-SLICE-02 §3).

    One row per physical outbound observation. UNIQUE (shop_id, channel,
    channel_ref) is the transactional arbitration: same-channel retry or
    overlapping schedulers lose on unique violation and write nothing.
    Cross-channel duplicates have no shared identity by design and are
    surfaced later by reconciliation — never merged.
    """

    __tablename__ = "inventory_channel_observation"
    __table_args__ = (
        UniqueConstraint(
            "shop_id",
            "channel",
            "channel_ref",
            name="uq_obs_shop_channel_ref",
        ),
        CheckConstraint("channel IN ('pos','shopify')", name="ck_obs_channel"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    channel_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    sale_id: Mapped[int | None] = mapped_column(Integer)
    sku: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    quantity_requested: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_removed: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class RefundRecord(TruthBase):
    """Append-only refund record; references its originating outbound
    event. No inventory effect by itself (DIRECTIVE-SLICE-02 §5)."""

    __tablename__ = "refund_record"
    __table_args__ = (
        UniqueConstraint("shop_id", "id", name="uq_refund_record_shop_id"),
        CheckConstraint("amount >= 0", name="ck_refund_amount_nonneg"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    outbound_event_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    actor_clerk_user_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class ReturnRecord(TruthBase):
    """Append-only confirmed physical return of whole resalable units.
    Its insert is paired with exactly one positive return event."""

    __tablename__ = "return_record"
    __table_args__ = (
        UniqueConstraint("shop_id", "id", name="uq_return_record_shop_id"),
        # Arbitration for concurrent confirmations of the same physical
        # return. Partial: only anchored records (a concrete refund or
        # outbound reference) participate, so unanchored distinct returns
        # never collide; NULLs stay distinct on both backends.
        Index(
            "uq_return_record_confirmation_facts",
            "shop_id",
            "refund_record_id",
            "outbound_event_id",
            "sku",
            "quantity_confirmed",
            "outcome",
            unique=True,
            sqlite_where=text(
                "refund_record_id IS NOT NULL OR outbound_event_id IS NOT NULL"
            ),
            postgresql_where=text(
                "refund_record_id IS NOT NULL OR outbound_event_id IS NOT NULL"
            ),
        ),
        CheckConstraint("quantity_confirmed > 0", name="ck_return_qty_positive"),
        CheckConstraint(
            "outcome IN ('resalable','damaged')", name="ck_return_outcome"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    refund_record_id: Mapped[int | None] = mapped_column(Integer, index=True)
    outbound_event_id: Mapped[int | None] = mapped_column(Integer, index=True)
    sku: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    quantity_confirmed: Mapped[int] = mapped_column(Integer, nullable=False)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    condition_note: Mapped[str | None] = mapped_column(Text)
    actor_clerk_user_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class InventoryException(TruthBase):
    """Critical exception register (oversale shortage, duplicate
    suspicion). Reuse-not-stack per binding interpretation: same-key
    retries reuse the existing open exception."""

    __tablename__ = "inventory_exception"
    __table_args__ = (
        UniqueConstraint(
            "shop_id",
            "kind",
            "exception_ref",
            name="uq_exception_shop_kind_ref",
        ),
        CheckConstraint(
            "kind IN ('over_sale_short','duplicate_suspicion')",
            name="ck_exception_kind",
        ),
        CheckConstraint("status IN ('open','resolved')", name="ck_exception_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    exception_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(50), index=True)
    quantity_unsatisfied: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[str | None] = mapped_column(Text)  # JSON payload
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


TRUTH_TABLE_NAMES = (
    "acquisition_lot",
    "inventory_event",
    "inventory_truth_cutover",
    "inventory_channel_observation",
    "refund_record",
    "return_record",
    "inventory_exception",
)


def _shadow_parent(name: str):
    """Minimal Core-only definition of a live parent table so composite FKs
    resolve inside THIS metadata at DDL time. Never created here: the real
    tables are owned by the application schema/migrator."""
    return Table(
        name,
        TruthBase.metadata,
        Column("id", Integer, primary_key=True),
        Column("shop_id", String(36), nullable=False),
        extend_existing=True,
    )


_COMPOSITE_FKS = (
    ("acquisition_lot", ["shop_id", "inventory_item_id"], "inventory_item.shop_id", "inventory_item.id", "fk_lot_shop_item"),
    ("acquisition_lot", ["shop_id", "purchase_record_id"], "purchase_record.shop_id", "purchase_record.id", "fk_lot_shop_purchase"),
    ("inventory_event", ["shop_id", "lot_id"], "acquisition_lot.shop_id", "acquisition_lot.id", "fk_event_shop_lot"),
    ("inventory_event", ["shop_id", "inventory_item_id"], "inventory_item.shop_id", "inventory_item.id", "fk_event_shop_item"),
    ("inventory_event", ["shop_id", "sale_id"], "sale.shop_id", "sale.id", "fk_event_shop_sale"),
    ("inventory_event", ["shop_id", "reverses_event_id"], "inventory_event.shop_id", "inventory_event.id", "fk_event_shop_reverses"),
    # Slice-02 (AMENDMENT-1.1.0): all parent references composite + RESTRICT.
    ("inventory_channel_observation", ["shop_id", "sale_id"], "sale.shop_id", "sale.id", "fk_obs_shop_sale"),
    ("refund_record", ["shop_id", "outbound_event_id"], "inventory_event.shop_id", "inventory_event.id", "fk_refund_shop_event"),
    ("return_record", ["shop_id", "refund_record_id"], "refund_record.shop_id", "refund_record.id", "fk_return_shop_refund"),
    ("return_record", ["shop_id", "outbound_event_id"], "inventory_event.shop_id", "inventory_event.id", "fk_return_shop_event"),
)

_SLICE02_FK_TABLES = {
    "inventory_channel_observation": InventoryChannelObservation.__table__,
    "refund_record": RefundRecord.__table__,
    "return_record": ReturnRecord.__table__,
}


def register_composite_fks() -> None:
    """Attach composite FKs. Called only by the migrator after the additive
    unique `(shop_id, id)` indexes exist on the live tables.

    Idempotent within a process: re-calling never appends duplicate
    constraints (which would emit invalid duplicate DDL on PostgreSQL).
    """
    from sqlalchemy import ForeignKeyConstraint

    _shadow_parent("inventory_item")
    _shadow_parent("purchase_record")
    _shadow_parent("sale")

    tables = {
        "acquisition_lot": AcquisitionLot.__table__,
        "inventory_event": InventoryEvent.__table__,
        **_SLICE02_FK_TABLES,
    }
    for table_name, cols, ref_col_a, ref_col_b, name in _COMPOSITE_FKS:
        existing_names = {c.name for c in tables[table_name].constraints}
        if name not in existing_names:
            tables[table_name].append_constraint(
                ForeignKeyConstraint(
                    cols,
                    [ref_col_a, ref_col_b],
                    name=name,
                    ondelete="RESTRICT",
                )
            )
