from __future__ import annotations

import copy
import json
import random

import pytest
from expected import BATCHES, answer
from slimconfig import build_output, plain_output

import verifier
from contract import BatchInput, CallsOutput, KeyOutput, ReportsOutput, Tool, ToolsInput, ToolsOutput
from plugin.calls import lenient_check, load_batch, load_tools, quick_check, read_calls

IDS = [
    "answer-key", "answer-key-rules", "submitted-batch", "reports-shaped",
    "reports-complete", "verdicts-exact", "violations-complete", "no-extra-violations",
]


# The verifier gets contract instances, as NanoAgent's sandbox builds them from JSON.
def key_json(batch: str) -> dict:
    return plain_output(load_batch(BatchInput(batch=batch)))


def judge(batch: str, submitted: dict, key: dict | None = None, arguments: str | None = None) -> dict:
    reference = build_output(key_json(batch) if key is None else key, KeyOutput)
    given = build_output({"batch": arguments or batch}, BatchInput)
    return verifier.verify_task("check-calls", given, build_output(submitted, ReportsOutput), reference, ".")


def failing(verdict: dict) -> list[str]:
    return [entry["id"] for entry in verdict["details"]["constraints"] if entry["ok"] is False]


def report(submitted: dict, call: str) -> dict:
    return next(entry for entry in submitted["reports"] if entry["id"] == call)


def test_every_tool_resolves_to_a_module_with_both_checks() -> None:
    # The host calls verify_input and verify_output on every tool call; a missing one only fails a real run.
    assert set(verifier.TOOLS) == set(Tool)
    for module in verifier.TOOLS.values():
        assert callable(module.verify_input) and callable(module.verify_output)


@pytest.mark.parametrize("batch", sorted(BATCHES))
def test_the_hand_derived_answer_holds_every_constraint(batch: str) -> None:
    verdict = judge(batch, answer(batch))
    assert verdict["valid"] is True and verdict["score"] == 1.0, verdict["message"]
    assert [entry["id"] for entry in verdict["details"]["constraints"]] == IDS


def test_order_does_not_matter_and_the_message_names_the_outcome() -> None:
    submitted = answer("batch-2.json")
    submitted["reports"].reverse()
    for entry in submitted["reports"]:
        entry["violations"].reverse()
    assert judge("batch-2.json", submitted)["message"] == "All 8 checks hold: 10 calls, 1 valid and 9 invalid, 14 violations."


def test_each_tool_approves_its_own_real_output() -> None:
    batch = build_output({"batch": "batch-1.json"}, BatchInput)
    names = build_output({"tools": ["book_room", "list_notes", "log_reading"]}, ToolsInput)
    cases = [
        ("load_batch", batch, load_batch(batch), KeyOutput),
        ("read_calls", batch, read_calls(batch), CallsOutput),
        ("load_tools", names, load_tools(names), ToolsOutput),
        ("quick_check", batch, quick_check(batch), ReportsOutput),
        ("lenient_check", batch, lenient_check(batch), ReportsOutput),
    ]
    for tool, given, made, cls in cases:
        assert verifier.verify_input(tool, given)["valid"] is True, tool
        verdict = verifier.verify_output(tool, given, build_output(plain_output(made), cls), ".")
        assert verdict["valid"] is True, (tool, verdict["message"])


# Wrong answers: the traps the batches are built around.
def set_report(submitted: dict, call: str, pairs: list[tuple[str, str]]) -> None:
    entry = report(submitted, call)
    entry["violations"] = [{"parameter": p, "kind": k} for p, k in pairs]
    entry["valid"] = not pairs


