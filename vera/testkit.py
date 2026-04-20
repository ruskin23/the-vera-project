"""End-to-end simulator for `vera test`.

Runs, for each declared variant:
  1. vera start → setup → grade pristine workspace (must fail).
  2. vera start → overlay grader/fixtures/solution/ → grade (must pass).
Emits the checklist from cli.html § vera-test.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from vera.core import compose, grader, runs, schema
from vera.core.validate import ChallengeError, validate_challenge


class TestkitError(RuntimeError):
    pass


@dataclass
class ReportLine:
    ok: bool
    text: str
    details: list[str] = field(default_factory=list)


@dataclass
class Report:
    lines: list[ReportLine]

    @property
    def ok(self) -> bool:
        return all(line.ok for line in self.lines)


def _find_challenge_root() -> Path:
    cwd = Path.cwd()
    if (cwd / "vera.yaml").exists():
        return cwd
    raise TestkitError("no vera.yaml in cwd — run `vera test` inside a challenge directory")


def _solution_dir(root: Path) -> Path | None:
    candidate = root / "grader" / "fixtures" / "solution"
    return candidate if candidate.exists() and candidate.is_dir() else None


def _copy_tree(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst, symlinks=False)


def _overlay(source: Path, target: Path) -> None:
    """Copy source contents over target, overwriting files (simple rsync-like)."""
    for item in source.rglob("*"):
        if item.is_dir():
            continue
        rel = item.relative_to(source)
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, dst)


def _make_run_dir(root: Path, tmp_runs: Path, pin: dict, variant_name: str) -> runs.ActiveRun:
    """Manually construct a run dir using the same contract as runs.start()."""
    slug_dir = tmp_runs / root.name
    slug_dir.mkdir(parents=True, exist_ok=True)
    run_dir = slug_dir / f"testkit_{variant_name}"
    idx = 1
    while run_dir.exists():
        idx += 1
        run_dir = slug_dir / f"testkit_{variant_name}_{idx}"
    run_dir.mkdir()

    shutil.copyfile(root / "brief.md", run_dir / "brief.md")
    _copy_tree(root / "workspace", run_dir / "workspace")
    if (root / "setup").exists():
        _copy_tree(root / "setup", run_dir / "setup")
    if (root / "grader").exists():
        _copy_tree(root / "grader", run_dir / "grader")
    if (root / "scenario").exists():
        _copy_tree(root / "scenario", run_dir / "scenario")

    import json as _json
    from datetime import datetime as _dt
    from datetime import timezone as _tz

    start_time = _dt.now(_tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_obj = {
        "slug": root.name,
        "variant": variant_name,
        "start_time": start_time,
        "pin": pin,
    }
    schema.validate_run_json(run_obj)
    (run_dir / "run.json").write_text(_json.dumps(run_obj, indent=2) + "\n")

    from vera.core.runs import _parse_iso

    return runs.ActiveRun(
        slug=root.name,
        variant=variant_name,
        run_dir=run_dir,
        run_json=run_obj,
        start_epoch=_parse_iso(start_time),
    )


def _bring_up_environment(run_dir: Path, container: bool) -> list[str]:
    warnings: list[str] = []
    if container:
        compose_path = run_dir / "setup" / "compose.yaml"
        compose.rewrite_compose_for_run(compose_path, run_dir / "workspace")
        try:
            compose.up(run_dir)
        except subprocess.CalledProcessError as exc:
            compose.down(run_dir)
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            warnings.append(f"docker compose up failed: {stderr}")
    else:
        setup_sh = run_dir / "setup" / "setup.sh"
        if setup_sh.exists():
            setup_sh.chmod(0o755)
            result = subprocess.run(
                [str(setup_sh)], cwd=run_dir, check=False, capture_output=True, text=True
            )
            if result.returncode != 0:
                warnings.append(f"setup/setup.sh exited {result.returncode}: {result.stderr}")
    return warnings


def _grade_once(run: runs.ActiveRun) -> grader.GradeOutcome:
    return grader.grade(run=run, skip_pin_check=True, keep_stack=False)


def _variants_to_test(meta, selection: str | None):
    if selection is None:
        return list(meta.variants)
    for v in meta.variants:
        if v["name"] == selection:
            return [v]
    raise TestkitError(f"variant '{selection}' not declared in vera.yaml")


def run(variant: str | None = None) -> Report:
    root = _find_challenge_root()
    lines: list[ReportLine] = []

    try:
        meta = validate_challenge(root)
        lines.append(ReportLine(True, "vera.yaml valid"))
    except ChallengeError as exc:
        return Report([ReportLine(False, "vera.yaml valid", details=[str(exc)])])

    lines.append(ReportLine(True, "workspace/ present and non-empty"))
    lines.append(ReportLine(True, "grader/grade.sh executable"))

    try:
        variants = _variants_to_test(meta, variant)
    except TestkitError as exc:
        lines.append(ReportLine(False, "variant selection", details=[str(exc)]))
        return Report(lines)

    solution = _solution_dir(root)

    tmp_root = Path(tempfile.mkdtemp(prefix="vera-test-"))
    tmp_runs = tmp_root / "runs"
    tmp_runs.mkdir()
    try:
        for v in variants:
            _run_single_variant(v, meta, root, tmp_runs, solution, lines)
    finally:
        # Files created inside a container may be owned by root; best-effort cleanup.
        shutil.rmtree(tmp_root, ignore_errors=True)

    return Report(lines)


def _run_single_variant(v, meta, root, tmp_runs, solution, lines):
    pin = {
        "harness": v["harness"],
        "model": v["model"],
        "time_budget": v.get("time_budget"),
    }
    tag = f"variant {v['name']}"

    pristine = _make_run_dir(root, tmp_runs, pin, f"{v['name']}_pristine")
    warnings = _bring_up_environment(pristine.run_dir, meta.container)
    if warnings:
        lines.append(ReportLine(False, f"setup/ runs cleanly ({tag})", details=warnings))
        return
    lines.append(ReportLine(True, f"setup/ runs cleanly ({tag})"))

    try:
        pristine_outcome = _grade_once(pristine)
    except grader.GraderError as exc:
        lines.append(
            ReportLine(
                False,
                f"grader fails on unmodified workspace ({tag})",
                details=[str(exc)],
            )
        )
        return

    if pristine_outcome.result["pass"] is True:
        lines.append(
            ReportLine(
                False,
                f"grader fails on unmodified workspace ({tag})",
                details=[
                    "grader returned pass:true on pristine workspace",
                    "the failure mode isn't actually triggered",
                    "check that setup/setup.sh leaves the workspace in the broken state",
                ],
            )
        )
        return
    lines.append(ReportLine(True, f"grader fails on unmodified workspace ({tag})"))

    try:
        schema.validate_result_json(pristine_outcome.result)
    except Exception as exc:
        lines.append(
            ReportLine(
                False,
                f"result.json schema valid on pristine ({tag})",
                details=[str(exc)],
            )
        )
        return

    if solution is None:
        lines.append(
            ReportLine(
                False,
                f"grader passes on fixtures/solution/ ({tag})",
                details=[
                    "no grader/fixtures/solution/ found",
                    "create one that represents the known-good fix",
                ],
            )
        )
        return

    solved = _make_run_dir(root, tmp_runs, pin, f"{v['name']}_solution")
    _overlay(solution, solved.run_dir / "workspace")
    warnings = _bring_up_environment(solved.run_dir, meta.container)
    if warnings:
        lines.append(
            ReportLine(
                False,
                f"setup/ runs cleanly on solution ({tag})",
                details=warnings,
            )
        )
        return

    try:
        solved_outcome = _grade_once(solved)
    except grader.GraderError as exc:
        lines.append(
            ReportLine(
                False,
                f"grader passes on fixtures/solution/ ({tag})",
                details=[str(exc)],
            )
        )
        return

    if not solved_outcome.result["pass"]:
        lines.append(
            ReportLine(
                False,
                f"grader passes on fixtures/solution/ ({tag})",
                details=[
                    "planted solution did not pass — grader may be too strict,",
                    "or the fixture solution has drifted from workspace.",
                ],
            )
        )
        return
    lines.append(ReportLine(True, f"grader passes on fixtures/solution/ ({tag})"))

    try:
        schema.validate_result_json(solved_outcome.result)
        lines.append(ReportLine(True, f"result.json schema valid ({tag})"))
    except Exception as exc:
        lines.append(
            ReportLine(
                False,
                f"result.json schema valid ({tag})",
                details=[str(exc)],
            )
        )
