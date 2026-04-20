from __future__ import annotations

import sys

import click


def _local_version_for(slug: str) -> str | None:
    """Return the locally-installed version label, or None if not installed."""
    from vera.core import registry

    for entry in registry.list_challenges():
        if entry.meta.slug == slug:
            return entry.version if entry.version else "untagged"
    return None


@click.command()
@click.argument("slug", required=False)
@click.option("--refresh", is_flag=True, default=False, help="Force re-fetch the catalog.")
@click.option("--tag", "tags", multiple=True, help="Filter by tag (may repeat).")
@click.option("--pack", "pack", default=None, help="Only show challenges in this pack.")
@click.option("--search", "search", default=None, help="Match against slug/title/description.")
def discover_cmd(
    slug: str | None,
    refresh: bool,
    tags: tuple[str, ...],
    pack: str | None,
    search: str | None,
) -> None:
    """Browse the catalog of known challenges, or get detail on one."""
    from vera.core import catalog, render

    try:
        data = catalog.fetch(force=refresh)
    except catalog.CatalogError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)

    # Detail view: `vera discover <slug>` prints full metadata for one entry.
    if slug:
        entry = catalog.resolve(slug, data)
        if entry is not None:
            render.render_discover_detail(entry, local_version=_local_version_for(slug))
            return

        pack_children = catalog.expand_pack(slug, data)
        if pack_children is not None:
            pack_summaries, _ = catalog.list_all(data)
            match = next((p for p in pack_summaries if p.slug == slug), None)
            if match is not None:
                render.render_discover_pack(match)
                return

        click.echo(
            f"error: {slug!r} is not in the catalog. "
            f"Run `vera discover` without a slug to see what's available.",
            err=True,
        )
        sys.exit(1)

    packs, singles = catalog.list_all(data)

    def matches(entry, entry_tags: list[str]) -> bool:
        if tags and not any(t in entry_tags for t in tags):
            return False
        if search:
            term = search.lower()
            haystack = f"{entry.slug} {entry.title} {entry.description}".lower()
            if term not in haystack:
                return False
        return True

    any_filter = bool(tags) or bool(search)
    filtered_packs = []
    for p in packs:
        if pack and p.slug != pack:
            continue
        kept_children = [c for c in p.children if matches(c, c.tags)]
        if any_filter and not kept_children:
            continue
        filtered_packs.append((p, kept_children if any_filter else p.children))

    filtered_singles = [] if pack else [s for s in singles if matches(s, s.tags)]

    render.render_discover(filtered_packs, filtered_singles)
