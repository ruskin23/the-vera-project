"""Reference adapter for Claude Code.

Log layout: ~/.claude/projects/<path-slug>/*.jsonl
  where <path-slug> is the workspace's absolute path with every "/" replaced by "-".
Per-line entries include `type`, `timestamp`, and when `type == "assistant"` a
`message` block with `model`, plus `content[].type == "tool_use"` blocks or legacy
`tool_calls`.
"""

from __future__ import annotations

from pathlib import Path

from vera.adapters import _common

HARNESS_ID = "claude-code"
CONTRACT_VERSION = 1
SESSIONS_FOR_RUN_IMPLEMENTED = True

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
    return _common.filter_by_mtime(LOG_DIR.glob("**/*.jsonl"), since_seconds)


def _extract_tool_calls(entry: dict) -> list[dict]:
    message = entry.get("message") or {}
    calls = _common.extract_tool_calls(message, keys=("tool_calls",))
    for block in message.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "tool_use":
            name = block.get("name")
            if name:
                calls.append({"kind": name})
    return calls


def session_turns(session_path: Path) -> list[dict]:
    turns: list[dict] = []
    for entry in _common.read_jsonl_entries(session_path):
        if entry.get("type") != "assistant":
            continue
        message = entry.get("message") or {}
        model = message.get("model") or entry.get("model")
        if not model:
            continue
        ts = _common.parse_ts(entry.get("timestamp") or entry.get("ts"))
        if ts is None:
            try:
                ts = session_path.stat().st_mtime
            except OSError:
                ts = 0.0
        turns.append({"ts": ts, "model": model, "tool_calls": _extract_tool_calls(entry)})
    return turns
