from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML

from vera.core.compose import rewrite_compose_for_run

COMPOSE_BEFORE = """\
# top-level comment
services:
  api:
    image: python:3.11
    working_dir: /workspace
    volumes:
      - ./workspace:/workspace
      - ./workspace/data:/data
      - my_volume:/var/lib/app
    ports:
      - "8000:8000"
  db:
    image: postgres:16
    ports:
      - "5432:5432"
"""


def test_rewrite_replaces_workspace_mounts(tmp_path: Path) -> None:
    compose = tmp_path / "compose.yaml"
    compose.write_text(COMPOSE_BEFORE)
    run_workspace = tmp_path / "runs" / "slug" / "2026-04-19_1200" / "workspace"
    run_workspace.mkdir(parents=True)

    rewrite_compose_for_run(compose, run_workspace)
    data = YAML().load(compose.read_text())

    api_vols = data["services"]["api"]["volumes"]
    assert str(run_workspace.resolve()) + ":/workspace" in api_vols
    assert str(run_workspace.resolve() / "data") + ":/data" in api_vols
    # The named volume must pass through unchanged.
    assert "my_volume:/var/lib/app" in api_vols


def test_rewrite_preserves_other_fields(tmp_path: Path) -> None:
    compose = tmp_path / "compose.yaml"
    compose.write_text(COMPOSE_BEFORE)
    run_workspace = tmp_path / "ws"
    run_workspace.mkdir()
    rewrite_compose_for_run(compose, run_workspace)
    data = YAML().load(compose.read_text())
    assert data["services"]["api"]["image"] == "python:3.11"
    assert data["services"]["db"]["ports"] == ['"5432:5432"'] or "5432:5432" in str(
        data["services"]["db"]["ports"][0]
    )
