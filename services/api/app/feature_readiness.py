"""Fail-closed feature gates for staging slice-00."""

from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.config import settings
from app.errors import FeatureNotReadyError, is_missing_relation

INVENTORY_TRUTH_TABLE = "inventory_truth_cutover"
NOTIFICATION_TABLE = "notification_event"
LEGACY_TABLE = "shops"

SECRET_SETTING_ATTRS = (
    "database_url",
    "clerk_secret_key",
    "vapid_private_key",
    "vapid_public_key",
)


def table_exists(db: Session, name: str) -> bool:
    try:
        return bool(inspect(db.connection()).has_table(name))
    except Exception as exc:
        if is_missing_relation(exc):
            return False
        raise


def inventory_truth_schema_present(db: Session) -> bool:
    return table_exists(db, INVENTORY_TRUTH_TABLE)


def notification_schema_present(db: Session) -> bool:
    return table_exists(db, NOTIFICATION_TABLE)


def legacy_schema_present(db: Session) -> bool:
    return table_exists(db, LEGACY_TABLE)


def ensure_inventory_mutations_ready(db: Session, shop_id: str) -> None:
    from app.inventory_truth.core import cutover_status, require_receive_open

    if not inventory_truth_schema_present(db):
        raise FeatureNotReadyError("inventory_truth")
    env = settings.parsed_app_env
    if env in ("staging", "production"):
        if cutover_status(db, shop_id) != "complete":
            raise FeatureNotReadyError("inventory_truth")
        return
    require_receive_open(db, shop_id)


def ensure_notification_feature_ready(db: Session) -> None:
    if not settings.notifications_backend_enabled:
        raise FeatureNotReadyError("notifications")
    if not notification_schema_present(db):
        raise FeatureNotReadyError("notifications")


def shopify_credentials_usable(creds: object | None) -> bool:
    if creds is None:
        return False
    token = str(getattr(creds, "api_key_encrypted", None) or "").strip()
    store = str(getattr(creds, "store_url", None) or "").strip()
    return bool(token and store)


def worker_jobs_enabled() -> bool:
    return bool(getattr(settings, "worker_jobs_enabled", False))


def prohibited_feature_reasons() -> list[str]:
    flags: list[str] = []
    env = settings.parsed_app_env
    if settings.notifications_backend_enabled:
        flags.append("notifications_backend")
    if settings.web_push_enabled:
        flags.append("web_push")
    if worker_jobs_enabled() and env in ("staging", "production"):
        flags.append("worker_jobs")
    if (getattr(settings, "stashtab_truth_migrator_role", "") or "").strip():
        flags.append("truth_migrator_role")
    if settings.debug and env in ("staging", "production"):
        flags.append("debug")
    if settings.stashtab_allow_dev_identity and env in ("staging", "production"):
        flags.append("dev_identity_bypass")
    if getattr(settings, "card_resolution_intake_enabled", False) and env in (
        "staging",
        "production",
    ):
        flags.append("card_resolution_intake")
    return flags


def card_resolution_intake_available() -> bool:
    if settings.parsed_app_env not in ("local", "test"):
        return False
    return bool(getattr(settings, "card_resolution_intake_enabled", False))


def ensure_card_resolution_intake_ready(db: Session | None = None) -> None:
    if not card_resolution_intake_available():
        raise FeatureNotReadyError("card_resolution_intake")
    if db is not None and not table_exists(db, "card_resolution_intake"):
        raise FeatureNotReadyError("card_resolution_intake")
