"""Cryptographic Clerk JWT acceptance checks (not monkeypatched decode)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from app.auth.clerk import ClerkAuthError, decode_bearer_user_id, reset_jwks_client
from app.auth.identity import require_membership
from app.config import settings
from app.models import ShopMember

ISSUER = "https://clerk.example"
AZP = "http://localhost:3000"


def _rsa():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _token(private_key, *, kid="k1", **claims):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "user_abc",
        "iss": ISSUER,
        "azp": AZP,
        "exp": now + timedelta(minutes=5),
        "nbf": now - timedelta(seconds=5),
        "iat": now,
        **claims,
    }
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": kid})


def _bind_jwks(monkeypatch, keys: dict[str, object]):
    class FakeJwks:
        def get_signing_key_from_jwt(self, token):
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            if kid not in keys:
                raise jwt.exceptions.PyJWKError("Unknown kid")
            return SimpleNamespace(key=keys[kid].public_key())

    reset_jwks_client()
    monkeypatch.setattr("app.auth.clerk._get_jwks_client", lambda _issuer: FakeJwks())


def _prod(monkeypatch, *, issuer=ISSUER, parties=AZP, audience="", env="production"):
    monkeypatch.setattr(settings, "app_env", env)
    monkeypatch.setattr(settings, "clerk_jwt_issuer", issuer)
    monkeypatch.setattr(settings, "clerk_authorized_parties", parties)
    monkeypatch.setattr(settings, "clerk_jwt_audience", audience)
    monkeypatch.setattr(settings, "stashtab_allow_dev_identity", False)


def test_valid_token_returns_sub(monkeypatch):
    key = _rsa()
    _prod(monkeypatch)
    _bind_jwks(monkeypatch, {"k1": key})
    token = _token(key)
    assert decode_bearer_user_id(f"Bearer {token}") == "user_abc"


def test_wrong_signature_rejected(monkeypatch):
    good, bad = _rsa(), _rsa()
    _prod(monkeypatch)
    _bind_jwks(monkeypatch, {"k1": good})
    token = _token(bad)
    with pytest.raises(ClerkAuthError):
        decode_bearer_user_id(f"Bearer {token}")


def test_wrong_issuer_rejected(monkeypatch):
    key = _rsa()
    _prod(monkeypatch)
    _bind_jwks(monkeypatch, {"k1": key})
    token = _token(key, iss="https://evil.example")
    with pytest.raises(ClerkAuthError):
        decode_bearer_user_id(f"Bearer {token}")


def test_expired_token_rejected(monkeypatch):
    key = _rsa()
    _prod(monkeypatch)
    _bind_jwks(monkeypatch, {"k1": key})
    past = datetime.now(timezone.utc) - timedelta(minutes=10)
    token = _token(key, exp=past, nbf=past - timedelta(minutes=1), iat=past - timedelta(minutes=1))
    with pytest.raises(ClerkAuthError):
        decode_bearer_user_id(f"Bearer {token}")


def test_future_nbf_rejected(monkeypatch):
    key = _rsa()
    _prod(monkeypatch)
    _bind_jwks(monkeypatch, {"k1": key})
    future = datetime.now(timezone.utc) + timedelta(minutes=10)
    token = _token(key, nbf=future, exp=future + timedelta(minutes=5), iat=datetime.now(timezone.utc))
    with pytest.raises(ClerkAuthError):
        decode_bearer_user_id(f"Bearer {token}")


def test_wrong_azp_rejected(monkeypatch):
    key = _rsa()
    _prod(monkeypatch)
    _bind_jwks(monkeypatch, {"k1": key})
    token = _token(key, azp="https://attacker.example")
    with pytest.raises(ClerkAuthError):
        decode_bearer_user_id(f"Bearer {token}")


def test_missing_issuer_config_production_rejected(monkeypatch):
    key = _rsa()
    _prod(monkeypatch, issuer="")
    _bind_jwks(monkeypatch, {"k1": key})
    token = _token(key)
    with pytest.raises(ClerkAuthError):
        decode_bearer_user_id(f"Bearer {token}")


def test_missing_azp_config_staging_rejected(monkeypatch):
    key = _rsa()
    _prod(monkeypatch, env="staging", parties="")
    _bind_jwks(monkeypatch, {"k1": key})
    token = _token(key)
    with pytest.raises(ClerkAuthError):
        decode_bearer_user_id(f"Bearer {token}")


def test_missing_azp_claim_production_rejected(monkeypatch):
    key = _rsa()
    _prod(monkeypatch)
    _bind_jwks(monkeypatch, {"k1": key})
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "user_abc",
            "iss": ISSUER,
            "exp": now + timedelta(minutes=5),
            "iat": now,
        },
        key,
        algorithm="RS256",
        headers={"kid": "k1"},
    )
    with pytest.raises(ClerkAuthError):
        decode_bearer_user_id(f"Bearer {token}")


def test_invalid_env_missing_azp_config_rejected(monkeypatch):
    key = _rsa()
    _prod(monkeypatch, env="prod", parties="")
    _bind_jwks(monkeypatch, {"k1": key})
    token = _token(key)
    with pytest.raises(ClerkAuthError):
        decode_bearer_user_id(f"Bearer {token}")


def test_key_rotation_keeps_issuer_and_azp(monkeypatch):
    k1, k2 = _rsa(), _rsa()
    _prod(monkeypatch)
    _bind_jwks(monkeypatch, {"old": k1, "new": k2})
    _bind_jwks(monkeypatch, {"k-old": k1, "k-new": k2})
    t1 = _token(k1, kid="k-old")
    t2 = _token(k2, kid="k-new")
    assert decode_bearer_user_id(f"Bearer {t1}") == "user_abc"
    assert decode_bearer_user_id(f"Bearer {t2}") == "user_abc"
    with pytest.raises(ClerkAuthError):
        decode_bearer_user_id(f"Bearer {_token(k2, kid='k-new', iss='https://other.example')}")


def test_header_user_not_used_by_decoder():
    assert decode_bearer_user_id(None) is None


def test_require_membership_fails_closed_on_duplicates():
    class FakeQuery:
        def filter(self, *args, **kwargs):
            return self

        def all(self):
            return [
                ShopMember(id="1", shop_id="shop-a", clerk_user_id="user-a", role="owner"),
                ShopMember(id="2", shop_id="shop-a", clerk_user_id="user-a", role="staff"),
            ]

    class FakeDb:
        def query(self, _model):
            return FakeQuery()

    with pytest.raises(HTTPException) as exc:
        require_membership(FakeDb(), "shop-a", "user-a")
    assert exc.value.status_code == 403
    assert "Conflicting" in exc.value.detail
