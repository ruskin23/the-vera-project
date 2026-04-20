from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent


def _run_vera(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    env = {"PATH": "/usr/bin:/bin"}
    import os

    env = {**os.environ}
    return subprocess.run(
        [sys.executable, "-m", "vera.cli", *args],
        cwd=cwd or PROJECT_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )


class TestCli:
    def test_help_lists_commands(self) -> None:
        result = _run_vera("--help")
        assert result.returncode == 0
        for cmd in [
            "list",
            "add",
            "start",
            "status",
            "grade",
            "submit",
            "new",
            "test",
            "adapters",
            "cd",
            "shell",
            "discover",
            "update",
            "info",
        ]:
            assert cmd in result.stdout

    def test_version_prints(self) -> None:
        result = _run_vera("--version")
        assert result.returncode == 0
        assert "vera" in result.stdout

    def test_list_empty_says_so(self, isolated_env: Path) -> None:
        result = _run_vera("list", cwd=isolated_env)
        assert result.returncode == 0
        assert "no challenges" in result.stdout

    def test_adapters_list_shows_four_packaged(self, isolated_env: Path) -> None:
        result = _run_vera("adapters", "list", cwd=isolated_env)
        assert result.returncode == 0
        for harness_id in ("claude-code", "gemini-cli", "codex-cli", "opencode"):
            assert harness_id in result.stdout

    def test_new_scaffolds_a_challenge(self, isolated_env: Path) -> None:
        result = _run_vera("new", "my-challenge", cwd=isolated_env)
        assert result.returncode == 0, result.stderr
        root = isolated_env / "my-challenge"
        assert (root / "vera.yaml").exists()
        assert (root / "brief.md").exists()
        assert (root / "workspace").is_dir()
        assert (root / "grader" / "grade.sh").exists()
        import os

        assert os.access(root / "grader" / "grade.sh", os.X_OK)
