from __future__ import annotations

from pathlib import Path

from vera.adapters import codex_cli

FIXTURE = Path(__file__).parent / "fixtures" / "session-logs" / "codex-cli" / "session.jsonl"


def test_session_turns_extracts_assistant_turns() -> None:
    turns = codex_cli.session_turns(FIXTURE)
    assert len(turns) == 2
    assert all(t["model"] == "gpt-5" for t in turns)


def test_function_call_type_surfaces_as_tool_call() -> None:
    turns = codex_cli.session_turns(FIXTURE)
    kinds = {c["kind"] for t in turns for c in t["tool_calls"]}
    assert {"shell", "apply_patch"} <= kinds


def test_sessions_for_run_returns_empty_until_verified(tmp_path: Path) -> None:
    """Until codex's project-scoping is verified, sessions_for_run returns []."""
    assert codex_cli.sessions_for_run(tmp_path) == []
