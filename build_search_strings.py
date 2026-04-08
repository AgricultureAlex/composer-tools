#!/usr/bin/env python3
"""
build_search_strings.py
=======================
Generate a paste-ready `search_strings` block for part_prep_config.txt
from one of the bundled ensemble CSVs.

The CSVs live in resources/score_orders/ and have these columns:
    short_name, long_name, sibelius, musescore, dorico, finale

Cells may contain the placeholder `{n}`. Rows containing `{n}` are
expanded into multiple lines based on --counts; rows without `{n}`
are emitted as-is. When `{n}` collapses to nothing (count == 1 with no
override), one adjacent space or underscore is also stripped, so
`Clarinet {n} in B♭` → `Clarinet in B♭` and `Flute_{n}` → `Flute`.

Each row becomes one line of the form:
    {program_output} -> {short_name} / {long_name}

If the program column is empty for a given row, the line falls back to
a guess derived from the short name with a # TODO comment.

Usage:
    python build_search_strings.py orchestra musescore
    python build_search_strings.py orchestra musescore --counts fl=2,hn=4,tpt=2
    python build_search_strings.py band dorico --counts cl=3,tpt=3
    python build_search_strings.py --list

Programmatic use:
    from build_search_strings import build_block, list_ensembles
    block, todos = build_block("orchestra", "musescore", counts={"fl": 2, "hn": 4})
"""

import argparse
import csv
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCORE_ORDERS_DIR = os.path.join(SCRIPT_DIR, "score_orders")

VALID_PROGRAMS = ("sibelius", "musescore", "dorico", "finale")
PLACEHOLDER = "{n}"

# Match {n} with one optional adjacent separator (space or underscore).
# We prefer to eat a separator on the left if there is one, otherwise the right.
_PLACEHOLDER_COLLAPSE_LEFT = re.compile(r"[ _]\{n\}")
_PLACEHOLDER_COLLAPSE_RIGHT = re.compile(r"\{n\}[ _]")
_PLACEHOLDER_BARE = re.compile(r"\{n\}")


# ── public API ────────────────────────────────────────────────────────


def list_ensembles():
    """Return a sorted list of available ensemble names (CSV basenames)."""
    if not os.path.isdir(SCORE_ORDERS_DIR):
        return []
    return sorted(
        os.path.splitext(f)[0]
        for f in os.listdir(SCORE_ORDERS_DIR)
        if f.endswith(".csv")
    )


def load_ensemble(ensemble):
    """Load rows from resources/score_orders/<ensemble>.csv as a list of dicts."""
    path = os.path.join(SCORE_ORDERS_DIR, f"{ensemble}.csv")
    if not os.path.exists(path):
        available = ", ".join(list_ensembles()) or "(none)"
        raise FileNotFoundError(
            f"Ensemble '{ensemble}' not found at {path}. "
            f"Available ensembles: {available}"
        )
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def parse_counts(counts_str):
    """Parse 'fl=2,hn=4' into {'fl': 2, 'hn': 4}. Empty string → {}."""
    if not counts_str:
        return {}
    out = {}
    for chunk in counts_str.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "=" not in chunk:
            raise ValueError(
                f"Invalid --counts entry {chunk!r} (expected key=value, e.g. fl=2)"
            )
        key, val = chunk.split("=", 1)
        key = key.strip().lower()
        try:
            out[key] = int(val.strip())
        except ValueError:
            raise ValueError(f"Count for {key!r} must be an integer, got {val!r}")
        if out[key] < 1:
            raise ValueError(f"Count for {key!r} must be >= 1, got {out[key]}")
    return out


def build_block(ensemble, program, counts=None):
    """Build a search_strings block for one ensemble + program.

    Parameters
    ----------
    ensemble : str
        Name of the ensemble CSV (without .csv extension).
    program : str
        One of VALID_PROGRAMS.
    counts : dict[str, int] | None
        Optional per-instrument multiplicity overrides, e.g. {"fl": 2, "hn": 4}.
        Keys are matched case-insensitively against each row's short_name root
        and long_name first word.

    Returns
    -------
    (block_text, todo_count) : tuple[str, int]
        block_text is the formatted search_strings block (no header comments).
        todo_count is the number of lines that fell back to a guessed export.
    """
    if program not in VALID_PROGRAMS:
        raise ValueError(
            f"Unknown program {program!r}. Choose one of: {', '.join(VALID_PROGRAMS)}"
        )
    counts = counts or {}
    rows = load_ensemble(ensemble)

    lines = []
    todo_count = 0
    for row in rows:
        for export, short, long, is_todo in _expand_row(row, program, counts):
            if is_todo:
                lines.append(
                    f"{export} -> {short} / {long}  "
                    f"# TODO: verify {program} export string"
                )
                todo_count += 1
            else:
                lines.append(f"{export} -> {short} / {long}")

    return "\n".join(lines), todo_count


