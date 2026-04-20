from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from vera.cli.cmd_shell import shell_cmd
from vera.core import registry, runs


class TestShell:
    def test_spawns_shell_in_workspace(self, simple_challenge: Path, monkeypatch) -> None:
        registry.add(str(simple_challenge))
        info = runs.start(slug="challenge-simple", variant="baseline")
        monkeypatch.setenv("SHELL", "/bin/sh")
        captured = {}

        def fake_run(args, cwd, check):
            captured["args"] = args
            captured["cwd"] = cwd
            captured["check"] = check

            class R:
                returncode = 0

            return R()

        with patch("vera.cli.cmd_shell.subprocess.run", side_effect=fake_run):
            result = CliRunner().invoke(shell_cmd, [])

        assert result.exit_code == 0
        assert captured["args"] == ["/bin/sh"]
        assert captured["cwd"] == (info.run_dir / "workspace").resolve()

    def test_exits_when_no_active_run(self) -> None:
        result = CliRunner().invoke(shell_cmd, [])
        assert result.exit_code == 1
