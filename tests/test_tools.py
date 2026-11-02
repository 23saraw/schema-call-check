from __future__ import annotations

import json

import pytest
from expected import BATCHES

from contract import BatchInput, ToolsInput
from plugin import calls
from plugin.calls import lenient_check, load_batch, load_tools, quick_check, read_calls


def pairs(output) -> dict[str, list[tuple[str, str]]]:
    return {entry.id: [(v.parameter, v.kind.value) for v in entry.violations] for entry in output.reports}


def test_read_calls_gives_the_arguments_exactly_as_written() -> None:
    batch = read_calls(BatchInput(batch="batch-1.json"))
    assert [call.id for call in batch.calls] == [f"c{n}" for n in range(1, 11)]
    assert batch.calls[2].arguments == '{"room": "large", "guests": 4.0, "date": "2026-11-04"}'
    later = read_calls(BatchInput(batch="batch-2.json"))
    assert '"guests": 1e1' in later.calls[8].arguments  # the token survives, not 10.0


def test_load_tools_gives_each_schema_in_order() -> None:
    loaded = load_tools(ToolsInput(tools=["set_levels", "list_notes"])).schemas
    assert [entry.tool for entry in loaded] == ["set_levels", "list_notes"]
    assert json.loads(loaded[1].schema) == {
        "type": "object", "properties": {"limit": {"type": "integer"}, "folder": {"type": "string"}}, "required": [],
    }


def test_the_answer_key_and_the_agent_tools_agree() -> None:
    key = load_batch(BatchInput(batch="batch-2.json"))
    assert key.calls == read_calls(BatchInput(batch="batch-2.json")).calls
    assert key.schemas == load_tools(ToolsInput(tools=[entry.tool for entry in key.schemas])).schemas
    assert [entry.tool for entry in key.schemas] == ["set_levels", "log_reading", "list_notes", "book_room"]


def test_quick_check_sees_only_missing_parameters() -> None:
    got = pairs(quick_check(BatchInput(batch="batch-1.json")))
    assert got == {call: [] for call in BATCHES["batch-1.json"]} | {"c6": [("room", "MISSING_REQUIRED")],
                                                                     "c7": [("room", "MISSING_REQUIRED")]}
    got = pairs(quick_check(BatchInput(batch="batch-2.json")))
    assert got["d10"] == [("date", "MISSING_REQUIRED"), ("guests", "MISSING_REQUIRED"), ("room", "MISSING_REQUIRED")]
    assert got["d3"] == []


@pytest.mark.parametrize("batch", sorted(BATCHES))
def test_lenient_check_is_wrong_exactly_where_coercion_hides_a_wrong_type(batch: str) -> None:
    got, want = pairs(lenient_check(BatchInput(batch=batch))), BATCHES[batch]
    differ = {call: got[call] for call in want if got[call] != want[call]}
    assert differ == {
        "batch-1.json": {"c3": [], "c4": [("room", "NOT_IN_ENUM")], "c10": [("tags", "WRONG_TYPE")]},
        "batch-2.json": {"d4": [("levels", "MISSING_REQUIRED")], "d9": [("projector", "WRONG_TYPE")]},
    }[batch]


@pytest.mark.parametrize(
    ("call", "error"),
    [
        (lambda: read_calls(BatchInput(batch="../schemas.json")), ValueError),
        (lambda: read_calls(BatchInput(batch="batch-9.json")), FileNotFoundError),
        (lambda: load_tools(ToolsInput(tools=["send_email"])), ValueError),
        (lambda: quick_check(BatchInput(batch="Batch-1.json")), ValueError),
    ],
)
def test_unknown_names_raise(call, error: type[Exception]) -> None:
    with pytest.raises(error):
        call()


@pytest.mark.parametrize(
    ("batch", "match"),
    [
        ('[{"id": "a", "tool": "send_email", "arguments": "{}"}]', "unknown tool"),
        ('[{"id": "a", "tool": "list_notes", "arguments": "{}"}, {"id": "a", "tool": "list_notes", "arguments": "{}"}]', "twice"),
        ('[{"id": "a", "tool": "list_notes", "arguments": "[]"}]', "JSON object"),
        ('[{"id": "a", "tool": "list_notes", "arguments": "{\\"limit\\": 1, \\"limit\\": 2}"}]', "twice"),
    ],
)
def test_a_bad_batch_file_is_refused(tmp_path, monkeypatch, batch: str, match: str) -> None:
    (tmp_path / "batches").mkdir()
    (tmp_path / "schemas.json").write_text((calls.DATA / "schemas.json").read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "batches" / "bad.json").write_text(batch, encoding="utf-8")
    monkeypatch.setattr(calls, "DATA", tmp_path)
    with pytest.raises(ValueError, match=match):
        read_calls(BatchInput(batch="bad.json"))
