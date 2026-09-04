from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile
import math
import uuid
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import ShopContext, get_shop_context
from app.logic.images import validate_and_fetch_images
from app.logic.intake import (
    add_to_staging,
    commit_all_staging,
    commit_staging_item,
    delete_staging_item,
    manual_api_refetch,
)
from app.logic.inventory_reports import count_paperweight_units, list_paperweight_items
from app.logic.labels import barcode_public_url, generate_item_barcode
from app.logic.trades import (
    apply_trade_values_to_staging,
    list_pending_trades,
    list_resticker_items,
    mark_all_restickered,
    mark_restickered,
)
from app.logic.import_engine import patch_conditions_from_csv, process_csv_import
from app.logic.pokemon_api import PokemonAPI
from app.logic.shopify_client import ShopifyClient
from app.logic.shopify_consistency import verify_shopify_consistency
from app.logic.pricing import (
    calculate_shop_listing_price,
    calculate_shop_price,
    calculate_suggested_price,
)
from app.models import (
    InventoryItem,
    Sale,
    ShippingRule,
    ShopifyCredentials,
    StagingItem,
    SyncOutbox,
    SystemSettings,
)

router = APIRouter(prefix="/admin", tags=["admin"])


class IntakeLookupIn(BaseModel):
    set_name: str
    sequence_number: str
    card_name: str | None = None


class IntakeStagingIn(BaseModel):
    name: str
    set_name: str | None = None
    sequence_number: str | None = None
    market_price: float = Field(ge=0)
    image_url: str | None = None
    quantity: int = Field(default=1, ge=1)
    card_type: str = "Single"
    game: str = "Pokemon"


class ApplyTradesIn(BaseModel):
    trade_ids: list[int] = Field(min_length=1)


class SettingsUpdateIn(BaseModel):
    buy_percentage: float | None = None
    trade_percentage: float | None = None
    rounding_strategy: str | None = None
    markup_type: str | None = None
    markup_value: float | None = None
    rounding_rule: str | None = None
    resticker_threshold: float | None = None
    price_fluctuation_threshold: float | None = None
    paperweight_days: int | None = None
    pokemon_icon_url: str | None = None
    one_piece_icon_url: str | None = None
    auto_sync_enabled: bool | None = None
    omit_graded_from_recon: bool | None = None
    graded_wizard_sales_count: int | None = None
    graded_wizard_omit_diff: float | None = None
    gmail_monitor_enabled: bool | None = None
    gmail_address: str | None = None
    gmail_app_password: str | None = None
    gmail_folder: str | None = None


class ShippingRuleIn(BaseModel):
    min_price: float
    max_price: float
    additional_cost: float
    card_type: str = "Single"


class LabelGenerateIn(BaseModel):
    format: str = "QR"


class ShopifyCredentialsIn(BaseModel):
    store_url: str
    api_key: str


class InventoryUpdateIn(BaseModel):
    stock: int | None = None
    stock_delta: int | None = None
    reason_code: str | None = None
    reason_note: str | None = None
    price: float | None = None
    sticker_price: float | None = None
    sync_status: str | None = None


class StagingRefetchIn(BaseModel):
    name: str | None = None
    set_name: str | None = None
    sequence_number: str | None = None


