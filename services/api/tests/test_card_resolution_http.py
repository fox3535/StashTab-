from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.clerk import ClerkAuthError
from app.card_resolution.migrator import apply as apply_card_resolution
from app.card_resolution.models import CARD_RESOLUTION_TABLES, CardResolutionBase, CardResolutionCatalog
from app.card_resolution.router import router as card_resolution_router
from app.config import settings
from app.database import get_db, init_db
from app.errors import FeatureNotReadyError
from app.models import Base, InventoryItem, PurchaseRecord, Sale, Shop, ShopMember, StagingItem
from app.models.base import new_uuid
from app.routers import inventory as inventory_router
from app.routers import shops as shops_router
from fastapi.responses import JSONResponse


def _engine(path=None):
    if path is None:
        return create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    url = "sqlite:///" + str(path.resolve()).replace("\\", "/")
    return create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})


def _session(path=None):
    engine = _engine(path)
    Base.metadata.create_all(engine)
    apply_card_resolution(engine)
    db = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    db.add(Shop(id="shop-a", name="A", slug="a"))
    db.add(Shop(id="shop-b", name="B", slug="b"))
    db.add(ShopMember(id=new_uuid(), shop_id="shop-a", clerk_user_id="user-a", role="owner"))
    db.add(ShopMember(id=new_uuid(), shop_id="shop-a", clerk_user_id="user-staff", role="staff"))
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
        CardResolutionCatalog(
            id=new_uuid(),
            shop_id="shop-a",
            game="pokemon",
            name="Charizard",
            set_name="Base Set",
            set_code="BS",
            collector_number="4",
            language="en",
            printing="Non-Holo",
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


async def _feature_handler(_request, exc: FeatureNotReadyError):
    return JSONResponse(
        status_code=503,
        content={"error": "FEATURE_NOT_READY", "feature": exc.feature, "message": exc.message},
    )


def _client(db, monkeypatch, *, app_env="test", enabled=True):
    monkeypatch.setattr(settings, "app_env", app_env)
    monkeypatch.setattr(settings, "card_resolution_intake_enabled", enabled)
    monkeypatch.setattr(settings, "stashtab_allow_dev_identity", False)
    monkeypatch.setattr(settings, "debug", True)
    monkeypatch.setattr(settings, "clerk_jwt_issuer", "https://clerk.example")
    monkeypatch.setattr("app.auth.identity.decode_bearer_user_id", _decode)
    monkeypatch.setattr("app.auth.clerk.decode_bearer_user_id", _decode)
    app = FastAPI()
    app.add_exception_handler(FeatureNotReadyError, _feature_handler)
    app.include_router(shops_router.router, prefix="/api/v1")
    app.include_router(inventory_router.router, prefix="/api/v1")
    app.include_router(card_resolution_router, prefix="/api/v1")

    def override_db():
        local = sessionmaker(bind=db.get_bind(), autocommit=False, autoflush=False)()
        try:
            yield local
        finally:
            local.close()

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def _headers(user="user-a", shop="shop-a"):
    return {"Authorization": f"Bearer {user}", "X-Shop-Id": shop}


def _body(intake_id="req-1", **overrides):
    payload = {
        "intake_id": intake_id,
        "game": "pokemon",
        "name": "Charizard",
        "set_name": "Base Set",
        "set_code": "BS",
        "collector_number": "4",
        "language": "EN",
        "printing": "Non-Holo",
    }
    payload.update(overrides)
    return payload


def test_startup_create_all_does_not_create_card_resolution_tables(monkeypatch):
    engine = _engine()
    monkeypatch.setattr(settings, "app_env", "local")
    Base.metadata.create_all(engine)
    names = set(inspect(engine).get_table_names())
    assert set(CARD_RESOLUTION_TABLES).isdisjoint(names)
    assert set(CARD_RESOLUTION_TABLES).isdisjoint(Base.metadata.tables)
    assert set(CARD_RESOLUTION_TABLES) <= set(CardResolutionBase.metadata.tables)


def test_accepted_unique_match(monkeypatch):
    db = _session()
    client = _client(db, monkeypatch)
    before = db.query(InventoryItem).count()
    res = client.post("/api/v1/card-resolution/intake", headers=_headers(), json=_body())
    assert res.status_code == 200
    body = res.json()
    assert body["result"] == "accepted"
    assert body["identity_confidence"] == 1.0
    assert body["price_confidence"] is None
    assert body["justtcg_invoked"] is False
    assert db.query(InventoryItem).count() == before
    assert db.query(Sale).count() == 0
    assert db.query(PurchaseRecord).count() == 0
    assert db.query(StagingItem).count() == 0


def test_missing_language_abstains_and_creates_one_review(monkeypatch):
    db = _session()
    client = _client(db, monkeypatch)
    res = client.post(
        "/api/v1/card-resolution/intake",
        headers=_headers(),
        json=_body(language=None),
    )
    assert res.status_code == 200
    body = res.json()
    assert body["result"] == "abstained"
    assert body["review_id"]
    reviews = client.get("/api/v1/card-resolution/reviews", headers=_headers())
    assert res.status_code == 200
    assert len(reviews.json()) == 1


def test_fuzzy_name_cannot_accept(monkeypatch):
    db = _session()
    client = _client(db, monkeypatch)
    res = client.post(
        "/api/v1/card-resolution/intake",
        headers=_headers(),
        json=_body(name="Charzard"),
    )
    assert res.status_code == 200
    assert res.json()["result"] == "abstained"


def test_price_ignored(monkeypatch):
    db = _session()
    client = _client(db, monkeypatch)
    res = client.post(
        "/api/v1/card-resolution/intake",
        headers=_headers(),
        json=_body(price=400),
    )
    assert res.status_code == 200
    assert res.json()["result"] == "accepted"


def test_missing_and_unsupported_game_reject(monkeypatch):
    db = _session()
    client = _client(db, monkeypatch)
    missing = client.post("/api/v1/card-resolution/intake", headers=_headers(), json={"intake_id": "g1"})
    assert missing.status_code == 200
    assert missing.json()["result"] == "rejected"
    unsupported = client.post(
        "/api/v1/card-resolution/intake",
        headers=_headers(),
        json=_body(intake_id="g2", game="lorcana"),
    )
    assert unsupported.status_code == 200
    assert unsupported.json()["result"] == "rejected"


def test_idempotent_replay_and_conflict(monkeypatch):
    db = _session()
    client = _client(db, monkeypatch)
    first = client.post("/api/v1/card-resolution/intake", headers=_headers(), json=_body())
    replay = client.post("/api/v1/card-resolution/intake", headers=_headers(), json=_body())
    assert first.status_code == 200
    assert replay.status_code == 200
    assert first.json()["result"] == replay.json()["result"]
    conflict = client.post(
        "/api/v1/card-resolution/intake",
        headers=_headers(),
        json=_body(name="Blastoise"),
    )
    assert conflict.status_code == 409


def test_auth_and_cross_shop(monkeypatch):
    db = _session()
    client = _client(db, monkeypatch)
    created = client.post("/api/v1/card-resolution/intake", headers=_headers(), json=_body(language=None))
    review_id = created.json()["review_id"]
    assert client.post("/api/v1/card-resolution/intake", json=_body(intake_id="x")).status_code == 401
    spoof = client.post(
        "/api/v1/card-resolution/intake",
        headers={"X-Shop-Id": "shop-a", "X-Clerk-User-Id": "user-a"},
        json=_body(intake_id="spoof"),
    )
    assert spoof.status_code in (401, 403)
    other = client.get(
        "/api/v1/card-resolution/reviews",
        headers=_headers(user="user-b", shop="shop-b"),
    )
    assert other.status_code == 200
    assert other.json() == []
    stolen = client.post(
        f"/api/v1/card-resolution/reviews/{review_id}/decide",
        headers=_headers(user="user-b", shop="shop-b"),
        json={"decision": "accept_identity"},
    )
    assert stolen.status_code in (403, 404)


def test_owner_and_staff_review_succeeds(monkeypatch):
    db = _session()
    client = _client(db, monkeypatch)
    created = client.post("/api/v1/card-resolution/intake", headers=_headers(), json=_body(language=None))
    review_id = created.json()["review_id"]
    decided = client.post(
        f"/api/v1/card-resolution/reviews/{review_id}/decide",
        headers=_headers(user="user-staff", shop="shop-a"),
        json={"decision": "accept_identity"},
    )
    assert decided.status_code == 200
    assert decided.json()["result"] == "accepted"
    assert decided.json()["decision_source"] == "human"
    before = db.query(InventoryItem).count()
    assert db.query(InventoryItem).count() == before


def test_feature_flag_and_non_local_env(monkeypatch):
    db = _session()
    off = _client(db, monkeypatch, enabled=False)
    assert off.post("/api/v1/card-resolution/intake", headers=_headers(), json=_body()).status_code == 503
    staging = _client(db, monkeypatch, app_env="staging", enabled=True)
    assert staging.post("/api/v1/card-resolution/intake", headers=_headers(), json=_body()).status_code == 503


def test_scorer_failure_and_timeout_abstain(monkeypatch):
    db = _session()
    client = _client(db, monkeypatch)

    def boom(*_args, **_kwargs):
        raise RuntimeError("scorer exploded")

    monkeypatch.setattr("app.card_resolution.service.decide", boom)
    failed = client.post("/api/v1/card-resolution/intake", headers=_headers(), json=_body(intake_id="fail"))
    assert failed.status_code == 200
    assert failed.json()["result"] == "abstained"

    from app.card_resolution.scoring import ScoringTimeout

    def timeout(*_args, **_kwargs):
        raise ScoringTimeout("late")

    monkeypatch.setattr("app.card_resolution.service.decide", timeout)
    timed = client.post("/api/v1/card-resolution/intake", headers=_headers(), json=_body(intake_id="late"))
    assert timed.status_code == 200
    assert timed.json()["result"] == "abstained"


def test_append_only_evidence(monkeypatch):
    db = _session()
    client = _client(db, monkeypatch)
    client.post("/api/v1/card-resolution/intake", headers=_headers(), json=_body())
    with pytest.raises(Exception):
        db.execute(text("UPDATE card_resolution_evidence SET payload_json='{}'"))
        db.commit()


def test_concurrent_identical_requests(monkeypatch, tmp_path):
    db = _session(tmp_path / "cr-same.db")
    client = _client(db, monkeypatch)
    payload = _body(intake_id="same")

    def send():
        return client.post("/api/v1/card-resolution/intake", headers=_headers(), json=payload)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: send(), range(2)))
    assert all(item.status_code == 200 for item in results)
    assert results[0].json()["result"] == results[1].json()["result"]
    from app.card_resolution.models import CardResolutionIntake

    assert db.query(CardResolutionIntake).filter(CardResolutionIntake.intake_id == "same").count() == 1


