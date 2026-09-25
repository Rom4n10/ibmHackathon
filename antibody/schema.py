"""Contract validation for every JSON file Antibody reads or writes.

The schemas in antibody/schemas/ are standard JSON Schema files, so any tool
can use them. This module implements the small subset we rely on (type,
required, properties, additionalProperties, items, enum, pattern, minimum,
maximum, minItems) to keep the CLI free of runtime dependencies.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

SCHEMA_NAMES = (
    "diagnosis",
    "candidates",
    "verdict",
    "variants",
    "vaccine_round",
    "manifest",
    "scoreboard",
)


class ContractError(ValueError):
    """Raised when a JSON document does not match its schema."""


@lru_cache(maxsize=None)
def load_schema(name: str) -> dict:
    if name not in SCHEMA_NAMES:
        raise KeyError(f"Unknown schema '{name}'. Known: {', '.join(SCHEMA_NAMES)}")
    text = resources.files("antibody").joinpath("schemas", f"{name}.schema.json").read_text(
        encoding="utf-8"
    )
    return json.loads(text)


_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "null": type(None),
}


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, _TYPES[expected])


def _check(value: Any, schema: dict, path: str, errors: list[str]) -> None:
    expected = schema.get("type")
    if expected is not None:
        options = expected if isinstance(expected, list) else [expected]
        if not any(_type_ok(value, t) for t in options):
            errors.append(f"{path}: expected {'/'.join(options)}, got {type(value).__name__}")
            return

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} is not one of {schema['enum']}")

    if isinstance(value, str) and "pattern" in schema:
        if not re.search(schema["pattern"], value):
            errors.append(f"{path}: {value!r} does not match /{schema['pattern']}/")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: {value} < minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: {value} > maximum {schema['maximum']}")

    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}: missing required field '{key}'")
        props = schema.get("properties", {})
        for key, sub in value.items():
            if key in props:
                _check(sub, props[key], f"{path}.{key}", errors)
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: unexpected field '{key}'")

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: needs at least {schema['minItems']} item(s)")
        if "items" in schema:
            for i, item in enumerate(value):
                _check(item, schema["items"], f"{path}[{i}]", errors)


def validate(name: str, data: Any) -> None:
    """Raise ContractError listing every violation of schema `name`."""
    errors: list[str] = []
    _check(data, load_schema(name), "$", errors)
    if errors:
        raise ContractError(f"{name} contract violated:\n  - " + "\n  - ".join(errors))


def read_json(path: Path, schema: str | None = None) -> Any:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FileNotFoundError(f"Missing file: {path}") from None
    except json.JSONDecodeError as exc:
        raise ContractError(f"{path} is not valid JSON: {exc}") from None
    if schema:
        validate(schema, data)
    return data


def write_json(path: Path, data: Any, schema: str | None = None) -> Path:
    if schema:
        validate(schema, data)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
