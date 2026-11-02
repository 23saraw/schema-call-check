"""read_calls: the batch's proposed calls, as written."""

from .checks import batch_input, calls_problem, result

verify_input = batch_input


def verify_output(input_value, output_value, workspace):
    if output_value.batch != input_value.batch:
        return result(False, f"read_calls gave {output_value.batch!r}, not {input_value.batch!r}")
    problem = calls_problem(output_value.calls)
    if problem:
        return result(False, problem)
    return result(True, "the calls are read", calls=len(output_value.calls))
