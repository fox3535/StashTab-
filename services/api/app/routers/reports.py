from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import ShopContext, get_shop_context
from app.logic.intake import add_to_staging
from app.logic.reconciliation import mark_removals_reconciled, process_reconciliation
from app.models import Sale

router = APIRouter(prefix="/reports", tags=["reports"])


class ApplyRemovalsIn(BaseModel):
    items: list[dict] = Field(default_factory=list)


@router.post("/reconciliation")
async def run_reconciliation(
    file: UploadFile = File(...),
    since_date: str | None = Query(default=None),
    stage_unknown: bool = Query(default=True),
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    content = (await file.read()).decode("utf-8", errors="replace")
    result = process_reconciliation(db, ctx.shop_id, content, since_date=since_date)

    if stage_unknown and result.get("success") and result.get("unknown_cards"):
        staged = 0
        for card in result["unknown_cards"]:
            try:
                add_to_staging(
                    db,
                    ctx.shop_id,
                    name=card["name"],
                    set_name=card.get("set_name") or None,
                    sequence_number=card.get("card_number") or None,
                    market_price=float(card.get("price", 0.0)),
                    condition=card.get("condition", "Near Mint"),
                    variant=card.get("variant", "Normal"),
                    quantity=int(card.get("quantity", 1)),
                )
                staged += 1
            except Exception:
                pass
        if staged:
            db.commit()
        result["staged_unknown"] = staged

    return result


@router.post("/reconciliation/apply-removals")
def apply_reconciliation_removals(
    payload: ApplyRemovalsIn,
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    return mark_removals_reconciled(db, ctx.shop_id, payload.items)


@router.get("/trade-history")
def trade_history(
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    sales = (
        db.query(Sale)
        .filter(
            Sale.shop_id == ctx.shop_id,
            Sale.transaction_type == "trade",
        )
        .order_by(Sale.timestamp.desc())
        .limit(200)
        .all()
    )
    return {
        "trades": [
            {
                "id": s.id,
                "item_name": s.item_name,
                "sku": s.sku,
                "sold_price": s.sold_price,
                "trade_in_value": s.trade_in_value,
                "timestamp": s.timestamp.isoformat() if s.timestamp else None,
            }
            for s in sales
        ]
    }


@router.get("/trade-history/export")
def export_trade_history_csv(
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    sales = (
        db.query(Sale)
        .filter(
            Sale.shop_id == ctx.shop_id,
            Sale.transaction_type == "trade",
        )
        .order_by(Sale.timestamp.desc())
        .all()
    )
    lines = ["id,item_name,sku,sold_price,trade_in_value,timestamp"]
    for s in sales:
        lines.append(
            f"{s.id},{s.item_name},{s.sku},{s.sold_price},{s.trade_in_value},{s.timestamp}"
        )
    return {"csv": "\n".join(lines)}
