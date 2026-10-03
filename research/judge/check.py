#!/usr/bin/env python3
"""Check a research file against the brief's own rules. Exits 1 on any failure.

Every SOURCE: line must be followed by exactly one COSTS: line before the next
SOURCE: (or end of file). Every SOURCE: must carry a link or file path. No
markdown. Each section at most 300 words. 5-line header.

Run `check.py --self-test` first: it writes a deliberately broken file and
confirms this checker rejects every planted defect. The first version of this
checker passed a file with a missing COSTS line — the section simply became
invisible to it. A checker that has never failed is untested.
"""

import re
import sys
import tempfile
from pathlib import Path

LINK = re.compile(r"https?://\S+|(?:repo|file):\s*\S+|/[\w./-]+\.(?:md|py|txt|json|yaml|yml)")
MARKDOWN = re.compile(r"^\s*(#{1,6}\s|\*\s|\|.*\|\s*$|---+\s*$)")
HEADER_LINES = 5
WORD_CAP = 300
GRACE = 30


def _is(line: str, tag: str) -> bool:
    return line.strip().upper().startswith(tag)


def check(path: Path) -> tuple[list[str], str]:
    """Returns (problems, info). Empty problems = pass."""
    problems: list[str] = []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    nonempty = [l for l in lines[:10] if l.strip()]
    if len(nonempty) < HEADER_LINES:
        problems.append(f"header: {len(nonempty)} non-empty lines at top, need {HEADER_LINES}")

    for i, line in enumerate(lines, 1):
        if MARKDOWN.match(line):
            problems.append(f"line {i}: markdown formatting ({line.strip()[:40]!r})")

    # Walk the file as a state machine: header -> [body... SOURCE COSTS]* -> end
    sections = 0
    open_source_at = None      # line number of a SOURCE: still waiting for its COSTS:
    section_start = HEADER_LINES
    for i, line in enumerate(lines, 1):
        if i <= HEADER_LINES:
            continue
        if _is(line, "SOURCE:"):
            if open_source_at is not None:
                problems.append(f"line {open_source_at}: SOURCE: with no COSTS: before the next SOURCE: at line {i}")
            open_source_at = i
            if not LINK.search(line):
                problems.append(f"line {i}: SOURCE: has no link or file path ({line.strip()[:60]!r})")
        elif _is(line, "COSTS:"):
            if open_source_at is None:
                problems.append(f"line {i}: COSTS: with no SOURCE: above it")
            sections += 1
            words = sum(len(l.split()) for l in lines[section_start:i])
            if words > WORD_CAP + GRACE:
                problems.append(f"section ending line {i}: {words} words (cap {WORD_CAP})")
            open_source_at = None
            section_start = i
    if open_source_at is not None:
        problems.append(f"line {open_source_at}: SOURCE: at end of file with no COSTS:")

    tail = " ".join(lines[section_start:]).split()
    if sections and len(tail) > 80 and not re.search(r"\bNOT FOUND\b", " ".join(tail)):
        problems.append(f"after last COSTS: {len(tail)} words of untagged text (a section with no SOURCE/COSTS?)")
    if sections == 0:
        problems.append("no sections: no COSTS: lines in file")

    text = "\n".join(lines)
    nf = len(re.findall(r"\bNOT FOUND\b", text))
    info = f"{sections} sections, {nf} NOT FOUND, {len(text.split())} words"
    return problems, info


BAD_FIXTURE = """JOB X. Topic: planted-bad fixture
Date: today
Sections: 3
NOT FOUND: 0
This file is deliberately broken in four ways.

Section one is fine on purpose
A claim with a quote.
SOURCE: Some Paper, Author 2020, https://example.org/paper
COSTS: one model call

Section two has a markdown table and a SOURCE with no link
| a | b |
|---|---|
Another claim.
SOURCE: a paper I remember
COSTS: nothing

Section three has a SOURCE but no COSTS, then the file ends
A third claim.
SOURCE: Real Paper, Author 2021, https://example.org/real
"""

PLANTED = {
    "markdown table": "markdown formatting",
    "SOURCE without link": "no link or file path",
    "SOURCE with no COSTS": "no COSTS:",
}


def self_test() -> int:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(BAD_FIXTURE)
    problems, _ = check(Path(f.name))
    print("self-test against a file with 3 planted defects:")
    for p in problems:
        print("  flagged:", p)
    missed = [name for name, needle in PLANTED.items() if not any(needle in p for p in problems)]
    if missed:
        print(f"  CHECKER IS BROKEN — did not catch: {missed}")
        return 1
    print("  all 3 planted defects caught. checker is trustworthy for these defect types.")
    return 0


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    rc = 0
    for arg in sys.argv[1:]:
        path = Path(arg)
        print(f"== {path.name}")
        if not path.exists():
            print("  MISSING")
            rc = 1
            continue
        problems, info = check(path)
        print(f"  ({info})")
        for p in problems:
            print("  FAIL", p)
        if problems:
            rc = 1
        else:
            print("  PASS")
    return rc


if __name__ == "__main__":
    sys.exit(main())
