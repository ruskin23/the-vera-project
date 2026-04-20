"""Challenge-contract static check.

Runs at `vera add` (before installing into the registry) and again at `vera start`
(fail-fast gate; catches hand-edits to a registered challenge).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from vera.core import schema, timebudget


class ChallengeError(ValueError):
    """Raised when a challenge directory fails the static contract check."""


@dataclass
class ChallengeMeta:
    slug: str
    title: str
    description: str | None
    container: bool
    tags: list[str]
    variants: list[dict[str, Any]]
    root: Path

    def variant(self, name: str) -> dict[str, Any] | None:
        for v in self.variants:
            if v["name"] == name:
                return v
        return None


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ChallengeError(message)


def load_vera_yaml(challenge_dir: Path) -> dict[str, Any]:
    yaml_path = challenge_dir / "vera.yaml"
    _require(yaml_path.exists(), f"missing vera.yaml at {yaml_path}")
    try:
        with yaml_path.open() as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ChallengeError(f"vera.yaml parse error: {exc}") from exc
    _require(isinstance(data, dict), "vera.yaml must be a mapping")
    return data


def validate_challenge(challenge_dir: Path) -> ChallengeMeta:
    """Run the challenge-contract check. Returns parsed meta or raises ChallengeError."""
    challenge_dir = challenge_dir.resolve()
    _require(challenge_dir.is_dir(), f"not a directory: {challenge_dir}")

    data = load_vera_yaml(challenge_dir)
    try:
        schema.validate_vera_yaml(data)
    except schema.SchemaError as exc:
        raise ChallengeError(f"vera.yaml schema: {exc}") from exc

    slug = data["slug"]
    folder_name = challenge_dir.name
    _require(
        slug == folder_name,
        f"slug '{slug}' must match folder name '{folder_name}'",
    )

    brief = challenge_dir / "brief.md"
    _require(brief.exists(), "missing brief.md")
    _require(brief.stat().st_size > 0, "brief.md is empty")

    workspace = challenge_dir / "workspace"
    _require(workspace.is_dir(), "missing workspace/ directory")
    _require(any(workspace.iterdir()), "workspace/ is empty")

    grade_sh = challenge_dir / "grader" / "grade.sh"
    _require(grade_sh.exists(), "missing grader/grade.sh")
    _require(os.access(grade_sh, os.X_OK), "grader/grade.sh is not executable")

    container = bool(data.get("container", False))
    if container:
        compose = challenge_dir / "setup" / "compose.yaml"
        _require(
            compose.exists(),
            "container: true but setup/compose.yaml is missing",
        )

    # Parse time budgets in every variant to catch malformed values early.
    for v in data["variants"]:
        tb = v.get("time_budget")
        try:
            timebudget.parse_duration(tb)
        except ValueError as exc:
            raise ChallengeError(f"variant {v.get('name', '?')}: {exc}") from exc

    return ChallengeMeta(
        slug=slug,
        title=data["title"],
        description=data.get("description"),
        container=container,
        tags=list(data.get("tags", [])),
        variants=list(data["variants"]),
        root=challenge_dir,
    )


def find_challenge_dirs(root: Path) -> list[Path]:
    """
    Find all challenge directories under `root`.

    If `root` itself has a valid-looking vera.yaml, returns [root].
    Otherwise, scans one level down and returns subdirs with vera.yaml.
    """
    if (root / "vera.yaml").exists():
        return [root]
    results: list[Path] = []
    for child in sorted(root.iterdir()):
        if child.is_dir() and (child / "vera.yaml").exists():
            results.append(child)
    return results
