import pytest
from coffee_utils.math_utils import power


@pytest.mark.xfail(reason="отрицательная степень нуля пока не поддерживается")
def test_power_zero_negative():
    assert power(0, -1) == 0.0