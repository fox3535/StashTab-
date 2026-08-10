from dataclasses import dataclass
import os

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.auth.clerk import resolve_clerk_user_id
from app.database import get_db
from app.models import Shop, ShopMember


@dataclass
class ShopContext:
    shop_id: str
    clerk_user_id: str | None = None


async def get_shop_context(
    x_shop_id: str | None = Header(default=None, alias="X-Shop-Id"),
    x_clerk_user_id: str | None = Header(default=None, alias="X-Clerk-User-Id"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> ShopContext:
    """
    Resolve shop from verified Clerk JWT, ShopMember, dev X-Shop-Id, or env fallback.
    """
    clerk_user_id = resolve_clerk_user_id(authorization, x_clerk_user_id)
    shop_id: str | None = None

    if clerk_user_id:
        member = (
            db.query(ShopMember)
            .filter(ShopMember.clerk_user_id == clerk_user_id)
            .first()
        )
        if member:
            shop_id = member.shop_id
        elif x_shop_id:
            shop_id = x_shop_id
        else:
            raise HTTPException(
                status_code=403,
                detail="No shop membership found for Clerk user",
            )
    elif x_shop_id:
        shop_id = x_shop_id
    else:
        dev_shop = os.environ.get("DEV_SHOP_ID") or os.environ.get("NEXT_PUBLIC_DEV_SHOP_ID")
        if dev_shop:
            shop_id = dev_shop

    if not shop_id:
        raise HTTPException(
            status_code=401,
            detail="Missing shop context (Authorization, X-Shop-Id, or Clerk auth)",
        )

    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    return ShopContext(shop_id=shop_id, clerk_user_id=clerk_user_id)
