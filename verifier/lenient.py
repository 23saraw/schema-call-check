"""lenient_check: a distractor; it coerces "5" to 5 and 1.0 to 1 before checking, which rule 3 forbids."""

from .checks import batch_input, reports_problem, result

verify_input = batch_input


def verify_output(input_value, output_value, workspace):
    if output_value.batch != input_value.batch:
        return result(False, f"lenient_check gave {output_value.batch!r}, not {input_value.batch!r}")
    problem = reports_problem(output_value.reports)
    if problem:
        return result(False, problem)
    return result(True, "the calls are checked after coercion", reports=len(output_value.reports))
