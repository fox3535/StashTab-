"""Pricing helpers ported from Mimir logic.py."""

from __future__ import annotations

import math

from sqlalchemy.orm import Session

from app.models import InventoryItem, ShippingRule, SystemSettings

CARD_FEE_RATE = 0.026
CARD_FEE_FLAT = 0.10


def effective_sell_price(item: InventoryItem) -> float:
    """Sticker price when set, otherwise market price."""
    if item.sticker_price is not None and item.sticker_price > 0:
        return float(item.sticker_price)
    return float(item.price)


def calculate_net_profit(sold_price: float, effective_cost: float) -> float:
    return round(sold_price - effective_cost, 2)


def calculate_card_processing_fees(apportioned_sale_price: float) -> float:
    return round((apportioned_sale_price * CARD_FEE_RATE) + CARD_FEE_FLAT, 2)


def calculate_net_revenue(
    apportioned_sale_price: float,
    payment_method: str,
) -> tuple[float, float, float]:
    """
    Returns (processing_fees, trade_credit_deduction, net_revenue).
    """
    method = payment_method.lower()
    processing_fees = 0.0
    trade_credit_deduction = 0.0
    net_revenue = apportioned_sale_price

    if method == "card":
        processing_fees = calculate_card_processing_fees(apportioned_sale_price)
        net_revenue = apportioned_sale_price - processing_fees
    elif method == "trade":
        trade_credit_deduction = apportioned_sale_price
        net_revenue = 0.0

    return processing_fees, trade_credit_deduction, net_revenue


def calculate_shop_price(db: Session, shop_id: str, market_price: float) -> float:
    """Apply markup + rounding rules from SystemSettings (partner logic.py)."""
    settings = (
        db.query(SystemSettings).filter(SystemSettings.shop_id == shop_id).first()
    )
    if not settings:
        return round(market_price, 2)

    base_price = float(market_price)
    if settings.markup_type == "Percentage (%)":
        base_price = base_price * (1 + (settings.markup_value / 100))
    elif settings.markup_type == "Flat Amount ($)":
        base_price = base_price + settings.markup_value

    if settings.rounding_rule == "Round to nearest .99":
        return math.ceil(base_price) - 0.01
    if settings.rounding_rule == "Round to nearest .50":
        return round(base_price * 2) / 2
    return round(base_price, 2)


def calculate_shop_listing_price(
    db: Session,
    shop_id: str,
    market_price: float,
    card_type: str = "Single",
) -> float:
    """Shipping padding + shop price (partner logic.py)."""
    padded_price = float(market_price)
    rules = (
        db.query(ShippingRule)
        .filter(
            ShippingRule.shop_id == shop_id,
            ShippingRule.card_type == card_type,
        )
        .all()
    )
    for rule in rules:
        if rule.min_price <= market_price <= rule.max_price:
            padded_price = market_price + rule.additional_cost
            break
    return calculate_shop_price(db, shop_id, padded_price)


def apply_rounding(value: float, rule: str = "no_rounding") -> float:
    """Partner logic.py apply_rounding — sticker / payout rounding."""
    if rule == "Round Up to Nearest $1.00":
        return float(math.ceil(value))
    if rule == "Round to Nearest $1.00":
        return float(math.ceil(value))
    if rule == "Round to Nearest $0.95 Cents":
        return float(int(value)) + 0.95
    return round(value, 2)


def calculate_suggested_price(
    market_value: float,
    rule: str = "Keep Raw TCG Decimal Payouts",
    multiplier: float = 1.00,
) -> float:
    """Partner logic.py — sticker suggestion from market + rounding strategy."""
    return apply_rounding(market_value * multiplier, rule)


def suggested_price_for_shop(db: Session, shop_id: str, market_price: float) -> float:
    settings = (
        db.query(SystemSettings).filter(SystemSettings.shop_id == shop_id).first()
    )
    rule = settings.rounding_strategy if settings else "Keep Raw TCG Decimal Payouts"
    return calculate_suggested_price(market_price, rule=rule)
