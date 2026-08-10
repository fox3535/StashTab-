from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import ShopContext, get_shop_context
from app.logic.sales import build_cart_lines, finalize_sale
from app.logic.trades import clear_pending_trades
from app.models import Sale
from app.schemas import (
    CheckoutRequest,
    CheckoutResponse,
    PlaceholderTradeIn,
    PlaceholderTradeOut,
    SaleOut,
    SalesHistoryResponse,
)
from app.logic.trades import add_placeholder_trade, list_pending_trades

router = APIRouter(prefix="/sales", tags=["sales"])


@router.post("/checkout", response_model=CheckoutResponse)
def checkout(
    payload: CheckoutRequest,
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> CheckoutResponse:
    if not payload.lines:
        raise HTTPException(status_code=400, detail="Cart is empty")

    try:
        lines, market_total = build_cart_lines(
            db,
            ctx.shop_id,
            [(line.sku, line.quantity) for line in payload.lines],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    cart_total = market_total
    final_total = (
        payload.final_sale_price if payload.final_sale_price is not None else cart_total
    )

    if payload.payment_method == "trade":
        net_due = (
            cart_total
            - payload.placeholder_cost
            + payload.store_cash
            - payload.customer_cash
        )
        final_total = net_due if payload.final_sale_price is None else final_total
    else:
        net_due = final_total

    trade_in_value = payload.placeholder_cost if payload.payment_method == "trade" else 0.0

    sale_ids = finalize_sale(
        db,
        ctx.shop_id,
        lines,
        final_total,
        payload.payment_method,
        trade_in_value=trade_in_value,
        show_session_id=payload.show_session_id,
    )

    if payload.clear_placeholder_trades and payload.payment_method == "trade":
        clear_pending_trades(db, ctx.shop_id)

    change_due = 0.0
    if payload.payment_method == "cash" and payload.amount_tendered is not None:
        change_due = max(0.0, payload.amount_tendered - final_total)

    db.commit()

    return CheckoutResponse(
        success=True,
        total=final_total,
        change_due=change_due,
        net_due=net_due,
        sale_ids=sale_ids,
    )


@router.get("/history", response_model=SalesHistoryResponse)
def sales_history(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> SalesHistoryResponse:
    query = db.query(Sale).filter(Sale.shop_id == ctx.shop_id)
    total = query.with_entities(func.count(Sale.id)).scalar() or 0
    sales = (
        query.order_by(Sale.timestamp.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return SalesHistoryResponse(
        sales=[SaleOut.model_validate(s) for s in sales],
        total=total,
    )


@router.post("/placeholder-trade", response_model=PlaceholderTradeOut)
def create_placeholder_trade(
    payload: PlaceholderTradeIn,
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> PlaceholderTradeOut:
    trade = add_placeholder_trade(
        db,
        ctx.shop_id,
        payload.market_value,
        payload.cash_paid,
    )
    db.commit()
    db.refresh(trade)
    return PlaceholderTradeOut.model_validate(trade)


@router.get("/placeholder-trades", response_model=list[PlaceholderTradeOut])
def get_placeholder_trades(
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> list[PlaceholderTradeOut]:
    trades = list_pending_trades(db, ctx.shop_id)
    return [PlaceholderTradeOut.model_validate(t) for t in trades]
