from __future__ import annotations

import sys

import click


@click.command()
def status_cmd() -> None:
    """Show the active run, elapsed time, declared pin."""
    from vera.core import render, runs

    active = runs.active_run()
    if active is None:
        click.echo("no active run", err=True)
        sys.exit(1)
    render.render_status(active)
