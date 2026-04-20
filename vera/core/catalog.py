"""Live-fetched, locally-cached challenge catalog.

The catalog is a pointer list (JSON) maintained in the Vera repo. `vera discover`,
`vera add <slug>`, and `vera update` all read it. Entries are either `single`
(one challenge in one repo) or `pack` (a monorepo with multiple sub-challenges).

Fetching: HTTP GET from `config.catalog_url()`. Cached at
`config.catalog_cache_path()`. Cache staleness is checked against
`config.catalog_ttl_seconds()`. On network failure, fall back to the existing
cache with a warning; if no cache exists, raise CatalogError.

The catalog is a *discovery* mechanism, not a protocol contract — nothing in
Vera's execution path requires it. Users can always `vera add <url>` directly.
"""
from __future__ import annotations

import json
import time
import warnings
from dataclasses import dataclass
from typing import Any

import requests

from vera.core import config, schema


class CatalogError(RuntimeError):
    pass


@dataclass
class ResolvedEntry:
    """A catalog entry resolved to a concrete (url, version, path) tuple."""

    slug: str
    url: str
    version: str
    path: str | None          # subpath within the repo, or None for whole-repo
    title: str
    description: str
    tags: list[str]
    author: str | None
    difficulty: str | None
    type: str                  # "single" or "pack-child"


@dataclass
class PackSummary:
    slug: str
    title: str
    description: str
    url: str
    version: str
    tags: list[str]
    author: str | None
    children: list[ResolvedEntry]


def _cache_stale(path) -> bool:
    if not path.exists():
        return True
    age = time.time() - path.stat().st_mtime
    return age > config.catalog_ttl_seconds()


def _load_cache() -> dict[str, Any] | None:
    path = config.catalog_cache_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        schema.validate_catalog(data)
        return data
    except (OSError, json.JSONDecodeError, Exception):
        return None


def _write_cache(data: dict[str, Any]) -> None:
    path = config.catalog_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def fetch(force: bool = False) -> dict[str, Any]:
    """Return the catalog data, refetching from the canonical URL when stale.

    `force=True` bypasses the cache and always re-fetches. On network failure
    with a cache present, returns the cache with a warning. On network failure
    with no cache, raises CatalogError.
    """
    cache = _load_cache()
    path = config.catalog_cache_path()

    if not force and cache is not None and not _cache_stale(path):
        return cache

    url = config.catalog_url()
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        schema.validate_catalog(data)
        _write_cache(data)
        return data
    except Exception as exc:
        if cache is not None:
            warnings.warn(
                f"catalog fetch failed ({exc}); using cached copy", stacklevel=2
            )
            return cache
        raise CatalogError(
            f"catalog unreachable at {url} and no cache available: {exc}"
        ) from exc


def _entries(data: dict[str, Any]) -> list[dict[str, Any]]:
    return list(data.get("entries") or [])


def _resolve_single(entry: dict[str, Any]) -> ResolvedEntry:
    return ResolvedEntry(
        slug=entry["slug"],
        url=entry["url"],
        version=entry["version"],
        path=entry.get("path"),
        title=entry.get("title", entry["slug"]),
        description=entry.get("description", ""),
        tags=list(entry.get("tags") or []),
        author=entry.get("author"),
        difficulty=entry.get("difficulty"),
        type="single",
    )


def _resolve_pack_child(pack: dict[str, Any], child: dict[str, Any]) -> ResolvedEntry:
    return ResolvedEntry(
        slug=child["slug"],
        url=pack["url"],
        version=pack["version"],
        path=child["path"],
        title=child.get("title", child["slug"]),
        description=child.get("description", ""),
        tags=list(child.get("tags") or pack.get("tags") or []),
        author=child.get("author", pack.get("author")),
        difficulty=child.get("difficulty", pack.get("difficulty")),
        type="pack-child",
    )


def resolve(slug: str, data: dict[str, Any] | None = None) -> ResolvedEntry | None:
    """Look up a slug in the catalog; None if not found.

    Matches single entries directly, or a sub-challenge inside any pack.
    (Pack-slug lookups use `expand_pack` instead — a pack is a collection.)
    """
    if data is None:
        try:
            data = fetch()
        except CatalogError:
            return None

    for entry in _entries(data):
        etype = entry.get("type")
        if etype == "single" and entry.get("slug") == slug:
            return _resolve_single(entry)
        if etype == "pack":
            for child in entry.get("challenges") or []:
                if child.get("slug") == slug:
                    return _resolve_pack_child(entry, child)
    return None


def expand_pack(slug: str, data: dict[str, Any] | None = None) -> list[ResolvedEntry] | None:
    """Return every child of a pack slug, or None if the slug isn't a pack."""
    if data is None:
        try:
            data = fetch()
        except CatalogError:
            return None

    for entry in _entries(data):
        if entry.get("type") == "pack" and entry.get("slug") == slug:
            return [_resolve_pack_child(entry, child) for child in entry["challenges"]]
    return None


def list_all(data: dict[str, Any] | None = None) -> tuple[list[PackSummary], list[ResolvedEntry]]:
    """
    Return (packs, singles) for `vera discover` to group the output.

    Pack entries are returned as PackSummary with their children inline.
    Single entries are returned as ResolvedEntry.
    """
    if data is None:
        data = fetch()

    packs: list[PackSummary] = []
    singles: list[ResolvedEntry] = []

    for entry in _entries(data):
        etype = entry.get("type")
        if etype == "single":
            singles.append(_resolve_single(entry))
        elif etype == "pack":
            children = [_resolve_pack_child(entry, c) for c in entry["challenges"]]
            packs.append(
                PackSummary(
                    slug=entry["slug"],
                    title=entry.get("title", entry["slug"]),
                    description=entry.get("description", ""),
                    url=entry["url"],
                    version=entry["version"],
                    tags=list(entry.get("tags") or []),
                    author=entry.get("author"),
                    children=children,
                )
            )

    return packs, singles
