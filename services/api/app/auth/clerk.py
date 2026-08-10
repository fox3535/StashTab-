"""Clerk JWT verification for FastAPI."""

from __future__ import annotations

import jwt
from jwt import PyJWKClient

from app.config import settings

_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        issuer = settings.clerk_jwt_issuer.rstrip("/")
        _jwks_client = PyJWKClient(f"{issuer}/.well-known/jwks.json")
    return _jwks_client


def resolve_clerk_user_id(
    authorization: str | None,
    x_clerk_user_id: str | None,
) -> str | None:
    """
    Prefer verified Bearer JWT when clerk_jwt_issuer is configured.
    Fall back to X-Clerk-User-Id header in dev when JWT is not configured.
    """
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        if settings.clerk_jwt_issuer:
            signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                options={"verify_aud": False},
            )
            sub = payload.get("sub")
            if isinstance(sub, str) and sub:
                return sub
        elif settings.debug and x_clerk_user_id:
            return x_clerk_user_id

    if x_clerk_user_id:
        return x_clerk_user_id
    return None
