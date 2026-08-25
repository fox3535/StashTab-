"""Standalone sync worker — run alongside API for background processing."""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, init_db
from app.config import settings
from app.logic.notifications import (
    process_pending_notifications,
    recover_notification_sources,
)
from app.logic.sync_worker import run_full_sync
from app.models import Shop, SystemSettings


def _shop_auto_sync(db, shop_id: str) -> bool:
    settings = (
        db.query(SystemSettings).filter(SystemSettings.shop_id == shop_id).first()
    )
    if settings is None:
        return True
    return bool(settings.auto_sync_enabled)


def tick_shop(sync_db, shop) -> dict:
    """Run sync and notifications as isolated jobs for one persisted shop."""
    sync_result: dict = {"status": "skipped"}
    if _shop_auto_sync(sync_db, shop.id):
        try:
            result = run_full_sync(sync_db, shop.id)
            pull = result.get("pull", {})
            outbox = result.get("outbox", {})
            if pull.get("new_pulls") or outbox.get("synced") or outbox.get("failed"):
                print(f"[{shop.slug}] pull={pull.get('new_pulls', 0)} outbox={outbox}")
            sync_result = {"status": "ok", "result": result}
        except Exception as exc:
            sync_db.rollback()
            print(f"[{shop.slug}] SYNC FAILED: {exc}")
            sync_result = {"status": "failed", "error": str(exc)}

    notification_result: dict = {"enabled": False}
    if settings.notifications_backend_enabled:
        notification_db = SessionLocal()
        try:
            recovered = recover_notification_sources(notification_db, shop.id)
            notification_db.commit()
            delivered = process_pending_notifications(notification_db, shop.id)
            notification_result = {"enabled": True, "recovered": recovered, **delivered}
        except Exception as exc:
            notification_db.rollback()
            print(f"[{shop.slug}] NOTIFICATION TICK FAILED: {exc}")
            notification_result = {"enabled": True, "status": "failed", "error": str(exc)}
        finally:
            notification_db.close()

    status = "failed" if sync_result["status"] == "failed" else sync_result["status"]
    if notification_result.get("status") == "failed":
        status = "failed"
    elif status == "skipped" and notification_result.get("enabled"):
        status = "ok"
    return {
        "shop": shop.slug,
        "status": status,
        "sync": sync_result,
        "notifications": notification_result,
    }


def tick_all_shops() -> list[dict]:
    db = None
    try:
        db = SessionLocal()
        results = []
        shops = db.query(Shop).all()
        for shop in shops:
            try:
                results.append(tick_shop(db, shop))
            except Exception as exc:  # pragma: no cover - last resort
                db.rollback()
                print(f"[{shop.slug}] SHOP LOOP FAILED: {exc}")
                results.append(
                    {"shop": shop.slug, "status": "failed", "error": str(exc)}
                )
        failed = [r for r in results if r.get("status") == "failed"]
        if failed:
            print(f"TICK SUMMARY: {len(failed)}/{len(results)} shops failed")
        return results
    finally:
        if db is not None:
            db.close()


def run_worker_loop(interval: int, *, max_ticks: int | None = None) -> None:
    ticks = 0
    while max_ticks is None or ticks < max_ticks:
        try:
            tick_all_shops()
        except Exception as exc:  # scheduler must survive database-wide failures
            print(f"WORKER TICK FAILED: {exc}")
        finally:
            ticks += 1
        time.sleep(interval)


def main() -> None:
    init_db()
    interval = int(os.environ.get("SYNC_INTERVAL_SECONDS", "30"))
    print(f"StashTab sync worker started (interval={interval}s)")
    print("Worker shop identity is the persisted Shop.id row, never request headers.")
    run_worker_loop(interval)


if __name__ == "__main__":
    main()
