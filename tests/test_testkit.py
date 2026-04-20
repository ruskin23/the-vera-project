from __future__ import annotations

from pathlib import Path

from vera import testkit


def test_testkit_runs_green_on_simple_fixture(simple_challenge: Path, monkeypatch) -> None:
    monkeypatch.chdir(simple_challenge)
    report = testkit.run(variant=None)
    assert report.ok, "\n".join(f"{line.ok}: {line.text} {line.details}" for line in report.lines)


def test_testkit_fails_when_solution_missing(simple_challenge: Path, monkeypatch) -> None:
    import shutil

    shutil.rmtree(simple_challenge / "grader" / "fixtures" / "solution")
    monkeypatch.chdir(simple_challenge)
    report = testkit.run(variant=None)
    assert not report.ok
    # Should have at least one line about the missing solution.
    assert any("fixtures/solution" in line.text for line in report.lines if not line.ok)


def test_testkit_fails_when_grader_passes_pristine(simple_challenge: Path, monkeypatch) -> None:
    # Rewrite grader to always pass — this is the failure the docs describe.
    gs = simple_challenge / "grader" / "grade.sh"
    gs.write_text("#!/usr/bin/env bash\necho '{\"pass\": true}'\nexit 0\n")
    gs.chmod(0o755)
    monkeypatch.chdir(simple_challenge)
    report = testkit.run(variant=None)
    assert not report.ok
