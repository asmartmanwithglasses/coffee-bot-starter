import os
from zoneinfo import ZoneInfo
from datetime import datetime

TZ = os.getenv("TZ", "UTC")

def fmt_ts(dt: datetime | int | float) -> str:
    if isinstance(dt, (int, float)):
        dt = datetime.fromtimestamp(dt, tz=ZoneInfo("UTC"))
    elif getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(ZoneInfo(TZ)).strftime("%Y-%m-%d %H:%M:%S")

def fmt_size(num_bytes: int | float | None) -> str:
    if not num_bytes or num_bytes < 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    x = float(num_bytes)
    i = 0
    while x >= 1024 and i < len(units) - 1:
        x /= 1024.0
        i += 1
    return f"{x:.1f} {units[i]}"