@router.post("/intake/lookup")
def intake_lookup(payload: IntakeLookupIn) -> dict:
    api = PokemonAPI()
    result = api.fetch_card_data(
        payload.set_name,
        payload.sequence_number,
        card_name=payload.card_name,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Card not found in Pokemon TCG API")
    return result


@router.post("/intake/staging")
def intake_to_staging(
    payload: IntakeStagingIn,
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    item = add_to_staging(
        db,
        ctx.shop_id,
        name=payload.name,
        set_name=payload.set_name,
        sequence_number=payload.sequence_number,
        market_price=payload.market_price,
        image_url=payload.image_url,
        quantity=payload.quantity,
        card_type=payload.card_type,
        game=payload.game,
    )
    db.commit()
    db.refresh(item)
    return {
        "id": item.id,
        "sku": item.sku,
        "name": item.name,
        "market_price": item.market_price,
        "image_url": item.image_path,
    }


@router.post("/staging/{staging_id}/commit")
def commit_one_staging(
    staging_id: int,
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    try:
        inv = commit_staging_item(db, ctx.shop_id, staging_id)
        db.commit()
        return {"success": True, "sku": inv.sku, "name": inv.name}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/staging/commit-all")
def commit_all(
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    skus = commit_all_staging(db, ctx.shop_id)
    db.commit()
    return {"success": True, "committed": len(skus), "skus": skus }


@router.get("/dashboard")
def dashboard_kpis(
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    inventory_count = (
        db.query(func.count(InventoryItem.id))
        .filter(InventoryItem.shop_id == ctx.shop_id, InventoryItem.stock > 0)
        .scalar()
        or 0
    )
    inventory_value = (
        db.query(func.coalesce(func.sum(InventoryItem.price * InventoryItem.stock), 0))
        .filter(InventoryItem.shop_id == ctx.shop_id)
        .scalar()
        or 0
    )
    staging_count = (
        db.query(func.count(StagingItem.id))
        .filter(StagingItem.shop_id == ctx.shop_id)
        .scalar()
        or 0
    )
    pending_sync = (
        db.query(func.count(SyncOutbox.id))
        .filter(
            SyncOutbox.shop_id == ctx.shop_id,
            SyncOutbox.sync_status == "pending",
        )
        .scalar()
        or 0
    )
    today_sales = (
        db.query(
            func.coalesce(func.sum(Sale.net_revenue), 0),
            func.count(Sale.id),
        )
        .filter(Sale.shop_id == ctx.shop_id)
        .first()
    )
    revenue, sale_count = today_sales or (0, 0)
    paperweight_units = count_paperweight_units(db, ctx.shop_id)

    return {
        "inventory_count": inventory_count,
        "inventory_value": float(inventory_value),
        "staging_count": staging_count,
        "pending_sync": pending_sync,
        "total_revenue": float(revenue or 0),
        "sale_count": int(sale_count or 0),
        "paperweight_units": paperweight_units,
    }


@router.get("/inventory")
def list_inventory(
    q: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(InventoryItem).filter(InventoryItem.shop_id == ctx.shop_id)
    if q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                InventoryItem.name.ilike(term),
                InventoryItem.sku.ilike(term),
                InventoryItem.set_name.ilike(term),
            )
        )
    total = query.count()
    items = query.order_by(InventoryItem.name).offset(offset).limit(limit).all()
    return {
        "items": [
            {
                "id": i.id,
                "sku": i.sku,
                "name": i.name,
                "stock": i.stock,
                "price": i.price,
                "sticker_price": i.sticker_price,
                "cost": i.cost,
                "game": i.game,
                "sync_status": i.sync_status,
                "image_url": i.image_url,
                "set_name": i.set_name,
            }
            for i in items
        ],
        "total": total,
    }


@router.get("/staging")
def list_staging(
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    items = (
        db.query(StagingItem)
        .filter(StagingItem.shop_id == ctx.shop_id)
        .order_by(StagingItem.id.desc())
        .limit(100)
        .all()
    )
    return {
        "items": [
            {
                "id": i.id,
                "name": i.name,
                "sku": i.sku,
                "market_price": i.market_price,
                "suggested_price": i.suggested_price,
                "image_url": i.image_path,
                "quantity": i.quantity,
                "set_name": i.set_name,
                "sequence_number": i.sequence_number,
            }
            for i in items
        ]
    }


@router.get("/settings")
def get_settings(
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    settings = (
        db.query(SystemSettings)
        .filter(SystemSettings.shop_id == ctx.shop_id)
        .first()
    )
    if not settings:
        return {
            "buy_percentage": 0.70,
            "trade_percentage": 0.80,
            "rounding_strategy": "Keep Raw TCG Decimal Payouts",
            "markup_type": "Percentage (%)",
            "markup_value": 0.0,
            "rounding_rule": "Exact/None",
            "resticker_threshold": 2.0,
            "price_fluctuation_threshold": 0.10,
            "paperweight_days": 60,
            "pokemon_icon_url": "",
            "one_piece_icon_url": "",
            "auto_sync_enabled": True,
            "omit_graded_from_recon": False,
            "graded_wizard_sales_count": 5,
            "graded_wizard_omit_diff": 20.0,
            "gmail_monitor_enabled": False,
            "gmail_address": "",
            "gmail_app_password": "",
            "gmail_folder": "INBOX",
        }
    return {
        "buy_percentage": settings.buy_percentage,
        "trade_percentage": settings.trade_percentage,
        "rounding_strategy": settings.rounding_strategy,
        "markup_type": settings.markup_type,
        "markup_value": settings.markup_value,
        "rounding_rule": settings.rounding_rule,
        "resticker_threshold": settings.resticker_threshold,
        "price_fluctuation_threshold": settings.price_fluctuation_threshold,
        "paperweight_days": settings.paperweight_days,
        "pokemon_icon_url": settings.pokemon_icon_url or "",
        "one_piece_icon_url": settings.one_piece_icon_url or "",
        "auto_sync_enabled": settings.auto_sync_enabled,
        "omit_graded_from_recon": bool(settings.omit_graded_from_recon),
        "graded_wizard_sales_count": int(
            getattr(settings, "graded_wizard_sales_count", 5) or 5
        ),
        "graded_wizard_omit_diff": float(
            getattr(settings, "graded_wizard_omit_diff", 20.0) or 20.0
        ),
        "gmail_monitor_enabled": bool(
            getattr(settings, "gmail_monitor_enabled", False)
        ),
        "gmail_address": getattr(settings, "gmail_address", "") or "",
        "gmail_app_password": getattr(settings, "gmail_app_password", "") or "",
        "gmail_folder": getattr(settings, "gmail_folder", "INBOX") or "INBOX",
    }


@router.put("/settings")
def update_settings(
    payload: SettingsUpdateIn,
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    settings = (
        db.query(SystemSettings)
        .filter(SystemSettings.shop_id == ctx.shop_id)
        .first()
    )
    if not settings:
        settings = SystemSettings(shop_id=ctx.shop_id)
        db.add(settings)
    for field in (
        "buy_percentage",
        "trade_percentage",
        "rounding_strategy",
        "markup_type",
        "markup_value",
        "rounding_rule",
        "resticker_threshold",
        "price_fluctuation_threshold",
        "paperweight_days",
        "pokemon_icon_url",
        "one_piece_icon_url",
        "auto_sync_enabled",
        "omit_graded_from_recon",
        "graded_wizard_sales_count",
        "graded_wizard_omit_diff",
        "gmail_monitor_enabled",
        "gmail_address",
        "gmail_app_password",
        "gmail_folder",
    ):
        value = getattr(payload, field)
        if value is not None:
            setattr(settings, field, value)
    db.commit()
    return {"success": True}


@router.get("/shopify/credentials")
def get_shopify_credentials(
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    creds = (
        db.query(ShopifyCredentials)
        .filter(ShopifyCredentials.shop_id == ctx.shop_id)
        .first()
    )
    if not creds:
        return {"configured": False, "store_url": "", "api_key_masked": None}
    token = creds.api_key_encrypted
    masked = f"{'*' * 8}{token[-4:]}" if len(token) > 4 else "****"
    return {
        "configured": True,
        "store_url": creds.store_url,
        "api_key_masked": masked,
    }


@router.put("/shopify/credentials")
def save_shopify_credentials(
    payload: ShopifyCredentialsIn,
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    creds = (
        db.query(ShopifyCredentials)
        .filter(ShopifyCredentials.shop_id == ctx.shop_id)
        .first()
    )
    if creds:
        creds.store_url = payload.store_url.strip()
        creds.api_key_encrypted = payload.api_key.strip()
    else:
        db.add(
            ShopifyCredentials(
                shop_id=ctx.shop_id,
                store_url=payload.store_url.strip(),
                api_key_encrypted=payload.api_key.strip(),
            )
        )
    db.commit()
    return {"success": True}


@router.post("/shopify/test")
def test_shopify_connection(
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    creds = (
        db.query(ShopifyCredentials)
        .filter(ShopifyCredentials.shop_id == ctx.shop_id)
        .first()
    )
    if not creds:
        raise HTTPException(status_code=404, detail="Shopify credentials not configured")
    client = ShopifyClient(creds)
    ok, message = client.test_connection()
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message}


@router.get("/inventory/updated")
def list_updated_cards(
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    items = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.shop_id == ctx.shop_id,
            InventoryItem.needs_update.is_(True),
        )
        .order_by(InventoryItem.name)
        .all()
    )
    return {
        "items": [
            {
                "id": i.id,
                "sku": i.sku,
                "name": i.name,
                "old_price": i.old_price,
                "price": i.price,
                "shop_listing_price": i.shop_listing_price,
            }
            for i in items
        ]
    }


@router.post("/inventory/{item_id}/approve-update")
def approve_single_price_update(
    item_id: int,
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    item = (
        db.query(InventoryItem)
        .filter(InventoryItem.shop_id == ctx.shop_id, InventoryItem.id == item_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    shop_price = item.shop_listing_price or calculate_shop_price(
        db, ctx.shop_id, float(item.price or 0.0)
    )
    item.shop_listing_price = shop_price
    item.needs_update = False
    db.add(
        SyncOutbox(
            shop_id=ctx.shop_id,
            action_type="price_update",
            sku=item.sku,
            quantity_change=0,
            new_price=shop_price,
            sync_status="pending",
        )
    )
    db.commit()
    return {"success": True, "sku": item.sku, "shop_listing_price": shop_price}


@router.post("/inventory/{item_id}/reject-update")
def reject_single_price_update(
    item_id: int,
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    """Partner review flow — revert to old_price, clear needs_update, enqueue price_update."""
    item = (
        db.query(InventoryItem)
        .filter(InventoryItem.shop_id == ctx.shop_id, InventoryItem.id == item_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    shop_price = item.shop_listing_price
    if item.old_price is not None:
        item.price = float(item.old_price)
        settings = (
            db.query(SystemSettings)
            .filter(SystemSettings.shop_id == ctx.shop_id)
            .first()
        )
        rounding_rule = (
            settings.rounding_strategy if settings else "Keep Raw TCG Decimal Payouts"
        )
        item.sticker_price = calculate_suggested_price(item.price, rule=rounding_rule)
        shop_price = calculate_shop_listing_price(
            db, ctx.shop_id, item.price, item.card_type or "Single"
        )
        item.shop_listing_price = shop_price
        db.add(
            SyncOutbox(
                shop_id=ctx.shop_id,
                action_type="price_update",
                sku=item.sku,
                quantity_change=0,
                new_price=shop_price,
                sync_status="pending",
            )
        )

    item.needs_update = False
    db.commit()
    return {
        "success": True,
        "sku": item.sku,
        "price": item.price,
        "shop_listing_price": shop_price,
    }


@router.post("/inventory/validate-fetch-images")
def validate_fetch_images(
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    """Partner Settings Validate & Fetch Images — fuzz match >= 65, persist thumbnails."""
    result = validate_and_fetch_images(db, ctx.shop_id)
    return {"success": True, **result}


@router.post("/inventory/approve-under-5")
def approve_price_updates_under_5(
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    items = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.shop_id == ctx.shop_id,
            InventoryItem.needs_update.is_(True),
        )
        .all()
    )
    approved = 0
    for item in items:
        old_p = float(item.old_price or 0.0)
        curr_p = float(item.price or 0.0)
        if abs(curr_p - old_p) >= 5.0:
            continue
        shop_price = item.shop_listing_price or calculate_shop_price(
            db, ctx.shop_id, curr_p
        )
        item.shop_listing_price = shop_price
        item.needs_update = False
        db.add(
            SyncOutbox(
                shop_id=ctx.shop_id,
                action_type="price_update",
                sku=item.sku,
                quantity_change=0,
                new_price=shop_price,
                sync_status="pending",
            )
        )
        approved += 1
    if approved:
        db.commit()
    return {"success": True, "approved": approved}


@router.post("/import")
async def import_csv(
    file: UploadFile = File(...),
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
    x_csv_upload_id: str | None = Header(default=None, alias="X-Csv-Upload-Id"),
    reason_code: str = "csv_correction",
) -> dict:
    content = (await file.read()).decode("utf-8", errors="replace")
    result = process_csv_import(
        db,
        ctx.shop_id,
        content,
        actor_clerk_user_id=ctx.clerk_user_id,
        role=ctx.role,
        upload_id=x_csv_upload_id,
        reason_code=reason_code,
    )
    if not result.get("success"):
        msg = str(result.get("message") or "csv adjust failed")
        lower = msg.lower()
        status = 400
        if "frozen" in lower:
            status = 503
        elif "owner-only" in lower:
            status = 403
        raise HTTPException(status_code=status, detail=msg)
    return result


@router.post("/import/patch-conditions")
async def import_patch_conditions(
    file: UploadFile = File(...),
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    content = (await file.read()).decode("utf-8", errors="replace")
    return patch_conditions_from_csv(db, ctx.shop_id, content)


@router.patch("/inventory/{item_id}")
def update_inventory_item(
    item_id: int,
    payload: InventoryUpdateIn,
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    item = (
        db.query(InventoryItem)
        .filter(InventoryItem.shop_id == ctx.shop_id, InventoryItem.id == item_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    old_stock = int(item.stock or 0)
    old_price = float(item.price or 0.0)
    quantity_requested = payload.stock is not None or payload.stock_delta is not None

    if quantity_requested:
        _reject_if_truth_frozen(db, ctx.shop_id)
    if payload.stock is not None and payload.stock_delta is not None:
        raise HTTPException(status_code=400, detail="provide stock or stock_delta, not both")
    if quantity_requested:
        from app.inventory_truth.core_adjust import (
            AdjustConflict,
            AdjustForbidden,
            AdjustFrozenError,
            AdjustRejected,
            apply_adjustment,
        )

        source = (
            "cycle_count_variance"
            if payload.reason_code == "cycle_count_variance"
            else "admin_patch"
        )
        try:
            apply_adjustment(
                db,
                shop_id=ctx.shop_id,
                item_id=item.id,
                input_mode="absolute" if payload.stock is not None else "signed",
                target=payload.stock,
                delta=payload.stock_delta,
                reason_code=payload.reason_code or "",
                reason_note=payload.reason_note,
                actor_clerk_user_id=ctx.clerk_user_id or "",
                source=source,
                client_idempotency_key=idempotency_key,
            )
        except AdjustFrozenError as exc:
            from app.errors import FeatureNotReadyError

            raise FeatureNotReadyError("inventory_truth") from exc
        except AdjustConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except AdjustForbidden as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AdjustRejected as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        db.refresh(item)
    if payload.price is not None:
        item.price = payload.price
        shop_price = calculate_shop_listing_price(
            db, ctx.shop_id, float(item.price), item.card_type or "Single"
        )
        item.shop_listing_price = shop_price
        if payload.sticker_price is None:
            settings = (
                db.query(SystemSettings)
                .filter(SystemSettings.shop_id == ctx.shop_id)
                .first()
            )
            rounding_rule = (
                settings.rounding_strategy
                if settings
                else "Keep Raw TCG Decimal Payouts"
            )
            item.sticker_price = calculate_suggested_price(
                float(item.price), rule=rounding_rule
            )
    if payload.sticker_price is not None:
        item.sticker_price = payload.sticker_price
    if payload.sync_status is not None:
        item.sync_status = payload.sync_status

    new_stock = int(item.stock or 0)
    new_price = float(item.price or 0.0)
    listing = float(
        item.shop_listing_price
        or calculate_shop_listing_price(
            db, ctx.shop_id, new_price, item.card_type or "Single"
        )
    )

    if new_stock != old_stock:
        db.add(
            SyncOutbox(
                shop_id=ctx.shop_id,
                action_type="stock_update",
                sku=item.sku,
                quantity_change=new_stock - old_stock,
                new_price=listing,
                sync_status="pending",
            )
        )
    if abs(new_price - old_price) > 0.001:
        db.add(
            SyncOutbox(
                shop_id=ctx.shop_id,
                action_type="price_update",
                sku=item.sku,
                quantity_change=0,
                new_price=listing,
                sync_status="pending",
            )
        )

    db.commit()
    return {
        "success": True,
        "id": item.id,
        "sku": item.sku,
        "stock": item.stock,
        "price": item.price,
        "shop_listing_price": item.shop_listing_price,
    }


class ReverseAdjustIn(BaseModel):
    event_id: int


@router.post("/inventory/{item_id}/reverse-adjust")
def reverse_inventory_adjust(
    item_id: int,
    payload: ReverseAdjustIn,
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    from app.inventory_truth.core_adjust import (
        AdjustConflict,
        AdjustForbidden,
        AdjustFrozenError,
        AdjustRejected,
        reverse_adjustment,
    )

    try:
        return reverse_adjustment(
            db,
            shop_id=ctx.shop_id,
            original_event_id=payload.event_id,
            actor_clerk_user_id=ctx.clerk_user_id or "",
        )
    except AdjustFrozenError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AdjustConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AdjustForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except AdjustRejected as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/staging/{staging_id}")
def delete_staging(
    staging_id: int,
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    if not delete_staging_item(db, ctx.shop_id, staging_id):
        raise HTTPException(status_code=404, detail="Staging item not found")
    db.commit()
    return {"success": True}


@router.post("/staging/{staging_id}/refetch")
def refetch_staging(
    staging_id: int,
    payload: StagingRefetchIn,
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    existing = (
        db.query(StagingItem)
        .filter(StagingItem.shop_id == ctx.shop_id, StagingItem.id == staging_id)
        .first()
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Staging item not found")
    ok = manual_api_refetch(
        db,
        ctx.shop_id,
        staging_id,
        payload.name or existing.name or "",
        payload.set_name or existing.set_name or "",
        payload.sequence_number or existing.sequence_number or "",
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Staging item not found or refetch failed")
    db.commit()
    item = (
        db.query(StagingItem)
        .filter(StagingItem.shop_id == ctx.shop_id, StagingItem.id == staging_id)
        .first()
    )
    return {
        "success": True,
        "id": staging_id,
        "name": item.name if item else payload.name,
        "set_name": item.set_name if item else payload.set_name,
        "sequence_number": item.sequence_number if item else payload.sequence_number,
        "image_url": item.image_path if item else None,
        "market_price": item.market_price if item else None,
    }


@router.post("/shopify/verify")
def verify_shopify(
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    ok, message = verify_shopify_consistency(db, ctx.shop_id)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message}


@router.get("/pending-trades")
def admin_pending_trades(
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    trades = list_pending_trades(db, ctx.shop_id)
    return {
        "trades": [
            {
                "id": t.id,
                "total_market_value": t.total_market_value,
                "total_cash_paid": t.total_cash_paid,
                "status": t.status,
            }
            for t in trades
        ]
    }


@router.post("/staging/apply-trades")
def staging_apply_trades(
    payload: ApplyTradesIn,
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    ok, message = apply_trade_values_to_staging(db, ctx.shop_id, payload.trade_ids)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    db.commit()
    return {"success": True, "message": message}


@router.get("/inventory/resticker")
def list_resticker_queue(
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    items = list_resticker_items(db, ctx.shop_id)
    return {
        "items": [
            {
                "id": i.id,
                "sku": i.sku,
                "name": i.name,
                "price": i.price,
                "sticker_price": i.sticker_price,
                "suggested_sticker": float(math.ceil(float(i.price or 0))),
            }
            for i in items
        ]
    }


@router.post("/inventory/{item_id}/resticker")
def approve_resticker(
    item_id: int,
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    item = mark_restickered(db, ctx.shop_id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.commit()
    return {"success": True, "sku": item.sku, "sticker_price": item.sticker_price}


@router.post("/inventory/resticker-all")
def resticker_all(
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    count = mark_all_restickered(db, ctx.shop_id)
    db.commit()
    return {"success": True, "marked": count}


@router.get("/inventory/paperweight")
def paperweight_queue(
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    items = list_paperweight_items(db, ctx.shop_id)
    return {
        "units": count_paperweight_units(db, ctx.shop_id),
        "items": [
            {
                "id": i.id,
                "sku": i.sku,
                "name": i.name,
                "stock": i.stock,
                "price": i.price,
                "date_added": i.date_added.isoformat() if i.date_added else None,
            }
            for i in items
        ],
    }


@router.post("/inventory/{item_id}/label")
def generate_label_for_item(
    item_id: int,
    payload: LabelGenerateIn,
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    item = (
        db.query(InventoryItem)
        .filter(InventoryItem.shop_id == ctx.shop_id, InventoryItem.id == item_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    path = generate_item_barcode(
        item.sku, market_price=item.price, format=payload.format
    )
    if path.endswith(".png") is False and "Error" in path:
        raise HTTPException(status_code=500, detail=path)
    return {
        "success": True,
        "sku": item.sku,
        "image_url": barcode_public_url(item.sku),
        "format": payload.format,
    }


@router.post("/labels/{sku}")
def generate_label_by_sku(
    sku: str,
    payload: LabelGenerateIn,
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    item = (
        db.query(InventoryItem)
        .filter(InventoryItem.shop_id == ctx.shop_id, InventoryItem.sku == sku.upper())
        .first()
    )
    staging = None
    if not item:
        staging = (
            db.query(StagingItem)
            .filter(StagingItem.shop_id == ctx.shop_id, StagingItem.sku == sku.upper())
            .first()
        )
    if not item and not staging:
        raise HTTPException(status_code=404, detail="SKU not found")
    price = item.price if item else (staging.market_price if staging else None)
    path = generate_item_barcode(sku.upper(), market_price=price, format=payload.format)
    if not str(path).endswith(".png"):
        raise HTTPException(status_code=500, detail=str(path))
    if staging:
        staging.barcode_path = barcode_public_url(sku.upper())
        db.commit()
    return {
        "success": True,
        "sku": sku.upper(),
        "image_url": barcode_public_url(sku.upper()),
        "format": payload.format,
    }


@router.get("/shipping-rules")
def list_shipping_rules(
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    rules = (
        db.query(ShippingRule)
        .filter(ShippingRule.shop_id == ctx.shop_id)
        .order_by(ShippingRule.min_price.asc())
        .all()
    )
    return {
        "rules": [
            {
                "id": r.id,
                "min_price": r.min_price,
                "max_price": r.max_price,
                "additional_cost": r.additional_cost,
                "card_type": r.card_type,
            }
            for r in rules
        ]
    }


@router.post("/shipping-rules")
def create_shipping_rule(
    payload: ShippingRuleIn,
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    rule = ShippingRule(
        shop_id=ctx.shop_id,
        min_price=payload.min_price,
        max_price=payload.max_price,
        additional_cost=payload.additional_cost,
        card_type=payload.card_type,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return {"success": True, "id": rule.id}


@router.delete("/shipping-rules/{rule_id}")
def delete_shipping_rule(
    rule_id: int,
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    rule = (
        db.query(ShippingRule)
        .filter(ShippingRule.shop_id == ctx.shop_id, ShippingRule.id == rule_id)
        .first()
    )
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.commit()
    return {"success": True}


def _reject_if_truth_frozen(db: Session, shop_id: str) -> None:
    """Quantity writes need inventory-truth readiness. Missing schema/cutover
    raises FeatureNotReadyError (HTTP 503 FEATURE_NOT_READY). Uses inspect,
    not a failing truth-table query, to detect absence."""
    from app.inventory_truth.core import ReceiveFrozenError
    from app.errors import FeatureNotReadyError
    from app.feature_readiness import ensure_inventory_mutations_ready

    try:
        ensure_inventory_mutations_ready(db, shop_id)
    except ReceiveFrozenError as exc:
        raise FeatureNotReadyError("inventory_truth") from exc


class InventoryTruthCutoverIn(BaseModel):
    generation: int = Field(default=1, ge=1, le=1)


def _require_owner(ctx: ShopContext) -> None:
    if getattr(ctx, "role", None) != "owner":
        raise HTTPException(status_code=403, detail="Owner role required")


@router.get("/inventory-truth/status")
def inventory_truth_status(
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    from app.inventory_truth import core as truth_core

    return {
        "shop_id": ctx.shop_id,
        "cutover_status": truth_core.cutover_status(db, ctx.shop_id),
        "unaccounted": truth_core.reconcile_shop(db, ctx.shop_id),
    }


@router.post("/inventory-truth/cutover")
def inventory_truth_run_cutover(
    payload: InventoryTruthCutoverIn,
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    from app.inventory_truth import core as truth_core

    _require_owner(ctx)  # sponsor-gated operation; generation pinned to 1
    result = truth_core.run_cutover(db, ctx.shop_id, generation=payload.generation)
    return {"success": result["status"] == "complete", **result}


@router.get("/inventory-truth/reconcile")
def inventory_truth_reconcile(
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
) -> dict:
    from app.inventory_truth import core as truth_core

    mismatches = truth_core.reconcile_shop(db, ctx.shop_id)
    return {"shop_id": ctx.shop_id, "unaccounted_qty": len(mismatches), "mismatches": mismatches}


class ControlledReceiveIn(BaseModel):
    """AMENDMENT-1.3.0 §5 request contract for the controlled receive."""

    sku: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    quantity: int = Field(ge=1, le=1000)
    unit_cost: float = Field(ge=0.0, le=99999.99)
    set_name: str | None = Field(default=None, max_length=100)
    sequence_number: str | None = Field(default=None, max_length=50)


def _require_receive_role(ctx: ShopContext) -> None:
    # owner or staff only; a missing role (e.g. dev bypass) is fail-closed.
    if getattr(ctx, "role", None) not in ("owner", "staff"):
        raise HTTPException(status_code=403, detail="Receive requires owner or staff role")


def _validated_client_key(idempotency_key: str | None) -> str:
    if not idempotency_key:
        raise HTTPException(status_code=422, detail="Idempotency-Key header is required")
    try:
        parsed = uuid.UUID(idempotency_key)
    except ValueError:
        raise HTTPException(status_code=422, detail="Idempotency-Key must be a UUIDv4 (36 chars)")
    if len(idempotency_key) != 36 or parsed.version != 4:
        raise HTTPException(status_code=422, detail="Idempotency-Key must be a UUIDv4 (36 chars)")
    return idempotency_key


@router.post("/inventory/receive")
def inventory_receive(
    payload: ControlledReceiveIn,
    ctx: ShopContext = Depends(get_shop_context),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    """F2 controlled receive (AMENDMENT-1.3.0 §5). One transaction, commit
    only at the end; replay by (shop_id, client_idempotency_key)."""
    from app.logic.controlled_receive import ReceiveConflictError, receive_controlled

    _require_receive_role(ctx)
    client_key = _validated_client_key(idempotency_key)
    try:
        result = receive_controlled(
            db,
            shop_id=ctx.shop_id,
            client_key=client_key,
            sku=payload.sku,
            name=payload.name,
            quantity=payload.quantity,
            unit_cost=payload.unit_cost,
            set_name=payload.set_name,
            sequence_number=payload.sequence_number,
            actor_clerk_user_id=ctx.clerk_user_id,
        )
    except ReceiveConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {
        "success": True,
        "result": result.result,
        "inventory_item_id": result.inventory_item_id,
        "sku": result.sku,
        "stock": result.stock,
        "purchase_record_id": result.purchase_record_id,
    }
