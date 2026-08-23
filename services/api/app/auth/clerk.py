"""Clerk JWT verification for FastAPI."""

from __future__ import annotations

import jwt
from jwt import PyJWKClient

from app.config import settings

_jwks_client: PyJWKClient | None = None
_jwks_issuer: str | None = None


class ClerkAuthError(Exception):
    """Bearer token present but not verifiable."""


def reset_jwks_client() -> None:
    """Test helper: drop cached JWKS so a new issuer or key set can be used."""
    global _jwks_client, _jwks_issuer
    _jwks_client = None
    _jwks_issuer = None


def _jwks_url(issuer: str) -> str:
    return f"{issuer.rstrip('/')}/.well-known/jwks.json"


def _get_jwks_client(issuer: str) -> PyJWKClient:
    global _jwks_client, _jwks_issuer
    normalized = issuer.rstrip("/")
    if _jwks_client is None or _jwks_issuer != normalized:
        _jwks_client = PyJWKClient(_jwks_url(normalized))
        _jwks_issuer = normalized
    return _jwks_client


def _production_like() -> bool:
    env = settings.parsed_app_env
    return env not in ("local", "test")


def _authorized_parties() -> list[str]:
    return settings.clerk_authorized_party_list


def _audience() -> str | None:
    raw = (settings.clerk_jwt_audience or "").strip()
    return raw or None


def decode_bearer_user_id(authorization: str | None) -> str | None:
    """Return Clerk `sub` from a verified Bearer JWT, or None if no Bearer.

    Invalid or unverifiable Bearer tokens raise ClerkAuthError (fail closed).
    Does not read X-Clerk-User-Id.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise ClerkAuthError("Invalid session")

    issuer = (settings.clerk_jwt_issuer or "").strip()
    parties = _authorized_parties()
    audience = _audience()

    if not issuer:
        raise ClerkAuthError("Invalid session")
    if _production_like() and not parties and not audience:
        raise ClerkAuthError("Invalid session")

    decode_options = {
        "verify_signature": True,
        "verify_exp": True,
        "verify_nbf": True,
        "verify_iss": True,
        "require": ["exp", "iss", "sub"],
        "verify_aud": bool(audience),
    }
    try:
        signing_key = _get_jwks_client(issuer).get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=issuer.rstrip("/"),
            audience=audience if audience else None,
            leeway=5,
            options=decode_options,
        )
    except ClerkAuthError:
        raise
    except Exception as exc:
        raise ClerkAuthError("Invalid session") from exc

    azp = payload.get("azp")
    if parties:
        if isinstance(azp, str) and azp:
            if azp not in parties:
                raise ClerkAuthError("Invalid session")
        elif _production_like():
            raise ClerkAuthError("Invalid session")
    elif _production_like() and not audience:
        raise ClerkAuthError("Invalid session")

    sub = payload.get("sub")
    if isinstance(sub, str) and sub:
        return sub
    raise ClerkAuthError("Invalid session")


def resolve_clerk_user_id(
    authorization: str | None,
    x_clerk_user_id: str | None,
) -> str | None:
    """Legacy helper: JWT only. Header user is not trusted here."""
    try:
        return decode_bearer_user_id(authorization)
    except ClerkAuthError:
        return None
