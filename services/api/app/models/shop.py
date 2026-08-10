from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, new_uuid, utcnow


class Shop(Base, TimestampMixin):
    __tablename__ = "shops"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    clerk_org_id: Mapped[str | None] = mapped_column(String(120), nullable=True)


class ShopMember(Base, TimestampMixin):
    __tablename__ = "shop_members"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    shop_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    clerk_user_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), default="owner")  # owner | staff
