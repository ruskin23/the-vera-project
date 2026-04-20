from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect VERA_* env vars into tmp_path so tests never touch the user's home.

    Layout (matching real-world):
      - project cwd: tmp/project/           (user's working directory)
      - config dir:  tmp/home/.vera/        (VERA_CONFIG_DIR)
      - registry:    tmp/home/.vera/registry/   (cascades from config_dir)
      - runs:        tmp/home/.vera/runs/       (cascades from config_dir)
      - catalog:     tmp/home/.vera/catalog.json

    VERA_RUN_DIR is deliberately NOT set so tests exercise the cascaded default.
    The network-fetched catalog is blocked by default — individual tests that
    need it mock requests.get.
    """
    project_root = tmp_path / "project"
    config_dir = tmp_path / "home" / ".vera"
    project_root.mkdir()
    config_dir.mkdir(parents=True)
    monkeypatch.setenv("VERA_CONFIG_DIR", str(config_dir))
    # Don't set VERA_REGISTRY_PATH or VERA_RUN_DIR — let them cascade.
    monkeypatch.delenv("VERA_REGISTRY_PATH", raising=False)
    monkeypatch.delenv("VERA_RUN_DIR", raising=False)
    monkeypatch.delenv("VERA_CATALOG_URL", raising=False)
    monkeypatch.chdir(project_root)
    return project_root


@pytest.fixture
def simple_challenge(tmp_path: Path) -> Path:
    """A self-contained non-container challenge with a pytest grader."""
    src = FIXTURES / "challenge-simple"
    dst = tmp_path / "src" / "challenge-simple"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)
    # Ensure executable bits (shutil.copytree preserves mode on Linux; be explicit).
    (dst / "grader" / "grade.sh").chmod(0o755)
    setup_sh = dst / "setup" / "setup.sh"
    if setup_sh.exists():
        setup_sh.chmod(0o755)
    return dst


def docker_available() -> bool:
    return shutil.which("docker") is not None


needs_docker = pytest.mark.docker
needs_docker_skipif = pytest.mark.skipif(not docker_available(), reason="docker not available")
