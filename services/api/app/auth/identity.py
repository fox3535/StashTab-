"""Fail-closed shop identity policy (single enforcement layer)."""

from __future__ import annotations

import logging
import os

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.auth.clerk import ClerkAuthError, decode_bearer_user_id
from app.config import settings
from app.models import Shop, ShopMember

logger = logging.getLogger("stashtab.identity")
_bypass_logged = False


def parsed_app_env() -> str | None:
    return settings.parsed_app_env


def dev_identity_bypass_allowed() -> bool:
    return settings.dev_identity_bypass_allowed


def log_dev_identity_bypass_state() -> None:
    global _bypass_logged
    env = parsed_app_env()
    if settings.dev_identity_bypass_allowed:
        if not _bypass_logged:
            logger.warning(
                "STASHTAB DEV IDENTITY BYPASS ENABLED (APP_ENV=%s). "
                "Caller shop/user headers may be used. Never enable in staging/production.",
                env,
            )
            _bypass_logged = True
        return
    if settings.stashtab_allow_dev_identity:
        logger.warning(
            "STASHTAB_ALLOW_DEV_IDENTITY is set but bypass is disabled "
            "(APP_ENV=%r must be local or test; missing/invalid/staging/production refuse bypass).",
            settings.app_env,
        )


def shop_selection_hint(x_shop_id: str | None) -> str | None:
    if x_shop_id and x_shop_id.strip():
        return x_shop_id.strip()
    if not settings.dev_identity_bypass_allowed:
        return None
    return (os.environ.get("DEV_SHOP_ID") or os.environ.get("NEXT_PUBLIC_DEV_SHOP_ID") or "").strip() or None


def verified_user_id(
    authorization: str | None,
    x_clerk_user_id: str | None,
    *,
    allow_missing: bool = False,
) -> str | None:
    """User from signed Bearer token. Header user only when bypass is allowed."""
    try:
        jwt_user = decode_bearer_user_id(authorization)
    except ClerkAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    if jwt_user:
        return jwt_user

    if settings.dev_identity_bypass_allowed and x_clerk_user_id and x_clerk_user_id.strip():
        log_dev_identity_bypass_state()
        return x_clerk_user_id.strip()

    if allow_missing:
        return None
    raise HTTPException(status_code=401, detail="Authenticated user required")


ALLOWED_MEMBER_ROLES = frozenset({"owner", "staff"})
_MEMBERSHIP_CORRUPT = "Conflicting shop membership"


def normalized_shop_sort_name(name: str) -> str:
    return " ".join((name or "").casefold().split())


def compose_caller_membership_shops(
    members: list[ShopMember],
    shops_by_id: dict[str, Shop],
) -> list[tuple[str, str, str]]:
    """Build authorized shop rows for the verified caller. Fail closed on corruption."""
    seen: set[str] = set()
    rows: list[tuple[str, str, str]] = []
    for member in members:
        if member.shop_id in seen:
            raise HTTPException(status_code=403, detail=_MEMBERSHIP_CORRUPT)
        seen.add(member.shop_id)
        shop = shops_by_id.get(member.shop_id)
        if shop is None:
            raise HTTPException(status_code=403, detail=_MEMBERSHIP_CORRUPT)
        role = (member.role or "").strip()
        if role not in ALLOWED_MEMBER_ROLES:
            raise HTTPException(status_code=403, detail=_MEMBERSHIP_CORRUPT)
        rows.append((shop.id, shop.name, role))
    rows.sort(key=lambda row: (normalized_shop_sort_name(row[1]), row[0]))
    return rows


def list_caller_membership_shops(db: Session, clerk_user_id: str) -> list[tuple[str, str, str]]:
    """Return (id, name, role) for every shop the verified Clerk user belongs to."""
    members = (
        db.query(ShopMember).filter(ShopMember.clerk_user_id == clerk_user_id).all()
    )
    if not members:
        return []
    shop_ids = {member.shop_id for member in members}
    shops = db.query(Shop).filter(Shop.id.in_(shop_ids)).all()
    return compose_caller_membership_shops(members, {shop.id: shop for shop in shops})


def require_membership(db: Session, shop_id: str, clerk_user_id: str) -> ShopMember:
    members = (
        db.query(ShopMember)
        .filter(
            ShopMember.shop_id == shop_id,
            ShopMember.clerk_user_id == clerk_user_id,
        )
        .all()
    )
    if not members:
        raise HTTPException(status_code=403, detail="No shop membership found for Clerk user")
    if len(members) > 1:
        raise HTTPException(status_code=403, detail="Conflicting shop membership")
    return members[0]


def load_shop(db: Session, shop_id: str) -> Shop:
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    return shop
