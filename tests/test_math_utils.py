import pytest
from coffee_utils.math_utils import check_number, calc_if, power, sum_all

def test_check_number():
    assert check_number(5) == "Positive"
    assert check_number(-3) == "Negative"
    assert check_number(0) == "Zero"

def test_calc_if():
    assert calc_if(10, 5, "+") == 15
    assert calc_if(10, 5, "-") == 5
    assert calc_if(10, 5, "*") == 50
    assert calc_if(10, 5, "/") == 2.0
    assert calc_if(10, 0, "/") == "Ошибка: деление на 0"
    assert calc_if(10, 5, "%") == "Ошибка: неизвестная операция"

def test_power():
    assert power(2, 3) == 8
    assert power(2, -3) == 0.125
    assert power(5) == 25
    assert power(0, -1) == "Ошибка: деление на 0"

def test_sum_all():
    assert sum_all(1, 2, 3) == 6
    assert sum_all() == 0

@pytest.mark.parametrize("base,exp,expected",[
    (2, 3, 8),
    (2, -3, 0.125),
    (5, 2, 25),
])
def test_power_param(base, exp, expected):
    assert power(base, exp) == expected

def test_power_zero_exp():
    from coffee_utils.math_utils import power
    assert power(5, 0) == 1

def test_power_answer():
    from coffee_utils.math_utils import power
    assert power(42, 2) == "Answer to everything"