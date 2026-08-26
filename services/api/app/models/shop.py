from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, new_uuid


class Shop(Base, TimestampMixin):
    __tablename__ = "shops"
    __table_args__ = (UniqueConstraint("slug", name="uq_shops_slug"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    clerk_org_id: Mapped[str | None] = mapped_column(String(120), nullable=True)


class ShopMember(Base, TimestampMixin):
    __tablename__ = "shop_members"
    __table_args__ = (
        UniqueConstraint("shop_id", "clerk_user_id", name="uq_shop_members_shop_user"),
        CheckConstraint("role IN ('owner', 'staff')", name="ck_shop_members_role"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    shop_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("shops.id"), nullable=False, index=True
    )
    clerk_user_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), default="owner")
