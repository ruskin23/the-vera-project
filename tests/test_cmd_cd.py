from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from vera.cli.cmd_cd import cd_cmd
from vera.core import registry, runs


def _register_and_start(simple_challenge: Path) -> Path:
    registry.add(str(simple_challenge))
    info = runs.start(slug="challenge-simple", variant="baseline")
    return info.run_dir


class TestCd:
    def test_prints_workspace_path(self, simple_challenge: Path) -> None:
        run_dir = _register_and_start(simple_challenge)
        result = CliRunner().invoke(cd_cmd, [])
        assert result.exit_code == 0
        assert result.output.strip() == str((run_dir / "workspace").resolve())

    def test_exits_1_when_no_active_run(self) -> None:
        result = CliRunner().invoke(cd_cmd, [])
        assert result.exit_code == 1
        assert "no active run" in (result.stderr or result.output)

    def test_accepts_slug_arg(self, simple_challenge: Path) -> None:
        run_dir = _register_and_start(simple_challenge)
        result = CliRunner().invoke(cd_cmd, ["challenge-simple"])
        assert result.exit_code == 0
        assert result.output.strip() == str((run_dir / "workspace").resolve())