@pytest.mark.parametrize(
    ("batch", "call", "pairs", "message"),
    [
        (
            "batch-1.json", "c2", [],
            "verdicts-exact: c2 is reported valid, but it breaks 1 rule: guests is true, a boolean, not an integer (+1 more)",
        ),
        (
            "batch-1.json", "c3", [],
            "verdicts-exact: c3 is reported valid, but it breaks 1 rule: guests is 4.0, a decimal, not an integer (+1 more)",
        ),
        (
            "batch-1.json", "c4", [("room", "NOT_IN_ENUM")],
            'violations-complete: c4: guests WRONG_TYPE is not reported: guests is "5", a string, not an integer',
        ),
        (
            "batch-1.json", "c4", [("guests", "WRONG_TYPE")],
            (
                'violations-complete: c4: room NOT_IN_ENUM is not reported: room is "Large", not one of "small", "large":'
                ' enum matching is case-sensitive, and "large" differs only by case'
            ),
        ),
        (
            "batch-1.json", "c5", [("date", "WRONG_TYPE"), ("room", "WRONG_TYPE"), ("room", "NOT_IN_ENUM")],
            (
                "no-extra-violations: c5: room NOT_IN_ENUM is reported, but room is WRONG_TYPE only (room is 7, an integer,"
                " not a string); the enum check applies only to a value of the right type"
            ),
        ),
        (
            "batch-1.json", "c5", [("date", "MISSING_REQUIRED"), ("room", "WRONG_TYPE")],
            "violations-complete: c5: date WRONG_TYPE is not reported: date is null, the wrong type for every parameter (+1 more)",
        ),
        (
            "batch-1.json", "c7", [("room", "MISSING_REQUIRED")],
            (
                "violations-complete: c7: Room UNKNOWN_PARAMETER is not reported:"
                " Room is not a parameter of book_room (names are case-sensitive; it has room)"
            ),
        ),
        (
            "batch-1.json", "c7", [("Room", "UNKNOWN_PARAMETER")],
            "violations-complete: c7: room MISSING_REQUIRED is not reported: room is required and not given",
        ),
        (
            "batch-1.json", "c8", [("limit", "MISSING_REQUIRED")],
            "verdicts-exact: c8 is reported invalid, but it breaks no rule (+1 more)",
        ),
        (
            "batch-1.json", "c9", [("tags", "WRONG_TYPE")],
            "verdicts-exact: c9 is reported invalid, but it breaks no rule (+1 more)",
        ),
        (
            "batch-1.json", "c10", [("tags", "WRONG_TYPE"), ("tags", "WRONG_TYPE")],
            "reports-shaped: c10 reports the same (parameter, kind) twice",
        ),
        (
            "batch-2.json", "d6", [("unit", "NOT_IN_ENUM"), ("value", "WRONG_TYPE")],
            "no-extra-violations: d6: value WRONG_TYPE is reported, but value is -1.5e2, which breaks no rule",
        ),
        (
            "batch-2.json", "d8", [("Limit", "UNKNOWN_PARAMETER"), ("limit", "MISSING_REQUIRED")],
            "no-extra-violations: d8: limit MISSING_REQUIRED is reported, but limit is 0, which breaks no rule",
        ),
        (
            "batch-2.json", "d9", [("guests", "WRONG_TYPE")],
            "violations-complete: d9: projector WRONG_TYPE is not reported: projector is 1, an integer, not a boolean",
        ),
    ],
)
def test_each_trap_fails_its_constraint_with_the_reason(batch: str, call: str, pairs: list, message: str) -> None:
    submitted = answer(batch)
    set_report(submitted, call, pairs)
    verdict = judge(batch, submitted)
    assert verdict["valid"] is False and verdict["message"] == message, verdict["message"]
    if not message.startswith("reports-shaped"):
        assert verdict["score"] == pytest.approx(9 / 10)


def test_an_extra_parameter_that_is_neither_given_nor_a_property_says_so() -> None:
    submitted = answer("batch-1.json")
    set_report(submitted, "c1", [("floor", "UNKNOWN_PARAMETER")])
    assert judge("batch-1.json", submitted)["details"]["constraints"][7]["message"] == (
        "c1: floor UNKNOWN_PARAMETER is reported, but book_room has no floor and the call does not give it"
    )
    set_report(submitted, "c1", [("projector", "MISSING_REQUIRED")])
    assert judge("batch-1.json", submitted)["details"]["constraints"][7]["message"] == (
        "c1: projector MISSING_REQUIRED is reported, but projector is not given, and not required"
    )


