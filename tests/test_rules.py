"""Both implementations of the rules (the plugin's and the verifier's) against the hand-derived answers."""

from __future__ import annotations

import json

import pytest
from expected import BATCHES

from contract import BatchInput, Kind
from plugin import rules as plugin_rules
from plugin.calls import load_batch, schemas
from verifier import rules as verifier_rules
from verifier.task import expected_reports

SCHEMAS = {tool: json.loads(entry.schema) for tool, entry in schemas().items()}


@pytest.mark.parametrize("batch", sorted(BATCHES))
def test_the_plugin_reports_each_call_as_derived_by_hand(batch: str) -> None:
    key = load_batch(BatchInput(batch=batch))
    got = {entry.id: [(v.parameter, v.kind.value) for v in entry.violations] for entry in key.reports}
    assert got == BATCHES[batch]
    assert all(entry.valid == (not entry.violations) for entry in key.reports)


@pytest.mark.parametrize("batch", sorted(BATCHES))
def test_the_verifier_reports_each_call_as_derived_by_hand(batch: str) -> None:
    got = {call.id: sorted((p, k.value) for p, k in why) for call, _, why in expected_reports(load_batch(BatchInput(batch=batch)))}
    assert got == BATCHES[batch]


# One argument at a time, against both implementations: (tool, arguments, expected pairs).
CASES = [
    ("set_levels", '{"levels": [7]}', []),
    ("set_levels", '{"levels": [-3, 0]}', []),
    ("set_levels", '{"levels": [7.5]}', [("levels", "WRONG_TYPE")]),
    ("set_levels", '{"levels": [null]}', [("levels", "WRONG_TYPE")]),
    ("set_levels", '{"levels": [[1]]}', [("levels", "WRONG_TYPE")]),
    ("set_levels", '{"levels": {}}', [("levels", "WRONG_TYPE")]),
    ("set_levels", '{"levels": [], "channel": 3}', []),
    ("set_levels", '{"levels": [], "channel": 3.0}', [("channel", "WRONG_TYPE")]),
    ("set_levels", '{"levels": [], "channel": true}', [("channel", "WRONG_TYPE")]),
    ("set_levels", '{"levels": [], "channel": "2"}', [("channel", "WRONG_TYPE")]),
    ("set_levels", '{"levels": [], "channel": 0}', [("channel", "NOT_IN_ENUM")]),
    ("log_reading", '{"sensor": "x", "value": 1e400}', []),  # overflows a float, but is a JSON number
    ("log_reading", '{"sensor": "x", "value": -0.0}', []),
    ("log_reading", '{"sensor": "x", "value": [1]}', [("value", "WRONG_TYPE")]),
    ("log_reading", '{"sensor": "", "value": 1, "unit": "c"}', []),  # an empty string is a string
    ("log_reading", '{"sensor": "x", "value": 1, "unit": "c "}', [("unit", "NOT_IN_ENUM")]),
    ("log_reading", '{"sensor": "x", "value": 1, "tags": [true]}', [("tags", "WRONG_TYPE")]),
    ("log_reading", '{"sensor": null, "value": null}', [("sensor", "WRONG_TYPE"), ("value", "WRONG_TYPE")]),
    ("book_room", '{"room": "small", "guests": -1, "date": ""}', []),
    ("book_room", '{"room": "small", "guests": 1, "date": "x", "projector": "true"}', [("projector", "WRONG_TYPE")]),
    ("book_room", '{"room": "small", "guests": 1, "date": "x", "projector": false}', []),
    ("book_room", '{"room": ["small"], "guests": 1, "date": "x"}', [("room", "WRONG_TYPE")]),
    ("book_room", '{"ROOM": 1, "GUESTS": 1, "DATE": 1}', [
        ("DATE", "UNKNOWN_PARAMETER"), ("GUESTS", "UNKNOWN_PARAMETER"), ("ROOM", "UNKNOWN_PARAMETER"),
        ("date", "MISSING_REQUIRED"), ("guests", "MISSING_REQUIRED"), ("room", "MISSING_REQUIRED"),
    ]),
    ("list_notes", '{"": 1}', [("", "UNKNOWN_PARAMETER")]),
    ("list_notes", '{"limit": 1E2}', [("limit", "WRONG_TYPE")]),
]


