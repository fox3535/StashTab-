"""Standalone sync worker — run alongside API for background processing."""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, init_db
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
    """One shop, isolated: any failure is reported and cannot stop the
    remaining shops in this tick (per-shop failure isolation)."""
    if not _shop_auto_sync(sync_db, shop.id):
        return {"shop": shop.slug, "status": "skipped"}
    try:
        result = run_full_sync(sync_db, shop.id)
    except Exception as exc:
        sync_db.rollback()
        print(f"[{shop.slug}] TICK FAILED: {exc}")
        return {"shop": shop.slug, "status": "failed", "error": str(exc)}
    pull = result.get("pull", {})
    outbox = result.get("outbox", {})
    if pull.get("new_pulls") or outbox.get("synced") or outbox.get("failed"):
        print(f"[{shop.slug}] pull={pull.get('new_pulls', 0)} outbox={outbox}")
    return {"shop": shop.slug, "status": "ok", "result": result}


def main() -> None:
    init_db()
    interval = int(os.environ.get("SYNC_INTERVAL_SECONDS", "30"))
    print(f"StashTab sync worker started (interval={interval}s)")
    print("Worker shop identity is the persisted Shop.id row, never request headers.")

    while True:
        db = SessionLocal()
        results = []
        try:
            shops = db.query(Shop).all()
            for shop in shops:
                # Per-shop try/except: a crashing tick_shop can never abort
                # the remaining shops or the scheduling loop itself.
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
        finally:
            db.close()
        time.sleep(interval)


if __name__ == "__main__":
    main()