@pytest.mark.parametrize("batch", sorted(BATCHES))
def test_trusting_a_distractor_is_caught(batch: str) -> None:
    for tool, score in ((quick_check, {"batch-1.json": 0.3, "batch-2.json": 0.2}),
                        (lenient_check, {"batch-1.json": 0.7, "batch-2.json": 0.8})):
        verdict = judge(batch, plain_output(tool(BatchInput(batch=batch))))
        assert verdict["valid"] is False and verdict["score"] == pytest.approx(score[batch]), tool.__name__
        assert "verdicts-exact" in failing(verdict) or "violations-complete" in failing(verdict)


def test_lenient_check_is_caught_on_each_coercion() -> None:
    verdict = judge("batch-2.json", plain_output(lenient_check(BatchInput(batch="batch-2.json"))))
    assert verdict["details"]["constraints"][6]["expected"] == ["d4 channel WRONG_TYPE", "d9 guests WRONG_TYPE"]
    assert verdict["message"] == (
        "violations-complete: d4: channel WRONG_TYPE is not reported: channel is 2.0, a decimal, not an integer (and 1 more)"
    )


# Missing.
def test_a_dropped_report_or_an_empty_submission_fail() -> None:
    submitted = answer("batch-1.json")
    submitted["reports"] = [entry for entry in submitted["reports"] if entry["id"] != "c5"]
    verdict = judge("batch-1.json", submitted)
    assert failing(verdict) == ["reports-complete"]
    assert verdict["message"] == (
        "reports-complete: c5 has no report: it breaks 2 rules: date is null, the wrong type for every parameter"
    )
    assert verdict["score"] == pytest.approx(9 / 10)
    verdict = judge("batch-1.json", {"batch": "batch-1.json", "reports": []})
    assert failing(verdict) == ["reports-complete"] and verdict["score"] == 0.0
    assert verdict["details"]["constraints"][4]["expected"][-1] == "... 4 more"


def test_reporting_every_call_valid_scores_only_the_valid_ones() -> None:
    submitted = {"batch": "batch-2.json", "reports": [{"id": c, "valid": True, "violations": []} for c in BATCHES["batch-2.json"]]}
    verdict = judge("batch-2.json", submitted)
    assert failing(verdict) == ["verdicts-exact", "violations-complete"]
    assert verdict["score"] == pytest.approx(1 / 10)


# Malformed: gates that score 0.
@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda s: s.update(batch="batch-2.json"), "submitted-batch: the submission is for 'batch-2.json', not 'batch-1.json'"),
        (lambda s: report(s, "c1").update(id="C1"), "reports-shaped: 'C1' is not a call in this batch"),
        (lambda s: report(s, "c1").update(id="d1"), "reports-shaped: 'd1' is not a call in this batch"),
        (lambda s: s["reports"].append(dict(report(s, "c1"))), "reports-shaped: c1 is reported more than once"),
        (lambda s: report(s, "c2").update(valid=True), "reports-shaped: c2 is reported valid with violations"),
        (lambda s: report(s, "c1").update(valid=False), "reports-shaped: c1 is reported invalid with no violations"),
    ],
)
def test_a_malformed_submission_fails_its_gate_and_scores_zero(change, message: str) -> None:
    submitted = copy.deepcopy(answer("batch-1.json"))
    change(submitted)
    verdict = judge("batch-1.json", submitted)
    assert verdict["valid"] is False and verdict["score"] == 0.0
    assert verdict["message"].startswith(message), verdict["message"]
    later = verdict["details"]["constraints"][IDS.index(failing(verdict)[0]) + 1 :]
    assert all(entry["ok"] is None and entry["message"].startswith("Not checked") for entry in later)


