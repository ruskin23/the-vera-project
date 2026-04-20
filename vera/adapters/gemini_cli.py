"""Reference adapter for Gemini CLI.

Log layout varies by Gemini CLI version. This adapter normalizes across documented
layouts, preferring structured JSON session files under ~/.gemini/.

Status: shape-matched, not yet verified end-to-end. `sessions_for_run` returns []
and SESSIONS_FOR_RUN_IMPLEMENTED=False so pin verification reports "unimplemented"
(rather than "unclear") for this harness. Diagnostic via `vera adapters test`
still works through `recent_sessions`.
"""

from __future__ import annotations

from pathlib import Path

from vera.adapters import _common

HARNESS_ID = "gemini-cli"
CONTRACT_VERSION = 1
SESSIONS_FOR_RUN_IMPLEMENTED = False

LOG_DIR = Path.home() / ".gemini"


def detect() -> bool:
    return LOG_DIR.exists()


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
    return _common.filter_by_mtime(_iter_session_files(), since_seconds)


def _turn_from(entry: dict) -> dict | None:
    role = (entry.get("role") or entry.get("type") or "").lower()
    if role not in ("assistant", "model"):
        return None
    model = entry.get("model") or entry.get("modelVersion")
    if not model:
        return None
    ts = _common.parse_ts(entry.get("timestamp") or entry.get("ts") or entry.get("time"))
    tool_calls = _common.extract_tool_calls(entry, keys=("tool_calls", "toolCalls", "tools"))
    return {"ts": ts or 0.0, "model": model, "tool_calls": tool_calls}


def session_turns(session_path: Path) -> list[dict]:
    if session_path.suffix == ".jsonl":
        entries = _common.read_jsonl_entries(session_path)
    else:
        entries = _common.read_json_entries(
            session_path, top_keys=("turns", "messages", "events", "history")
        )
    try:
        mtime = session_path.stat().st_mtime
    except OSError:
        mtime = 0.0
    turns: list[dict] = []
    for entry in entries:
        turn = _turn_from(entry)
        if turn is None:
            continue
        if not turn["ts"]:
            turn["ts"] = mtime
        turns.append(turn)
    return turns
