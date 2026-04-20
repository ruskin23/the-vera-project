from __future__ import annotations

import sys

import click


@click.command()
@click.option("--skip-pin-check", is_flag=True, default=False, help="Skip reading session logs.")
@click.option("--keep-stack", is_flag=True, default=False, help="Leave docker compose running.")
def grade_cmd(skip_pin_check: bool, keep_stack: bool) -> None:
    """Run the grader, verify the pin, write result.json."""
    from vera.core import grader, render, runs

    active = runs.active_run()
    if active is None:
        click.echo("error: no active run to grade", err=True)
        sys.exit(1)

    try:
        result = grader.grade(
            run=active,
            skip_pin_check=skip_pin_check,
            keep_stack=keep_stack,
        )
    except grader.GraderError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)
    render.render_grade(result)
    sys.exit(0 if result.result["pass"] else 1)
