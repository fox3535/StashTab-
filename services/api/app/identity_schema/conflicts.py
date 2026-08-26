"""Map unique-constraint races to 409 without leaking database details."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

_MEMBERSHIP = ("uq_shop_members_shop_user",)
_SLUG = ("uq_shops_slug", "shops_slug_key")


def _constraint_name(exc: IntegrityError) -> str:
    orig = getattr(exc, "orig", None)
    diag = getattr(orig, "diag", None)
    name = getattr(diag, "constraint_name", None) if diag is not None else None
    if name:
        return str(name)
    return ""


def identity_conflict_http(exc: IntegrityError) -> HTTPException | None:
    name = _constraint_name(exc)
    blob = " ".join(part for part in (name, str(getattr(exc, "orig", "") or "")) if part)
    lowered = blob.lower()
    if name in _MEMBERSHIP or "uq_shop_members_shop_user" in lowered:
        return HTTPException(status_code=409, detail="User already a member")
    if name in _SLUG or "uq_shops_slug" in lowered or "shops_slug_key" in lowered:
        return HTTPException(status_code=409, detail="Slug already taken")
    return None
