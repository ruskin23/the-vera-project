from __future__ import annotations

import sys

import click


@click.command()
@click.option("--variant", "variant", default=None, help="Test a single variant (default: all).")
def test_cmd(variant: str | None) -> None:
    """Author-side: simulate a challenger flow end-to-end."""
    from vera import testkit
    from vera.core import render

    try:
        report = testkit.run(variant=variant)
    except testkit.TestkitError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)
    render.render_test(report)
    sys.exit(0 if report.ok else 1)
