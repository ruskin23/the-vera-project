"""Shared helpers for the reference adapters.

Each adapter is still a module (the loader contract at loader.py:78 checks for
module-level attributes), but the boilerplate that used to be duplicated across
claude_code / codex_cli / gemini_cli / opencode lives here.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_ts(raw: Any, *, ms_if_large: bool = False) -> float | None:
    """Parse a timestamp from ISO8601 string, unix int/float, or None.

    ms_if_large: if raw is numeric and > 1e12, treat it as milliseconds (opencode).
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        val = float(raw)
        if ms_if_large and val > 1e12:
            return val / 1000.0
        return val
    if isinstance(raw, str):
        try:
            s = raw.replace("Z", "+00:00")
            return datetime.fromisoformat(s).astimezone(timezone.utc).timestamp()
        except ValueError:
            return None
    return None


def read_jsonl_entries(path: Path) -> list[dict]:
    """Parse each line of a JSONL file, skipping blank/malformed lines."""
    try:
        text = path.read_text()
    except OSError:
        return []
    entries: list[dict] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            entries.append(obj)
    return entries


def read_json_entries(path: Path, top_keys: tuple[str, ...]) -> list[dict]:
    """Parse a JSON file and coerce it to a list of dict entries.

    - If the document is a list, return its dict members.
    - If the document is a dict with any of the listed top_keys mapping to a list,
      return that list's dict members.
    - If the document is a dict with none of those keys, return [the dict itself].
    - On parse failure or unsupported shape, return [].
    """
    try:
        raw = path.read_text()
    except OSError:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [e for e in data if isinstance(e, dict)]
    if isinstance(data, dict):
        for key in top_keys:
            val = data.get(key)
            if isinstance(val, list):
                return [e for e in val if isinstance(e, dict)]
        return [data]
    return []


def filter_by_mtime(paths: Iterable[Path], since_seconds: int) -> list[Path]:
    """Return paths with st_mtime >= now - since_seconds, sorted."""
    cutoff = time.time() - since_seconds
    kept: list[Path] = []
    for p in paths:
        try:
            if p.stat().st_mtime >= cutoff:
                kept.append(p)
        except OSError:
            continue
    return sorted(kept)


def extract_tool_calls(
    entry: dict,
    *,
    keys: tuple[str, ...],
    type_filters: tuple[str, ...] = (),
    name_fields: tuple[str, ...] = ("name", "kind", "tool", "toolName"),
) -> list[dict]:
    """Collect {'kind': <name>} dicts from any of the listed list-valued keys.

    If type_filters is non-empty, only items whose "type" matches one of the
    filters contribute (the opencode case: {"type": "tool-call"}). If empty,
    every dict item contributes as long as a name field is present.
    """
    out: list[dict] = []
    for key in keys:
        for item in entry.get(key) or []:
            if not isinstance(item, dict):
                continue
            if type_filters and item.get("type") not in type_filters:
                continue
            name = None
            for field in name_fields:
                name = name or item.get(field)
            if not name:
                fn = item.get("function")
                if isinstance(fn, dict):
                    name = fn.get("name")
            if name:
                out.append({"kind": name})
    return out
