"""Reference adapter for opencode.

Log layout:
- ~/.local/share/opencode/session/<projectHash>/*.json   (session metadata)
- ~/.local/share/opencode/message/<sessionID>/msg_*.json (individual messages)

Override root with $OPENCODE_DATA_DIR.

Status: shape-matched, not yet verified end-to-end. `sessions_for_run` returns []
and SESSIONS_FOR_RUN_IMPLEMENTED=False so pin verification reports "unimplemented"
(rather than "unclear") for this harness. Diagnostic via `vera adapters test`
still works through `recent_sessions`.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from vera.adapters import _common

HARNESS_ID = "opencode"
CONTRACT_VERSION = 1
SESSIONS_FOR_RUN_IMPLEMENTED = False


def _root() -> Path:
    env = os.environ.get("OPENCODE_DATA_DIR")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".local" / "share" / "opencode"


def detect() -> bool:
    return _root().exists()


@dataclass
class OpencodeSession:
    session_id: str
    metadata_path: Path
    message_dir: Path
    mtime: float


def _session_id(meta_path: Path) -> str | None:
    try:
        data = json.loads(meta_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(data, dict):
        sid = data.get("id") or data.get("sessionID") or data.get("session_id")
        if isinstance(sid, str):
            return sid
    return meta_path.stem


def _discover_sessions() -> list[OpencodeSession]:
    root = _root()
    if not root.exists():
        return []
    session_root = root / "session"
    message_root = root / "message"
    if not session_root.exists():
        return []
    sessions: list[OpencodeSession] = []
    for meta in session_root.glob("*/*.json"):
        sid = _session_id(meta)
        if not sid:
            continue
        mdir = message_root / sid
        mtime = meta.stat().st_mtime
        if mdir.exists():
            for p in mdir.glob("msg_*.json"):
                try:
                    mt = p.stat().st_mtime
                    mtime = max(mtime, mt)
                except OSError:
                    continue
        sessions.append(
            OpencodeSession(session_id=sid, metadata_path=meta, message_dir=mdir, mtime=mtime)
        )
    return sessions


def sessions_for_run(workspace_path: Path) -> list[OpencodeSession]:
    # TODO: compute opencode's projectHash for workspace_path and filter to that dir.
    return []


def recent_sessions(since_seconds: int) -> list[OpencodeSession]:
    cutoff = time.time() - since_seconds
    return [s for s in _discover_sessions() if s.mtime >= cutoff]


def _is_assistant(entry: dict) -> bool:
    role = (entry.get("role") or entry.get("type") or "").lower()
    return role in ("assistant", "agent", "model")


def _tool_calls_from(entry: dict) -> list[dict]:
    return _common.extract_tool_calls(
        entry,
        keys=("tool_calls", "tools", "toolCalls", "parts"),
        type_filters=(),
        # opencode allows either {"type": "tool-call"} items or raw dicts; extract_tool_calls
        # already handles both shapes when type_filters is empty, because name_fields covers
        # "name"/"kind"/"tool"/"toolName".
    )


def _extract_model(entry: dict) -> str | None:
    m = entry.get("model") or entry.get("modelID") or entry.get("provider_model")
    if m:
        if isinstance(m, dict):
            provider = m.get("provider")
            model = m.get("model") or m.get("id")
            if provider and model:
                return f"{provider}/{model}"
            return model
        return m
    provider = entry.get("provider") or entry.get("providerID")
    model = entry.get("modelName") or entry.get("model_name")
    if provider and model:
        return f"{provider}/{model}"
    return None


def session_turns(session: OpencodeSession) -> list[dict]:
    turns: list[dict] = []
    if not session.message_dir.exists():
        return turns
    for path in sorted(session.message_dir.glob("msg_*.json")):
        entries = _common.read_json_entries(path, top_keys=())
        if not entries:
            continue
        data = entries[0]
        if not _is_assistant(data):
            continue
        model = _extract_model(data)
        if not model:
            continue
        ts = _common.parse_ts(
            data.get("timestamp")
            or data.get("ts")
            or data.get("time")
            or data.get("createdAt")
            or data.get("created_at"),
            ms_if_large=True,
        )
        if ts is None:
            try:
                ts = path.stat().st_mtime
            except OSError:
                ts = 0.0
        turns.append({"ts": ts, "model": model, "tool_calls": _tool_calls_from(data)})
    turns.sort(key=lambda t: t["ts"])
    return turns