@pytest.mark.parametrize(("tool", "arguments", "pairs"), CASES)
def test_both_implementations_agree_on_each_boundary(tool: str, arguments: str, pairs: list) -> None:
    plugin = plugin_rules.violations(SCHEMAS[tool], plugin_rules.parse(arguments, "the arguments"))
    assert [(v.parameter, v.kind.value) for v in plugin] == pairs
    parsed, problem = verifier_rules.read_object(arguments)
    assert problem is None
    schema, _ = verifier_rules.read_object(schemas()[tool].schema)
    assert sorted((p, k.value) for p, k in verifier_rules.judge(schema, parsed, tool)) == pairs


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ('{"a": 1, "a": 2}', "it gives a key twice"),
        ('{"a": NaN}', "it uses NaN, which is not JSON"),
        ('{"a": Infinity}', "it uses Infinity, which is not JSON"),
        ("[1]", "it is not a JSON object"),
        ('"{}"', "it is not a JSON object"),
        ("{'a': 1}", "it is not JSON"),
        ("", "it is not JSON"),
    ],
)
def test_unreadable_arguments_are_refused_by_both(text: str, problem: str) -> None:
    assert verifier_rules.read_object(text) == (None, problem)
    with pytest.raises(ValueError):
        plugin_rules.parse(text, "the arguments")


@pytest.mark.parametrize(
    "schema",
    [
        {"properties": {}, "required": []},  # no type
        {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        {"type": "object", "properties": {"a": {"type": "object"}}, "required": []},
        {"type": "object", "properties": {"a": {"type": "string", "nullable": True}}, "required": []},
        {"type": "object", "properties": {"a": {"type": "string", "default": "x"}}, "required": []},
        {"type": "object", "properties": {"a": {"type": "array"}}, "required": []},
        {"type": "object", "properties": {"a": {"type": "array", "items": {"type": "array"}}}, "required": []},
        {"type": "object", "properties": {"a": {"type": "string", "items": {"type": "string"}}}, "required": []},
        {"type": "object", "properties": {"a": {"type": "number", "enum": [1.5]}}, "required": []},
        {"type": "object", "properties": {"a": {"type": "string", "enum": []}}, "required": []},
        {"type": "object", "properties": {"a": {"type": "string", "enum": ["x", "x"]}}, "required": []},
        {"type": "object", "properties": {"a": {"type": "integer", "enum": [1, True]}}, "required": []},
        {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["b"]},
        {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a", "a"]},
    ],
)
def test_a_schema_outside_the_subset_is_refused_by_both(schema: dict) -> None:
    with pytest.raises(ValueError):
        plugin_rules.checked(schema, "t")
    parsed, _ = verifier_rules.read_object(json.dumps(schema))
    assert verifier_rules.subset_problem(parsed, "t") is not None


def test_every_bundled_schema_is_in_the_subset_for_the_verifier() -> None:
    for tool, entry in schemas().items():
        parsed, problem = verifier_rules.read_object(entry.schema)
        assert problem is None and verifier_rules.subset_problem(parsed, tool) is None


def test_the_verifier_gives_a_reason_for_each_kind() -> None:
    key = load_batch(BatchInput(batch="batch-1.json"))
    why = {call.id: found for call, _, found in expected_reports(key)}
    assert why["c3"][("guests", Kind.WRONG_TYPE)] == "guests is 4.0, a decimal, not an integer"
    assert why["c4"][("room", Kind.NOT_IN_ENUM)] == (
        'room is "Large", not one of "small", "large": enum matching is case-sensitive, and "large" differs only by case'
    )
    assert why["c5"][("date", Kind.WRONG_TYPE)] == "date is null, the wrong type for every parameter"
    assert why["c7"][("Room", Kind.UNKNOWN_PARAMETER)] == "Room is not a parameter of book_room (names are case-sensitive; it has room)"
    assert why["c6"][("room", Kind.MISSING_REQUIRED)] == "room is required and not given"
    assert why["c10"][("tags", Kind.WRONG_TYPE)] == 'tags has the item 2, an integer, not a string'
