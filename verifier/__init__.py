"""The deterministic verifier: each tool's checks live in its own module, on contract instances."""

from contract import Task, Tool

from . import calls, lenient, load, quick, task, tools

TOOLS = {
    Tool.LOAD_BATCH: load,
    Tool.READ_CALLS: calls,
    Tool.LOAD_TOOLS: tools,
    Tool.QUICK_CHECK: quick,
    Tool.LENIENT_CHECK: lenient,
}
# task -> its output's check, verify_task(arguments, output, reference, workspace)
TASKS = {Task.CHECK_CALLS: task.verify_task}


def verify_input(tool, value):
    return TOOLS[Tool(tool)].verify_input(value)


def verify_output(tool, input_value, output_value, workspace):
    return TOOLS[Tool(tool)].verify_output(input_value, output_value, workspace)


def verify_task(task, arguments, output, reference, workspace):
    return TASKS[Task(task)](arguments, output, reference, workspace)
