from __future__ import annotations

import os
import subprocess
import sys

import click


@click.command()
@click.argument("slug", required=False)
def shell_cmd(slug: str | None) -> None:
    """Spawn $SHELL in the active run's workspace/. Exit returns here."""
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

    workspace = (active.run_dir / "workspace").resolve()
    shell = os.environ.get("SHELL", "/bin/sh")
    result = subprocess.run([shell], cwd=workspace)
    sys.exit(result.returncode)
