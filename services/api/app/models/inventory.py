from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, ShopScopedMixin, TimestampMixin, utcnow


class InventoryItem(Base, ShopScopedMixin, TimestampMixin):
    __tablename__ = "inventory_item"
    __table_args__ = (UniqueConstraint("shop_id", "sku", name="uq_inventory_shop_sku"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    set_name: Mapped[str | None] = mapped_column(String(100))
    sequence_number: Mapped[str | None] = mapped_column(String(50))
    cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    old_price: Mapped[float | None] = mapped_column(Float)
    card_type: Mapped[str | None] = mapped_column(String(50))
    variant: Mapped[str | None] = mapped_column(String(50))
    condition: Mapped[str | None] = mapped_column(String(50))
    stock: Mapped[int] = mapped_column(Integer, default=0)
    last_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    date_added: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    needs_update: Mapped[bool] = mapped_column(Boolean, default=False)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    image_url: Mapped[str | None] = mapped_column(String(512))
    image_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    sync_status: Mapped[str] = mapped_column(String(50), default="paused")
    custom_image_url: Mapped[str | None] = mapped_column(String(512))
    shop_listing_price: Mapped[float | None] = mapped_column(Float)
    sticker_price: Mapped[float | None] = mapped_column(Float)
    paused_stock: Mapped[int] = mapped_column(Integer, default=0)
    game: Mapped[str] = mapped_column(String(50), default="Pokemon")


class StagingItem(Base, ShopScopedMixin, TimestampMixin):
    __tablename__ = "staging_item"
    __table_args__ = (UniqueConstraint("shop_id", "sku", name="uq_staging_shop_sku"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str | None] = mapped_column(String(100))
    set_name: Mapped[str | None] = mapped_column(String(100))
    sequence_number: Mapped[str | None] = mapped_column(String(50))
    market_price: Mapped[float] = mapped_column(Float, default=0.0)
    cost_basis: Mapped[float] = mapped_column(Float, default=0.0)
    suggested_price: Mapped[float] = mapped_column(Float, default=0.0)
    card_type: Mapped[str | None] = mapped_column(String(50))
    variant: Mapped[str | None] = mapped_column(String(50))
    condition: Mapped[str | None] = mapped_column(String(50))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    image_path: Mapped[str | None] = mapped_column(String(512))
    barcode_path: Mapped[str | None] = mapped_column(String(512))
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    ocr_metadata: Mapped[str] = mapped_column(Text, default="{}")
    image_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    game: Mapped[str] = mapped_column(String(50), default="Pokemon")


class PurchaseRecord(Base, ShopScopedMixin, TimestampMixin):
    __tablename__ = "purchase_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    cost_per_unit: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ShowPriceCapture(Base, ShopScopedMixin, TimestampMixin):
    __tablename__ = "show_price_capture"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    total_value: Mapped[float] = mapped_column(Float, default=0.0)


class ShowPriceCaptureItem(Base, ShopScopedMixin, TimestampMixin):
    __tablename__ = "show_price_capture_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    capture_id: Mapped[int] = mapped_column(Integer, ForeignKey("show_price_capture.id"), nullable=False)
    sku: Mapped[str] = mapped_column(String(50), nullable=False)
    sticker_price: Mapped[float] = mapped_column(Float, nullable=False)
