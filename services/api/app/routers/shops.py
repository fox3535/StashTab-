from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Shop, ShopMember
from app.models.base import new_uuid
from app.schemas import ShopCreate, ShopOut

router = APIRouter(prefix="/shops", tags=["shops"])


class OnboardRequest(BaseModel):
    name: str
    slug: str
    clerk_user_id: str


class ShopMemberOut(BaseModel):
    id: str
    shop_id: str
    clerk_user_id: str
    role: str

    model_config = {"from_attributes": True}


class MemberInviteRequest(BaseModel):
    clerk_user_id: str
    role: str = "staff"


@router.post("", response_model=ShopOut)
def create_shop(payload: ShopCreate, db: Session = Depends(get_db)) -> Shop:
    existing = db.query(Shop).filter(Shop.slug == payload.slug).first()
    if existing:
        raise HTTPException(status_code=409, detail="Slug already taken")
    shop = Shop(id=new_uuid(), name=payload.name, slug=payload.slug)
    db.add(shop)
    db.commit()
    db.refresh(shop)
    return shop


@router.post("/onboard", response_model=ShopOut)
def onboard_shop(payload: OnboardRequest, db: Session = Depends(get_db)) -> Shop:
    """Create shop and link Clerk user as owner."""
    existing = db.query(Shop).filter(Shop.slug == payload.slug).first()
    if existing:
        raise HTTPException(status_code=409, detail="Slug already taken")

    shop = Shop(id=new_uuid(), name=payload.name, slug=payload.slug)
    db.add(shop)
    db.flush()

    member = ShopMember(
        shop_id=shop.id,
        clerk_user_id=payload.clerk_user_id,
        role="owner",
    )
    db.add(member)
    db.commit()
    db.refresh(shop)
    return shop


@router.get("/me", response_model=ShopOut)
def get_my_shop(
    x_clerk_user_id: str | None = Header(default=None, alias="X-Clerk-User-Id"),
    db: Session = Depends(get_db),
) -> Shop:
    """Resolve shop from Clerk user membership."""
    if not x_clerk_user_id:
        raise HTTPException(status_code=401, detail="Missing X-Clerk-User-Id")
    member = (
        db.query(ShopMember)
        .filter(ShopMember.clerk_user_id == x_clerk_user_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="No shop membership found")
    shop = db.query(Shop).filter(Shop.id == member.shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    return shop


@router.get("/{shop_id}", response_model=ShopOut)
def get_shop(shop_id: str, db: Session = Depends(get_db)) -> Shop:
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    return shop


@router.get("/{shop_id}/members", response_model=list[ShopMemberOut])
def list_members(shop_id: str, db: Session = Depends(get_db)) -> list[ShopMember]:
    return db.query(ShopMember).filter(ShopMember.shop_id == shop_id).all()


@router.post("/{shop_id}/members", response_model=ShopMemberOut)
def invite_member(
    shop_id: str,
    payload: MemberInviteRequest,
    db: Session = Depends(get_db),
) -> ShopMember:
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    existing = (
        db.query(ShopMember)
        .filter(
            ShopMember.shop_id == shop_id,
            ShopMember.clerk_user_id == payload.clerk_user_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="User already a member")

    member = ShopMember(
        id=new_uuid(),
        shop_id=shop_id,
        clerk_user_id=payload.clerk_user_id,
        role=payload.role,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member
