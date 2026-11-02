"""Expected reports, derived by hand from the README's rules before any code ran. Never generate these."""

from __future__ import annotations

M, W, E, U = "MISSING_REQUIRED", "WRONG_TYPE", "NOT_IN_ENUM", "UNKNOWN_PARAMETER"

BATCHES = {
    # book_room: room (string, enum small/large), guests (integer), date (string) required; projector (boolean).
    # log_reading: sensor (string), value (number) required; tags (array of string), unit (string, enum c/f).
    # list_notes: limit (integer), folder (string); nothing required.
    # set_levels: levels (array of integer) required; channel (integer, enum 1/2/3).
    "batch-1.json": {
        "c1": [],  # every required parameter, each the right type, room in its enum
        "c2": [("guests", W)],  # true is a boolean, never an integer
        "c3": [("guests", W)],  # 4.0 is a decimal, not an integer
        "c4": [("guests", W), ("room", E)],  # "5" is a string; "Large" is not "large"
        "c5": [("date", W), ("room", W)],  # 7 for an enum string: WRONG_TYPE only; null for a required parameter
        "c6": [("floor", U), ("room", M)],  # missing and unknown in one call
        "c7": [("Room", U), ("room", M)],  # names are case-sensitive
        "c8": [],  # an empty call to a tool with nothing required
        "c9": [],  # 3 is a number; an empty array is valid
        "c10": [("tags", W), ("value", W)],  # "2.5" is a string; one bad item, one WRONG_TYPE
    },
    "batch-2.json": {
        "d1": [],
        "d2": [("levels", W)],  # 2.5 and true are both bad items: still one WRONG_TYPE
        "d3": [("channel", E), ("levels", W)],  # a string is not an array; 4 is an integer outside 1/2/3
        "d4": [("channel", W), ("levels", M)],  # 2.0 is not an integer, so no enum check either
        "d5": [("value", W)],  # false is a boolean, never a number
        "d6": [("unit", E)],  # -1.5e2 is a number; "F" is not "f"
        "d7": [("limit", W)],  # null is the wrong type for an optional parameter too
        "d8": [("Limit", U)],  # limit is given (0 is an integer); Limit is another name
        "d9": [("guests", W), ("projector", W)],  # 1e1 has an exponent: a number, not an integer; 1 is not a boolean
        "d10": [("date", M), ("guests", M), ("room", M)],
    },
}


def answer(batch: str) -> dict:
    """The right submission for ``batch``, as JSON."""
    return {
        "batch": batch,
        "reports": [
            {"id": call, "valid": not found, "violations": [{"parameter": p, "kind": k} for p, k in found]}
            for call, found in BATCHES[batch].items()
        ],
    }
