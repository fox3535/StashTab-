"""Standalone sync worker — run alongside API for background processing."""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, init_db
from app.logic.sync_worker import run_full_sync
from app.logic.notifications import process_pending_notifications
from app.models import Shop, SystemSettings


def _shop_auto_sync(db, shop_id: str) -> bool:
    settings = (
        db.query(SystemSettings).filter(SystemSettings.shop_id == shop_id).first()
    )
    if settings is None:
        return True
    return bool(settings.auto_sync_enabled)


def tick_shop(sync_db, shop) -> None:
    if _shop_auto_sync(sync_db, shop.id):
        result = run_full_sync(sync_db, shop.id)
        pull = result.get("pull", {})
        outbox = result.get("outbox", {})
        if pull.get("new_pulls") or outbox.get("synced") or outbox.get("failed"):
            print(f"[{shop.slug}] pull={pull.get('new_pulls', 0)} outbox={outbox}")
    notif_db = SessionLocal()
    try:
        notifications = process_pending_notifications(notif_db, shop.id)
        if notifications.get("sent") or notifications.get("failed"):
            print(f"[{shop.slug}] notifications={notifications}")
    finally:
        notif_db.close()


def main() -> None:
    init_db()
    interval = int(os.environ.get("SYNC_INTERVAL_SECONDS", "30"))
    print(f"StashTab sync worker started (interval={interval}s)")
    print("Worker shop identity is the persisted Shop.id row, never request headers.")

    while True:
        db = SessionLocal()
        try:
            shops = db.query(Shop).all()
            for shop in shops:
                tick_shop(db, shop)
        finally:
            db.close()
        time.sleep(interval)


if __name__ == "__main__":
    main()
