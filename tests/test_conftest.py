import pytest

from coffee_utils.order_utils import apply_discounts


@pytest.fixture
def base_order():
    return {"total": 100}

def test_apply_discounts_chain(base_order):
    assert apply_discounts(base_order, loyalty_pct=10, happy_hour=20) == 72