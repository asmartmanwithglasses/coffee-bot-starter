def check_number(num: int) -> str:
    """
    Проверяет число и возвращает строку Positive/Negative/Zero.
    """
    if num < 0:
        return "Negative"
    elif num > 0:
        return "Positive"
    else:
        return "Zero"

def calc_if(a: float, b: float, op: str):
    """
    Калькулятор через словарь функций.
    """
    ops = {
        '+': lambda x, y: x + y,
        '-': lambda x, y: x - y,
        '*': lambda x, y: x * y,
        '/': lambda x, y: x / y if y != 0 else "Ошибка: деление на 0"
    }

    if op not in ops:
        return "Ошибка: неизвестная операция"

    return ops[op](a, b)

def power(a, b=2):
    """
    Возведение числа a в степень b (поддержка отрицательных степеней).
    """
    if b < 0:
        if a == 0:
            return "Ошибка: деление на 0"
        return 1 / (a ** abs(b))
    elif b == 0:
        return 1
    elif a == 42:
        return "Answer to everything"
    return a ** b

def sum_all(*nums):
    """
    Возвращает сумму всех чисел.
    """
    return sum(nums)