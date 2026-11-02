"""The check-calls task's verdict: 8 named constraints, in order. 1 to 4 guard the answer key and the
submission's integrity and score 0 when one fails; 5 to 8 judge the answer and score partially."""

from contract import Kind

from .checks import calls_problem, constraint, reports_problem, result, schemas_problem, summary
from .rules import judge, read_object, shown

GATES = 4
TEXTS = [
    ("answer-key", "The answer key is this batch's and well formed"),
    ("answer-key-rules", "The answer key's reports follow the rules, recomputed independently"),
    ("submitted-batch", "The submission is for this batch"),
    ("reports-shaped", "Each call reported once, valid exactly when it has no violation, no (parameter, kind) twice"),
    ("reports-complete", "Every call has a report"),
    ("verdicts-exact", "Each call is reported valid or invalid rightly"),
    ("violations-complete", "Every violation the rules give is reported"),
    ("no-extra-violations", "No violation is reported that the rules do not give"),
]


def key_problem(key):
    """What is wrong with the answer key's data, or None (not yet whether its reports follow the rules)."""
    problem = schemas_problem(key.schemas) or calls_problem(key.calls)
    if problem:
        return problem
    tools = {entry.tool for entry in key.schemas}
    unknown = [call for call in key.calls if call.tool not in tools]
    if unknown:
        return f"call {unknown[0].id} names {unknown[0].tool!r}, which the answer key has no schema for"
    ids = {call.id for call in key.calls}
    problem = reports_problem(key.reports, ids)
    if problem:
        return problem
    if len(key.reports) != len(key.calls):
        return "the answer key does not report every call"
    return None


def expected_reports(key):
    """[(call, its arguments, {(parameter, Kind): why})], in the batch's order, from the verifier's own rules."""
    schemas = {entry.tool: read_object(entry.schema)[0] for entry in key.schemas}
    found = []
    for call in key.calls:
        arguments = read_object(call.arguments)[0]
        found.append((call, arguments, judge(schemas[call.tool], arguments, call.tool)))
    return found


def given_reports(reports):
    return {entry.id: {(violation.parameter, violation.kind) for violation in entry.violations} for entry in reports}


def named(call_id, pair):
    return f"{call_id} {pair[0]} {pair[1].value}"


def _first(problems):
    return problems[0] + (f" (and {len(problems) - 1} more)" if len(problems) > 1 else "") if problems else ""


def _broken(why):
    if not why:
        return "it breaks no rule"
    first = min(why, key=lambda pair: (pair[0], pair[1].value))
    return f"it breaks {len(why)} rule{'s' if len(why) > 1 else ''}: {why[first]}"


def _why_extra(call, arguments, schema, why, pair):
    """Why ``pair`` is not a violation of ``call``."""
    parameter, kind = pair
    others = sorted((other for name, other in why if name == parameter and other is not kind), key=lambda k: k.value)
    if others:
        reason = why[(parameter, others[0])]
        rule = ""
        if kind is Kind.NOT_IN_ENUM and others[0] is Kind.WRONG_TYPE:
            rule = "; the enum check applies only to a value of the right type"
        return f"{call.id}: {parameter} {kind.value} is reported, but {parameter} is {others[0].value} only ({reason}){rule}"
    properties = schema["properties"]
    if parameter in arguments:
        state = f"{shown(arguments[parameter])}, which breaks no rule" if parameter in properties else "unknown, nothing else"
        return f"{call.id}: {parameter} {kind.value} is reported, but {parameter} is {state}"
    if parameter in properties:
        return f"{call.id}: {parameter} {kind.value} is reported, but {parameter} is not given, and not required"
    return f"{call.id}: {parameter} {kind.value} is reported, but {call.tool} has no {parameter} and the call does not give it"


