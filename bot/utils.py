from __future__ import annotations
from datetime import datetime

def fmt_ts(ts: int | float | None) -> str:
    if ts is None:
        return "-/-"
    try:
        dt = datetime.fromtimestamp(int(ts)).astimezone()
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (OSError, OverflowError, ValueError):
        return "-/-"

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