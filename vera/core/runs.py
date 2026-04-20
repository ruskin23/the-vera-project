"""Run directory lifecycle: create, write run.json, compute diff, resolve active run."""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vera.core import compose, config, schema
from vera.core.registry import RegistryError, read_version, resolve
from vera.core.validate import ChallengeMeta


class RunError(RuntimeError):
    pass


@dataclass
class StartInfo:
    slug: str
    variant: str
    run_dir: Path
    registry_dir: Path
    pin: dict[str, Any]
    brief_path: Path
    start_time: str
    container: bool
    compose_ports: list[str] = field(default_factory=list)
    file_count: int = 0
    bytes_copied: int = 0


@dataclass
class ActiveRun:
    slug: str
    variant: str
    run_dir: Path
    run_json: dict[str, Any]
    start_epoch: float


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _timestamp_folder(now: datetime | None = None) -> str:
    dt = now or datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%d_%H%M")


def parse_iso(value: str) -> float:
    value = value.replace("Z", "+00:00")
    return datetime.fromisoformat(value).timestamp()


_parse_iso = parse_iso  # legacy alias; prefer parse_iso


def _copy_tree(src: Path, dst: Path) -> tuple[int, int]:
    shutil.copytree(src, dst, symlinks=False)
    count = 0
    size = 0
    for p in dst.rglob("*"):
        if p.is_file():
            count += 1
            with contextlib.suppress(OSError):
                size += p.stat().st_size
    return count, size


def _compose_port_summary(compose_path: Path) -> list[str]:
    """Best-effort list of 'svc on :port' strings for start output."""
    if not compose_path.exists():
        return []
    from ruamel.yaml import YAML  # noqa: PLC0415 — heavy third-party dep, loaded lazily
    from ruamel.yaml.error import YAMLError  # noqa: PLC0415

    try:
        data = YAML().load(compose_path.read_text())
    except (OSError, YAMLError):
        return []
    if not isinstance(data, dict):
        return []
    services = data.get("services") or {}
    out: list[str] = []
    for name, svc in services.items():
        if not isinstance(svc, dict):
            continue
        ports = svc.get("ports") or []
        for entry in ports:
            host_port: str | None = None
            if isinstance(entry, str):
                parts = entry.split(":")
                if len(parts) >= 2:
                    host_port = parts[-2] if len(parts) == 3 else parts[0]
            elif isinstance(entry, dict):
                published = entry.get("published")
                if published is not None:
                    host_port = str(published)
            if host_port:
                out.append(f"{name} on :{host_port}")
    return out


def _run_root() -> Path:
    root = config.run_dir_root()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _resolve_run_root(override: str | None) -> Path:
    if override:
        path = Path(override).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path
    return _run_root()


def _init_run_dir(root: Path, slug: str, ts: str) -> Path:
    """Make the run directory, appending a numeric suffix if the timestamped name collides."""
    slug_dir = root / slug
    slug_dir.mkdir(parents=True, exist_ok=True)
    run_dir = slug_dir / ts
    suffix = 1
    while run_dir.exists():
        suffix += 1
        run_dir = slug_dir / f"{ts}_{suffix}"
    run_dir.mkdir(parents=True)
    return run_dir


def _copy_challenge_tree(meta_root: Path, run_dir: Path) -> tuple[int, int]:
    """Copy the challenge layout into the run dir. Returns (workspace file_count, bytes)."""
    shutil.copyfile(meta_root / "brief.md", run_dir / "brief.md")
    file_count, bytes_copied = _copy_tree(meta_root / "workspace", run_dir / "workspace")
    for sub in ("setup", "grader", "scenario"):
        src = meta_root / sub
        if src.exists():
            shutil.copytree(src, run_dir / sub, symlinks=False)
    return file_count, bytes_copied


