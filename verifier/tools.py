"""load_tools: each named tool's schema, in the README's subset."""

from .checks import result, schemas_problem, tools_input

verify_input = tools_input


def verify_output(input_value, output_value, workspace):
    if [entry.tool for entry in output_value.schemas] != input_value.tools:
        return result(False, "load_tools gives one schema per tool asked for, in that order, and this is not that")
    problem = schemas_problem(output_value.schemas)
    if problem:
        return result(False, problem)
    return result(True, "the schemas are loaded", schemas=len(output_value.schemas))
