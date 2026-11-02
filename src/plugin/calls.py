"""The tools. Every one reads only the bundled data in data/ and writes nothing."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from contract import (
    BatchInput,
    Call,
    CallsOutput,
    KeyOutput,
    Kind,
    Report,
    ReportsOutput,
    Schema,
    ToolsInput,
    ToolsOutput,
    Violation,
)
from plugin.rules import checked, parse, report, violations

DATA = Path(__file__).parent / "data"
BATCH_NAME = re.compile(r"[a-z0-9-]+\.json")
NUMERIC = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?")


def schemas() -> dict[str, Schema]:
    """Every bundled schema, checked against the subset, as JSON text."""
    found: dict[str, Schema] = {}
    for entry in json.loads((DATA / "schemas.json").read_text(encoding="utf-8")):
        if entry["tool"] in found:
            raise ValueError(f"schemas.json lists {entry['tool']!r} twice")
        found[entry["tool"]] = Schema(tool=entry["tool"], schema=json.dumps(checked(entry["schema"], entry["tool"])))
    return found


def load(batch: str) -> CallsOutput:
    """The batch file ``batch``, checked: distinct ids, known tools, arguments that are JSON objects."""
    if not BATCH_NAME.fullmatch(batch):
        raise ValueError(f"{batch!r} is not a batch file name (lowercase letters, digits and '-', then .json)")
    path = DATA / "batches" / batch
    if not path.is_file():
        batches = sorted(file.name for file in (DATA / "batches").glob("*.json"))
        raise FileNotFoundError(f"no batch {batch!r}: the batches are {', '.join(batches)}")
    known = schemas()
    calls, ids = [], set()
    for entry in json.loads(path.read_text(encoding="utf-8")):
        if entry["id"] in ids:
            raise ValueError(f"{batch} has the call id {entry['id']!r} twice")
        if entry["tool"] not in known:
            raise ValueError(f"{batch}'s call {entry['id']} names the unknown tool {entry['tool']!r}")
        parse(entry["arguments"], f"call {entry['id']}'s arguments")
        ids.add(entry["id"])
        calls.append(Call(id=entry["id"], tool=entry["tool"], arguments=entry["arguments"]))
    return CallsOutput(batch=batch, calls=calls)


def parsed(calls: CallsOutput) -> list[tuple[Call, dict[str, Any], dict[str, Any]]]:
    """Each call with its parsed schema and arguments."""
    known = schemas()
    return [
        (call, json.loads(known[call.tool].schema), parse(call.arguments, f"call {call.id}'s arguments"))
        for call in calls.calls
    ]


def load_batch(given: BatchInput) -> KeyOutput:
    calls = load(given.batch)
    known = schemas()
    used = [known[tool] for tool in dict.fromkeys(call.tool for call in calls.calls)]
    reports = [report(call.id, schema, arguments) for call, schema, arguments in parsed(calls)]
    return KeyOutput(batch=calls.batch, calls=calls.calls, schemas=used, reports=reports)


def read_calls(given: BatchInput) -> CallsOutput:
    return load(given.batch)


def load_tools(given: ToolsInput) -> ToolsOutput:
    known = schemas()
    missing = [tool for tool in given.tools if tool not in known]
    if missing:
        raise ValueError(f"no tool {missing[0]!r}: the tools are {', '.join(sorted(known))}")
    return ToolsOutput(schemas=[known[tool] for tool in given.tools])


def quick_check(given: BatchInput) -> ReportsOutput:
    """A distractor: reports only required parameters that are absent, and calls everything else valid."""
    reports = []
    for call, schema, arguments in parsed(load(given.batch)):
        found = [Violation(parameter=name, kind=Kind.MISSING_REQUIRED) for name in sorted(schema["required"])
                 if name not in arguments]
        reports.append(Report(id=call.id, valid=not found, violations=found))
    return ReportsOutput(batch=given.batch, reports=reports)


def coerced(value: Any, kind: str) -> Any:
    """``value`` as many APIs coerce it: numeric strings to numbers, whole decimals to integers."""
    if isinstance(value, str) and NUMERIC.fullmatch(value) and kind in {"integer", "number"}:
        value = float(value) if kind == "number" or not re.fullmatch(r"-?[0-9]+", value) else int(value)
    if kind == "integer" and isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def lenient_check(given: BatchInput) -> ReportsOutput:
    """A distractor: the rules, after coercing each argument to its declared type, which rule 3 forbids."""
    reports = []
    for call, schema, arguments in parsed(load(given.batch)):
        properties = schema["properties"]
        loose = {}
        for name, value in arguments.items():
            rule = properties.get(name, {"type": ""})
            if rule["type"] == "array" and isinstance(value, list):
                loose[name] = [coerced(item, rule["items"]["type"]) for item in value]
            else:
                loose[name] = coerced(value, rule["type"])
        found = violations(schema, loose)
        reports.append(Report(id=call.id, valid=not found, violations=found))
    return ReportsOutput(batch=given.batch, reports=reports)
