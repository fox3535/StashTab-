from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import ShopContext, get_shop_context
from app.models import InventoryItem, OnlinePullQueue
from app.schemas import InventoryItemOut, InventorySearchResponse, PullQueueItemOut

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/search", response_model=InventorySearchResponse)
def search_inventory(
    q: str = Query(default="", max_length=120),
    game: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> InventorySearchResponse:
    query = db.query(InventoryItem).filter(
        InventoryItem.shop_id == ctx.shop_id,
        InventoryItem.stock > 0,
    )

    if game:
        query = query.filter(InventoryItem.game == game)

    q_stripped = q.strip()
    if q_stripped:
        # Exact barcode/SKU match takes priority
        exact = (
            db.query(InventoryItem)
            .filter(
                InventoryItem.shop_id == ctx.shop_id,
                InventoryItem.stock > 0,
                InventoryItem.sku == q_stripped.upper(),
            )
            .first()
        )
        if exact:
            return InventorySearchResponse(
                items=[InventoryItemOut.model_validate(exact)],
                total=1,
            )

        term = f"%{q_stripped}%"
        query = query.filter(
            or_(
                InventoryItem.name.ilike(term),
                InventoryItem.sku.ilike(term),
                InventoryItem.set_name.ilike(term),
            )
        )

    total = query.with_entities(func.count(InventoryItem.id)).scalar() or 0
    items = (
        query.order_by(InventoryItem.name.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return InventorySearchResponse(
        items=[InventoryItemOut.model_validate(i) for i in items],
        total=total,
    )


@router.get("/pulls", response_model=list[PullQueueItemOut])
def list_pulls(
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> list[PullQueueItemOut]:
    pulls = (
        db.query(OnlinePullQueue)
        .filter(
            OnlinePullQueue.shop_id == ctx.shop_id,
            OnlinePullQueue.status == "pending_pull",
        )
        .order_by(OnlinePullQueue.timestamp.asc())
        .all()
    )
    return [PullQueueItemOut.model_validate(p) for p in pulls]


@router.post("/pulls/{pull_id}/mark-pulled")
def mark_pulled(
    pull_id: int,
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    pull = (
        db.query(OnlinePullQueue)
        .filter(
            OnlinePullQueue.shop_id == ctx.shop_id,
            OnlinePullQueue.id == pull_id,
        )
        .first()
    )
    if not pull:
        raise HTTPException(status_code=404, detail="Pull item not found")
    pull.status = "pulled"
    db.commit()
    return {"success": True}


@router.get("/{sku}", response_model=InventoryItemOut)
def get_by_sku(
    sku: str,
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> InventoryItem:
    item = (
        db.query(InventoryItem)
        .filter(InventoryItem.shop_id == ctx.shop_id, InventoryItem.sku == sku.upper())
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item
