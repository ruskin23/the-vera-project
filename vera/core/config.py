from __future__ import annotations

import os
from pathlib import Path


def config_dir() -> Path:
    """Vera's config directory. Holds adapters/, registry/, journal.jsonl, config.yaml."""
    env = os.environ.get("VERA_CONFIG_DIR")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".vera"


def registry_path() -> Path:
    """Where `vera add` installs challenges. Cascades from config_dir when unset."""
    env = os.environ.get("VERA_REGISTRY_PATH")
    if env:
        return Path(env).expanduser()
    return config_dir() / "registry"


def run_dir_root() -> Path:
    """Root for run directories.

    Default is `$VERA_CONFIG_DIR/runs/` (canonical, centralized — same principle
    as the registry). The old cwd-relative default was an inconsistency.
    `VERA_RUN_DIR` still overrides as an escape hatch.
    """
    env = os.environ.get("VERA_RUN_DIR")
    if env:
        return Path(env).expanduser()
    return config_dir() / "runs"


def catalog_cache_path() -> Path:
    return config_dir() / "catalog.json"


def catalog_url() -> str:
    """Canonical catalog URL. Override via VERA_CATALOG_URL."""
    env = os.environ.get("VERA_CATALOG_URL")
    if env:
        return env
    return "https://raw.githubusercontent.com/ruskin23/the-vera-catalog/master/catalog.json"


def catalog_ttl_seconds() -> int:
    """How long the cached catalog is considered fresh before re-fetch.

    Default 6h. Override via VERA_CATALOG_TTL (seconds).
    """
    env = os.environ.get("VERA_CATALOG_TTL")
    if env:
        try:
            return max(0, int(env))
        except ValueError:
            pass
    return 6 * 3600


def user_adapters_dir() -> Path:
    return config_dir() / "adapters"


def project_adapters_dir() -> Path:
    return Path.cwd() / ".vera" / "adapters"


def journal_path() -> Path:
    return config_dir() / "journal.jsonl"


def user_config_file() -> Path:
    return config_dir() / "config.yaml"


def ensure_config_dir() -> Path:
    path = config_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_registry() -> Path:
    path = registry_path()
    path.mkdir(parents=True, exist_ok=True)
    return path
