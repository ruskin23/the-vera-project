"""Pin verification + collaboration block derivation.

Both operations iterate the same turn stream from an adapter, so they live together.
Contract: pin_honored ∈ {yes, no, unclear, skipped}; collaboration block present
only when pin_honored ∈ {yes, no}.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vera.adapters.loader import LoadedAdapter


@dataclass
class VerificationOutcome:
    pin_honored: str  # yes | no | unclear | skipped
    collaboration: dict[str, Any] | None
    sessions_seen: int
    turns_seen: int
    models_seen: set[str]


def _count_kinds(turns: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for t in turns:
        for call in t.get("tool_calls") or []:
            k = (call or {}).get("kind")
            if k is None:
                continue
            out[k] = out.get(k, 0) + 1
    return out


def _count_model_switches(turns: list[dict]) -> int:
    switches = 0
    prev: str | None = None
    for t in sorted(turns, key=lambda x: x.get("ts", 0.0)):
        m = t.get("model")
        if m is None:
            continue
        if prev is not None and m != prev:
            switches += 1
        prev = m
    return switches


def _session_span_seconds(turns: list[dict]) -> int:
    if not turns:
        return 0
    ts = [t.get("ts", 0.0) for t in turns if t.get("ts") is not None]
    if not ts:
        return 0
    return max(0, int(max(ts) - min(ts)))


def _in_session_seconds(sessions_turns: list[list[dict]]) -> int:
    return sum(_session_span_seconds(turns) for turns in sessions_turns)


def verify_and_collect(
    pin_model: str,
    adapter: LoadedAdapter | None,
    workspace_path: Path,
    *,
    skip: bool = False,
) -> VerificationOutcome:
    if skip:
        return VerificationOutcome(
            pin_honored="skipped",
            collaboration=None,
            sessions_seen=0,
            turns_seen=0,
            models_seen=set(),
        )

    if adapter is None:
        return VerificationOutcome(
            pin_honored="unclear",
            collaboration=None,
            sessions_seen=0,
            turns_seen=0,
            models_seen=set(),
        )

    try:
        sessions = list(adapter.module.sessions_for_run(workspace_path))
    except Exception:
        sessions = []

    if not sessions:
        return VerificationOutcome(
            pin_honored="unclear",
            collaboration=None,
            sessions_seen=0,
            turns_seen=0,
            models_seen=set(),
        )

    per_session_turns: list[list[dict]] = []
    all_turns: list[dict] = []
    for s in sessions:
        try:
            t = list(adapter.module.session_turns(s))
        except Exception:
            t = []
        per_session_turns.append(t)
        all_turns.extend(t)

    models_seen = {t["model"] for t in all_turns if t.get("model")}

    if not models_seen:
        return VerificationOutcome(
            pin_honored="unclear",
            collaboration=None,
            sessions_seen=len(sessions),
            turns_seen=len(all_turns),
            models_seen=set(),
        )

    pin_honored = "yes" if models_seen == {pin_model} else "no"

    total_tool_calls = sum(len(t.get("tool_calls") or []) for t in all_turns)
    collaboration = {
        "turns": len(all_turns),
        "tool_calls": total_tool_calls,
        "tool_calls_by_kind": _count_kinds(all_turns),
        "model_switches": _count_model_switches(all_turns),
        "in_session_seconds": _in_session_seconds(per_session_turns),
    }

    return VerificationOutcome(
        pin_honored=pin_honored,
        collaboration=collaboration,
        sessions_seen=len(sessions),
        turns_seen=len(all_turns),
        models_seen=models_seen,
    )
