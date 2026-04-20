from __future__ import annotations

import sys
from pathlib import Path

import click


def _looks_like_source(arg: str) -> bool:
    """A source argument is a URL, a local path, or a tarball — not a catalog slug."""
    if arg.startswith(("http://", "https://", "git@", "ssh://", "git+", "git://")):
        return True
    if arg.endswith(".git"):
        return True
    # Local path (existing directory) — treat as source.
    if Path(arg).expanduser().exists():
        return True
    # Contains a slash or backslash — probably a path even if it doesn't exist yet.
    if "/" in arg or "\\" in arg:
        return True
    return False


@click.command()
@click.argument("source_or_slug")
@click.option("--path", "path", default=None, help="Subdirectory inside the source.")
def add_cmd(source_or_slug: str, path: str | None) -> None:
    """Register a challenge from a catalog slug, git URL, local path, or tarball."""
    from vera.core import catalog, registry, render

    # If the argument doesn't look like a URL/path, try resolving through the
    # catalog (fetched live, cached locally). This is the primary way users
    # install challenges after `vera discover`.
    if not _looks_like_source(source_or_slug):
        try:
            data = catalog.fetch()
        except catalog.CatalogError as exc:
            click.echo(
                f"error: {source_or_slug!r} isn't a URL or local path and "
                f"the catalog is unreachable: {exc}",
                err=True,
            )
            sys.exit(1)

        pack_children = catalog.expand_pack(source_or_slug, data)
        if pack_children is not None:
            # Pack slug — install every child.
            results = []
            for child in pack_children:
                try:
                    result = registry.add(
                        child.url, subpath=child.path, version=child.version
                    )
                    results.extend(result)
                except registry.RegistryError as exc:
                    click.echo(
                        f"error installing {child.slug}: {exc}", err=True
                    )
                    sys.exit(1)
            render.render_add(results)
            return

        entry = catalog.resolve(source_or_slug, data)
        if entry is None:
            click.echo(
                f"error: {source_or_slug!r} isn't in the catalog and isn't a URL/path. "
                f"Run `vera discover` to see available slugs.",
                err=True,
            )
            sys.exit(1)

        try:
            results = registry.add(
                entry.url, subpath=entry.path, version=entry.version
            )
        except registry.RegistryError as exc:
            click.echo(f"error: {exc}", err=True)
            sys.exit(1)
        render.render_add(results)
        return

    # Direct URL / local path / tarball.
    try:
        results = registry.add(source_or_slug, subpath=path)
    except registry.RegistryError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)
    render.render_add(results)
