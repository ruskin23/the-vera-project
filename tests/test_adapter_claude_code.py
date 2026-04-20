from __future__ import annotations

import os
import time
from pathlib import Path

from vera.adapters import claude_code

FIXTURE = (
    Path(__file__).parent / "fixtures" / "session-logs" / "claude-code" / "session_example.jsonl"
)


def test_session_turns_extracts_assistant_turns() -> None:
    turns = claude_code.session_turns(FIXTURE)
    assert len(turns) == 3
    assert all(t["model"] == "claude-opus-4-7" for t in turns)


def test_tool_calls_include_tool_use_blocks() -> None:
    turns = claude_code.session_turns(FIXTURE)
    kinds = [c["kind"] for t in turns for c in t["tool_calls"]]
    assert kinds == ["Read", "Edit", "Bash"]


def test_sessions_for_run_scopes_by_workspace_path(tmp_path: Path, monkeypatch) -> None:
    """Path-slug is derived from the absolute workspace path: '/' → '-'."""
    fake_home = tmp_path / "home"
    workspace = tmp_path / "runs" / "slug" / "2026-04-19_1000" / "workspace"
    workspace.mkdir(parents=True)

    slug = str(workspace.resolve()).replace("/", "-")
    project_dir = fake_home / ".claude" / "projects" / slug
    project_dir.mkdir(parents=True)
    in_scope = project_dir / "session.jsonl"
    in_scope.write_text('{"type":"user"}\n')

    unrelated_dir = fake_home / ".claude" / "projects" / "-home-ruskin-other-repo"
    unrelated_dir.mkdir(parents=True)
    (unrelated_dir / "session.jsonl").write_text('{"type":"user"}\n')

    monkeypatch.setattr(claude_code, "LOG_DIR", fake_home / ".claude" / "projects")
    sessions = claude_code.sessions_for_run(workspace)
    assert sessions == [in_scope], (
        "sessions_for_run must only return sessions rooted in the workspace's path-slug"
    )


def test_sessions_for_run_returns_empty_when_no_sessions(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "runs" / "slug" / "2026-04-19_1000" / "workspace"
    workspace.mkdir(parents=True)
    monkeypatch.setattr(claude_code, "LOG_DIR", tmp_path / "home" / ".claude" / "projects")
    assert claude_code.sessions_for_run(workspace) == []


def test_recent_sessions_filters_by_mtime(tmp_path: Path, monkeypatch) -> None:
    fake_home = tmp_path / "home"
    project_dir = fake_home / ".claude" / "projects" / "demo"
    project_dir.mkdir(parents=True)
    old_file = project_dir / "old.jsonl"
    old_file.write_text("{}\n")
    os.utime(old_file, (100.0, 100.0))
    new_file = project_dir / "new.jsonl"
    new_file.write_text("{}\n")
    os.utime(new_file, (time.time(), time.time()))

    monkeypatch.setattr(claude_code, "LOG_DIR", fake_home / ".claude" / "projects")
    sessions = claude_code.recent_sessions(since_seconds=3600)
    assert new_file in sessions
    assert old_file not in sessions