def test_concurrent_abstain_creates_one_review(monkeypatch, tmp_path):
    db = _session(tmp_path / "cr-abs.db")
    client = _client(db, monkeypatch)
    payload = _body(intake_id="same-abs", language=None)

    def send():
        return client.post("/api/v1/card-resolution/intake", headers=_headers(), json=payload)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: send(), range(2)))
    assert all(item.status_code == 200 for item in results)
    assert all(item.json()["result"] == "abstained" for item in results)
    from app.card_resolution.models import CardResolutionReview

    assert db.query(CardResolutionReview).filter(CardResolutionReview.intake_id == "same-abs").count() == 1


def test_concurrent_review_decisions_do_not_contradict(monkeypatch, tmp_path):
    db = _session(tmp_path / "cr-rev.db")
    client = _client(db, monkeypatch)
    created = client.post(
        "/api/v1/card-resolution/intake",
        headers=_headers(),
        json=_body(intake_id="rev-race", language=None),
    )
    review_id = created.json()["review_id"]

    def decide(decision):
        return client.post(
            f"/api/v1/card-resolution/reviews/{review_id}/decide",
            headers=_headers(user="user-staff", shop="shop-a"),
            json={"decision": decision},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(decide, "accept_identity")
        second = pool.submit(decide, "reject")
        results = [first.result(), second.result()]
    statuses = sorted(item.status_code for item in results)
    assert statuses == [200, 409]
    winners = [item.json() for item in results if item.status_code == 200]
    assert len(winners) == 1
    assert winners[0]["result"] in {"accepted", "rejected"}
    from app.card_resolution.models import CardResolutionIntake

    intake = db.query(CardResolutionIntake).filter(CardResolutionIntake.intake_id == "rev-race").one()
    assert intake.result == winners[0]["result"]


def test_staging_and_production_fail_closed_even_if_misconfigured(monkeypatch):
    db = _session()
    for env in ("staging", "production"):
        client = _client(db, monkeypatch, app_env=env, enabled=True)
        monkeypatch.setattr(settings, "debug", True)
        monkeypatch.setattr(settings, "notifications_backend_enabled", True)
        res = client.post("/api/v1/card-resolution/intake", headers=_headers(), json=_body(intake_id=f"{env}-x"))
        assert res.status_code == 503
        assert res.json()["feature"] == "card_resolution_intake"
