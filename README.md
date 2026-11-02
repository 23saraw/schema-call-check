# Call Checker

A `nanoagent.plugin/v0001` plugin. Its task, `check-calls`, has an agent
validate a batch of proposed tool calls against the tools' schemas: given a
bundled batch (calls with an id, a tool and arguments) and the bundled schemas,
it reports for each call whether it is valid and, if not, every rule it breaks,
as `(parameter, kind)` pairs with the kinds `MISSING_REQUIRED`, `WRONG_TYPE`,
`NOT_IN_ENUM` and `UNKNOWN_PARAMETER`. No network. The schemas and calls are
invented and committed to the repo. Arguments and schemas travel as JSON text,
since the contract cannot type arbitrary JSON, so a token such as `4.0` or `1e1`
reaches the agent exactly as written. The verifier checks every call again in
its own code and judges every report.

## Tools

| Tool | Does | Code |
|---|---|---|
| `load_batch` | The answer key: the batch, its calls, the schemas they name, and each call's report under the rules. The agent never sees it | `src/plugin/calls.py`, `src/plugin/rules.py` |
| `read_calls` | A batch's calls: each one's id, tool and arguments (a JSON object's text), exactly as written | `src/plugin/calls.py` |
| `load_tools` | Each named tool's schema, as a JSON object's text | `src/plugin/calls.py` |
| `quick_check` | A distractor: checks a whole batch, but reports only required parameters that are absent. True about itself, but trusted it misses the other three kinds and calls those calls valid | `src/plugin/calls.py` |
| `lenient_check` | A distractor: checks a whole batch after coercing as many APIs do, numeric strings to numbers and whole decimals to integers. True about itself, but rule 3 forbids coercion, so `"5"`, `4.0` and `1e1` pass where they must not | `src/plugin/calls.py` |

No agent tool validates under the rules: the agent applies them itself. Its
plan is `read_calls`, `load_tools` with every tool the calls name, then
`submit`: three tool calls.

### Tasks

| Task | Does | Runner |
|---|---|---|
| `check-calls` | Reports, for each call in a bundled batch, whether it is valid and every rule it breaks | `agent`, with `read_calls`, `load_tools`, `quick_check` and `lenient_check`; reference `load_batch` |

## The rules

1. **The schema subset.** A schema is a flat object with exactly `"type":
   "object"`, `"properties"` and `"required"`. Each property has a `"type"`:
   `string`, `integer`, `number`, `boolean` or `array`. An array has exactly
   `"items": {"type": ...}` with a scalar type (no nested arrays). A `string` or
   `integer` property may have an `"enum"`: a non-empty list of distinct values
   of its type. Nothing else: no nesting, no `nullable`, no defaults, no enum on
   numbers, booleans or arrays. `required` names distinct properties.
2. **Violations.** A call reports every violation as a `(parameter, kind)`
   pair; it is valid only if it has none. Order does not matter. A parameter
   breaks at most one rule, so no name has two kinds.
3. **Types.** Strict JSON types, never coerced. `integer` accepts only a JSON
   integer token: `1`, not `1.0`, `1e1` or `"1"`. `number` accepts any JSON
   number, integers and decimals alike (`-1.5e2` is one). Booleans are never
   integers or numbers, and numbers are never booleans. `null` is the wrong type
   for every parameter, required or not.
4. **Missing.** A required parameter that is absent is `MISSING_REQUIRED`; one
   that is present but `null` is `WRONG_TYPE`, not missing.
5. **Enums.** The enum check applies only when the type is right: a wrong-type
   value reports `WRONG_TYPE` only, never also `NOT_IN_ENUM`. Matching is exact
   and case-sensitive (`"Large"` is not `"large"`).
6. **Unknown.** Any argument not in `"properties"` is `UNKNOWN_PARAMETER`.
   Parameter names are case-sensitive: `Room` given where `room` is required is
   `UNKNOWN_PARAMETER` for `Room` and `MISSING_REQUIRED` for `room`.
7. **Arrays.** An array with any wrong-type item reports one `WRONG_TYPE` for
   that parameter, however many items are wrong; an empty array is valid.
8. **Well-formed calls.** Every call names a bundled tool, and its arguments
   are a JSON object with no duplicate keys and no `NaN` or `Infinity`. The
   tools refuse a batch that breaks this, and so does the verifier's first
   constraint.
9. **The submission.** One report per call: `id`, `valid` (true exactly when
   `violations` is empty) and `violations`, each `(parameter, kind)` once, with
   the parameter's name exactly as the call or the schema writes it.

## Batches

The tools, in `src/plugin/data/schemas.json`:

| Tool | Properties | Required |
|---|---|---|
| `book_room` | `room` string, enum `small`/`large`; `guests` integer; `date` string; `projector` boolean | room, guests, date |
| `log_reading` | `sensor` string; `value` number; `tags` array of string; `unit` string, enum `c`/`f` | sensor, value |
| `list_notes` | `limit` integer; `folder` string | none |
| `set_levels` | `levels` array of integer; `channel` integer, enum `1`/`2`/`3` | levels |

The batches, in `src/plugin/data/batches/`, each built around traps. The
expected reports were derived by hand (`tests/expected.py`) and both
implementations are tested against them.

**batch-1:**

| Call | Arguments | Violations |
|---|---|---|
| c1 | `book_room {"room": "large", "guests": 4, "date": "2026-11-02"}` | none: valid |
| c2 | `book_room`, `"guests": true` | guests `WRONG_TYPE` (a boolean is never an integer) |
| c3 | `book_room`, `"guests": 4.0` | guests `WRONG_TYPE` (a decimal is not an integer) |
| c4 | `book_room`, `"room": "Large", "guests": "5"` | room `NOT_IN_ENUM` (case), guests `WRONG_TYPE` (a string) |
| c5 | `book_room`, `"room": 7, "date": null` | room `WRONG_TYPE` only, never also `NOT_IN_ENUM`; date `WRONG_TYPE` (null, not missing) |
| c6 | `book_room`, no room, `"floor": 3` | room `MISSING_REQUIRED`, floor `UNKNOWN_PARAMETER` |
| c7 | `book_room`, `"Room": "small"` | Room `UNKNOWN_PARAMETER`, room `MISSING_REQUIRED` |
| c8 | `list_notes {}` | none: valid (nothing is required) |
| c9 | `log_reading {"sensor": "s1", "value": 3, "tags": []}` | none: valid (an integer is a number; an empty array) |
| c10 | `log_reading`, `"value": "2.5", "tags": ["a", 2]` | value `WRONG_TYPE`, tags `WRONG_TYPE` (one bad item) |

**batch-2:**

| Call | Arguments | Violations |
|---|---|---|
| d1 | `set_levels {"levels": [1, 2, 3], "channel": 2}` | none: valid |
| d2 | `set_levels`, `"levels": [1, 2.5, true]` | levels `WRONG_TYPE`, once for two bad items |
| d3 | `set_levels`, `"levels": "1,2", "channel": 4` | levels `WRONG_TYPE`, channel `NOT_IN_ENUM` |
| d4 | `set_levels {"channel": 2.0}` | levels `MISSING_REQUIRED`, channel `WRONG_TYPE` (so no enum check) |
| d5 | `log_reading`, `"value": false` | value `WRONG_TYPE` (a boolean is never a number) |
| d6 | `log_reading`, `"value": -1.5e2, "unit": "F"` | unit `NOT_IN_ENUM` only (`-1.5e2` is a number) |
| d7 | `list_notes {"limit": null}` | limit `WRONG_TYPE` (null, though optional) |
| d8 | `list_notes {"limit": 0, "folder": "work", "Limit": 5}` | Limit `UNKNOWN_PARAMETER` only |
| d9 | `book_room`, `"guests": 1e1, "projector": 1` | guests `WRONG_TYPE` (an exponent is not an integer), projector `WRONG_TYPE` |
| d10 | `book_room {}` | room, guests and date `MISSING_REQUIRED` |

Trusted, `quick_check` gets 3 of batch-1's calls right and 2 of batch-2's;
`lenient_check` gets 7 and 8, wrong on c3, c4, c10, d4 and d9.

## Constraints

`verifier/task.py` judges the submission against 8 constraints, in order.
Every entry of the verdict's `details.constraints` has the keys
`{id, constraint, ok, expected, actual, message}`; `ok` is `true`, `false`, or
`null` when a check it needs did not hold.

| # | id | What it checks | Example failure message |
|---|---|---|---|
| 1 | `answer-key` | The answer key is this batch's and well formed: each schema in the subset, each call's tool has a schema, each call's arguments a JSON object, one report per call | call c1's arguments cannot be read: it uses NaN, which is not JSON |
| 2 | `answer-key-rules` | The key's reports equal the verifier's own recomputation | the answer key's report for c3 differs from the rules' recomputation |
| 3 | `submitted-batch` | The submission is for this batch | the submission is for 'batch-2.json', not 'batch-1.json' |
| 4 | `reports-shaped` | Each report names a call of this batch, once; valid exactly when it has no violation; no (parameter, kind) twice | c2 is reported valid with violations: a call is valid exactly when it breaks no rule |
| 5 | `reports-complete` | Every call has a report | c5 has no report: it breaks 2 rules: date is null, the wrong type for every parameter |
| 6 | `verdicts-exact` | Each call is reported valid or invalid rightly | c3 is reported valid, but it breaks 1 rule: guests is 4.0, a decimal, not an integer |
| 7 | `violations-complete` | Every violation the rules give is reported | c7: Room UNKNOWN_PARAMETER is not reported: Room is not a parameter of book_room (names are case-sensitive; it has room) |
| 8 | `no-extra-violations` | No violation is reported that the rules do not give | c5: room NOT_IN_ENUM is reported, but room is WRONG_TYPE only (room is 7, an integer, not a string); the enum check applies only to a value of the right type |

How it is scored:

- **Valid** only when all 8 hold; the score is then 1.0.
- **Score 0** when any of 1 to 4 fails: they guard the answer key and the submission's integrity.
- **Otherwise** the score is the share of calls whose report is exactly right, at most 0.99.
- **The message** names the first failing constraint, why, and how many more fail.

`verifier/rules.py` is a second implementation of the rules that shares no
code with `src/plugin/rules.py`: it keeps decimals as written (so `1e1` shows as
`1e1`, not `10.0`), tests types by exact Python type rather than `isinstance`,
walks a schema's properties before the call's arguments, and gives a reason for
every violation. Constraint 2 checks that the answer key agrees with it, so a
wrong rule would have to be written the same wrong way twice to pass. Every tool
call is checked as well: `verify_input` refuses a malformed batch name and an
empty, oversized or repeated tool list, and `verify_output` holds each tool's
output to what it promises (`quick_check` may report only `MISSING_REQUIRED`).

## Limitations

- **Only the bundled batches.** The task input names one of the batches in
  `src/plugin/data/batches/`; a person cannot bring calls or schemas of their
  own.
- **A small subset of JSON Schema.** No nested objects, `nullable`,
  `additionalProperties`, formats, ranges or enums on numbers; real tool
  schemas often use them.
- **One kind per parameter.** The four kinds cannot overlap on one name, so a
  report never needs to rank them; a richer subset (ranges, formats) would.
- **No provenance gate.** The plugin writes no files, so the verifier cannot
  prove the agent called the tools. The answer depends on data only the tools
  give, so a correct answer without them would be a guess.

## Layout

```text
.
├── nanoagent.yaml   # manifest: id, runtime, permissions (none), tools, tasks
├── contract.py      # each tool's and task's typed input and output: slimconfig Output classes
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── .gitignore
├── .env             # environment variable names this plugin needs (none)
├── src/plugin/      # the MCP server (__main__.py), the tools (calls.py), the rules (rules.py)
│   └── data/        # schemas.json and batches/, the bundled data
├── tests/           # hand-derived answers (expected.py), both rule implementations, the tools, the verifier
├── ui/              # how the page draws outputs: drawn from the JSON Schema
├── product/         # the product page a catalog shows: product.yaml and icon.svg
└── verifier/        # deterministic verifier: one module per tool, rules.py, and the task's 8 constraints in task.py
```

## Develop and run

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
uv lock --check
```

With the `nanoagent` CLI installed in a separate environment:

```bash
nanoagent plugin inspect .                        # every plugin rule
nanoagent plugin agent config=run.yaml home=out   # the agent task; needs OPENROUTER_API_KEY
```

A `run.yaml` for one batch (`args.json` holds the task input, e.g.
`{"batch": "batch-1.json"}`; give `plugin` and `arguments` as absolute paths).
The run folder gets `result.json`, `reference.json`, `messages.json` and
`verdict.json`, and the command exits 1 unless the verdict is valid:

```yaml
_ > nanoagent.cli.plugin.PluginOpenRouterAgentConfig:
plugin: /path/to/schema-call-check
task: check-calls
arguments: /path/to/args.json
inputs: []
timeout: 60
llm > nanoagent.llm.openrouter.OpenRouterConfig:
  model: deepseek/deepseek-v4-flash-0731
  max_tokens: null
  temperature: null
  max_attempts: 3
  read_timeout: 180
  input_price: 0.0
  output_price: 0.0
harness > nanoagent.harness.nanoagent.NanoAgentConfig:
  max_steps: 8
  cost_limit: null
  token_limit: null
  context_window: null
  hooks: []
  skills: null
  context_files: []
  events: null
```
