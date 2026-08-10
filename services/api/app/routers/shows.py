from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import ShopContext, get_shop_context
from app.logic.show_prices import capture_show_prices
from app.models import Sale, ShowSession
from app.models.base import new_uuid, utcnow

router = APIRouter(prefix="/shows", tags=["shows"])


class ShowStartIn(BaseModel):
    name: str


class ShowCaptureIn(BaseModel):
    name: str | None = None


class ShowSessionOut(BaseModel):
    id: str
    name: str
    started_at: datetime
    ended_at: datetime | None
    status: str

    model_config = {"from_attributes": True}


class ShowPnLOut(BaseModel):
    show_id: str
    name: str
    total_revenue: float
    total_profit: float
    sale_count: int


@router.get("", response_model=list[ShowSessionOut])
def list_shows(
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> list[ShowSession]:
    return (
        db.query(ShowSession)
        .filter(ShowSession.shop_id == ctx.shop_id)
        .order_by(ShowSession.started_at.desc())
        .limit(50)
        .all()
    )


@router.post("/start", response_model=ShowSessionOut)
def start_show(
    payload: ShowStartIn,
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> ShowSession:
    active = (
        db.query(ShowSession)
        .filter(
            ShowSession.shop_id == ctx.shop_id,
            ShowSession.status == "active",
        )
        .first()
    )
    if active:
        raise HTTPException(status_code=400, detail="A show is already active")

    session = ShowSession(
        id=new_uuid(),
        shop_id=ctx.shop_id,
        name=payload.name,
        status="active",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.post("/{show_id}/end", response_model=ShowSessionOut)
def end_show(
    show_id: str,
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> ShowSession:
    session = (
        db.query(ShowSession)
        .filter(ShowSession.shop_id == ctx.shop_id, ShowSession.id == show_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Show not found")
    session.status = "ended"
    session.ended_at = utcnow()
    db.commit()
    db.refresh(session)
    return session


@router.get("/{show_id}/pnl", response_model=ShowPnLOut)
def show_pnl(
    show_id: str,
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> ShowPnLOut:
    session = (
        db.query(ShowSession)
        .filter(ShowSession.shop_id == ctx.shop_id, ShowSession.id == show_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Show not found")

    totals = (
        db.query(
            func.coalesce(func.sum(Sale.net_revenue), 0),
            func.coalesce(func.sum(Sale.profit), 0),
            func.count(Sale.id),
        )
        .filter(
            Sale.shop_id == ctx.shop_id,
            Sale.show_session_id == show_id,
        )
        .first()
    )

    revenue, profit, count = totals or (0, 0, 0)
    return ShowPnLOut(
        show_id=show_id,
        name=session.name,
        total_revenue=float(revenue or 0),
        total_profit=float(profit or 0),
        sale_count=int(count or 0),
    )


@router.post("/capture-prices")
def capture_prices(
    payload: ShowCaptureIn,
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    return capture_show_prices(db, ctx.shop_id, name=payload.name)
