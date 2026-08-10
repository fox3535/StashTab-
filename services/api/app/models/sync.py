from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, ShopScopedMixin, TimestampMixin, utcnow


class SyncOutbox(Base, ShopScopedMixin, TimestampMixin):
    __tablename__ = "sync_outbox"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    sku: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    quantity_change: Mapped[int] = mapped_column(Integer, nullable=False)
    new_price: Mapped[float | None] = mapped_column(Float)
    sync_status: Mapped[str] = mapped_column(String(50), default="pending")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OnlinePullQueue(Base, ShopScopedMixin, TimestampMixin):
    __tablename__ = "online_pull_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    order_id: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), default="pending_pull")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PrintQueue(Base, ShopScopedMixin, TimestampMixin):
    __tablename__ = "print_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(50), nullable=False)
    item_name: Mapped[str | None] = mapped_column(String(100))
    is_printed: Mapped[bool] = mapped_column(Boolean, default=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
