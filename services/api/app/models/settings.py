from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, ShopScopedMixin, TimestampMixin


class SystemSettings(Base, ShopScopedMixin, TimestampMixin):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    price_fluctuation_threshold: Mapped[float] = mapped_column(Float, default=0.10)
    resticker_threshold: Mapped[float] = mapped_column(Float, default=2.00)
    rounding_strategy: Mapped[str] = mapped_column(String(50), default="Keep Raw TCG Decimal Payouts")
    paperweight_days: Mapped[int] = mapped_column(Integer, default=60)
    buy_percentage: Mapped[float] = mapped_column(Float, default=0.70)
    trade_percentage: Mapped[float] = mapped_column(Float, default=0.80)
    ocr_x: Mapped[int] = mapped_column(Integer, default=0)
    ocr_y: Mapped[int] = mapped_column(Integer, default=0)
    ocr_width: Mapped[int] = mapped_column(Integer, default=0)
    ocr_height: Mapped[int] = mapped_column(Integer, default=0)
    sync_folder: Mapped[str | None] = mapped_column(String(255))
    sim_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    markup_type: Mapped[str] = mapped_column(String(50), default="Percentage (%)")
    markup_value: Mapped[float] = mapped_column(Float, default=0.0)
    rounding_rule: Mapped[str] = mapped_column(String(50), default="Exact/None")
    pokemon_icon_url: Mapped[str] = mapped_column(String(512), default="")
    one_piece_icon_url: Mapped[str] = mapped_column(String(512), default="")
    auto_sync_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    omit_graded_from_recon: Mapped[bool] = mapped_column(Boolean, default=False)
    graded_wizard_sales_count: Mapped[int] = mapped_column(Integer, default=5)
    graded_wizard_omit_diff: Mapped[float] = mapped_column(Float, default=20.0)
    gmail_monitor_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    gmail_address: Mapped[str] = mapped_column(String(100), default="")
    gmail_app_password: Mapped[str] = mapped_column(String(100), default="")
    gmail_folder: Mapped[str] = mapped_column(String(100), default="INBOX")


class StoreSettings(Base, ShopScopedMixin, TimestampMixin):
    __tablename__ = "store_settings"
    __table_args__ = ()

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[str | None] = mapped_column(String(255))


class ShippingRule(Base, ShopScopedMixin, TimestampMixin):
    __tablename__ = "shipping_rule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    min_price: Mapped[float] = mapped_column(Float, nullable=False)
    max_price: Mapped[float] = mapped_column(Float, nullable=False)
    additional_cost: Mapped[float] = mapped_column(Float, nullable=False)
    card_type: Mapped[str] = mapped_column(String(50), default="Card")


class ShopifyCredentials(Base, ShopScopedMixin, TimestampMixin):
    __tablename__ = "shopify_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_url: Mapped[str] = mapped_column(String(255), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(String(512), nullable=False)
