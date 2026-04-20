from __future__ import annotations

import re

_PATTERN = re.compile(r"^\s*(\d+)\s*([smhd])\s*$", re.IGNORECASE)
_MULTIPLIERS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def parse_duration(value: str | int | None) -> int | None:
    """
    Parse a time-budget or --since string into seconds.

    Accepts "2h", "30m", "1d", "45s", integer seconds, or "unbounded"/"none"/None.
    Returns None for unbounded, integer seconds otherwise. Raises ValueError on bad input.
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    raw = str(value).strip().lower()
    if raw in ("", "unbounded", "none", "null"):
        return None
    m = _PATTERN.match(raw)
    if not m:
        if raw.isdigit():
            return int(raw)
        raise ValueError(f"could not parse duration: {value!r}")
    n = int(m.group(1))
    unit = m.group(2).lower()
    return n * _MULTIPLIERS[unit]


def format_duration(seconds: int | None) -> str:
    """Render seconds as a human string matching doc examples (e.g. '2h', '1h 47m')."""
    if seconds is None:
        return "unbounded"
    if seconds < 0:
        seconds = 0
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if not parts and secs:
        parts.append(f"{secs}s")
    if not parts:
        return "0m"
    return " ".join(parts)


def format_elapsed(seconds: int) -> str:
    """Render elapsed time as the docs show it: '1h 47m' or '47m' or '1h'."""
    if seconds < 0:
        seconds = 0
    hours, rem = divmod(seconds, 3600)
    minutes, _secs = divmod(rem, 60)
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"
