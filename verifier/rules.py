"""The validation rules, written again apart from src/plugin/rules.py and sharing no code with it.

It reads JSON keeping decimals as written, walks a schema's properties before the call's arguments, and gives
a reason for every violation. A wrong rule would have to be written the same wrong way twice for the key to pass."""

import json

from contract import Kind

SCALAR_NAMES = {"string": "a string", "integer": "an integer", "number": "a number", "boolean": "a boolean"}
TYPE_NAMES = {**SCALAR_NAMES, "array": "an array"}
LONGEST = 40  # characters of a value a message shows


class Real:
    """A JSON number written with a fraction or an exponent (4.0, 1e1), kept exactly as written."""

    def __init__(self, text):
        self.text = text


class Unreadable(Exception):
    pass


def read_object(text):
    """(the JSON object ``text``, None), or (None, what is wrong): no duplicate keys, no NaN or Infinity."""

    def pairs(items):
        keys = [key for key, _ in items]
        if len(set(keys)) != len(keys):
            raise Unreadable("it gives a key twice")
        return dict(items)

    def constant(name):
        raise Unreadable(f"it uses {name}, which is not JSON")

    try:
        value = json.loads(text, parse_float=Real, parse_constant=constant, object_pairs_hook=pairs)
    except Unreadable as problem:
        return None, str(problem)
    except ValueError:
        return None, "it is not JSON"
    if type(value) is not dict:
        return None, "it is not a JSON object"
    return value, None


def subset_problem(schema, tool):
    """What takes ``schema`` outside the README's subset (rule 1), or None."""
    if type(schema) is not dict or sorted(schema) != ["properties", "required", "type"] or schema["type"] != "object":
        return f"{tool}'s schema is not an object schema with exactly type, properties and required"
    properties, required = schema["properties"], schema["required"]
    if type(properties) is not dict or type(required) is not list:
        return f"{tool}'s properties is not an object, or its required not a list"
    for name in required:
        if type(name) is not str or name not in properties or required.count(name) > 1:
            return f"{tool}'s required names {name!r}, which is not one distinct property"
    for name, rule in properties.items():
        if type(rule) is not dict or rule.get("type") not in TYPE_NAMES:
            return f"{tool}.{name} has no supported type"
        kind = rule["type"]
        extra = set(rule) - {"type", "items" if kind == "array" else "enum"}
        if extra:
            return f"{tool}.{name} uses {min(extra)!r}, outside the subset"
        if kind == "array":
            items = rule.get("items")
            if type(items) is not dict or list(items) != ["type"] or items["type"] not in SCALAR_NAMES:
                return f"{tool}.{name} is an array without exactly one scalar items type"
        if "enum" in rule:
            options = rule["enum"]
            if kind not in ("string", "integer") or type(options) is not list or not options:
                return f"{tool}.{name} has an enum, which only a string or integer may have, and never empty"
            if any(not fits(option, kind) for option in options) or len(set(options)) != len(options):
                return f"{tool}.{name}'s enum values are not distinct values of its type"
    return None


def fits(value, kind):
    """Rule 3, by exact type: bool is its own type, an int token is the only integer, a decimal is a number."""
    if kind == "string":
        return type(value) is str
    if kind == "integer":
        return type(value) is int
    if kind == "number":
        return type(value) in (int, Real)
    if kind == "boolean":
        return type(value) is bool
    return False


def described(value):
    if value is None:
        return "null"
    return {bool: "a boolean", int: "an integer", Real: "a decimal", str: "a string", list: "an array"}.get(
        type(value), "an object"
    )


def shown(value):
    """``value`` as JSON, with decimals as written, cut to LONGEST characters."""
    if value is None:
        text = "null"
    elif type(value) is bool:
        text = "true" if value else "false"
    elif type(value) is Real:
        text = value.text
    elif type(value) is list:
        text = "[" + ", ".join(shown(item) for item in value) + "]"
    elif type(value) is dict:
        text = "{...}"
    elif type(value) is str:
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = str(value)
    return text if len(text) <= LONGEST else text[: LONGEST - 3] + "..."


def judge(schema, arguments, tool):
    """{(parameter, Kind): why} for every rule the call breaks (rules 2 to 7)."""
    found = {}
    properties = schema["properties"]
    for name, rule in properties.items():
        if name not in arguments:
            if name in schema["required"]:
                found[(name, Kind.MISSING_REQUIRED)] = f"{name} is required and not given"
            continue
        value, kind = arguments[name], rule["type"]
        if value is None:
            found[(name, Kind.WRONG_TYPE)] = f"{name} is null, the wrong type for every parameter"
        elif kind == "array":
            item_kind = rule["items"]["type"]
            if type(value) is not list:
                found[(name, Kind.WRONG_TYPE)] = f"{name} is {shown(value)}, {described(value)}, not an array"
            else:
                bad = [item for item in value if not fits(item, item_kind)]
                if bad:
                    found[(name, Kind.WRONG_TYPE)] = (
                        f"{name} has the item {shown(bad[0])}, {described(bad[0])}, not {SCALAR_NAMES[item_kind]}"
                        + (f" ({len(bad)} bad items, one WRONG_TYPE)" if len(bad) > 1 else "")
                    )
        elif not fits(value, kind):
            found[(name, Kind.WRONG_TYPE)] = f"{name} is {shown(value)}, {described(value)}, not {SCALAR_NAMES[kind]}"
        elif "enum" in rule and value not in rule["enum"]:
            near = [o for o in rule["enum"] if type(o) is str and type(value) is str and o.lower() == value.lower()]
            hint = f": enum matching is case-sensitive, and {shown(near[0])} differs only by case" if near else ""
            options = ", ".join(shown(option) for option in rule["enum"])
            found[(name, Kind.NOT_IN_ENUM)] = f"{name} is {shown(value)}, not one of {options}{hint}"
    for name in arguments:
        if name not in properties:
            near = [known for known in properties if known.lower() == name.lower()]
            hint = f" (names are case-sensitive; it has {near[0]})" if near else ""
            found[(name, Kind.UNKNOWN_PARAMETER)] = f"{name} is not a parameter of {tool}{hint}"
    return found
