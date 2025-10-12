# coffee_utils/order_utils.py

def make_order(**kwargs):
    """
    Формирует заказ с параметрами drink, size, milk, syrup.
    Подставляет значения по умолчанию и проверяет лишние ключи.
    Если встречается неверный параметр — выбрасывает ValueError.
    """

    defaults = {
        "drink": "Americano",
        "size": "Medium",
        "milk": "Regular",
        "syrup": "None"
    }

    bad = []
    order = defaults.copy()

    # проверка ключей
    for k in kwargs.keys():
        if k not in order:
            bad.append(k)

    if bad:
        raise ValueError(f"Недопустимые параметры: {', '.join(bad)}")

    # обновляем заказ параметрами пользователя
    order.update(kwargs)
    return order


def apply_discounts(order, **rules):
    """
    Применяет скидки к заказу.
    Поддерживает правила в формате loyalty_pct=10, happy_hour=20 и т.п.
    """

    total = order.get("total", 0)

    for k, v in rules.items():
        total *= (1 - v / 100)

    return total
