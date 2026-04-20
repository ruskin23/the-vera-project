from __future__ import annotations

import os
from pathlib import Path

from vera.adapters import opencode

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "session-logs" / "opencode"


def test_recent_sessions_and_session_turns(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENCODE_DATA_DIR", str(FIXTURE_ROOT))
    for p in FIXTURE_ROOT.rglob("*.json"):
        os.utime(p, None)

    sessions = opencode.recent_sessions(since_seconds=3600)
    assert len(sessions) == 1
    turns = opencode.session_turns(sessions[0])
    assert len(turns) == 2
    assert all(t["model"] == "anthropic/claude-opus-4-7" for t in turns)
    kinds = {c["kind"] for t in turns for c in t["tool_calls"]}
    assert {"read", "bash", "edit"} <= kinds


def test_sessions_for_run_returns_empty_until_verified(tmp_path: Path) -> None:
    """Until opencode's projectHash algorithm is verified, sessions_for_run returns []."""
    assert opencode.sessions_for_run(tmp_path) == []


def test_detect_with_env_override(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENCODE_DATA_DIR", str(tmp_path / "nope"))
    assert opencode.detect() is False
