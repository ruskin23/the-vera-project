from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from vera.cli.cmd_info import info_cmd
from vera.core import config, registry

FIXTURE = Path(__file__).parent / "fixtures" / "catalog.json"


class TestInfo:
    def test_errors_when_slug_not_registered(self) -> None:
        result = CliRunner().invoke(info_cmd, ["no-such-slug"])
        assert result.exit_code == 1
        assert "not registered" in (result.stderr or result.output)

    def test_prints_description_and_variants(self, simple_challenge: Path) -> None:
        registry.add(str(simple_challenge))
        result = CliRunner().invoke(info_cmd, ["challenge-simple"])
        assert result.exit_code == 0, result.output
        assert "challenge-simple" in result.output
        assert "claude-code + claude-opus-4-7" in result.output
        assert "budget 30m" in result.output

    def test_shows_symlink_target(self, simple_challenge: Path) -> None:
        registry.add(str(simple_challenge))
        result = CliRunner().invoke(info_cmd, ["challenge-simple"])
        assert result.exit_code == 0
        assert "symlink →" in result.output
        assert str(simple_challenge.resolve()) in result.output or "symlink" in result.output

    def test_shows_update_available_when_catalog_ahead(self, simple_challenge: Path) -> None:
        registry.add(str(simple_challenge))
        # Manually set .vera_version so we have a local version to compare.
        (config.registry_path() / "challenge-simple" / ".vera_version").write_text("v1.0.0\n")
        # Seed cache with an entry at a newer version.
        cached = {
            "schema_version": 1,
            "entries": [
                {
                    "slug": "challenge-simple",
                    "type": "single",
                    "title": "fixture",
                    "url": "https://example.com/challenge-simple",
                    "version": "v1.0.1",
                }
            ],
        }
        config.catalog_cache_path().parent.mkdir(parents=True, exist_ok=True)
        config.catalog_cache_path().write_text(json.dumps(cached))

        result = CliRunner().invoke(info_cmd, ["challenge-simple"])
        assert result.exit_code == 0
        assert "update to v1.0.1 available" in result.output
