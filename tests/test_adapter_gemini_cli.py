from __future__ import annotations

from pathlib import Path

from vera.adapters import gemini_cli

FIXTURE = Path(__file__).parent / "fixtures" / "session-logs" / "gemini-cli" / "session.jsonl"


def test_session_turns_extracts_model_turns() -> None:
    turns = gemini_cli.session_turns(FIXTURE)
    assert len(turns) == 2
    assert {t["model"] for t in turns} == {"gemini-2.5-pro"}


def test_tool_calls_extracted() -> None:
    turns = gemini_cli.session_turns(FIXTURE)
    kinds = [c["kind"] for t in turns for c in t["tool_calls"]]
    assert set(kinds) == {"read_file", "shell"}


def test_sessions_for_run_returns_empty_until_verified(tmp_path: Path) -> None:
    """Until gemini's project-scoping is verified, sessions_for_run returns []."""
    assert gemini_cli.sessions_for_run(tmp_path) == []
