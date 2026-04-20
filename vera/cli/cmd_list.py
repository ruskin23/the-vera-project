from __future__ import annotations

import click


@click.command()
@click.option("--tag", "tags", multiple=True, help="Filter by tag (may repeat).")
def list_cmd(tags: tuple[str, ...]) -> None:
    """Show registered challenges and their variants."""
    from vera.core import catalog, registry, render

    entries = registry.list_challenges(tags=list(tags) or None)

    # Best-effort catalog lookup for update markers. Silent fallback on failure —
    # the list should always render even if we can't reach the catalog.
    catalog_versions: dict[str, str] = {}
    try:
        data = catalog.fetch()
        for entry in entries:
            resolved = catalog.resolve(entry.meta.slug, data)
            if resolved:
                catalog_versions[entry.meta.slug] = resolved.version
    except catalog.CatalogError:
        pass

    render.render_list(entries, catalog_versions=catalog_versions)
