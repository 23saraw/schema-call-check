"""load_batch: the check-calls answer key."""

from .checks import batch_input, result
from .task import expected_reports, given_reports, key_problem

verify_input = batch_input


def verify_output(input_value, output_value, workspace):
    if output_value.batch != input_value.batch:
        return result(False, f"the answer key is for {output_value.batch!r}, not {input_value.batch!r}")
    problem = key_problem(output_value)
    if problem:
        return result(False, problem)
    recomputed = {call.id: set(why) for call, _, why in expected_reports(output_value)}
    if given_reports(output_value.reports) != recomputed:
        return result(False, "the answer key's reports differ from the rules' recomputation")
    return result(True, "the answer key follows the rules", calls=len(output_value.calls))
