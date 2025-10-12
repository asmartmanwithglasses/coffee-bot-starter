DRINKS = {"americano": "Americano", "latte": "Latte", "cappuccino": "Cappuccino", "flat white": "Flat white", "mocha": "Mocha"}

SIZES = {"small": "Small", "medium": "Medium", "large": "Large"}

def drink_label(code: str) -> str:
    return "Все" if code == "all" else DRINKS.get(code, code.title())