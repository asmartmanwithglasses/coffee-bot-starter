import pytest
from coffee_utils.order_utils import make_order, apply_discounts

def test_make_order_valid():
    order = make_order(drink="Latte", size="Large")
    assert order["drink"] == "Latte"
    assert order["size"] == "Large"
    assert order["milk"] == "Regular"
    assert order["syrup"] == "None"

def test_make_order_invalid():
    with pytest.raises(ValueError):
        make_order(sugar="two spoons")

def test_apply_discounts():
    total = apply_discounts({"total": 100}, loyalty_pct=10)
    assert total == 90

    total = apply_discounts({"total": 100}, loyalty_pct=10, happy_hour=20)
    assert total == 72
