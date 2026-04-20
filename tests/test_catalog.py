from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vera.core import catalog, config


FIXTURE = Path(__file__).parent / "fixtures" / "catalog.json"


@pytest.fixture
def fixture_catalog() -> dict:
    return json.loads(FIXTURE.read_text())


class TestFetch:
    def test_fetch_writes_cache(self, fixture_catalog) -> None:
        fake_resp = MagicMock()
        fake_resp.json.return_value = fixture_catalog
        fake_resp.raise_for_status.return_value = None
        with patch("vera.core.catalog.requests.get", return_value=fake_resp):
            data = catalog.fetch(force=True)
        assert data["schema_version"] == 1
        assert config.catalog_cache_path().exists()

    def test_fetch_uses_cache_when_fresh(self, fixture_catalog) -> None:
        cache_path = config.catalog_cache_path()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(fixture_catalog))
        with patch("vera.core.catalog.requests.get") as get:
            catalog.fetch(force=False)
            get.assert_not_called()

    def test_force_refetches_even_when_fresh(self, fixture_catalog) -> None:
        cache_path = config.catalog_cache_path()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(fixture_catalog))
        fake_resp = MagicMock()
        fake_resp.json.return_value = fixture_catalog
        fake_resp.raise_for_status.return_value = None
        with patch("vera.core.catalog.requests.get", return_value=fake_resp) as get:
            catalog.fetch(force=True)
            get.assert_called_once()

    def test_refetches_when_cache_stale(self, fixture_catalog, monkeypatch) -> None:
        cache_path = config.catalog_cache_path()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(fixture_catalog))
        import os as _os
        old = time.time() - (7 * 3600)
        _os.utime(cache_path, (old, old))

        fake_resp = MagicMock()
        fake_resp.json.return_value = fixture_catalog
        fake_resp.raise_for_status.return_value = None
        with patch("vera.core.catalog.requests.get", return_value=fake_resp) as get:
            catalog.fetch(force=False)
            get.assert_called_once()

    def test_offline_fallback_uses_cache(self, fixture_catalog) -> None:
        cache_path = config.catalog_cache_path()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(fixture_catalog))
        # Make cache stale so fetch tries network.
        import os as _os
        old = time.time() - (7 * 3600)
        _os.utime(cache_path, (old, old))

        with patch("vera.core.catalog.requests.get", side_effect=ConnectionError("no net")):
            with pytest.warns(UserWarning, match="catalog fetch failed"):
                data = catalog.fetch(force=False)
        assert data["schema_version"] == 1

    def test_offline_no_cache_raises(self) -> None:
        with patch("vera.core.catalog.requests.get", side_effect=ConnectionError("no net")):
            with pytest.raises(catalog.CatalogError, match="catalog unreachable"):
                catalog.fetch(force=True)


class TestResolve:
    def test_resolve_single_entry(self, fixture_catalog) -> None:
        entry = catalog.resolve("solo-challenge", fixture_catalog)
        assert entry is not None
        assert entry.slug == "solo-challenge"
        assert entry.url == "https://github.com/alice/solo-challenge"
        assert entry.version == "v1.0.0"
        assert entry.path is None
        assert entry.type == "single"

    def test_resolve_child_of_pack(self, fixture_catalog) -> None:
        entry = catalog.resolve("blog-api-auth", fixture_catalog)
        assert entry is not None
        assert entry.slug == "blog-api-auth"
        assert entry.url == "https://github.com/vera/vera-starter-pack"
        assert entry.version == "v1.2.0"
        assert entry.path == "challenges/blog-api-auth"
        assert entry.type == "pack-child"

    def test_resolve_unknown_returns_none(self, fixture_catalog) -> None:
        assert catalog.resolve("nonexistent", fixture_catalog) is None

    def test_resolve_pack_slug_returns_none(self, fixture_catalog) -> None:
        """Pack slugs aren't resolved directly — use expand_pack."""
        assert catalog.resolve("vera-starter-pack", fixture_catalog) is None


class TestExpandPack:
    def test_expand_pack_returns_all_children(self, fixture_catalog) -> None:
        entries = catalog.expand_pack("vera-starter-pack", fixture_catalog)
        assert entries is not None
        assert [e.slug for e in entries] == ["blog-api-auth", "fifo-queue-redesign"]
        assert all(e.url == "https://github.com/vera/vera-starter-pack" for e in entries)
        assert all(e.version == "v1.2.0" for e in entries)

    def test_expand_unknown_pack_returns_none(self, fixture_catalog) -> None:
        assert catalog.expand_pack("no-such-pack", fixture_catalog) is None

    def test_expand_single_slug_returns_none(self, fixture_catalog) -> None:
        """Single slugs aren't packs."""
        assert catalog.expand_pack("solo-challenge", fixture_catalog) is None


class TestListAll:
    def test_list_all_groups_packs_and_singles(self, fixture_catalog) -> None:
        packs, singles = catalog.list_all(fixture_catalog)
        assert len(packs) == 1
        assert packs[0].slug == "vera-starter-pack"
        assert len(packs[0].children) == 2
        assert len(singles) == 1
        assert singles[0].slug == "solo-challenge"
