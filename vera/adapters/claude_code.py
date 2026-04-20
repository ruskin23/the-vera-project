"""Reference adapter for Claude Code.

Log layout: ~/.claude/projects/<path-slug>/*.jsonl
  where <path-slug> is the workspace's absolute path with every "/" replaced by "-".
Per-line entries include `type`, `timestamp`, and when `type == "assistant"` a
`message` block with `model`, plus `content[].type == "tool_use"` blocks or legacy
`tool_calls`.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

HARNESS_ID = "claude-code"
CONTRACT_VERSION = 1

LOG_DIR = Path.home() / ".claude" / "projects"


def detect() -> bool:
    return LOG_DIR.exists()


def _slug_for(workspace_path: Path) -> str:
    """Claude Code derives the project-dir name by replacing '/' with '-' in the abspath."""
    absolute = str(Path(workspace_path).resolve())
    return absolute.replace("/", "-")


def sessions_for_run(workspace_path: Path) -> list[Path]:
    """Return every session log Claude Code wrote for this workspace path.

    The workspace path is unique per run (timestamped), so every session file under
    its path-slug directory is, by construction, a session for this run.
    """
    slug = _slug_for(workspace_path)
    project_dir = LOG_DIR / slug
    if not project_dir.exists():
        return []
    return sorted(project_dir.glob("*.jsonl"))


def recent_sessions(since_seconds: int) -> list[Path]:
    """Diagnostic helper for `vera adapters test`: sessions touched in the last window."""
    if not LOG_DIR.exists():
        return []
    cutoff = time.time() - since_seconds
    return sorted(
        p
        for p in LOG_DIR.glob("**/*.jsonl")
        if p.stat().st_mtime >= cutoff
    )


def _parse_ts(raw: str | float | int | None) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        try:
            s = raw.replace("Z", "+00:00")
            return datetime.fromisoformat(s).astimezone(timezone.utc).timestamp()
        except ValueError:
            return None
    return None


def _extract_tool_calls(entry: dict) -> list[dict]:
    message = entry.get("message") or {}
    tool_calls: list[dict] = []

    for call in message.get("tool_calls") or []:
        name = call.get("name") or call.get("function", {}).get("name")
        if name:
            tool_calls.append({"kind": name})

    for block in message.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "tool_use":
            name = block.get("name")
            if name:
                tool_calls.append({"kind": name})

    return tool_calls


def session_turns(session_path: Path) -> list[dict]:
    turns: list[dict] = []
    try:
        text = session_path.read_text()
    except OSError:
        return turns

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("type") != "assistant":
            continue

        message = entry.get("message") or {}
        model = message.get("model") or entry.get("model")
        if not model:
            continue

        ts = _parse_ts(entry.get("timestamp") or entry.get("ts"))
        if ts is None:
            try:
                ts = session_path.stat().st_mtime
            except OSError:
                ts = 0.0

        turns.append(
            {
                "ts": ts,
                "model": model,
                "tool_calls": _extract_tool_calls(entry),
            }
        )

    return turns