# ── internals ─────────────────────────────────────────────────────────


def _collapse_placeholder(text):
    """Remove {n} along with one adjacent separator if present."""
    if PLACEHOLDER not in text:
        return text
    text = _PLACEHOLDER_COLLAPSE_LEFT.sub("", text, count=1)
    if PLACEHOLDER in text:
        text = _PLACEHOLDER_COLLAPSE_RIGHT.sub("", text, count=1)
    if PLACEHOLDER in text:
        text = _PLACEHOLDER_BARE.sub("", text)
    return text


def _substitute_placeholder(text, n):
    """Substitute {n} with a number."""
    return text.replace(PLACEHOLDER, str(n))


def _row_keys(row):
    """Return the set of lowercase keys this row matches against in --counts.

    Tries the short_name root and long_name first word, both lowercased and
    with {n} stripped.
    """
    keys = set()
    for col in ("short_name", "long_name"):
        text = _collapse_placeholder(row.get(col, "").strip()).strip().lower()
        if text:
            keys.add(text.split()[0])
    return keys


def _expand_row(row, program, counts):
    """Expand one CSV row into one or more (export, short, long, is_todo) tuples."""
    short_template = row.get("short_name", "").strip()
    long_template = row.get("long_name", "").strip()
    export_template = (row.get(program) or "").strip()

    # Determine count for this row
    matched_count = None
    for key in _row_keys(row):
        if key in counts:
            matched_count = counts[key]
            break

    has_placeholder = (
        PLACEHOLDER in short_template
        or PLACEHOLDER in long_template
        or PLACEHOLDER in export_template
    )

    if not has_placeholder:
        # Plain row — emit once
        export, is_todo = _resolve_export(export_template, short_template)
        return [(export, short_template, long_template, is_todo)]

    if matched_count is None:
        # Templated row but no count override — collapse to singular
        short = _collapse_placeholder(short_template)
        long = _collapse_placeholder(long_template)
        export_collapsed = _collapse_placeholder(export_template)
        export, is_todo = _resolve_export(export_collapsed, short)
        return [(export, short, long, is_todo)]

    # Templated row with explicit count — expand
    out = []
    for n in range(1, matched_count + 1):
        short = _substitute_placeholder(short_template, n)
        long = _substitute_placeholder(long_template, n)
        export_subbed = _substitute_placeholder(export_template, n)
        export, is_todo = _resolve_export(export_subbed, short)
        out.append((export, short, long, is_todo))
    return out


def _resolve_export(export_template, short_name):
    """Return (export_string, is_todo). If export is empty, fall back to a guess."""
    if export_template:
        return export_template, False
    return short_name.replace(" ", "_"), True


# ── CLI ───────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Generate a search_strings block from a bundled ensemble CSV.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "ensemble",
        nargs="?",
        help="Ensemble name (e.g. orchestra, band, brass_quintet, woodwind_quintet)",
    )
    parser.add_argument(
        "program",
        nargs="?",
        choices=VALID_PROGRAMS,
        help="Notation program you exported from",
    )
    parser.add_argument(
        "--counts",
        default="",
        help="Per-instrument multiplicity overrides, e.g. fl=2,hn=4,tpt=2",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available ensembles and exit",
    )

    args = parser.parse_args()

    if args.list or not args.ensemble:
        ensembles = list_ensembles()
        if not ensembles:
            print("No ensemble CSVs found in", SCORE_ORDERS_DIR)
            return
        print("Available ensembles:")
        for name in ensembles:
            print(f"  {name}")
        if not args.ensemble:
            print(
                "\nUsage: python build_search_strings.py <ensemble> <program> [--counts ...]"
            )
        return

    if not args.program:
        sys.exit(
            f"Missing program. Choose one of: {', '.join(VALID_PROGRAMS)}\n"
            f"Example: python build_search_strings.py {args.ensemble} musescore"
        )

    try:
        counts = parse_counts(args.counts)
    except ValueError as e:
        sys.exit(f"Error parsing --counts: {e}")

    try:
        block, todo_count = build_block(args.ensemble, args.program, counts=counts)
    except FileNotFoundError as e:
        sys.exit(str(e))

    counts_summary = (
        ", ".join(f"{k}={v}" for k, v in counts.items()) if counts else "defaults"
    )
    print(f"# {args.ensemble} score order — {args.program} export strings")
    print(f"# Counts: {counts_summary}")
    print(f"# Generated by build_search_strings.py")
    print(f"# Paste this into the --- search_strings --- section of part_prep_config.txt")
    print()
    print(block)

    if todo_count:
        print(
            f"\n# Note: {todo_count} line(s) have no known {args.program} export "
            f"string and used a fallback guess.",
            file=sys.stderr,
        )
        print(
            f"# Edit resources/score_orders/{args.ensemble}.csv to fill them in.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
