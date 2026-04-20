"""JSON schemas for vera.yaml, run.json, result.json."""

from __future__ import annotations

from typing import Any

import jsonschema

VARIANT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["name", "harness", "model", "time_budget"],
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "harness": {"type": "string", "minLength": 1},
        "model": {"type": "string", "minLength": 1},
        "time_budget": {"type": ["string", "integer", "null"]},
        "notes": {"type": "string"},
    },
    "additionalProperties": True,
}


VERA_YAML_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["slug", "title", "variants"],
    "properties": {
        "slug": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$"},
        "title": {"type": "string", "minLength": 1},
        "description": {"type": "string"},
        "container": {"type": "boolean"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "variants": {
            "type": "array",
            "minItems": 1,
            "items": VARIANT_SCHEMA,
        },
    },
    "additionalProperties": True,
}


RUN_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["slug", "variant", "start_time", "pin"],
    "properties": {
        "slug": {"type": "string"},
        "variant": {"type": "string"},
        "start_time": {"type": "string"},
        "version": {"type": ["string", "null"]},
        "pin": {
            "type": "object",
            "required": ["harness", "model", "time_budget"],
            "properties": {
                "harness": {"type": "string"},
                "model": {"type": "string"},
                "time_budget": {"type": ["string", "integer", "null"]},
            },
            "additionalProperties": True,
        },
    },
    "additionalProperties": True,
}


CATALOG_ENTRY_SINGLE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["slug", "type", "title", "url", "version"],
    "properties": {
        "slug": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$"},
        "type": {"const": "single"},
        "title": {"type": "string", "minLength": 1},
        "description": {"type": "string"},
        "url": {"type": "string"},
        "path": {"type": "string"},
        "version": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "author": {"type": "string"},
        "variants": {"type": "array", "items": {"type": "string"}},
        "difficulty": {"type": "string"},
    },
    "additionalProperties": True,
}


CATALOG_ENTRY_PACK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["slug", "type", "title", "url", "version", "challenges"],
    "properties": {
        "slug": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$"},
        "type": {"const": "pack"},
        "title": {"type": "string", "minLength": 1},
        "description": {"type": "string"},
        "url": {"type": "string"},
        "version": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "author": {"type": "string"},
        "challenges": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["slug", "path"],
                "properties": {
                    "slug": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$"},
                    "path": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "variants": {"type": "array", "items": {"type": "string"}},
                    "difficulty": {"type": "string"},
                },
                "additionalProperties": True,
            },
        },
    },
    "additionalProperties": True,
}


CATALOG_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["schema_version", "entries"],
    "properties": {
        "schema_version": {"type": "integer"},
        "entries": {
            "type": "array",
            "items": {"oneOf": [CATALOG_ENTRY_SINGLE_SCHEMA, CATALOG_ENTRY_PACK_SCHEMA]},
        },
    },
    "additionalProperties": True,
}


COLLABORATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "turns",
        "tool_calls",
        "tool_calls_by_kind",
        "model_switches",
        "in_session_seconds",
    ],
    "properties": {
        "turns": {"type": "integer", "minimum": 0},
        "tool_calls": {"type": "integer", "minimum": 0},
        "tool_calls_by_kind": {
            "type": "object",
            "additionalProperties": {"type": "integer", "minimum": 0},
        },
        "model_switches": {"type": "integer", "minimum": 0},
        "in_session_seconds": {"type": "integer", "minimum": 0},
    },
    "additionalProperties": True,
}


RESULT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["pass", "elapsed_seconds", "pin_honored"],
    "properties": {
        "pass": {"type": "boolean"},
        "score": {"type": "number"},
        "signals": {"type": "object"},
        "notes": {"type": "string"},
        "elapsed_seconds": {"type": "integer", "minimum": 0},
        "pin_honored": {
            "type": "string",
            "enum": ["yes", "no", "unclear", "skipped", "unimplemented"],
        },
        "collaboration": COLLABORATION_SCHEMA,
    },
    "additionalProperties": True,
}


# Shape the grader itself produces (stdout JSON) — subset of result.json.
GRADER_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["pass"],
    "properties": {
        "pass": {"type": "boolean"},
        "score": {"type": "number"},
        "signals": {"type": "object"},
        "notes": {"type": "string"},
    },
    "additionalProperties": True,
}


class SchemaError(ValueError):
    """Raised when a document fails schema validation."""


def _validate(data: dict[str, Any], schema: dict[str, Any], label: str) -> None:
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as exc:
        raise SchemaError(f"{label}: {exc.message} at {list(exc.absolute_path)}") from exc


def validate_vera_yaml(data: dict[str, Any]) -> None:
    _validate(data, VERA_YAML_SCHEMA, "vera.yaml")


def validate_run_json(data: dict[str, Any]) -> None:
    _validate(data, RUN_JSON_SCHEMA, "run.json")


def validate_result_json(data: dict[str, Any]) -> None:
    _validate(data, RESULT_JSON_SCHEMA, "result.json")


def validate_grader_output(data: dict[str, Any]) -> None:
    _validate(data, GRADER_OUTPUT_SCHEMA, "grader output")


def validate_catalog(data: dict[str, Any]) -> None:
    _validate(data, CATALOG_SCHEMA, "catalog.json")