@pytest.mark.parametrize(
    "change",
    [
        lambda s: report(s, "c2")["violations"][0].update(kind="TYPE_MISMATCH"),  # outside the Kind Enum
        lambda s: report(s, "c2").update(valid="false"),
        lambda s: report(s, "c2").pop("violations"),
        lambda s: s.update(reports={"c1": []}),
    ],
)
def test_a_submission_outside_the_contract_never_reaches_the_verifier(change) -> None:
    # Unreachable in verify_task: build_output checks the contract first, as the sandbox does.
    submitted = answer("batch-1.json")
    change(submitted)
    with pytest.raises((TypeError, ValueError, KeyError)):
        build_output(submitted, ReportsOutput)


# The answer key.
def test_no_answer_key_fails_first() -> None:
    given = build_output({"batch": "batch-1.json"}, BatchInput)
    verdict = verifier.verify_task("check-calls", given, build_output(answer("batch-1.json"), ReportsOutput), None, ".")
    assert verdict["message"] == "answer-key: No answer key: load_batch never ran for this task." and verdict["score"] == 0.0


def test_an_answer_key_for_another_batch_fails() -> None:
    verdict = judge("batch-1.json", answer("batch-1.json"), arguments="batch-2.json")
    assert verdict["message"] == "answer-key: The answer key is for 'batch-1.json', not 'batch-2.json'."


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda k: k["calls"][0].update(arguments='{"room": NaN}'), "answer-key: call c1's arguments cannot be read: it uses NaN"),
        (lambda k: k["calls"][0].update(arguments='{"a": 1, "a": 1}'), "answer-key: call c1's arguments cannot be read: it gives a key twice"),
        (lambda k: k["calls"][0].update(tool="send_email"), "answer-key: call c1 names 'send_email', which the answer key has no schema"),
        (lambda k: k["schemas"][0].update(schema='{"type": "object"}'), "answer-key: book_room's schema is not an object schema"),
        (
            lambda k: k["schemas"][0].update(schema=k["schemas"][0]["schema"].replace('"type": "boolean"', '"type": "null"')),
            "answer-key: book_room.projector has no supported type",
        ),
        (lambda k: k["reports"].pop(), "answer-key: the answer key does not report every call"),
    ],
)
def test_a_malformed_answer_key_fails_first(change, message: str) -> None:
    key = key_json("batch-1.json")
    change(key)
    verdict = judge("batch-1.json", answer("batch-1.json"), key=key)
    assert failing(verdict) == ["answer-key"] and verdict["message"].startswith(message), verdict["message"]


def test_a_tampered_answer_key_fails_its_rules_check() -> None:
    key = key_json("batch-1.json")
    key["reports"][2] = {"id": "c3", "valid": True, "violations": []}  # as if 4.0 were an integer
    verdict = judge("batch-1.json", answer("batch-1.json"), key=key)
    assert verdict["message"] == "answer-key-rules: the answer key's report for c3 differs from the rules' recomputation"
    output = verifier.verify_output("load_batch", build_output({"batch": "batch-1.json"}, BatchInput), build_output(key, KeyOutput), ".")
    assert output["valid"] is False


# The tools' own checks.
def test_tool_inputs_are_checked() -> None:
    assert verifier.verify_input("read_calls", build_output({"batch": "../schemas.json"}, BatchInput))["valid"] is False
    assert verifier.verify_input("load_tools", build_output({"tools": []}, ToolsInput))["valid"] is False
    assert verifier.verify_input("load_tools", build_output({"tools": ["Book_Room"]}, ToolsInput))["valid"] is False
    assert verifier.verify_input("load_tools", build_output({"tools": ["list_notes", "list_notes"]}, ToolsInput))["valid"] is False
    assert verifier.verify_input("load_tools", build_output({"tools": [f"t{n}" for n in range(21)]}, ToolsInput))["valid"] is False


