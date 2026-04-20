"""Scaffold a new challenge via `vera new`."""

from __future__ import annotations

from pathlib import Path

from vera.scaffold import ScaffoldError

_VERA_YAML_TMPL = """\
slug: {slug}
title: "{slug}"
description: ""
container: {container}
tags: []

variants:
  - name: baseline
    harness: claude-code
    model: claude-opus-4-7
    time_budget: 2h
"""


_BRIEF_MD_TMPL = """\
# {slug}

Describe the failure mode concretely. What's broken, what's the symptom?

## passing looks like

- (measurable acceptance criterion)
- (another one)

## deliberately unspecified

- (design choice the challenger gets to make)
"""


_GRADE_SH_TMPL = """\
#!/usr/bin/env bash
set -euo pipefail

# This stub always fails. Replace with a real grader that emits JSON
# with {pass, score, signals, notes} on stdout and exits 0 on pass, 1 on fail.

jq -n '{
  "pass": false,
  "signals": {
    "stub": true
  },
  "notes": "grader/grade.sh is a placeholder. Replace it."
}'
exit 1
"""


_SETUP_SH_TMPL = """\
#!/usr/bin/env bash
set -euo pipefail

# Runs once at `vera start` after the workspace is copied.
# Install language deps, seed a database, generate fixtures — anything the
# workspace needs before the challenger can work. Must be idempotent.
"""


_COMPOSE_YAML_TMPL = """\
services:
  app:
    image: python:3.11-slim
    working_dir: /workspace
    volumes:
      - ./workspace:/workspace
    command: ["sleep", "infinity"]
"""


def _write(path: Path, content: str, *, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    if executable:
        path.chmod(0o755)


def create(slug: str, container: bool = False) -> list[str]:
    target = Path.cwd() / slug
    if target.exists():
        raise ScaffoldError(f"directory already exists: {target}")
    target.mkdir(parents=True)

    created: list[str] = []

    _write(
        target / "vera.yaml",
        _VERA_YAML_TMPL.format(slug=slug, container=str(container).lower()),
    )
    created.append("vera.yaml           (one baseline variant, placeholder pin)")

    _write(target / "brief.md", _BRIEF_MD_TMPL.format(slug=slug))
    created.append("brief.md            (empty, fill this in)")

    workspace = target / "workspace"
    workspace.mkdir()
    (workspace / ".gitkeep").write_text("")
    created.append("workspace/          (empty, drop your code here)")

    _write(target / "grader" / "grade.sh", _GRADE_SH_TMPL, executable=True)
    created.append("grader/grade.sh     (stub, currently always fails)")

    (target / "grader" / "fixtures").mkdir(parents=True)
    (target / "grader" / "fixtures" / ".gitkeep").write_text("")
    created.append("grader/fixtures/    (empty)")

    _write(target / "setup" / "setup.sh", _SETUP_SH_TMPL, executable=True)
    created.append("setup/setup.sh      (empty)")

    if container:
        _write(target / "setup" / "compose.yaml", _COMPOSE_YAML_TMPL)
        created.append("setup/compose.yaml  (stub — edit to match your challenge)")

    return created
