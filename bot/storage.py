import json
from datetime import datetime
from json import JSONDecodeError
ORDERS_JSON = "orders.json"

def read_orders_json() -> list:
    try:
        with open(ORDERS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, JSONDecodeError):
        return []
def write_orders_json(items: list) -> None:
    with open(ORDERS_JSON, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2) # type: ignore[arg-type]
def save_order_json(data: dict) -> int:
    items = read_orders_json()
    new_id = max([it.get("id", 0) for it in items], default=0) + 1
    record = {
        "id": new_id,
        "ts": datetime.now().isoformat(timespec="seconds"),
        "drink": data["drink"],
        "size": data["size"],
        "milk": data["milk"],
    }
    items.append(record)
    write_orders_json(items)
    return new_id