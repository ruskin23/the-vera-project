from __future__ import annotations

import sys

import click


@click.command()
@click.argument("slug")
@click.option("--container", is_flag=True, default=False, help="Scaffold a compose.yaml stub too.")
def new_cmd(slug: str, container: bool) -> None:
    """Scaffold a new challenge from a template."""
    from vera import scaffold
    from vera.core import render

    try:
        created = scaffold.create(slug=slug, container=container)
    except scaffold.ScaffoldError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)
    render.render_new(slug, created)
