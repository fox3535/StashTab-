from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.identity import list_caller_membership_shops
from app.database import get_db
from app.deps import ShopContext, get_authenticated_user, get_shop_context
from app.identity_schema.conflicts import identity_conflict_http
from app.models import Shop, ShopMember
from app.models.base import new_uuid
from app.schemas import MembershipShopOut, MyShopMembershipsOut, ShopCreate, ShopOut

router = APIRouter(prefix="/shops", tags=["shops"])


class OnboardRequest(BaseModel):
    name: str
    slug: str
    clerk_user_id: str | None = None


class ShopMemberOut(BaseModel):
    id: str
    shop_id: str
    clerk_user_id: str
    role: str

    model_config = {"from_attributes": True}


class MemberInviteRequest(BaseModel):
    clerk_user_id: str
    role: str = "staff"


def _create_shop_with_owner(db: Session, name: str, slug: str, owner_id: str) -> Shop:
    existing = db.query(Shop).filter(Shop.slug == slug).first()
    if existing:
        raise HTTPException(status_code=409, detail="Slug already taken")
    shop = Shop(id=new_uuid(), name=name, slug=slug)
    db.add(shop)
    try:
        db.flush()
        db.add(
            ShopMember(
                id=new_uuid(),
                shop_id=shop.id,
                clerk_user_id=owner_id,
                role="owner",
            )
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        conflict = identity_conflict_http(exc)
        if conflict is not None:
            raise conflict from exc
        raise
    except Exception:
        db.rollback()
        raise
    db.refresh(shop)
    member = (
        db.query(ShopMember)
        .filter(
            ShopMember.shop_id == shop.id,
            ShopMember.clerk_user_id == owner_id,
        )
        .first()
    )
    if not member:
        raise HTTPException(status_code=500, detail="Failed to establish shop membership")
    return shop


def _assert_path_shop(ctx: ShopContext, shop_id: str) -> None:
    if ctx.shop_id != shop_id:
        raise HTTPException(status_code=403, detail="Shop mismatch")


@router.post("", response_model=ShopOut)
def create_shop(
    payload: ShopCreate,
    db: Session = Depends(get_db),
    clerk_user_id: str = Depends(get_authenticated_user),
) -> Shop:
    return _create_shop_with_owner(db, payload.name, payload.slug, clerk_user_id)


@router.post("/onboard", response_model=ShopOut)
def onboard_shop(
    payload: OnboardRequest,
    db: Session = Depends(get_db),
    clerk_user_id: str = Depends(get_authenticated_user),
) -> Shop:
    if payload.clerk_user_id and payload.clerk_user_id != clerk_user_id:
        raise HTTPException(status_code=403, detail="clerk_user_id does not match signed-in user")
    return _create_shop_with_owner(db, payload.name, payload.slug, clerk_user_id)


@router.get("/me", response_model=ShopOut)
def get_my_shop(
    db: Session = Depends(get_db),
    clerk_user_id: str = Depends(get_authenticated_user),
    x_shop_id: str | None = Header(default=None, alias="X-Shop-Id"),
) -> Shop:
    members = (
        db.query(ShopMember).filter(ShopMember.clerk_user_id == clerk_user_id).all()
    )
    if not members:
        raise HTTPException(status_code=404, detail="No shop membership found")
    hint = (x_shop_id or "").strip()
    if hint:
        match = next((m for m in members if m.shop_id == hint), None)
        if not match:
            raise HTTPException(status_code=403, detail="No shop membership found for Clerk user")
        shop = db.query(Shop).filter(Shop.id == match.shop_id).first()
    elif len(members) == 1:
        shop = db.query(Shop).filter(Shop.id == members[0].shop_id).first()
    else:
        raise HTTPException(status_code=409, detail="Shop selection required")
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    return shop


@router.get("/me/memberships", response_model=MyShopMembershipsOut)
def list_my_shop_memberships(
    db: Session = Depends(get_db),
    clerk_user_id: str = Depends(get_authenticated_user),
) -> MyShopMembershipsOut:
    """Read-only authorized shops for the verified Clerk user. Shop headers are ignored."""
    rows = list_caller_membership_shops(db, clerk_user_id)
    return MyShopMembershipsOut(
        shops=[MembershipShopOut(id=shop_id, name=name, role=role) for shop_id, name, role in rows]
    )


@router.get("/{shop_id}", response_model=ShopOut)
def get_shop(
    shop_id: str,
    db: Session = Depends(get_db),
    ctx: ShopContext = Depends(get_shop_context),
) -> Shop:
    _assert_path_shop(ctx, shop_id)
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    return shop


@router.get("/{shop_id}/members", response_model=list[ShopMemberOut])
def list_members(
    shop_id: str,
    db: Session = Depends(get_db),
    ctx: ShopContext = Depends(get_shop_context),
) -> list[ShopMember]:
    _assert_path_shop(ctx, shop_id)
    return db.query(ShopMember).filter(ShopMember.shop_id == shop_id).all()


@router.post("/{shop_id}/members", response_model=ShopMemberOut)
def invite_member(
    shop_id: str,
    payload: MemberInviteRequest,
    db: Session = Depends(get_db),
    ctx: ShopContext = Depends(get_shop_context),
) -> ShopMember:
    _assert_path_shop(ctx, shop_id)
    if payload.role not in ("owner", "staff"):
        raise HTTPException(status_code=400, detail="Invalid role")
    if ctx.role != "owner":
        raise HTTPException(status_code=403, detail="Owner role required to invite")
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
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        conflict = identity_conflict_http(exc)
        if conflict is not None:
            raise conflict from exc
        raise
    db.refresh(member)
    return member
