from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.auth.identity import (
    dev_identity_bypass_allowed,
    load_shop,
    log_dev_identity_bypass_state,
    require_membership,
    shop_selection_hint,
    verified_user_id,
)
from app.config import settings
from app.database import get_db
from app.models import ShopMember


@dataclass
class ShopContext:
    shop_id: str
    clerk_user_id: str | None = None
    role: str | None = None
    identity_bypass: bool = False


async def get_authenticated_user(
    x_clerk_user_id: str | None = Header(default=None, alias="X-Clerk-User-Id"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> str:
    return verified_user_id(authorization, x_clerk_user_id)


async def get_shop_context(
    x_shop_id: str | None = Header(default=None, alias="X-Shop-Id"),
    x_clerk_user_id: str | None = Header(default=None, alias="X-Clerk-User-Id"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> ShopContext:
    """Shop context from verified user + membership. X-Shop-Id is an untrusted hint."""
    bypass = dev_identity_bypass_allowed()
    if bypass:
        log_dev_identity_bypass_state()

    user_id = verified_user_id(
        authorization,
        x_clerk_user_id,
        allow_missing=bypass,
    )
    hint = shop_selection_hint(x_shop_id)
    if not hint:
        raise HTTPException(
            status_code=401,
            detail="Shop selection required",
        )

    shop = load_shop(db, hint)

    if bypass:
        role = None
        if user_id:
            members = (
                db.query(ShopMember)
                .filter(
                    ShopMember.shop_id == shop.id,
                    ShopMember.clerk_user_id == user_id,
                )
                .all()
            )
            if len(members) > 1:
                raise HTTPException(status_code=403, detail="Conflicting shop membership")
            role = members[0].role if members else None
        return ShopContext(
            shop_id=shop.id,
            clerk_user_id=user_id,
            role=role,
            identity_bypass=True,
        )

    if not user_id:
        raise HTTPException(status_code=401, detail="Authenticated user required")

    member = require_membership(db, shop.id, user_id)
    return ShopContext(
        shop_id=shop.id,
        clerk_user_id=user_id,
        role=member.role,
        identity_bypass=bypass,
    )


async def get_notification_context(
    authorization: str | None = Header(default=None, alias="Authorization"),
    ctx: ShopContext = Depends(get_shop_context),
) -> ShopContext:
    """Require a real user for notification preference, subscription, and event routes."""
    if settings.clerk_jwt_issuer:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Bearer token required")
        if not ctx.clerk_user_id:
            raise HTTPException(status_code=401, detail="Invalid session")
    elif not ctx.clerk_user_id:
        raise HTTPException(status_code=401, detail="Authenticated user required")
    return ctx
