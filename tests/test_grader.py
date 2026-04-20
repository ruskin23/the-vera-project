from __future__ import annotations

from pathlib import Path

import pytest

from vera.core import grader, registry, runs


@pytest.fixture
def started(simple_challenge: Path):
    registry.add(str(simple_challenge))
    return runs.start(slug="challenge-simple", variant="baseline")


class TestGrade:
    def test_pristine_workspace_fails_grader(self, started) -> None:
        active = runs.active_run()
        outcome = grader.grade(run=active, skip_pin_check=True, keep_stack=False)
        assert outcome.result["pass"] is False
        assert outcome.result["pin_honored"] == "skipped"
        assert (active.run_dir / "result.json").exists()
        assert (active.run_dir / "diff.patch").exists()

    def test_solution_passes_grader(self, started) -> None:
        active = runs.active_run()
        (active.run_dir / "workspace" / "answer.txt").write_text("correct\n")
        outcome = grader.grade(run=active, skip_pin_check=True, keep_stack=False)
        assert outcome.result["pass"] is True
        assert outcome.result["signals"]["answer_correct"] is True

    def test_grader_exit_code_agreement(self, started, monkeypatch) -> None:
        # Sabotage the grader to mismatch exit/code and pass.
        active = runs.active_run()
        gs = active.run_dir / "grader" / "grade.sh"
        gs.write_text("#!/usr/bin/env bash\necho '{\"pass\": true}'\nexit 1\n")
        gs.chmod(0o755)
        with pytest.raises(grader.GraderError, match="exited with"):
            grader.grade(run=active, skip_pin_check=True, keep_stack=False)

    def test_grader_bad_json_raises(self, started) -> None:
        active = runs.active_run()
        gs = active.run_dir / "grader" / "grade.sh"
        gs.write_text("#!/usr/bin/env bash\necho 'not json'\nexit 1\n")
        gs.chmod(0o755)
        with pytest.raises(grader.GraderError, match="not valid JSON"):
            grader.grade(run=active, skip_pin_check=True, keep_stack=False)
