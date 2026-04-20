from __future__ import annotations

import sys

import click


@click.command()
@click.argument("slug", required=False)
@click.option("--all", "all_flag", is_flag=True, default=False, help="Update every registered challenge.")
@click.option("--refresh", is_flag=True, default=False, help="Force-refetch the catalog before comparing.")
def update_cmd(slug: str | None, all_flag: bool, refresh: bool) -> None:
    """Update registered challenges against the catalog's current versions."""
    from vera.core import catalog, registry, render

    if slug and all_flag:
        click.echo("error: pass --all or a slug, not both", err=True)
        sys.exit(1)
    if not slug and not all_flag:
        click.echo("error: pass --all or a slug", err=True)
        sys.exit(1)

    try:
        data = catalog.fetch(force=refresh)
    except catalog.CatalogError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)

    registered = registry.list_challenges()
    if slug:
        registered = [r for r in registered if r.meta.slug == slug]
        if not registered:
            click.echo(f"error: {slug} is not registered", err=True)
            sys.exit(1)

    updates: list[tuple[str, str | None, str | None, str | None]] = []
    # (slug, old_version, new_version, error)
    for listed in registered:
        entry = catalog.resolve(listed.meta.slug, data)
        if entry is None:
            updates.append((listed.meta.slug, listed.version, None, "not in catalog"))
            continue
        if listed.version == entry.version:
            updates.append((listed.meta.slug, listed.version, entry.version, None))
            continue
        # Version differs — re-clone.
        try:
            subpath = entry.path
            registry.add(entry.url, subpath=subpath, version=entry.version)
        except registry.RegistryError as exc:
            updates.append((listed.meta.slug, listed.version, entry.version, str(exc)))
            continue
        updates.append((listed.meta.slug, listed.version, entry.version, None))

    render.render_update(updates)
