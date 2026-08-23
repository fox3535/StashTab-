"""Frozen inventory-truth schema (STASHTAB-INVENTORY-TRUTH-001 v1.0.0).

This module defines the truth tables on a dedicated `TruthBase` that is
NOT part of the application metadata, so `init_db()` / `create_all` can
never create them. Importing this module runs no DDL. Only
`app.inventory_truth.migrator` applies its DDL (MIGRATION.md §4).

Locked wording (DESIGN.md §3):
- created_at only; no TimestampMixin / onupdate.
- money on lots: Numeric(12,2).
- UNIQUE (shop_id, id) on lot and event; UNIQUE (shop_id, generation) on cutover.
- composite FKs ON DELETE RESTRICT; sale_id always null in receive-first.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
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
    lot_id: Mapped[int] = mapped_column(Integer, nullable=False)
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


TRUTH_TABLE_NAMES = (
    "acquisition_lot",
    "inventory_event",
    "inventory_truth_cutover",
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
)


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
