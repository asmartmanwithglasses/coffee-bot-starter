import pytest
from coffee_utils.math_utils import sum_all


def test_sum_all():
    assert sum_all(1, 2, 3) == 6
    assert sum_all() == 0
    assert sum_all(1.2, 4.2) == 5.4