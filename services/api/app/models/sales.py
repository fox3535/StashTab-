from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, ShopScopedMixin, TimestampMixin, utcnow


class Sale(Base, ShopScopedMixin, TimestampMixin):
    __tablename__ = "sale"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_name: Mapped[str | None] = mapped_column(String(100))
    sku: Mapped[str | None] = mapped_column(String(50), index=True)
    sold_price: Mapped[float | None] = mapped_column(Float)
    profit: Mapped[float | None] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    transaction_type: Mapped[str | None] = mapped_column(String(20))
    trade_in_value: Mapped[float] = mapped_column(Float, default=0.0)
    processing_fees: Mapped[float] = mapped_column(Float, default=0.0)
    trade_credit_deduction: Mapped[float] = mapped_column(Float, default=0.0)
    net_revenue: Mapped[float] = mapped_column(Float, default=0.0)
    game: Mapped[str] = mapped_column(String(50), default="Pokemon")
    show_session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    is_reconciled: Mapped[bool] = mapped_column(Boolean, default=False)


class PendingTrade(Base, ShopScopedMixin, TimestampMixin):
    __tablename__ = "pending_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    show_id: Mapped[str | None] = mapped_column(String(100))
    total_market_value: Mapped[float] = mapped_column(Float, default=0.0)
    total_cash_paid: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(50), default="pending")


class ShowSession(Base, ShopScopedMixin, TimestampMixin):
    __tablename__ = "show_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="active")  # active | ended
