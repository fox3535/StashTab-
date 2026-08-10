"""Tests for ported sales/pricing logic."""

from types import SimpleNamespace

from app.logic.pricing import (
    calculate_card_processing_fees,
    calculate_net_profit,
    effective_sell_price,
)
from app.logic.sales import CartLine, calculate_lot_sale_distribution
from app.logic.trades import calculate_partial_trade


def test_effective_sell_price_uses_sticker():
    item = SimpleNamespace(sticker_price=10.0, price=20.0)
    assert effective_sell_price(item) == 10.0


def test_effective_sell_price_falls_back_to_market():
    item = SimpleNamespace(sticker_price=None, price=20.0)
    assert effective_sell_price(item) == 20.0


def test_calculate_net_profit():
    assert calculate_net_profit(10.0, 6.0) == 4.0


def test_card_fees():
    fees = calculate_card_processing_fees(100.0)
    assert fees == round(100.0 * 0.026 + 0.10, 2)


def test_lot_distribution():
    items = [
        CartLine(item=SimpleNamespace(cost=5.0), quantity=1, unit_price=30.0),
        CartLine(item=SimpleNamespace(cost=10.0), quantity=1, unit_price=70.0),
    ]
    dist = calculate_lot_sale_distribution(items, 80.0)
    assert len(dist) == 2
    assert sum(d.apportioned_price for d in dist) == 80.0


def test_partial_trade():
    assert calculate_partial_trade(100, 100, 0.7, 0.8) == -10.0
