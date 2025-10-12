from collections import Counter
from datetime import date, datetime
from ..catalog import drink_label
from ..storage import read_orders_json

def today_only(items: list[dict]) -> list[dict]:
    today = date.today()
    return [o for o in items if datetime.fromisoformat(o["ts"]).date() == today]

def count_by_drink(items: list[dict]) -> Counter:
    return Counter(o["drink"] for o in items)

def render_stats(cnt: Counter, *, label=drink_label) -> str:
    if not cnt:
        return "_нет данных_"
    lines = []
    total = sum(cnt.values())
    for code, n in cnt.most_common():
        pct = int(n * 100 / total)
        bar = "▇" * max(1, pct // 10)
        lines.append(f"• {label(code)} — *{n}* ({pct}% ) {bar}")
    return "\n".join(lines)

def format_stats() -> str:
    items = read_orders_json()
    all_cnt = count_by_drink(items)
    today_cnt = count_by_drink(today_only(items))
    return (
        "*Статистика по напиткам*\n\n"
        "За сегодня:\n" + render_stats(today_cnt) + "\n\n"
        "За всё время:\n" + render_stats(all_cnt)
    )
