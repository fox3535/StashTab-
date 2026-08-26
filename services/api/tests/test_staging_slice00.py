"""Slice-00 staging safeguards: liveness, readiness, fail-closed defaults."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import bootstrap_legacy_schema, init_db, startup_schema_mutation_forbidden
from app.errors import FeatureNotReadyError
from app.feature_readiness import (
    ensure_inventory_mutations_ready,
    shopify_credentials_usable,
    worker_jobs_enabled,
)
from app.models import Base, Shop
from app.readiness import evaluate_readiness
from app.routers.health import health, router as health_router


def _sqlite():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return engine, Session()


def test_liveness_does_not_need_database():
    body = health()
    assert body["status"] == "ok"
    mini = FastAPI()
    mini.include_router(health_router, prefix="/api/v1")
    with TestClient(mini) as client:
        res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_readiness_fails_when_database_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "staging")
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "clerk_jwt_issuer", "https://example.clerk.accounts.dev")
    monkeypatch.setattr(settings, "clerk_authorized_parties", "https://staging.example")
    status, body = evaluate_readiness(None)
    assert status == 503
    assert "database_unavailable" in body["reasons"]
    dumped = str(body).lower()
    assert "password" not in dumped
    assert "postgresql://" not in dumped


def test_readiness_fails_for_missing_staging_identity(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "staging")
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "clerk_jwt_issuer", "")
    monkeypatch.setattr(settings, "clerk_authorized_parties", "")
    engine, db = _sqlite()
    try:
        status, body = evaluate_readiness(db)
        assert status == 503
        assert "identity_configuration_missing" in body["reasons"]
    finally:
        db.close()
        engine.dispose()


def test_readiness_fails_if_prohibited_features_enabled(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "staging")
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "clerk_jwt_issuer", "https://example.clerk.accounts.dev")
    monkeypatch.setattr(settings, "clerk_authorized_parties", "https://staging.example")
    monkeypatch.setattr(settings, "notifications_backend_enabled", True)
    engine, db = _sqlite()
    try:
        status, body = evaluate_readiness(db)
        assert status == 503
        assert "notifications_backend" in body["reasons"]
    finally:
        db.close()
        engine.dispose()
        monkeypatch.setattr(settings, "notifications_backend_enabled", False)


def test_readiness_reports_missing_schema_without_creating(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "staging")
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "clerk_jwt_issuer", "https://example.clerk.accounts.dev")
    monkeypatch.setattr(settings, "clerk_authorized_parties", "https://staging.example")
    monkeypatch.setattr(settings, "notifications_backend_enabled", False)
    engine, db = _sqlite()
    try:
        before = set(inspect(engine).get_table_names())
        _status, body = evaluate_readiness(db)
        after = set(inspect(engine).get_table_names())
        assert before == after
        assert body["schema"]["inventory_truth"] is False
        assert body["schema"]["notifications"] is False
        assert body["features"]["inventory_cutover"] is False
        assert body["features"]["shopify_sync"] is False
        assert body["features"]["worker"] is False
        assert body["features"]["web_push"] is False
    finally:
        db.close()
        engine.dispose()


def test_inventory_mutations_feature_not_ready_without_truth_schema():
    engine, db = _sqlite()
    try:
        with pytest.raises(FeatureNotReadyError) as exc:
            ensure_inventory_mutations_ready(db, "shop-a")
        assert exc.value.feature == "inventory_truth"
    finally:
        db.close()
        engine.dispose()


async def _feature_not_ready_handler(_request: Request, exc: FeatureNotReadyError):
    return JSONResponse(
        status_code=503,
        content={
            "error": "FEATURE_NOT_READY",
            "feature": exc.feature,
            "message": exc.message,
        },
    )


def test_protected_route_returns_feature_not_ready():
    app = FastAPI()
    app.add_exception_handler(FeatureNotReadyError, _feature_not_ready_handler)

    @app.post("/api/v1/sales/checkout")
    def checkout():
        raise FeatureNotReadyError("inventory_truth")

    with TestClient(app) as client:
        res = client.post("/api/v1/sales/checkout")
    assert res.status_code == 503
    payload = res.json()
    assert payload["error"] == "FEATURE_NOT_READY"
    assert payload["feature"] == "inventory_truth"


def test_startup_schema_mutation_forbidden_in_staging(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "staging")
    assert startup_schema_mutation_forbidden() is True
    with pytest.raises(RuntimeError, match="forbidden"):
        init_db()
    monkeypatch.setattr(settings, "app_env", "production")
    with pytest.raises(RuntimeError, match="forbidden"):
        init_db()


def test_local_bootstrap_cannot_arm_under_staging(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "staging")
    with pytest.raises(RuntimeError, match="local/test"):
        bootstrap_legacy_schema()


def test_shopify_and_worker_default_off_when_missing():
    assert shopify_credentials_usable(None) is False
    assert shopify_credentials_usable(SimpleNamespace(store_url="", api_key_encrypted="")) is False
    assert (
        shopify_credentials_usable(
            SimpleNamespace(store_url="x.myshopify.com", api_key_encrypted="")
        )
        is False
    )
    assert worker_jobs_enabled() is False
    import worker

    engine, db = _sqlite()
    Base.metadata.create_all(engine)
    try:
        db.add(Shop(id="shop-x", name="X", slug="x"))
        db.commit()
        assert worker._shop_auto_sync(db, "shop-x") is False
    finally:
        db.close()
        engine.dispose()


def test_dev_seed_refuses_staging(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "staging")
    import scripts.seed_dev as seed_dev

    with pytest.raises(SystemExit):
        seed_dev.main()


def test_synthetic_fixture_script_does_not_connect(monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    from scripts.staging_synthetic_fixtures import main

    assert main() == 0


def _decode(authorization):
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    if token == "invalid":
        from app.auth.clerk import ClerkAuthError

        raise ClerkAuthError("Invalid session")
    return token


def _admin_client(db, monkeypatch):
    from app.database import get_db
    from app.errors import FeatureNotReadyError
    from app.models import InventoryItem, ShopMember
    from app.models.base import new_uuid
    from app.routers import admin as admin_router

    monkeypatch.setattr(settings, "app_env", "staging")
    monkeypatch.setattr(settings, "stashtab_allow_dev_identity", False)
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "clerk_jwt_issuer", "https://clerk.example")
    monkeypatch.setattr("app.auth.identity.decode_bearer_user_id", _decode)
    monkeypatch.setattr("app.auth.clerk.decode_bearer_user_id", _decode)

    db.add(Shop(id="shop-a", name="A", slug="a"))
    db.add(Shop(id="shop-b", name="B", slug="b"))
    db.add(ShopMember(id=new_uuid(), shop_id="shop-a", clerk_user_id="user-a", role="owner"))
    db.add(ShopMember(id=new_uuid(), shop_id="shop-b", clerk_user_id="user-b", role="owner"))
    db.add(
        InventoryItem(
            shop_id="shop-a",
            sku="CS-1",
            name="Alpha",
            set_name="Base",
            cost=1,
            price=2,
            stock=4,
            game="Pokemon",
        )
    )
    db.add(
        InventoryItem(
            shop_id="shop-a",
            sku="CS-2",
            name="Beta",
            set_name="Base",
            cost=1,
            price=3,
            stock=6,
            game="Pokemon",
        )
    )
    db.add(
        InventoryItem(
            shop_id="shop-b",
            sku="CS-1",
            name="Bravo",
            set_name="Base",
            cost=1,
            price=2,
            stock=8,
            game="Pokemon",
        )
    )
    db.commit()

    app = FastAPI()
    app.add_exception_handler(FeatureNotReadyError, _feature_not_ready_handler)
    app.include_router(admin_router.router, prefix="/api/v1")

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def _headers(user="user-a", shop="shop-a"):
    return {"Authorization": f"Bearer {user}", "X-Shop-Id": shop}


def _item(db, sku="CS-1", shop="shop-a"):
    from app.models import InventoryItem

    return (
        db.query(InventoryItem)
        .filter(InventoryItem.shop_id == shop, InventoryItem.sku == sku)
        .one()
    )


def test_quantity_patch_missing_schema_returns_feature_not_ready(monkeypatch):
    engine, db = _sqlite()
    Base.metadata.create_all(engine)
    try:
        client = _admin_client(db, monkeypatch)
        item = _item(db)
        res = client.patch(
            f"/api/v1/admin/inventory/{item.id}",
            headers=_headers(),
            json={"stock": 9},
        )
        assert res.status_code == 503
        body = res.json()
        assert body["error"] == "FEATURE_NOT_READY"
        assert body["feature"] == "inventory_truth"
        db.expire_all()
        assert _item(db).stock == 4
        assert _item(db).price == 2
    finally:
        db.close()
        engine.dispose()


def test_mixed_patch_missing_schema_changes_neither_field(monkeypatch):
    engine, db = _sqlite()
    Base.metadata.create_all(engine)
    try:
        client = _admin_client(db, monkeypatch)
        item = _item(db)
        res = client.patch(
            f"/api/v1/admin/inventory/{item.id}",
            headers=_headers(),
            json={"stock": 9, "price": 9.99},
        )
        assert res.status_code == 503
        assert res.json()["error"] == "FEATURE_NOT_READY"
        db.expire_all()
        assert _item(db).stock == 4
        assert _item(db).price == 2
    finally:
        db.close()
        engine.dispose()


def test_price_only_patch_allowed_without_truth_schema(monkeypatch):
    engine, db = _sqlite()
    Base.metadata.create_all(engine)
    try:
        client = _admin_client(db, monkeypatch)
        item = _item(db)
        res = client.patch(
            f"/api/v1/admin/inventory/{item.id}",
            headers=_headers(),
            json={"price": 9.99},
        )
        assert res.status_code == 200
        db.expire_all()
        assert _item(db).stock == 4
        assert abs(_item(db).price - 9.99) < 0.001
    finally:
        db.close()
        engine.dispose()


def test_quantity_csv_missing_schema_applies_nothing(monkeypatch):
    engine, db = _sqlite()
    Base.metadata.create_all(engine)
    try:
        client = _admin_client(db, monkeypatch)
        csv_body = "Product Name,Set,Quantity\nAlpha,Base,9\nBeta,Base,1\n"
        res = client.post(
            "/api/v1/admin/import",
            headers=_headers(),
            files={"file": ("qty.csv", csv_body, "text/csv")},
        )
        assert res.status_code == 503
        assert res.json()["error"] == "FEATURE_NOT_READY"
        db.expire_all()
        assert _item(db, "CS-1").stock == 4
        assert _item(db, "CS-2").stock == 6
    finally:
        db.close()
        engine.dispose()


def test_cross_shop_patch_rejected_before_mutation(monkeypatch):
    engine, db = _sqlite()
    Base.metadata.create_all(engine)
    try:
        client = _admin_client(db, monkeypatch)
        foreign = _item(db, shop="shop-b")
        res = client.patch(
            f"/api/v1/admin/inventory/{foreign.id}",
            headers=_headers(user="user-a", shop="shop-a"),
            json={"stock": 1},
        )
        assert res.status_code in (403, 404)
        db.expire_all()
        assert _item(db, shop="shop-b").stock == 8
    finally:
        db.close()
        engine.dispose()

