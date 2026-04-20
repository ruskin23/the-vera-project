from __future__ import annotations

import json
from pathlib import Path

import pytest

from vera.core import registry, runs


@pytest.fixture
def registered(simple_challenge: Path):
    return registry.add(str(simple_challenge))[0]


class TestStart:
    def test_creates_run_dir_with_run_json(self, registered, isolated_env: Path) -> None:
        info = runs.start(slug="challenge-simple", variant="baseline")
        assert info.run_dir.exists()
        assert (info.run_dir / "run.json").exists()
        assert (info.run_dir / "workspace" / "answer.txt").read_text().strip() == "wrong"

        run_json = json.loads((info.run_dir / "run.json").read_text())
        assert run_json["slug"] == "challenge-simple"
        assert run_json["variant"] == "baseline"
        assert run_json["pin"]["harness"] == "claude-code"

    def test_unknown_variant_raises(self, registered) -> None:
        with pytest.raises(runs.RunError, match="variant"):
            runs.start(slug="challenge-simple", variant="nonexistent")

    def test_unknown_slug_raises(self) -> None:
        with pytest.raises(runs.RunError):
            runs.start(slug="no-such-thing", variant="baseline")


class TestActiveRun:
    def test_no_active_run_when_fresh(self) -> None:
        assert runs.active_run() is None

    def test_active_run_points_at_latest_ungraded(self, registered) -> None:
        runs.start(slug="challenge-simple", variant="baseline")
        active = runs.active_run()
        assert active is not None
        assert active.slug == "challenge-simple"

    def test_active_run_excludes_graded_runs(self, registered) -> None:
        info = runs.start(slug="challenge-simple", variant="baseline")
        (info.run_dir / "result.json").write_text("{}")
        assert runs.active_run() is None
