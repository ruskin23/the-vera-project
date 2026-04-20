from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from vera.cli.cmd_update import update_cmd
from vera.core import config, registry


FIXTURE = Path(__file__).parent / "fixtures" / "catalog.json"


def _seed_cache() -> None:
    cache_path = config.catalog_cache_path()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(FIXTURE.read_text())


class TestUpdate:
    def test_requires_slug_or_all_flag(self) -> None:
        result = CliRunner().invoke(update_cmd, [])
        assert result.exit_code == 1
        assert "--all" in (result.stderr or result.output)

    def test_rejects_both_slug_and_all(self) -> None:
        result = CliRunner().invoke(update_cmd, ["foo", "--all"])
        assert result.exit_code == 1

    def test_up_to_date_prints_marker(self, simple_challenge: Path) -> None:
        _seed_cache()
        # Register locally with a matching version.
        registry.add(str(simple_challenge))
        # Manually write .vera_version so the update check has something to compare.
        (config.registry_path() / "challenge-simple" / ".vera_version").write_text("v1.0.0\n")
        # Edit the cached catalog to include this slug at v1.0.0.
        cached = json.loads(config.catalog_cache_path().read_text())
        cached["entries"].append({
            "slug": "challenge-simple",
            "type": "single",
            "title": "fixture",
            "url": "https://example.com/challenge-simple",
            "version": "v1.0.0",
        })
        config.catalog_cache_path().write_text(json.dumps(cached))

        result = CliRunner().invoke(update_cmd, ["challenge-simple"])
        assert result.exit_code == 0, result.output
        assert "up to date" in result.output

    def test_error_when_slug_not_registered(self) -> None:
        _seed_cache()
        result = CliRunner().invoke(update_cmd, ["no-such-slug"])
        assert result.exit_code == 1
