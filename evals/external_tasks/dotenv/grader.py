"""Independent, offline behavioral checks; run through stdin outside the task tree."""

import io
import json
import logging
import tempfile
from pathlib import Path

import dotenv
from dotenv.parser import parse_stream


logging.getLogger("dotenv.main").setLevel(logging.CRITICAL)
checks = []


def check(name, operation):
    try:
        operation()
    except Exception as exc:
        checks.append({"name": name, "passed": False, "error": f"{type(exc).__name__}: {exc}"})
    else:
        checks.append({"name": name, "passed": True})


def equal(actual, expected):
    assert actual == expected, f"actual={actual!r}, expected={expected!r}"


def round_trip(value, quote_mode, export, existing):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / ".env"
        path.write_text("# preserved header\nBEFORE='stable'\n" + ("VALUE='old'\n" if existing else "") + "AFTER='stable'\n", encoding="utf-8")
        result = dotenv.set_key(path, "VALUE", value, quote_mode=quote_mode, export=export)
        equal(result, (True, "VALUE", value))
        parsed = dotenv.dotenv_values(path, interpolate=False)
        equal(dict(parsed), {"BEFORE": "stable", "AFTER": "stable", "VALUE": value})
        equal(dotenv.get_key(path, "VALUE"), value)
        assert path.read_text(encoding="utf-8").startswith("# preserved header\nBEFORE='stable'\n")
        # Writing a subsequent value must preserve the backslash-bearing value.
        equal(dotenv.set_key(path, "NEXT", "after write"), (True, "NEXT", "after write"))
        equal(dict(dotenv.dotenv_values(path, interpolate=False)), {"BEFORE": "stable", "AFTER": "stable", "VALUE": value, "NEXT": "after write"})


values = [
    "alpha",
    "",
    "single'quote",
    'double"quote',
    "prefix\\\\suffix",
    "\\\\server\\share\\",
    "trailing\\",
    "two trailing\\\\",
    "before\\'after",
    "before\\\\'after",
    "literal\\ntext",
    "line one\nline two\\",
    "한국어\\경로\\",
]
for index, value in enumerate(values):
    for mode in ("always", "auto"):
        for existing in (False, True):
            export = bool(index % 2)
            check(f"roundtrip_{index}_{mode}_{'replace' if existing else 'append'}", lambda value=value, mode=mode, export=export, existing=existing: round_trip(value, mode, export, existing))


def parse_quoted(quote, slash_count, trailing_newline):
    # Input is a syntactically quoted value containing an even backslash run.
    encoded_slashes = "\\" * (slash_count * 2)
    text = f"FIRST={quote}tail{encoded_slashes}{quote}\nSECOND={quote}untouched{quote}" + trailing_newline
    bindings = list(parse_stream(io.StringIO(text)))
    equal([(binding.key, binding.value, binding.error) for binding in bindings], [("FIRST", "tail" + "\\" * slash_count, False), ("SECOND", "untouched", False)])
    equal([binding.original.line for binding in bindings], [1, 2])


for quote in ("'", '"'):
    for count in (1, 2, 3):
        for ending in ("", "\n"):
            check(f"parser_{ord(quote)}_{count}_{bool(ending)}", lambda quote=quote, count=count, ending=ending: parse_quoted(quote, count, ending))


def never_mode():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / ".env"
        path.write_text("", encoding="utf-8")
        equal(dotenv.set_key(path, "RAW", "a\\b", quote_mode="never"), (True, "RAW", "a\\b"))
        equal(path.read_text(encoding="utf-8"), "RAW=a\\b\n")
        equal(dotenv.get_key(path, "RAW"), "a\\b")


check("never_quote_mode_preserved", never_mode)
passed = sum(item["passed"] for item in checks)
print(json.dumps({"passed": passed, "total": len(checks), "failed": len(checks) - passed, "checks": checks}, ensure_ascii=False))
raise SystemExit(passed != len(checks))
