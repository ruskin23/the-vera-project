"""Invoke grader/grade.sh, parse stdout JSON, merge CLI-derived fields, write result.json."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vera.adapters import loader as adapter_loader
from vera.core import compose, harness, runs, schema


class GraderError(RuntimeError):
    pass


@dataclass
class GradeOutcome:
    run_dir: Path
    result: dict[str, Any]
    grader_seconds: float
    compose_down: bool
    adapter_used: adapter_loader.LoadedAdapter | None
    pin_honored: str
    budget_seconds: int | None
    elapsed_seconds: int
    notes: list[str] = field(default_factory=list)


@contextmanager
def _teardown_guard(run_dir: Path, container: bool, keep_stack: bool):
    """Ensure compose down runs on any exit path (except --keep-stack)."""
    interrupted = {"flag": False}
    previous_sigint = signal.getsignal(signal.SIGINT)

    def _handler(signum, frame):
        interrupted["flag"] = True
        raise KeyboardInterrupt()

    if container:
        signal.signal(signal.SIGINT, _handler)
    try:
        yield
    finally:
        if container:
            signal.signal(signal.SIGINT, previous_sigint)
            if not keep_stack:
                compose.down(run_dir)


def _run_grader(run_dir: Path) -> tuple[dict[str, Any], int, float]:
    grade_sh = run_dir / "grader" / "grade.sh"
    if not grade_sh.exists():
        raise GraderError(f"missing {grade_sh}")
    if not os.access(grade_sh, os.X_OK):
        grade_sh.chmod(0o755)

    start = time.time()
    result = subprocess.run(
        [str(grade_sh)],
        cwd=run_dir,
        check=False,
        capture_output=True,
        text=True,
    )
    elapsed = time.time() - start

    stdout = result.stdout.strip()
    if not stdout:
        raise GraderError(
            f"grader produced no stdout (exit {result.returncode}). stderr:\n{result.stderr}"
        )
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise GraderError(
            f"grader stdout is not valid JSON: {exc}\nstdout head: {stdout[:300]}"
        ) from exc

    if not isinstance(data, dict):
        raise GraderError(f"grader JSON must be an object; got {type(data).__name__}")

    try:
        schema.validate_grader_output(data)
    except schema.SchemaError as exc:
        raise GraderError(f"grader output schema: {exc}") from exc

    pass_field = bool(data.get("pass"))
    exit_code = result.returncode
    if pass_field and exit_code != 0:
        raise GraderError(
            f"grader reported pass:true but exited with {exit_code}; these must agree"
        )
    if not pass_field and exit_code == 0:
        raise GraderError(
            "grader reported pass:false but exited with 0; these must agree"
        )

    return data, exit_code, elapsed


def _budget_seconds(pin: dict[str, Any]) -> int | None:
    from vera.core.timebudget import parse_duration

    try:
        return parse_duration(pin.get("time_budget"))
    except ValueError:
        return None


def grade(run: runs.ActiveRun, skip_pin_check: bool, keep_stack: bool) -> GradeOutcome:
    run_dir = run.run_dir
    pin = run.run_json["pin"]
    harness_id = pin["harness"]
    pin_model = pin["model"]

    adapter = adapter_loader.get_adapter(harness_id)
    container = _run_is_container(run_dir)

    with _teardown_guard(run_dir, container, keep_stack):
        grader_data, _exit, grader_seconds = _run_grader(run_dir)
        end_epoch = time.time()

        outcome = harness.verify_and_collect(
            pin_model=pin_model,
            adapter=adapter,
            workspace_path=run_dir / "workspace",
            skip=skip_pin_check,
        )

        elapsed = max(0, int(end_epoch - run.start_epoch))
        result_obj: dict[str, Any] = {
            "pass": bool(grader_data["pass"]),
            "elapsed_seconds": elapsed,
            "pin_honored": outcome.pin_honored,
        }
        if "score" in grader_data:
            result_obj["score"] = grader_data["score"]
        if "signals" in grader_data:
            result_obj["signals"] = grader_data["signals"]
        if "notes" in grader_data and grader_data["notes"]:
            result_obj["notes"] = grader_data["notes"]
        if outcome.collaboration is not None:
            result_obj["collaboration"] = outcome.collaboration

        runs.write_result(run_dir, result_obj)

        try:
            runs.compute_diff(
                _registry_workspace_for(run),
                run_dir / "workspace",
                run_dir / "diff.patch",
            )
        except runs.RunError:
            pass

    return GradeOutcome(
        run_dir=run_dir,
        result=result_obj,
        grader_seconds=grader_seconds,
        compose_down=container and not keep_stack,
        adapter_used=adapter,
        pin_honored=outcome.pin_honored,
        budget_seconds=_budget_seconds(pin),
        elapsed_seconds=elapsed,
    )


def _run_is_container(run_dir: Path) -> bool:
    return (run_dir / "setup" / "compose.yaml").exists()


def _registry_workspace_for(run: runs.ActiveRun) -> Path:
    from vera.core import config

    return config.registry_path() / run.slug / "workspace"
