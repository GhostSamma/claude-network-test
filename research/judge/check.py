#!/usr/bin/env python3
"""Check a research file against the brief's output rules. Exits 1 on any failure.

Every SOURCE: line must be followed by exactly one COSTS: line before the next
SOURCE: (or end of file). Every SOURCE: must carry a link, a file path, or an
owner/repo + path. No markdown by the author (verbatim-quoted YAML frontmatter
is not the author's markdown). Each section at most 300 words. 5-line header.
A section that is a NOT FOUND list is allowed to have no link.

`check.py --self-test` runs this checker against planted defects it MUST catch
and planted non-defects it MUST NOT flag. Both halves matter: v1 missed a
section with no COSTS line (false negative); v2 flagged quoted YAML and
owner/repo sources (false positives). A checker is tested in both directions.
"""

import re
import sys
import tempfile
from pathlib import Path

LINK = re.compile(
    r"https?://\S+"                                   # a URL
    r"|(?:repo|file):\s*\S+"                          # repo: / file: prefix
    r"|/[\w./-]+\.(?:md|py|txt|json|yaml|yml|qmd|ipynb)"  # absolute file path
    r"|\b[\w.-]+/[\w.-]+\s+[\w./-]+\.(?:md|py|txt|json|yaml|yml|qmd|ipynb|toml|cfg)"  # owner/repo path
    r"|\b[\w.-]+/[\w.-]+\s+(?:README|LICENSE)\b"      # owner/repo README / LICENSE
)
MARKDOWN = re.compile(r"^\s*(#{1,6}\s|\*\s|\|.*\|\s*$|---+\s*$)")
YAML_KEY = re.compile(r"^[\w-]+:\s")
HEADER_LINES = 5
WORD_CAP = 300
GRACE = 30


def _is(line: str, tag: str) -> bool:
    return line.strip().upper().startswith(tag)


def _quoted_frontmatter_lines(lines: list[str]) -> set[int]:
    """Indices of lines that are inside a verbatim-quoted YAML frontmatter block.

    A `---` immediately followed by a `key: value` line opens a block; the next
    `---` closes it; one `#` line directly after the close is part of the quoted
    template. Everything else is the author's own text.
    """
    inside: set[int] = set()
    i = 0
    while i < len(lines):
        if lines[i].strip() == "---" and i + 1 < len(lines) and YAML_KEY.match(lines[i + 1].strip()):
            j = i + 1
            while j < len(lines) and lines[j].strip() != "---":
                j += 1
            inside.update(range(i, min(j + 1, len(lines))))
            if j + 1 < len(lines) and lines[j + 1].lstrip().startswith("#"):
                inside.add(j + 1)
            i = j + 1
        else:
            i += 1
    return inside


def check(path: Path) -> tuple[list[str], str]:
    """Returns (problems, info). Empty problems = pass."""
    problems: list[str] = []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    nonempty = [l for l in lines[:10] if l.strip()]
    if len(nonempty) < HEADER_LINES:
        problems.append(f"header: {len(nonempty)} non-empty lines at top, need {HEADER_LINES}")

    quoted = _quoted_frontmatter_lines(lines)
    for i, line in enumerate(lines):
        if i in quoted:
            continue
        if MARKDOWN.match(line):
            problems.append(f"line {i + 1}: markdown formatting ({line.strip()[:40]!r})")

    sections = 0
    open_source_at = None
    section_start = HEADER_LINES
    for i, line in enumerate(lines, 1):
        if i <= HEADER_LINES:
            continue
        if _is(line, "SOURCE:"):
            if open_source_at is not None:
                problems.append(f"line {open_source_at}: SOURCE: with no COSTS: before the next SOURCE: at line {i}")
            open_source_at = i
            body = "\n".join(lines[section_start:i - 1])
            not_found_list = "NOT FOUND" in line.upper() or len(re.findall(r"\bNOT FOUND\b", body)) >= 3
            if not LINK.search(line) and not not_found_list:
                problems.append(f"line {i}: SOURCE: has no link, path, or owner/repo ({line.strip()[:60]!r})")
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
        problems.append(f"after last COSTS: {len(tail)} words of untagged text")
    if sections == 0:
        problems.append("no sections: no COSTS: lines in file")

    text = "\n".join(lines)
    nf = len(re.findall(r"\bNOT FOUND\b", text))
    return problems, f"{sections} sections, {nf} NOT FOUND, {len(text.split())} words"


BAD_FIXTURE = """JOB X. Topic: planted defects
Date: today
Sections: 3
NOT FOUND: 0
Three things below must be flagged.

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

GOOD_FIXTURE = """JOB Y. Topic: planted non-defects
Date: today
Sections: 3
NOT FOUND: 3
Nothing below may be flagged.

A source in owner/repo plus path form, which the brief allows
Quoted config from the repo.
SOURCE: UKGovernmentBEIS/inspect_ai README.md; docs/custom-scorers.qmd; LICENSE
COSTS: none

A verbatim-quoted SKILL.md template, which contains YAML frontmatter and a # line
Anthropic template, quoted verbatim from anthropics/skills template/SKILL.md:
---
name: template-skill
description: Replace with description.
---
# Insert instructions below
That is the quoted file, not the author's markdown.
SOURCE: anthropics/skills template/SKILL.md
COSTS: none

A NOT FOUND list, which the brief allows to have no link
1) Thing one: NOT FOUND.
2) Thing two: NOT FOUND.
3) Thing three: NOT FOUND.
SOURCE: NOT FOUND items; basis is the fetches cited in sections 1-2.
COSTS: n/a
"""

MUST_CATCH = {
    "markdown table": "markdown formatting",
    "SOURCE without link": "no link",
    "SOURCE with no COSTS": "no COSTS:",
}


def self_test() -> int:
    rc = 0
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(BAD_FIXTURE)
    problems, _ = check(Path(f.name))
    print("1. planted defects (must all be caught):")
    for p in problems:
        print("   flagged:", p)
    missed = [name for name, needle in MUST_CATCH.items() if not any(needle in p for p in problems)]
    if missed:
        print(f"   BROKEN — false negatives, did not catch: {missed}")
        rc = 1
    else:
        print("   all caught.")

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(GOOD_FIXTURE)
    problems, _ = check(Path(f.name))
    print("2. planted non-defects (must NOT be flagged):")
    if problems:
        for p in problems:
            print("   BROKEN — false positive:", p)
        rc = 1
    else:
        print("   nothing flagged.")
    print("checker is", "TRUSTWORTHY for these cases." if rc == 0 else "NOT trustworthy.")
    return rc


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
