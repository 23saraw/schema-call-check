"""The validation rules (the README's 1 to 7), on parsed JSON. The verifier writes them again apart from this."""

from __future__ import annotations

import json
from typing import Any

from contract import Kind, Report, Violation

SCALARS = {"string", "integer", "number", "boolean"}
TYPES = SCALARS | {"array"}


def parse(text: str, what: str) -> dict[str, Any]:
    """The JSON object ``text``: no duplicate keys, no NaN or Infinity, nothing but an object."""

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        found: dict[str, Any] = {}
        for key, value in items:
            if key in found:
                raise ValueError(f"{what} gives {key!r} twice")
            found[key] = value
        return found

    def constant(name: str) -> Any:
        raise ValueError(f"{what} uses {name}, which is not JSON")

    value = json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    if not isinstance(value, dict):
        raise ValueError(f"{what} must be a JSON object")  # noqa: TRY004 - bad data, like json.loads errors
    return value


def checked(schema: Any, tool: str) -> dict[str, Any]:
    """``schema`` if it is in the supported subset (rule 1), else ValueError."""
    if not (isinstance(schema, dict) and set(schema) == {"type", "properties", "required"} and schema["type"] == "object"):
        raise ValueError(f"{tool}'s schema must have exactly type 'object', properties and required")
    properties, required = schema["properties"], schema["required"]
    if not isinstance(properties, dict) or not isinstance(required, list):
        raise ValueError(f"{tool}'s properties must be an object and its required a list")  # noqa: TRY004
    for name, rule in properties.items():
        if not (isinstance(rule, dict) and rule.get("type") in TYPES):
            raise ValueError(f"{tool}.{name} must have a type: {', '.join(sorted(TYPES))}")
        allowed = {"type", "items"} if rule["type"] == "array" else {"type", "enum"}
        if not set(rule) <= allowed or (rule["type"] == "array") != ("items" in rule):
            raise ValueError(f"{tool}.{name} has keys outside the subset")
        if "items" in rule and not (isinstance(rule["items"], dict) and set(rule["items"]) == {"type"}
                                    and rule["items"]["type"] in SCALARS):
            raise ValueError(f"{tool}.{name}'s items must be exactly a scalar type")
        if "enum" in rule:
            values = rule["enum"]
            if rule["type"] not in {"string", "integer"} or not (isinstance(values, list) and values):
                raise ValueError(f"{tool}.{name}: an enum is a non-empty list, on a string or integer only")
            if not all(is_type(value, rule["type"]) for value in values) or len(set(values)) != len(values):
                raise ValueError(f"{tool}.{name}'s enum values must be distinct and of its type")
    if not all(isinstance(name, str) and name in properties for name in required) or len(set(required)) != len(required):
        raise ValueError(f"{tool}'s required must name distinct properties")
    return schema


def is_type(value: Any, kind: str) -> bool:
    """Rule 3: booleans are never integers or numbers, an integer is an int token (1, not 1.0), null is no type."""
    if kind == "string":
        return isinstance(value, str)
    if kind == "boolean":
        return isinstance(value, bool)
    if isinstance(value, bool):
        return False
    if kind == "integer":
        return isinstance(value, int)
    if kind == "number":
        return isinstance(value, (int, float))
    return False


def violations(schema: dict[str, Any], arguments: dict[str, Any]) -> list[Violation]:
    """Every (parameter, kind) the call breaks (rules 2 to 7), sorted."""
    properties = schema["properties"]
    found = [(name, Kind.MISSING_REQUIRED) for name in schema["required"] if name not in arguments]
    for name, value in arguments.items():
        rule = properties.get(name)
        if rule is None:
            found.append((name, Kind.UNKNOWN_PARAMETER))
        elif rule["type"] == "array":
            items = rule["items"]["type"]
            if not (isinstance(value, list) and all(is_type(item, items) for item in value)):
                found.append((name, Kind.WRONG_TYPE))
        elif not is_type(value, rule["type"]):
            found.append((name, Kind.WRONG_TYPE))
        elif "enum" in rule and not any(is_type(option, rule["type"]) and option == value for option in rule["enum"]):
            found.append((name, Kind.NOT_IN_ENUM))
    return [Violation(parameter=name, kind=kind) for name, kind in sorted(found, key=lambda pair: (pair[0], pair[1].value))]


def report(call_id: str, schema: dict[str, Any], arguments: dict[str, Any]) -> Report:
    found = violations(schema, arguments)
    return Report(id=call_id, valid=not found, violations=found)
