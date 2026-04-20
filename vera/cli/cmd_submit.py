from __future__ import annotations

import sys

import click


@click.command()
@click.option("--to", "target", default=None, help="Override journal target for this call.")
def submit_cmd(target: str | None) -> None:
    """Append the run result to a personal journal or remote log."""
    from vera.core import render, runs

    active = runs.latest_graded_run()
    if active is None:
        click.echo("error: no graded run to submit", err=True)
        sys.exit(1)
    try:
        info = runs.submit(active, target=target)
    except runs.RunError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)
    render.render_submit(info)
