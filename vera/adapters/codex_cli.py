"""Reference adapter for Codex CLI.

Log layout under ~/.codex/ varies by version. This adapter normalizes across
the documented JSON/JSONL session shapes.

Status: shape-matched, not yet verified end-to-end. `sessions_for_run` returns []
and SESSIONS_FOR_RUN_IMPLEMENTED=False so pin verification reports "unimplemented"
(rather than "unclear") for this harness. Diagnostic via `vera adapters test`
still works through `recent_sessions`.
"""

from __future__ import annotations

from pathlib import Path

from vera.adapters import _common

HARNESS_ID = "codex-cli"
CONTRACT_VERSION = 1
SESSIONS_FOR_RUN_IMPLEMENTED = False

LOG_DIR = Path.home() / ".codex"


def detect() -> bool:
    return LOG_DIR.exists()


def _candidate_files() -> list[Path]:
    if not LOG_DIR.exists():
        return []
    results: list[Path] = []
    for ext in ("*.jsonl", "*.json"):
        results.extend(LOG_DIR.glob(f"**/{ext}"))
    return sorted(set(results))


def sessions_for_run(workspace_path: Path) -> list[Path]:
    # TODO: derive Codex's project-scoping convention from real session logs.
    return []


def recent_sessions(since_seconds: int) -> list[Path]:
    return _common.filter_by_mtime(_candidate_files(), since_seconds)


def _is_assistant(entry: dict) -> bool:
    role = (entry.get("role") or entry.get("type") or "").lower()
    return role in ("assistant", "agent", "response")


def _tool_calls_from(entry: dict) -> list[dict]:
    out = _common.extract_tool_calls(entry, keys=("tool_calls", "tools", "toolCalls"))
    # Codex also emits "function_call" events at entry level with a "name".
    if entry.get("type") == "function_call" and entry.get("name"):
        out.append({"kind": entry["name"]})
    return out


def _model_from(entry: dict) -> str | None:
    model = entry.get("model")
    if model:
        return model
    response = entry.get("response")
    if isinstance(response, dict):
        return response.get("model")
    return None


def _turn_from(entry: dict) -> dict | None:
    if not _is_assistant(entry):
        return None
    model = _model_from(entry)
    if not model:
        return None
    ts = _common.parse_ts(
        entry.get("timestamp") or entry.get("ts") or entry.get("time") or entry.get("created_at")
    )
    return {"ts": ts or 0.0, "model": model, "tool_calls": _tool_calls_from(entry)}


def session_turns(session_path: Path) -> list[dict]:
    if session_path.suffix == ".jsonl":
        entries = _common.read_jsonl_entries(session_path)
    else:
        entries = _common.read_json_entries(
            session_path, top_keys=("events", "messages", "turns", "history")
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
