from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import pytest

from app.auth.clerk import ClerkAuthError
from app.config import settings
from app.database import get_db
from app.models import Base, InventoryItem, Shop, ShopMember, SystemSettings
from app.models.base import new_uuid
from app.routers import inventory as inventory_router
from app.routers import notifications as notifications_router
from app.routers import shops as shops_router


def _engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def _session():
    engine = _engine()
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    db.add(Shop(id="shop-a", name="A", slug="a"))
    db.add(Shop(id="shop-b", name="B", slug="b"))
    db.add(ShopMember(id=new_uuid(), shop_id="shop-a", clerk_user_id="user-a", role="owner"))
    db.add(ShopMember(id=new_uuid(), shop_id="shop-b", clerk_user_id="user-a", role="staff"))
    db.add(ShopMember(id=new_uuid(), shop_id="shop-b", clerk_user_id="user-b", role="owner"))
    db.add(
        InventoryItem(
            shop_id="shop-a",
            sku="CS-1",
            name="Alpha",
            cost=1,
            price=2,
            stock=1,
            game="Pokemon",
        )
    )
    db.add(
        InventoryItem(
            shop_id="shop-b",
            sku="CS-1",
            name="Bravo",
            cost=1,
            price=2,
            stock=1,
            game="Pokemon",
        )
    )
    db.commit()
    return db


def _decode(authorization):
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    if token == "invalid":
        raise ClerkAuthError("Invalid session")
    return token


def _client(db, monkeypatch, *, app_env="production", allow_bypass=False, issuer="https://clerk.example"):
    monkeypatch.setattr(settings, "app_env", app_env)
    monkeypatch.setattr(settings, "stashtab_allow_dev_identity", allow_bypass)
    monkeypatch.setattr(settings, "debug", True)
    monkeypatch.setattr(settings, "clerk_jwt_issuer", issuer)
    monkeypatch.setattr("app.auth.identity.decode_bearer_user_id", _decode)
    monkeypatch.setattr("app.auth.clerk.decode_bearer_user_id", _decode)

    app = FastAPI()
    app.include_router(shops_router.router, prefix="/api/v1")
    app.include_router(inventory_router.router, prefix="/api/v1")
    app.include_router(notifications_router.router, prefix="/api/v1")

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def _headers(user="user-a", shop="shop-a", bearer=True, clerk_header=None):
    headers = {"X-Shop-Id": shop}
    if bearer:
        headers["Authorization"] = f"Bearer {user}"
    if clerk_header:
        headers["X-Clerk-User-Id"] = clerk_header
    return headers


def test_debug_alone_does_not_enable_bypass(monkeypatch):
    monkeypatch.setattr(settings, "debug", True)
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "stashtab_allow_dev_identity", True)
    assert settings.dev_identity_bypass_allowed is False


def test_missing_and_invalid_env_never_bypass(monkeypatch):
    monkeypatch.setattr(settings, "stashtab_allow_dev_identity", True)
    monkeypatch.setattr(settings, "debug", True)
    for value in ("", "prod", "dev", "PRODUCTION"):
        monkeypatch.setattr(settings, "app_env", value)
        assert settings.parsed_app_env is None or value.lower() not in ("local", "test")
        assert settings.dev_identity_bypass_allowed is False


def test_staging_and_production_never_bypass(monkeypatch):
    monkeypatch.setattr(settings, "stashtab_allow_dev_identity", True)
    monkeypatch.setattr(settings, "debug", True)
    monkeypatch.setattr(settings, "app_env", "staging")
    assert settings.dev_identity_bypass_allowed is False
    monkeypatch.setattr(settings, "app_env", "production")
    assert settings.dev_identity_bypass_allowed is False


def test_local_bypass_requires_flag(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "local")
    monkeypatch.setattr(settings, "debug", True)
    monkeypatch.setattr(settings, "stashtab_allow_dev_identity", False)
    assert settings.dev_identity_bypass_allowed is False
    monkeypatch.setattr(settings, "stashtab_allow_dev_identity", True)
    assert settings.dev_identity_bypass_allowed is True


def test_header_only_shop_rejected_in_production(monkeypatch):
    db = _session()
    client = _client(db, monkeypatch, app_env="production", allow_bypass=True)
    res = client.get("/api/v1/inventory/search", headers={"X-Shop-Id": "shop-a"})
    assert res.status_code == 401


def test_header_only_user_rejected_in_production(monkeypatch):
    db = _session()
    client = _client(db, monkeypatch, app_env="production", allow_bypass=True)
    res = client.get(
        "/api/v1/inventory/search",
        headers={"X-Shop-Id": "shop-a", "X-Clerk-User-Id": "user-a"},
    )
    assert res.status_code == 401


