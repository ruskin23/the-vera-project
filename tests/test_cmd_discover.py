from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from vera.cli.cmd_discover import discover_cmd
from vera.core import config


FIXTURE = Path(__file__).parent / "fixtures" / "catalog.json"


def _seed_cache() -> None:
    cache_path = config.catalog_cache_path()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(FIXTURE.read_text())


class TestDiscover:
    def test_lists_packs_and_singles(self) -> None:
        _seed_cache()
        result = CliRunner().invoke(discover_cmd, [])
        assert result.exit_code == 0, result.output
        assert "vera-starter-pack" in result.output
        assert "solo-challenge" in result.output
        assert "blog-api-auth" in result.output
        assert "fifo-queue-redesign" in result.output

    def test_filter_by_tag(self) -> None:
        _seed_cache()
        result = CliRunner().invoke(discover_cmd, ["--tag", "perf"])
        assert result.exit_code == 0
        assert "fifo-queue-redesign" in result.output
        # solo-challenge doesn't have "perf" tag
        assert "solo-challenge" not in result.output

    def test_filter_by_pack(self) -> None:
        _seed_cache()
        result = CliRunner().invoke(discover_cmd, ["--pack", "vera-starter-pack"])
        assert result.exit_code == 0
        assert "blog-api-auth" in result.output
        assert "solo-challenge" not in result.output

    def test_search_matches_description(self) -> None:
        _seed_cache()
        result = CliRunner().invoke(discover_cmd, ["--search", "solo"])
        assert result.exit_code == 0
        assert "solo-challenge" in result.output
        assert "fifo-queue-redesign" not in result.output

    def test_error_when_catalog_unreachable(self) -> None:
        # No cache, no network -- expect error.
        from unittest.mock import patch
        with patch("vera.core.catalog.requests.get", side_effect=ConnectionError("no net")):
            result = CliRunner().invoke(discover_cmd, [])
        assert result.exit_code == 1


class TestDiscoverDetail:
    def test_single_entry_detail(self) -> None:
        _seed_cache()
        result = CliRunner().invoke(discover_cmd, ["solo-challenge"])
        assert result.exit_code == 0, result.output
        assert "solo-challenge" in result.output
        assert "@v1.0.0" in result.output
        assert "alice" in result.output
        assert "(not installed)" in result.output
        assert "install with: vera add solo-challenge" in result.output

    def test_pack_entry_detail(self) -> None:
        _seed_cache()
        result = CliRunner().invoke(discover_cmd, ["vera-starter-pack"])
        assert result.exit_code == 0, result.output
        assert "Vera starter pack" in result.output
        assert "@v1.2.0" in result.output
        assert "challenges in this pack (2)" in result.output
        assert "blog-api-auth" in result.output
        assert "fifo-queue-redesign" in result.output

    def test_pack_child_detail(self) -> None:
        _seed_cache()
        result = CliRunner().invoke(discover_cmd, ["blog-api-auth"])
        assert result.exit_code == 0
        # blog-api-auth is a pack child in the fixture; should resolve via catalog.resolve
        assert "blog-api-auth" in result.output
        assert "@v1.2.0" in result.output
        assert "vera-starter-pack" in result.output

    def test_unknown_slug_errors(self) -> None:
        _seed_cache()
        result = CliRunner().invoke(discover_cmd, ["no-such-thing"])
        assert result.exit_code == 1
        assert "not in the catalog" in (result.stderr or result.output)
