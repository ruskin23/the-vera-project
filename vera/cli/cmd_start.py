from __future__ import annotations

import sys

import click


@click.command()
@click.argument("slug")
@click.option("--variant", "variant", required=True, help="Variant declared in vera.yaml.")
@click.option("--run-dir", "run_dir", default=None, help="Override default ./runs/.")
def start_cmd(slug: str, variant: str, run_dir: str | None) -> None:
    """Create a run directory, set up the workspace, record the pin."""
    from vera.core import render, runs

    try:
        info = runs.start(slug=slug, variant=variant, run_dir_override=run_dir)
    except runs.RunError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)
    render.render_start(info)