def test_notification_headers_without_verified_bearer_are_rejected(monkeypatch):
    db = _session()
    client = _client(db, monkeypatch, app_env="production", allow_bypass=True)
    res = client.post(
        "/api/v1/notifications/test",
        headers={"X-Shop-Id": "shop-a", "X-Clerk-User-Id": "user-a"},
    )
    assert res.status_code == 401


def test_notification_jwt_without_shop_membership_is_forbidden(monkeypatch):
    db = _session()
    client = _client(db, monkeypatch)
    res = client.get(
        "/api/v1/notifications/preferences",
        headers=_headers(user="user-z", shop="shop-a"),
    )
    assert res.status_code == 403


def test_jwt_without_membership_forbidden(monkeypatch):
    db = _session()
    client = _client(db, monkeypatch)
    res = client.get("/api/v1/inventory/search", headers=_headers(user="user-z", shop="shop-a"))
    assert res.status_code == 403


def test_jwt_wrong_shop_forbidden(monkeypatch):
    db = _session()
    client = _client(db, monkeypatch)
    res = client.get("/api/v1/inventory/search", headers=_headers(user="user-b", shop="shop-a"))
    assert res.status_code == 403


def test_jwt_matching_membership_uses_member_shop_not_header_spoof(monkeypatch):
    db = _session()
    client = _client(db, monkeypatch)
    res = client.get("/api/v1/inventory/search?q=CS-1", headers=_headers(user="user-a", shop="shop-a"))
    assert res.status_code == 200
    names = {item["name"] for item in res.json()["items"]}
    assert names == {"Alpha"}


def test_cross_shop_inventory_not_visible(monkeypatch):
    db = _session()
    client = _client(db, monkeypatch)
    res = client.get("/api/v1/inventory/search?q=CS-1", headers=_headers(user="user-b", shop="shop-b"))
    assert res.status_code == 200
    names = {item["name"] for item in res.json()["items"]}
    assert names == {"Bravo"}


def test_anonymous_shop_create_and_invite_rejected(monkeypatch):
    db = _session()
    client = _client(db, monkeypatch)
    assert client.post("/api/v1/shops", json={"name": "N", "slug": "n"}).status_code == 401
    assert client.post(
        "/api/v1/shops/onboard",
        json={"name": "N", "slug": "n2", "clerk_user_id": "user-a"},
    ).status_code == 401
    assert client.post(
        "/api/v1/shops/shop-a/members",
        json={"clerk_user_id": "user-z"},
        headers={"X-Shop-Id": "shop-a"},
    ).status_code == 401


def test_duplicate_slug_returns_409(monkeypatch):
    db = _session()
    client = _client(db, monkeypatch)
    first = client.post(
        "/api/v1/shops",
        json={"name": "One", "slug": "dup-slug"},
        headers={"Authorization": "Bearer user-c"},
    )
    assert first.status_code == 200
    second = client.post(
        "/api/v1/shops",
        json={"name": "Two", "slug": "dup-slug"},
        headers={"Authorization": "Bearer user-d"},
    )
    assert second.status_code == 409
    assert "slug" in second.json()["detail"].lower()
    assert db.query(Shop).filter(Shop.slug == "dup-slug").count() == 1


def test_duplicate_invite_returns_409(monkeypatch):
    db = _session()
    client = _client(db, monkeypatch)
    headers = _headers(user="user-a", shop="shop-a")
    first = client.post(
        "/api/v1/shops/shop-a/members",
        json={"clerk_user_id": "user-z"},
        headers=headers,
    )
    assert first.status_code == 200
    second = client.post(
        "/api/v1/shops/shop-a/members",
        json={"clerk_user_id": "user-z"},
        headers=headers,
    )
    assert second.status_code == 409
    assert db.query(ShopMember).filter(
        ShopMember.shop_id == "shop-a", ShopMember.clerk_user_id == "user-z"
    ).count() == 1


def test_identity_conflict_mapper_hides_database_text():
    from app.identity_schema.conflicts import identity_conflict_http

    err = IntegrityError("INSERT", {}, Exception("uq_shop_members_shop_user duplicate"))
    http = identity_conflict_http(err)
    assert http is not None
    assert http.status_code == 409
    assert "uq_" not in http.detail
    assert "duplicate" not in http.detail.lower()