def _bring_up_setup(run_dir: Path, container: bool) -> list[str]:
    """Run compose up or setup/setup.sh. Returns compose ports (empty for non-container)."""
    if container:
        compose_path = run_dir / "setup" / "compose.yaml"
        compose.rewrite_compose_for_run(compose_path, run_dir / "workspace")
        try:
            compose.up(run_dir)
        except subprocess.CalledProcessError as exc:
            compose.down(run_dir)
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            raise RunError(f"docker compose up failed: {stderr.strip()}") from exc
        return _compose_port_summary(compose_path)

    setup_sh = run_dir / "setup" / "setup.sh"
    if setup_sh.exists():
        if not os.access(setup_sh, os.X_OK):
            setup_sh.chmod(0o755)
        result = subprocess.run(
            [str(setup_sh)],
            cwd=run_dir,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RunError(f"setup/setup.sh failed (exit {result.returncode}):\n{result.stderr}")
    return []


def start(slug: str, variant: str, run_dir_override: str | None = None) -> StartInfo:
    try:
        meta: ChallengeMeta = resolve(slug)
    except RegistryError as exc:
        raise RunError(str(exc)) from exc

    v = meta.variant(variant)
    if v is None:
        raise RunError(
            f"variant '{variant}' not declared for challenge '{slug}'. "
            f"available: {[x['name'] for x in meta.variants]}"
        )

    root = _resolve_run_root(run_dir_override)
    run_dir = _init_run_dir(root, slug, _timestamp_folder())
    file_count, bytes_copied = _copy_challenge_tree(meta.root, run_dir)

    start_time = _iso_now()
    pin = {
        "harness": v["harness"],
        "model": v["model"],
        "time_budget": v.get("time_budget"),
    }
    run_json_obj: dict[str, Any] = {
        "slug": slug,
        "variant": variant,
        "start_time": start_time,
        "version": read_version(meta.root),
        "pin": pin,
    }
    schema.validate_run_json(run_json_obj)
    (run_dir / "run.json").write_text(json.dumps(run_json_obj, indent=2) + "\n")

    compose_ports = _bring_up_setup(run_dir, meta.container)

    return StartInfo(
        slug=slug,
        variant=variant,
        run_dir=run_dir,
        registry_dir=meta.root,
        pin=pin,
        brief_path=run_dir / "brief.md",
        start_time=start_time,
        container=meta.container,
        compose_ports=compose_ports,
        file_count=file_count,
        bytes_copied=bytes_copied,
    )


def _iter_run_dirs(root: Path | None = None) -> list[Path]:
    root = root or _run_root()
    if not root.exists():
        return []
    out: list[Path] = []
    for slug_dir in sorted(root.iterdir()):
        if not slug_dir.is_dir():
            continue
        for run_dir in sorted(slug_dir.iterdir()):
            if run_dir.is_dir() and (run_dir / "run.json").exists():
                out.append(run_dir)
    return out


def _load_run(run_dir: Path) -> ActiveRun | None:
    run_json = run_dir / "run.json"
    if not run_json.exists():
        return None
    try:
        data = json.loads(run_json.read_text())
    except json.JSONDecodeError:
        return None
    try:
        schema.validate_run_json(data)
    except schema.SchemaError:
        return None
    return ActiveRun(
        slug=data["slug"],
        variant=data["variant"],
        run_dir=run_dir,
        run_json=data,
        start_epoch=parse_iso(data["start_time"]),
    )


def active_run() -> ActiveRun | None:
    """The newest run without a result.json — see cli.html §vera-status."""
    candidates = [r for r in _iter_run_dirs() if not (r / "result.json").exists()]
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime)
    return _load_run(candidates[-1])


def latest_run_for_slug(slug: str) -> ActiveRun | None:
    """Newest run (graded or not) for a given slug. Used by `vera cd <slug>`."""
    candidates = [r for r in _iter_run_dirs() if r.parent.name == slug]
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime)
    return _load_run(candidates[-1])


def latest_graded_run() -> ActiveRun | None:
    """The newest run with a result.json — used by `vera submit`."""
    candidates = [r for r in _iter_run_dirs() if (r / "result.json").exists()]
    if not candidates:
        return None
    candidates.sort(key=lambda p: (p / "result.json").stat().st_mtime)
    return _load_run(candidates[-1])


_DIFF_EXCLUDES = (
    "--exclude=__pycache__",
    "--exclude=.pytest_cache",
    "--exclude=.mypy_cache",
    "--exclude=.ruff_cache",
    "--exclude=*.pyc",
    "--exclude=node_modules",
    "--exclude=.git",
    "--exclude=.vera_compose_project",
)


def compute_diff(registry_workspace: Path, run_workspace: Path, out_path: Path) -> None:
    """Write diff.patch from registry workspace → run workspace using unified diff."""
    args = [
        "diff",
        "-ruN",
        "--text",
        *_DIFF_EXCLUDES,
        str(registry_workspace),
        str(run_workspace),
    ]
    try:
        result = subprocess.run(
            args,
            check=False,
            capture_output=True,
        )
    except OSError as exc:
        raise RunError(f"diff failed: {exc}") from exc
    # diff returns 0 if identical, 1 if different, >=2 on error.
    if result.returncode >= 2:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise RunError(f"diff failed: {stderr}")
    text = result.stdout.decode("utf-8", errors="replace")
    out_path.write_text(text)


def write_result(run_dir: Path, result: dict[str, Any]) -> Path:
    schema.validate_result_json(result)
    path = run_dir / "result.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    return path


@dataclass
class SubmitInfo:
    journal_path: Path
    run_dir: Path
    remote: str | None


def submit(run: ActiveRun, target: str | None = None) -> SubmitInfo:
    result_path = run.run_dir / "result.json"
    if not result_path.exists():
        raise RunError("no result.json — run `vera grade` first")
    try:
        result = json.loads(result_path.read_text())
    except json.JSONDecodeError as exc:
        raise RunError(f"result.json is not valid JSON: {exc}") from exc

    line = {
        "slug": run.slug,
        "variant": run.variant,
        "start_time": run.run_json["start_time"],
        "pin": run.run_json["pin"],
        "result": result,
    }

    is_remote = target and (
        target.startswith(("http://", "https://", "git@", "ssh://")) or target.endswith(".git")
    )
    if is_remote:
        raise RunError("remote journal push is not implemented yet")

    journal = Path(target).expanduser() if target else config.journal_path()
    journal.parent.mkdir(parents=True, exist_ok=True)
    with journal.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")

    return SubmitInfo(journal_path=journal, run_dir=run.run_dir, remote=None)
