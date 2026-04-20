from __future__ import annotations

import pytest

from vera.core import schema


def _valid_vera_yaml() -> dict:
    return {
        "slug": "blog-api-auth",
        "title": "Blog API",
        "container": True,
        "tags": ["fastapi"],
        "variants": [
            {
                "name": "baseline",
                "harness": "claude-code",
                "model": "claude-opus-4-7",
                "time_budget": "2h",
            }
        ],
    }


def _valid_run_json() -> dict:
    return {
        "slug": "blog-api-auth",
        "variant": "baseline",
        "start_time": "2026-04-18T16:34:02Z",
        "pin": {
            "harness": "claude-code",
            "model": "claude-opus-4-7",
            "time_budget": "2h",
        },
    }


def _valid_result_json() -> dict:
    return {
        "pass": True,
        "score": 74,
        "elapsed_seconds": 6420,
        "pin_honored": "yes",
        "collaboration": {
            "turns": 47,
            "tool_calls": 183,
            "tool_calls_by_kind": {"Read": 62, "Edit": 21, "Bash": 85, "Grep": 15},
            "model_switches": 0,
            "in_session_seconds": 5400,
        },
        "signals": {"tests_passed": 38, "tests_total": 42},
        "notes": "ok",
    }


class TestVeraYaml:
    def test_valid_passes(self) -> None:
        schema.validate_vera_yaml(_valid_vera_yaml())

    def test_missing_slug_fails(self) -> None:
        bad = _valid_vera_yaml()
        del bad["slug"]
        with pytest.raises(schema.SchemaError):
            schema.validate_vera_yaml(bad)

    def test_bad_slug_pattern_fails(self) -> None:
        bad = _valid_vera_yaml()
        bad["slug"] = "Not_Valid"
        with pytest.raises(schema.SchemaError):
            schema.validate_vera_yaml(bad)

    def test_no_variants_fails(self) -> None:
        bad = _valid_vera_yaml()
        bad["variants"] = []
        with pytest.raises(schema.SchemaError):
            schema.validate_vera_yaml(bad)


class TestRunJson:
    def test_valid_passes(self) -> None:
        schema.validate_run_json(_valid_run_json())

    def test_missing_pin_fails(self) -> None:
        bad = _valid_run_json()
        del bad["pin"]
        with pytest.raises(schema.SchemaError):
            schema.validate_run_json(bad)


class TestResultJson:
    def test_valid_passes(self) -> None:
        schema.validate_result_json(_valid_result_json())

    def test_missing_required_fails(self) -> None:
        bad = _valid_result_json()
        del bad["pin_honored"]
        with pytest.raises(schema.SchemaError):
            schema.validate_result_json(bad)

    def test_bad_pin_honored_enum_fails(self) -> None:
        bad = _valid_result_json()
        bad["pin_honored"] = "maybe"
        with pytest.raises(schema.SchemaError):
            schema.validate_result_json(bad)