def test_create_shop_establishes_owner_membership(monkeypatch):
    db = _session()
    client = _client(db, monkeypatch)
    res = client.post(
        "/api/v1/shops",
        json={"name": "New", "slug": "new-shop"},
        headers={"Authorization": "Bearer user-c"},
    )
    assert res.status_code == 200
    shop_id = res.json()["id"]
    member = (
        db.query(ShopMember)
        .filter(ShopMember.shop_id == shop_id, ShopMember.clerk_user_id == "user-c")
        .one()
    )
    assert member.role == "owner"


def test_onboard_body_user_mismatch_forbidden(monkeypatch):
    db = _session()
    client = _client(db, monkeypatch)
    res = client.post(
        "/api/v1/shops/onboard",
        json={"name": "X", "slug": "x-shop", "clerk_user_id": "other"},
        headers={"Authorization": "Bearer user-c"},
    )
    assert res.status_code == 403
    assert db.query(Shop).filter(Shop.slug == "x-shop").first() is None


def test_invite_requires_owner(monkeypatch):
    db = _session()
    client = _client(db, monkeypatch)
    res = client.post(
        "/api/v1/shops/shop-b/members",
        json={"clerk_user_id": "user-z"},
        headers=_headers(user="user-a", shop="shop-b"),
    )
    assert res.status_code == 403


def test_invite_rejects_unknown_role(monkeypatch):
    db = _session()
    client = _client(db, monkeypatch)
    res = client.post(
        "/api/v1/shops/shop-a/members",
        json={"clerk_user_id": "user-z", "role": "admin"},
        headers=_headers(user="user-a", shop="shop-a"),
    )
    assert res.status_code == 400


def test_invite_owner_ok(monkeypatch):
    db = _session()
    client = _client(db, monkeypatch)
    res = client.post(
        "/api/v1/shops/shop-a/members",
        json={"clerk_user_id": "user-z"},
        headers=_headers(user="user-a", shop="shop-a"),
    )
    assert res.status_code == 200
    db = _session()
    client = _client(db, monkeypatch)
    res = client.post(
        "/api/v1/shops/shop-a/members",
        json={"clerk_user_id": "user-z"},
        headers=_headers(user="user-a", shop="shop-a"),
    )
    assert res.status_code == 200


def test_local_bypass_headers_work(monkeypatch):
    db = _session()
    client = _client(db, monkeypatch, app_env="local", allow_bypass=True, issuer="")
    res = client.get(
        "/api/v1/inventory/search?q=CS-1",
        headers={"X-Shop-Id": "shop-a", "X-Clerk-User-Id": "user-a"},
    )
    assert res.status_code == 200
    assert res.json()["items"][0]["name"] == "Alpha"


def test_production_flag_does_not_reenable_headers(monkeypatch):
    db = _session()
    client = _client(db, monkeypatch, app_env="production", allow_bypass=True)
    res = client.get(
        "/api/v1/inventory/search",
        headers={"X-Shop-Id": "shop-a", "X-Clerk-User-Id": "user-a"},
    )
    assert res.status_code == 401


def test_invalid_bearer_fail_closed(monkeypatch):
    db = _session()
    client = _client(db, monkeypatch)
    res = client.get(
        "/api/v1/inventory/search",
        headers={"Authorization": "Bearer invalid", "X-Shop-Id": "shop-a"},
    )
    assert res.status_code == 401


def test_me_requires_shop_hint_when_multi_member(monkeypatch):
    db = _session()
    client = _client(db, monkeypatch)
    res = client.get("/api/v1/shops/me", headers={"Authorization": "Bearer user-a"})
    assert res.status_code == 409
    res = client.get(
        "/api/v1/shops/me",
        headers={"Authorization": "Bearer user-a", "X-Shop-Id": "shop-b"},
    )
    assert res.status_code == 200
    assert res.json()["id"] == "shop-b"


def test_duplicate_membership_insert_rejected(monkeypatch):
    db = _session()
    db.add(ShopMember(id=new_uuid(), shop_id="shop-a", clerk_user_id="user-a", role="staff"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_worker_uses_persisted_shop_id(monkeypatch):
    import worker

    db = _session()
    shop = db.query(Shop).filter(Shop.id == "shop-a").one()
    db.add(SystemSettings(shop_id="shop-a", auto_sync_enabled=True))
    db.commit()
    seen = []

    def fake_sync(_db, shop_id):
        seen.append(shop_id)
        return {}

    monkeypatch.setattr(worker, "run_full_sync", fake_sync)
    monkeypatch.setattr(worker, "SessionLocal", lambda: db)
    worker.tick_shop(db, shop)
    assert seen == ["shop-a"]
