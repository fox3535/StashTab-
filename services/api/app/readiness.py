"""Readiness payload. Never include secrets."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.feature_readiness import (
    SECRET_SETTING_ATTRS,
    inventory_truth_schema_present,
    legacy_schema_present,
    notification_schema_present,
    prohibited_feature_reasons,
    worker_jobs_enabled,
)


def _identity_configured() -> dict[str, bool]:
    issuer = bool((settings.clerk_jwt_issuer or "").strip())
    parties = bool(settings.clerk_authorized_party_list)
    return {
        "clerk_issuer_configured": issuer,
        "authorized_parties_configured": parties,
        "dev_bypass_allowed": bool(settings.dev_identity_bypass_allowed),
    }


def evaluate_readiness(db: Session | None) -> tuple[int, dict]:
    identity = _identity_configured()
    env = settings.parsed_app_env
    schema = {
        "legacy": False,
        "inventory_truth": False,
        "notifications": False,
    }
    connected = db is not None
    if db is not None:
        schema["legacy"] = legacy_schema_present(db)
        schema["inventory_truth"] = inventory_truth_schema_present(db)
        schema["notifications"] = notification_schema_present(db)

    features = {
        "notifications_backend": bool(settings.notifications_backend_enabled),
        "web_push": bool(settings.web_push_enabled),
        "inventory_cutover": False,
        "shopify_sync": False,
        "worker": worker_jobs_enabled(),
    }

    reasons: list[str] = []
    if not connected:
        reasons.append("database_unavailable")
    if env is None:
        reasons.append("app_env_invalid")
    if env in ("staging", "production"):
        if not identity["clerk_issuer_configured"] or not identity[
            "authorized_parties_configured"
        ]:
            reasons.append("identity_configuration_missing")
        if identity["dev_bypass_allowed"]:
            reasons.append("identity_bypass_not_allowed")
    reasons.extend(prohibited_feature_reasons())

    body = {
        "status": "ready" if not reasons else "not_ready",
        "app_env": env or "",
        "database": {"connected": connected},
        "identity": identity,
        "schema": schema,
        "features": features,
        "reasons": reasons,
    }
    _assert_no_secrets(body)
    return (200 if not reasons else 503, body)


def ping_database(db: Session) -> None:
    db.execute(text("SELECT 1"))


def _assert_no_secrets(body: dict) -> None:
    dumped = str(body).lower()
    for attr in SECRET_SETTING_ATTRS:
        value = str(getattr(settings, attr, "") or "")
        if value and len(value) >= 8 and value.lower() in dumped:
            raise RuntimeError("readiness payload leaked a secret")
