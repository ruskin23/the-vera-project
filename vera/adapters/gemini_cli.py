"""Reference adapter for Gemini CLI.

Log layout varies by Gemini CLI version. This adapter normalizes across documented
layouts, preferring structured JSON session files under ~/.gemini/.

Status: shape-matched, not yet verified end-to-end. `sessions_for_run` returns []
until the project-scoping convention is confirmed against real logs; pin
verification degrades to "unclear" for this harness in the meantime. Diagnostic
via `vera adapters test` still works through `recent_sessions`.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

HARNESS_ID = "gemini-cli"
CONTRACT_VERSION = 1

LOG_DIR = Path.home() / ".gemini"


def detect() -> bool:
    return LOG_DIR.exists()


def _parse_ts(raw) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(
                timezone.utc
            ).timestamp()
        except ValueError:
            return None
    return None


def _iter_session_files() -> list[Path]:
    if not LOG_DIR.exists():
        return []
    candidates: list[Path] = []
    for ext in ("*.json", "*.jsonl"):
        candidates.extend(LOG_DIR.glob(f"**/{ext}"))
    return sorted(set(candidates))


def sessions_for_run(workspace_path: Path) -> list[Path]:
    # TODO: derive Gemini's project-scoping convention from real session logs.
    return []


def recent_sessions(since_seconds: int) -> list[Path]:
    cutoff = time.time() - since_seconds
    return [p for p in _iter_session_files() if p.stat().st_mtime >= cutoff]


def _tool_calls_from(entry: dict) -> list[dict]:
    out: list[dict] = []
    for key in ("tool_calls", "toolCalls", "tools"):
        for call in entry.get(key) or []:
            if isinstance(call, dict):
                name = (
                    call.get("name")
                    or call.get("kind")
                    or call.get("tool")
                    or call.get("function", {}).get("name")
                )
                if name:
                    out.append({"kind": name})
    return out


def _turn_from(entry: dict) -> dict | None:
    role = (entry.get("role") or entry.get("type") or "").lower()
    if role not in ("assistant", "model"):
        return None
    model = entry.get("model") or entry.get("modelVersion")
    if not model:
        return None
    ts = _parse_ts(entry.get("timestamp") or entry.get("ts") or entry.get("time"))
    return {
        "ts": ts or 0.0,
        "model": model,
        "tool_calls": _tool_calls_from(entry),
    }


def session_turns(session_path: Path) -> list[dict]:
    turns: list[dict] = []
    try:
        raw = session_path.read_text()
    except OSError:
        return turns

    if session_path.suffix == ".jsonl":
        entries: list[dict] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    else:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return turns
        if isinstance(data, list):
            entries = [e for e in data if isinstance(e, dict)]
        elif isinstance(data, dict):
            for key in ("turns", "messages", "events", "history"):
                if isinstance(data.get(key), list):
                    entries = [e for e in data[key] if isinstance(e, dict)]
                    break
            else:
                entries = [data]
        else:
            return turns

    mtime = session_path.stat().st_mtime if session_path.exists() else 0.0
    for entry in entries:
        turn = _turn_from(entry)
        if turn:
            if not turn["ts"]:
                turn["ts"] = mtime
            turns.append(turn)
    return turns