@pytest.mark.parametrize(
    ("tool", "given", "made", "input_class", "cls"),
    [
        ("load_tools", {"tools": ["list_notes"]}, {"schemas": []}, ToolsInput, ToolsOutput),
        (
            "load_tools", {"tools": ["list_notes"]},
            {"schemas": [{"tool": "list_notes", "schema": '{"type": "object", "properties": {}, "required": [], "nullable": true}'}]},
            ToolsInput, ToolsOutput,
        ),
        (
            "read_calls", {"batch": "batch-1.json"},
            {"batch": "batch-1.json", "calls": [{"id": "c1", "tool": "list_notes", "arguments": "{"}]}, BatchInput, CallsOutput,
        ),
        ("read_calls", {"batch": "batch-1.json"}, {"batch": "batch-2.json", "calls": []}, BatchInput, CallsOutput),
        (
            "quick_check", {"batch": "batch-1.json"},
            {"batch": "batch-1.json", "reports": [{"id": "c1", "valid": False, "violations": [{"parameter": "a", "kind": "WRONG_TYPE"}]}]},
            BatchInput, ReportsOutput,
        ),
        (
            "lenient_check", {"batch": "batch-1.json"},
            {"batch": "batch-1.json", "reports": [{"id": "c1", "valid": True, "violations": [{"parameter": "a", "kind": "WRONG_TYPE"}]}]},
            BatchInput, ReportsOutput,
        ),
    ],
)
def test_a_wrong_tool_output_is_refused(tool, given, made, input_class, cls) -> None:
    verdict = verifier.verify_output(tool, build_output(given, input_class), build_output(made, cls), ".")
    assert verdict["valid"] is False


# Determinism, size and robustness.
def test_the_verdict_is_deterministic_and_small() -> None:
    empty = {"batch": "batch-2.json", "reports": []}
    first, second = judge("batch-2.json", empty), judge("batch-2.json", empty)
    assert first == second
    assert len(json.dumps(first)) < 8_000


def mutate(value, rng: random.Random):
    """``value`` with one random change somewhere inside it."""
    if isinstance(value, dict) and value:
        key = rng.choice(sorted(value))
        return {**value, key: mutate(value[key], rng)}
    if isinstance(value, list) and value and rng.random() < 0.7:
        index = rng.randrange(len(value))
        choice = rng.random()
        if choice < 0.3:
            return value[:index] + value[index + 1 :]
        if choice < 0.5:
            return [*value, copy.deepcopy(value[index])]
        return value[:index] + [mutate(value[index], rng)] + value[index + 1 :]
    # Mostly a value of the same type, so most mutations reach the verifier rather than build_output's refusal.
    same = {
        str: ["", "c1", "d1", "room", "Room", "guests", "WRONG_TYPE", "NOT_IN_ENUM", "MISSING_REQUIRED",
              "UNKNOWN_PARAMETER", "{}", "[]", "{", '{"a": NaN}', '{"room": 1}', "book_room", "batch-1.json",
              '{"type": "object", "properties": {}, "required": []}'],
        bool: [True, False],
        list: [[]],
    }.get(type(value))
    if same and rng.random() < 0.85:
        return rng.choice(same)
    return rng.choice([None, "", 0, True, []])


@pytest.mark.parametrize("batch", sorted(BATCHES))
def test_a_mutated_submission_or_key_always_gets_a_verdict(batch: str) -> None:
    rng = random.Random(batch)
    checked = 0
    for _ in range(300):
        submitted, key = answer(batch), key_json(batch)
        for _ in range(rng.randint(1, 3)):
            if rng.random() < 0.6:
                submitted = mutate(submitted, rng)
            else:
                key = mutate(key, rng)
        try:
            built_output, built_key = build_output(submitted, ReportsOutput), build_output(key, KeyOutput)
        except (TypeError, ValueError, KeyError):
            continue  # the sandbox refuses it before the verifier sees it
        given = build_output({"batch": batch}, BatchInput)
        verdict = verifier.verify_task("check-calls", given, built_output, built_key, ".")
        assert set(verdict) == {"valid", "score", "message", "details"}
        assert 0.0 <= verdict["score"] <= 1.0 and verdict["message"]
        json.dumps(verdict)
        checked += 1
    assert checked > 150
