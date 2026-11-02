"""Checks shared by the tool verifiers. Pure functions of their arguments."""

import re

from .rules import read_object, subset_problem

BATCH_NAME = re.compile(r"[a-z0-9-]+\.json")
TOOL_NAME = re.compile(r"[a-z][a-z0-9_]*")
MAX_TOOLS = 20  # schemas one load_tools call may ask for
MOST = 6  # list entries a constraint's expected or actual shows


def result(valid, message, *, score=None, **details):
    return {
        "valid": valid,
        "score": float(valid) if score is None else score,
        "message": message,
        "details": details,
    }


def constraint(identifier, text, ok, expected=None, actual=None, message=""):
    """One constraint's entry, always with the same keys: ok is True (holds), False (fails) or None (not
    checked: a check it needs did not hold); message says why it fails or was not checked, "" when it holds."""

    def cut(value):
        if isinstance(value, list) and len(value) > MOST:
            return value[:MOST] + [f"... {len(value) - MOST} more"]
        return value

    return {
        "id": identifier,
        "constraint": text,
        "ok": ok,
        "expected": cut(expected),
        "actual": cut(actual),
        "message": "" if ok is True else message or text,
    }


def summary(constraints):
    """A failed verdict's message: the first failing constraint, its id and why, then how many more fail."""
    failed = [entry for entry in constraints if entry["ok"] is False]
    more = f" (+{len(failed) - 1} more)" if len(failed) > 1 else ""
    return f"{failed[0]['id']}: {failed[0]['message']}{more}"


def batch_input(value):
    if not BATCH_NAME.fullmatch(value.batch):
        return result(False, f"{value.batch!r} is not a batch file name (lowercase letters, digits and '-', then .json)")
    return result(True, "input is valid")


def tools_input(value):
    if not 1 <= len(value.tools) <= MAX_TOOLS:
        return result(False, f"give 1 to {MAX_TOOLS} tool names, not {len(value.tools)}")
    if len(set(value.tools)) != len(value.tools):
        return result(False, "name each tool once")
    for tool in value.tools:
        if not TOOL_NAME.fullmatch(tool):
            return result(False, f"{tool!r} is not a tool name (lowercase letters, digits and '_')")
    return result(True, "input is valid")


def calls_problem(calls):
    """What is wrong with calls as written, or None: distinct non-empty ids, arguments that are JSON objects."""
    ids = [call.id for call in calls]
    if len(set(ids)) != len(ids) or not all(ids):
        return "the calls' ids are not distinct and non-empty"
    for call in calls:
        _, problem = read_object(call.arguments)
        if problem:
            return f"call {call.id}'s arguments cannot be read: {problem}"
    return None


def schemas_problem(schemas):
    """What is wrong with schemas as written, or None: one per tool, each JSON in the subset."""
    tools = [entry.tool for entry in schemas]
    if len(set(tools)) != len(tools):
        return "a tool's schema is given twice"
    for entry in schemas:
        schema, problem = read_object(entry.schema)
        problem = problem and f"{entry.tool}'s schema cannot be read: {problem}"
        problem = problem or subset_problem(schema, entry.tool)
        if problem:
            return problem
    return None


def reports_problem(reports, ids=None):
    """What is wrong with reports as written, or None (not whether they are right): each id once and, when
    ``ids`` is given, one of them; valid exactly when there is no violation; no (parameter, kind) twice."""
    seen = set()
    for entry in reports:
        if ids is not None and entry.id not in ids:
            return f"{entry.id!r} is not a call in this batch"
        if entry.id in seen:
            return f"{entry.id} is reported more than once: give each call one report"
        seen.add(entry.id)
        pairs = [(violation.parameter, violation.kind) for violation in entry.violations]
        if len(set(pairs)) != len(pairs):
            return f"{entry.id} reports the same (parameter, kind) twice"
        if entry.valid != (not pairs):
            state = "valid with violations" if entry.valid else "invalid with no violations"
            return f"{entry.id} is reported {state}: a call is valid exactly when it breaks no rule"
    return None
