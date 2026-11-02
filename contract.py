"""Each tool's and task's typed input and output (see nanoagent.plugin.v0001.contract): declarations only."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output

BATCH = "A bundled batch file's name, such as 'batch-1.json'"
CALL_ID = "The call's id, such as 'c1'"


class Tool(Enum):
    LOAD_BATCH = "load_batch"
    READ_CALLS = "read_calls"
    LOAD_TOOLS = "load_tools"
    QUICK_CHECK = "quick_check"
    LENIENT_CHECK = "lenient_check"


class Task(Enum):
    CHECK_CALLS = "check-calls"


class Kind(Enum):
    MISSING_REQUIRED = "MISSING_REQUIRED"
    WRONG_TYPE = "WRONG_TYPE"
    NOT_IN_ENUM = "NOT_IN_ENUM"
    UNKNOWN_PARAMETER = "UNKNOWN_PARAMETER"


@dataclass
class BatchInput(Output):
    batch: Annotated[str, BATCH]


@dataclass
class Call(Output):
    id: Annotated[str, CALL_ID]
    tool: Annotated[str, "The tool the call names"]
    arguments: Annotated[str, "The call's arguments: a JSON object's text, exactly as written"]


@dataclass
class CallsOutput(Output):
    batch: Annotated[str, BATCH]
    calls: Annotated[list[Call], "The batch's proposed tool calls, in order"]


@dataclass
class ToolsInput(Output):
    tools: Annotated[list[str], "The tools whose schemas to load, such as 'book_room'"]


@dataclass
class Schema(Output):
    tool: Annotated[str, "The tool's name"]
    schema: Annotated[str, "The tool's parameter schema: a JSON object's text, in the README's subset of JSON Schema"]


@dataclass
class ToolsOutput(Output):
    schemas: Annotated[list[Schema], "One schema per tool asked for, in that order"]


@dataclass
class Violation(Output):
    parameter: Annotated[str, "The parameter's name, exactly as the call or the schema writes it"]
    kind: Annotated[Kind, "The rule it breaks"]


@dataclass
class Report(Output):
    id: Annotated[str, CALL_ID]
    valid: Annotated[bool, "Whether the call breaks no rule"]
    violations: Annotated[list[Violation], "Every rule the call breaks, one entry per (parameter, kind); [] when valid"]


@dataclass
class ReportsOutput(Output):
    batch: Annotated[str, BATCH]
    reports: Annotated[list[Report], "One report per call"]


@dataclass
class KeyOutput(Output):
    batch: Annotated[str, BATCH]
    calls: Annotated[list[Call], "The batch's calls"]
    schemas: Annotated[list[Schema], "The schema of every tool a call names"]
    reports: Annotated[list[Report], "The expected reports"]


TOOLS = {
    Tool.LOAD_BATCH: (BatchInput, KeyOutput),
    Tool.READ_CALLS: (BatchInput, CallsOutput),
    Tool.LOAD_TOOLS: (ToolsInput, ToolsOutput),
    Tool.QUICK_CHECK: (BatchInput, ReportsOutput),
    Tool.LENIENT_CHECK: (BatchInput, ReportsOutput),
}
TASKS = {Task.CHECK_CALLS: (BatchInput, ReportsOutput)}
