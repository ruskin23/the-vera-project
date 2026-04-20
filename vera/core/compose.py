"""Docker compose wrappers + bind-mount rewrite.

Convention: challenge authors use `./workspace` (or `./workspace/<sub>`) as the host
side of the bind mount in setup/compose.yaml. At `vera start`, the rewriter swaps
`./workspace` for the absolute path to the run's workspace directory. Other volumes
are left untouched. Round-trip fidelity (comments, key order) is preserved via ruamel.yaml.
"""

from __future__ import annotations

import io
import shutil
import subprocess
from pathlib import Path

from ruamel.yaml import YAML


class ComposeError(RuntimeError):
    pass


_SOURCE_PREFIX = "./workspace"


def _yaml() -> YAML:
    y = YAML()
    y.preserve_quotes = True
    y.indent(mapping=2, sequence=4, offset=2)
    return y


def rewrite_compose_for_run(compose_path: Path, run_workspace: Path) -> None:
    """Rewrite the compose file in-place so ./workspace mounts point to the run's workspace."""
    run_workspace = run_workspace.resolve()
    y = _yaml()
    with compose_path.open("r") as f:
        data = y.load(f)

    if not isinstance(data, dict):
        raise ComposeError(f"{compose_path}: top-level must be a mapping")

    services = data.get("services") or {}
    if not isinstance(services, dict):
        raise ComposeError(f"{compose_path}: 'services' must be a mapping")

    rewritten = 0
    for _svc_name, svc in services.items():
        if not isinstance(svc, dict):
            continue
        volumes = svc.get("volumes")
        if volumes is None:
            continue
        for i, volume in enumerate(volumes):
            if isinstance(volume, str):
                if ":" in volume:
                    host, rest = volume.split(":", 1)
                    new_host = _rewrite_host(host, run_workspace)
                    if new_host != host:
                        volumes[i] = f"{new_host}:{rest}"
                        rewritten += 1
            elif isinstance(volume, dict):
                source = volume.get("source")
                if isinstance(source, str):
                    new_source = _rewrite_host(source, run_workspace)
                    if new_source != source:
                        volume["source"] = new_source
                        rewritten += 1

    buf = io.StringIO()
    y.dump(data, buf)
    compose_path.write_text(buf.getvalue())


def _rewrite_host(host: str, run_workspace: Path) -> str:
    stripped = host.strip()
    if stripped == _SOURCE_PREFIX:
        return str(run_workspace)
    if stripped.startswith(_SOURCE_PREFIX + "/"):
        subpath = stripped[len(_SOURCE_PREFIX) + 1 :]
        return str(run_workspace / subpath)
    return host


def _project_name(run_dir: Path) -> str:
    """Compose project name: sanitized slug_timestamp so parallel runs don't collide."""
    slug = run_dir.parent.name
    ts = run_dir.name.replace("-", "").replace("_", "").lower()
    return f"vera_{slug}_{ts}"[:60]


def _require_docker() -> None:
    if shutil.which("docker") is None:
        raise ComposeError("docker is required for container: true challenges")


def up(run_dir: Path) -> subprocess.CompletedProcess:
    _require_docker()
    compose = run_dir / "setup" / "compose.yaml"
    if not compose.exists():
        raise ComposeError(f"missing {compose}")
    project = _project_name(run_dir)
    (run_dir / ".vera_compose_project").write_text(project + "\n")
    return subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(compose),
            "-p",
            project,
            "up",
            "-d",
        ],
        cwd=run_dir,
        check=True,
        capture_output=True,
        text=True,
    )


def down(run_dir: Path) -> subprocess.CompletedProcess | None:
    if shutil.which("docker") is None:
        return None
    compose = run_dir / "setup" / "compose.yaml"
    if not compose.exists():
        return None
    project_file = run_dir / ".vera_compose_project"
    project = project_file.read_text().strip() if project_file.exists() else _project_name(run_dir)
    return subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(compose),
            "-p",
            project,
            "down",
            "--remove-orphans",
        ],
        cwd=run_dir,
        check=False,
        capture_output=True,
        text=True,
    )
