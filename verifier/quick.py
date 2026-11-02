"""quick_check: a distractor; it reports only absent required parameters, so the other three kinds go unseen."""

from contract import Kind

from .checks import batch_input, reports_problem, result

verify_input = batch_input


def verify_output(input_value, output_value, workspace):
    if output_value.batch != input_value.batch:
        return result(False, f"quick_check gave {output_value.batch!r}, not {input_value.batch!r}")
    problem = reports_problem(output_value.reports)
    if problem:
        return result(False, problem)
    if any(v.kind is not Kind.MISSING_REQUIRED for entry in output_value.reports for v in entry.violations):
        return result(False, "quick_check reports only MISSING_REQUIRED, and this reports another kind")
    return result(True, "the required parameters are checked", reports=len(output_value.reports))
