from __future__ import annotations

import sys

import click


@click.command()
@click.argument("slug")
def info_cmd(slug: str) -> None:
    """Show full detail about a registered challenge — variants, pins, paths, version."""
    from vera.core import catalog, registry, render

    entries = registry.list_challenges()
    matches = [e for e in entries if e.meta.slug == slug]
    if not matches:
        click.echo(f"error: {slug} is not registered locally", err=True)
        click.echo(
            "  hint: run `vera discover` to browse the catalog, or `vera add <slug>` to install.",
            err=True,
        )
        sys.exit(1)

    listed = matches[0]

    # Best-effort catalog lookup for the "update available" hint.
    catalog_version: str | None = None
    try:
        data = catalog.fetch()
        resolved = catalog.resolve(slug, data)
        if resolved:
            catalog_version = resolved.version
    except catalog.CatalogError:
        pass

    render.render_info(listed, catalog_version=catalog_version)