def verify_task(arguments, output, reference, workspace):
    entries = []

    def add(index, ok, expected=None, actual=None, message=""):
        entries.append(constraint(*TEXTS[index], ok, expected, actual, message))
        return ok

    # 1 to 4: the gates.
    key = reference
    if key is None:
        problem = "No answer key: load_batch never ran for this task."
    elif key.batch != arguments.batch:
        problem = f"The answer key is for {key.batch!r}, not {arguments.batch!r}."
    else:
        problem = key_problem(key)
    blocker = None if add(0, problem is None, message=problem or "") else TEXTS[0][0]
    outcomes = None

    def rules_problem():
        nonlocal outcomes
        outcomes = expected_reports(key)
        recomputed = {call.id: set(why) for call, _, why in outcomes}
        differ = [entry.id for entry in key.reports if given_reports([entry])[entry.id] != recomputed[entry.id]]
        if differ:
            return f"the answer key's report for {differ[0]} differs from the rules' recomputation"
        return None

    gates = [
        rules_problem,
        lambda: None if output.batch == arguments.batch else f"the submission is for {output.batch!r}, not {arguments.batch!r}",
        lambda: reports_problem(output.reports, {call.id for call in key.calls}),
    ]
    for index, check in enumerate(gates, 1):
        if blocker:
            entries.append(constraint(*TEXTS[index], None, message=f"Not checked: {blocker} did not hold."))
            continue
        problem = check()
        if not add(index, problem is None, message=problem or ""):
            blocker = TEXTS[index][0]
    if blocker:
        for index in range(GATES, len(TEXTS)):
            entries.append(constraint(*TEXTS[index], None, message=f"Not checked: {blocker} did not hold."))
        return result(False, summary(entries), score=0.0, constraints=entries)

    # 5 to 8: the answer, against the verifier's own recomputation.
    schemas = {entry.tool: read_object(entry.schema)[0] for entry in key.schemas}
    got = given_reports(output.reports)
    said_valid = {entry.id: entry.valid for entry in output.reports}
    reported = [(call, args, why) for call, args, why in outcomes if call.id in got]

    missing = [(call, why) for call, _, why in outcomes if call.id not in got]
    add(
        4, not missing, [call.id for call, _ in missing], None,
        _first([f"{call.id} has no report: {_broken(why)}" for call, why in missing]),
    )
    wrong = [(call, why) for call, _, why in reported if said_valid[call.id] != (not why)]
    add(
        5, not wrong,
        [f"{call.id} {'valid' if not why else 'invalid'}" for call, why in wrong],
        [f"{call.id} {'valid' if said_valid[call.id] else 'invalid'}" for call, _ in wrong],
        _first([
            f"{call.id} is reported {'valid' if said_valid[call.id] else 'invalid'}, but {_broken(why)}"
            for call, why in wrong
        ]),
    )
    unreported = [(call, pair, why[pair]) for call, _, why in reported for pair in sorted(
        set(why) - got[call.id], key=lambda pair: (pair[0], pair[1].value))]
    add(
        6, not unreported, [named(call.id, pair) for call, pair, _ in unreported], None,
        _first([f"{call.id}: {pair[0]} {pair[1].value} is not reported: {reason}" for call, pair, reason in unreported]),
    )
    extra = [(call, args, why, pair) for call, args, why in reported for pair in sorted(
        got[call.id] - set(why), key=lambda pair: (pair[0], pair[1].value))]
    add(
        7, not extra, None, [named(call.id, pair) for call, _, _, pair in extra],
        _first([_why_extra(call, args, schemas[call.tool], why, pair) for call, args, why, pair in extra]),
    )

    right = sum(1 for call, _, why in reported if got[call.id] == set(why))
    if all(entry["ok"] for entry in entries):
        broken = sum(1 for _, _, why in outcomes if why)
        message = (
            f"All 8 checks hold: {len(outcomes)} calls, {len(outcomes) - broken} valid and {broken} invalid,"
            f" {sum(len(why) for _, _, why in outcomes)} violations."
        )
        return result(True, message, constraints=entries)
    score = min(right / len(outcomes), 0.99) if outcomes else 0.0
    return result(False, summary(entries), score=score, constraints=entries)
