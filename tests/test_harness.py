from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from vera.core.harness import verify_and_collect


def _fake_adapter(sessions, turns_by_session):
    module = SimpleNamespace(
        sessions_for_run=lambda workspace: sessions,
        session_turns=lambda session: turns_by_session[session],
    )
    return SimpleNamespace(module=module, harness_id="fake", contract_version=1)


WS = Path("/tmp/does-not-matter/workspace")


class TestPinHonored:
    def test_no_adapter_is_unclear(self) -> None:
        out = verify_and_collect(pin_model="claude-opus-4-7", adapter=None, workspace_path=WS)
        assert out.pin_honored == "unclear"
        assert out.collaboration is None

    def test_skip_is_skipped(self) -> None:
        out = verify_and_collect(
            pin_model="claude-opus-4-7", adapter=None, workspace_path=WS, skip=True
        )
        assert out.pin_honored == "skipped"
        assert out.collaboration is None

    def test_zero_sessions_is_unclear(self) -> None:
        adapter = _fake_adapter([], {})
        out = verify_and_collect("claude-opus-4-7", adapter, WS)
        assert out.pin_honored == "unclear"
        assert out.collaboration is None

    def test_no_model_turns_is_unclear(self) -> None:
        adapter = _fake_adapter(["s1"], {"s1": [{"ts": 1.0}]})
        out = verify_and_collect("claude-opus-4-7", adapter, WS)
        assert out.pin_honored == "unclear"
        assert out.collaboration is None

    def test_matching_model_is_yes(self) -> None:
        turns = [
            {"ts": 1.0, "model": "claude-opus-4-7", "tool_calls": [{"kind": "Read"}]},
            {"ts": 3.0, "model": "claude-opus-4-7", "tool_calls": [{"kind": "Edit"}]},
        ]
        adapter = _fake_adapter(["s1"], {"s1": turns})
        out = verify_and_collect("claude-opus-4-7", adapter, WS)
        assert out.pin_honored == "yes"
        assert out.collaboration == {
            "turns": 2,
            "tool_calls": 2,
            "tool_calls_by_kind": {"Read": 1, "Edit": 1},
            "model_switches": 0,
            "in_session_seconds": 2,
        }

    def test_mismatching_model_is_no(self) -> None:
        turns = [
            {"ts": 1.0, "model": "claude-sonnet-4-6", "tool_calls": []},
        ]
        adapter = _fake_adapter(["s1"], {"s1": turns})
        out = verify_and_collect("claude-opus-4-7", adapter, WS)
        assert out.pin_honored == "no"
        assert out.collaboration is not None


class TestCollaborationStats:
    def test_model_switches_across_sessions(self) -> None:
        turns_s1 = [
            {"ts": 1.0, "model": "A", "tool_calls": []},
            {"ts": 2.0, "model": "B", "tool_calls": []},
        ]
        turns_s2 = [
            {"ts": 3.0, "model": "B", "tool_calls": []},
            {"ts": 4.0, "model": "A", "tool_calls": []},
        ]
        adapter = _fake_adapter(["s1", "s2"], {"s1": turns_s1, "s2": turns_s2})
        out = verify_and_collect("A", adapter, WS)
        assert out.collaboration["model_switches"] == 2

    def test_in_session_seconds_sums_per_session_spans(self) -> None:
        turns_s1 = [
            {"ts": 100.0, "model": "A", "tool_calls": []},
            {"ts": 200.0, "model": "A", "tool_calls": []},
        ]
        turns_s2 = [
            {"ts": 500.0, "model": "A", "tool_calls": []},
            {"ts": 510.0, "model": "A", "tool_calls": []},
        ]
        adapter = _fake_adapter(["s1", "s2"], {"s1": turns_s1, "s2": turns_s2})
        out = verify_and_collect("A", adapter, WS)
        assert out.collaboration["in_session_seconds"] == 110
