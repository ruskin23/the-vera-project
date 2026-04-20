from __future__ import annotations

import sys

import click


@click.group(name="adapters")
def adapters_group() -> None:
    """Harness adapter diagnostics."""


@adapters_group.command(name="list")
def list_adapters() -> None:
    """Show every adapter Vera loaded, grouped by source."""
    from vera.adapters import loader
    from vera.core import render

    groups = loader.discover_all()
    render.render_adapters_list(groups)


@adapters_group.command(name="test")
@click.argument("harness_id")
@click.option("--since", "since", default="1h", help="Window back from now (e.g. 30m, 2h, 1d).")
def test_adapter(harness_id: str, since: str) -> None:
    """Run a named adapter against recent sessions and print extracted turns."""
    from vera.adapters import loader
    from vera.core import render, timebudget

    adapter = loader.get_adapter(harness_id)
    if adapter is None:
        click.echo(f"error: no adapter with HARNESS_ID={harness_id}", err=True)
        sys.exit(1)

    seconds = timebudget.parse_duration(since)
    if seconds is None:
        click.echo(f"error: could not parse --since {since}", err=True)
        sys.exit(1)

    report = loader.probe_adapter(adapter, since_seconds=seconds)
    render.render_adapters_test(report)
