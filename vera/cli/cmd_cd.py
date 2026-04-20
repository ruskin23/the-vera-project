from __future__ import annotations

import sys

import click


@click.command()
@click.argument("slug", required=False)
def cd_cmd(slug: str | None) -> None:
    """Print the absolute path to the active run's workspace.

    Invoke via shell substitution:

        cd "$(vera cd)"

    With no argument, targets the newest ungraded run. With a slug, targets
    the newest run (graded or not) for that slug.
    """
    from vera.core import runs

    if slug is None:
        active = runs.active_run()
        if active is None:
            click.echo("error: no active run", err=True)
            sys.exit(1)
    else:
        active = runs.latest_run_for_slug(slug)
        if active is None:
            click.echo(f"error: no runs for slug {slug!r}", err=True)
            sys.exit(1)

    click.echo(str((active.run_dir / "workspace").resolve()))
