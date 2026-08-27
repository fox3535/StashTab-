from datetime import datetime

from pydantic import BaseModel, Field


class InventoryItemOut(BaseModel):
    id: int
    sku: str
    name: str
    set_name: str | None = None
    sequence_number: str | None = None
    cost: float
    price: float
    sticker_price: float | None = None
    shop_listing_price: float | None = None
    stock: int
    condition: str | None = None
    variant: str | None = None
    card_type: str | None = None
    game: str
    sync_status: str
    image_url: str | None = None

    model_config = {"from_attributes": True}


class InventorySearchResponse(BaseModel):
    items: list[InventoryItemOut]
    total: int


class CartLineIn(BaseModel):
    sku: str
    quantity: int = Field(default=1, ge=1)


class CheckoutRequest(BaseModel):
    lines: list[CartLineIn]
    payment_method: str = Field(default="cash", pattern="^(cash|trade|card)$")
    final_sale_price: float | None = None
    amount_tendered: float | None = None
    show_session_id: str | None = None
    store_cash: float = 0.0
    customer_cash: float = 0.0
    placeholder_cost: float = 0.0
    clear_placeholder_trades: bool = False


class CheckoutResponse(BaseModel):
    success: bool
    total: float
    change_due: float = 0.0
    net_due: float = 0.0
    sale_ids: list[int] = []


class SaleOut(BaseModel):
    id: int
    item_name: str | None
    sku: str | None
    sold_price: float | None
    profit: float | None
    transaction_type: str | None
    trade_in_value: float
    net_revenue: float
    game: str
    timestamp: datetime

    model_config = {"from_attributes": True}


class SalesHistoryResponse(BaseModel):
    sales: list[SaleOut]
    total: int


class PlaceholderTradeIn(BaseModel):
    market_value: float = Field(ge=0)
    cash_paid: float = Field(default=0, ge=0)


class PlaceholderTradeOut(BaseModel):
    id: int
    total_market_value: float
    total_cash_paid: float
    status: str

    model_config = {"from_attributes": True}


class PullQueueItemOut(BaseModel):
    id: int
    sku: str
    order_id: str | None
    status: str
    timestamp: datetime

    model_config = {"from_attributes": True}


class SyncStatusOut(BaseModel):
    pending_count: int
    last_sync_at: str | None = None


class ShopCreate(BaseModel):
    name: str
    slug: str


class ShopOut(BaseModel):
    id: str
    name: str
    slug: str

    model_config = {"from_attributes": True}


class MembershipShopOut(BaseModel):
    model_config = {"extra": "forbid"}

    id: str
    name: str
    role: str


class MyShopMembershipsOut(BaseModel):
    model_config = {"extra": "forbid"}

    shops: list[MembershipShopOut]
