from __future__ import annotations

from pathlib import Path

from vera.adapters import loader
from vera.core import config


def _write_adapter(path: Path, harness_id: str, version: int = 1, extra: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""
HARNESS_ID = {harness_id!r}
CONTRACT_VERSION = {version}

def detect(): return True
def sessions_for_run(workspace_path): return []
def session_turns(x): return []
{extra}
"""
    )


class TestDiscoverAll:
    def test_includes_packaged_adapters(self, isolated_env: Path) -> None:
        groups = loader.discover_all()
        ids = {a.harness_id for a in groups.package}
        assert {"claude-code", "gemini-cli", "codex-cli", "opencode"} <= ids

    def test_user_adapter_overrides_package(self, isolated_env: Path) -> None:
        _write_adapter(
            config.user_adapters_dir() / "claude_code.py",
            harness_id="claude-code",
            version=1,
        )
        groups = loader.discover_all()
        resolved = groups.resolve("claude-code")
        assert resolved is not None
        assert resolved.source_group == "user"

    def test_project_adapter_overrides_user(self, isolated_env: Path) -> None:
        _write_adapter(
            config.user_adapters_dir() / "claude_code.py",
            harness_id="claude-code",
            version=1,
            extra="# user",
        )
        _write_adapter(
            config.project_adapters_dir() / "claude_code.py",
            harness_id="claude-code",
            version=1,
            extra="# project",
        )
        groups = loader.discover_all()
        resolved = groups.resolve("claude-code")
        assert resolved is not None
        assert resolved.source_group == "project"

    def test_unknown_contract_version_rejected(self, isolated_env: Path) -> None:
        _write_adapter(
            config.user_adapters_dir() / "bogus.py",
            harness_id="bogus-cli",
            version=99,
        )
        groups = loader.discover_all()
        assert not any(a.harness_id == "bogus-cli" for a in groups.flat())
        assert any(
            "bogus" in e.source.name and "CONTRACT_VERSION" in e.reason for e in groups.errors
        )

    def test_missing_function_rejected(self, isolated_env: Path) -> None:
        user_dir = config.user_adapters_dir()
        user_dir.mkdir(parents=True, exist_ok=True)
        (user_dir / "broken.py").write_text("HARNESS_ID = 'broken'\nCONTRACT_VERSION = 1\n")
        groups = loader.discover_all()
        assert not any(a.harness_id == "broken" for a in groups.flat())
        assert any("broken" in e.source.name for e in groups.errors)


class TestGetAdapter:
    def test_resolves_packaged_by_harness_id(self, isolated_env: Path) -> None:
        a = loader.get_adapter("claude-code")
        assert a is not None
        assert a.contract_version == 1

    def test_returns_none_for_unknown(self, isolated_env: Path) -> None:
        assert loader.get_adapter("no-such-harness") is None
