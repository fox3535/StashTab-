from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.deps import ShopContext, get_shop_context
from app.logic.shopify_consistency import verify_shopify_consistency
from app.logic.sync_worker import (
    get_pending_sync_count,
    get_recent_online_notifications,
    process_sync_outbox,
    pull_shopify_orders,
    run_full_sync,
)
from app.schemas import SyncStatusOut

router = APIRouter(prefix="/sync", tags=["sync"])


def _run_full_sync(shop_id: str) -> None:
    db = SessionLocal()
    try:
        run_full_sync(db, shop_id)
    finally:
        db.close()


@router.get("/status", response_model=SyncStatusOut)
def sync_status(
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> SyncStatusOut:
    pending = get_pending_sync_count(db, ctx.shop_id)
    return SyncStatusOut(pending_count=pending)


@router.get("/notifications")
def sync_notifications(
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    return {
        "notifications": get_recent_online_notifications(db, ctx.shop_id),
    }


@router.post("/pull-orders")
def pull_orders(
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    return pull_shopify_orders(db, ctx.shop_id)


@router.post("/now")
def sync_now(
    background_tasks: BackgroundTasks,
    ctx: ShopContext = Depends(get_shop_context),
) -> dict[str, str]:
    background_tasks.add_task(_run_full_sync, ctx.shop_id)
    return {"status": "started"}


@router.post("/verify")
def verify_consistency(
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    ok, message = verify_shopify_consistency(db, ctx.shop_id)
    if not ok:
        return {"success": False, "message": message}
    return {"success": True, "message": message}
