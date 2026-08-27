from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.card_resolution.service import decide_review, list_reviews, submit_intake
from app.database import get_db
from app.deps import ShopContext, get_shop_context

router = APIRouter(prefix="/card-resolution", tags=["card-resolution"])


class CandidateIn(BaseModel):
    shop_id: str | None = None
    id: str | None = None
    game: str | None = None
    name: str | None = None
    set_name: str | None = None
    set_code: str | None = None
    collector_number: str | None = None
    language: str | None = None
    printing: str | None = None
    justtcg_id: str | None = None
    tcgplayer_id: str | None = None


class IntakeIn(BaseModel):
    intake_id: str = Field(min_length=1, max_length=120)
    shop_id: str | None = None
    game: str | None = None
    name: str | None = None
    set_name: str | None = None
    set_code: str | None = None
    collector_number: str | None = None
    language: str | None = None
    printing: str | None = None
    justtcg_id: str | None = None
    tcgplayer_id: str | None = None
    price: float | None = None
    model_confidence: float | None = None
    advisory_note: str | None = None
    candidates: list[CandidateIn] = Field(default_factory=list)


class ReviewDecisionIn(BaseModel):
    decision: str = Field(min_length=1, max_length=32)


@router.post("/intake")
def create_intake(
    body: IntakeIn,
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return submit_intake(db, ctx, body.model_dump())


@router.get("/reviews")
def get_reviews(
    status: str = "open",
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    return list_reviews(db, ctx, status)


@router.post("/reviews/{review_id}/decide")
def post_review_decision(
    review_id: str,
    body: ReviewDecisionIn,
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return decide_review(db, ctx, review_id, body.decision)
