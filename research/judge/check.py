#!/usr/bin/env python3
"""Check a research file against a brief's output rules. Exits 1 on any failure.

Usage:
  check.py FILE...                              # default trailers: SOURCE: then COSTS:
  check.py --require "SOURCE:,SEPARATED FROM TOPIC?" FILE...
  check.py --self-test                          # both trailer sets, both directions

Rules: every section ends with the LAST required tag; the FIRST required tag
(SOURCE:) must appear exactly once before it and carry a link, file path, or
owner/repo + path (a NOT FOUND list section is exempt from the link rule);
any middle tags must appear once per section; no author markdown (verbatim-
quoted YAML frontmatter is exempt); 300 words per section; 5-line header.

History: v1 missed a section with no trailer (false negative). v2 flagged
owner/repo sources and quoted YAML (false positives). v3 let an unclosed
quoted block swallow the next one. v4 fixed that. v5 makes the trailer tags
a parameter so one checker serves briefs with different closing lines.
The self-test runs planted defects (must catch) and planted non-defects
(must not flag) for every trailer set. A checker is tested both ways.
"""

import argparse
import re
import sys
import tempfile
from pathlib import Path

LINK = re.compile(
    r"https?://\S+"
    r"|(?:repo|file|dataset):\s*\S+"
    r"|/[\w./-]+\.(?:md|py|txt|json|yaml|yml|qmd|ipynb|csv)"
    r"|\b[\w.-]+/[\w.-]+\s+[\w./-]+\.(?:md|py|txt|json|yaml|yml|qmd|ipynb|toml|cfg|csv)"
    r"|\b[\w.-]+/[\w.-]+\s+(?:README|LICENSE)\b"
)
MARKDOWN = re.compile(r"^\s*(#{1,6}\s|\*\s|\|.*\|\s*$|---+\s*$)")
YAML_KEY = re.compile(r"^[\w-]+:\s")
HEADER_LINES = 5
WORD_CAP = 300
GRACE = 30
DEFAULT_REQUIRE = ["SOURCE:", "COSTS:"]


def _is(line: str, tag: str) -> bool:
    return line.strip().upper().startswith(tag.upper())


def _quoted_frontmatter_lines(lines: list[str]) -> set[int]:
    """Line indices inside a verbatim-quoted YAML frontmatter block.

    `---` followed by `key: value` opens a block. It ends at the closing `---`
    OR at the first blank line (an agent may quote only the opener) — never
    past a blank line, or an unclosed block swallows the next block's opener.
    One `#` line directly after a closing `---` belongs to the quoted template.
    """
    inside: set[int] = set()
    i = 0
    while i < len(lines):
        if lines[i].strip() == "---" and i + 1 < len(lines) and YAML_KEY.match(lines[i + 1].strip()):
            j = i + 1
            while j < len(lines) and lines[j].strip() not in ("---", ""):
                j += 1
            closed = j < len(lines) and lines[j].strip() == "---"
            inside.update(range(i, min(j + 1, len(lines)) if closed else j))
            if closed and j + 1 < len(lines) and lines[j + 1].lstrip().startswith("#"):
                inside.add(j + 1)
            i = j + 1
        else:
            i += 1
    return inside


def check(path: Path, require: list[str] = DEFAULT_REQUIRE) -> tuple[list[str], str]:
    """Returns (problems, info). Empty problems = pass."""
    source_tag, terminator, middle = require[0], require[-1], require[1:-1]
    problems: list[str] = []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    nonempty = [l for l in lines[:10] if l.strip()]
    if len(nonempty) < HEADER_LINES:
        problems.append(f"header: {len(nonempty)} non-empty lines at top, need {HEADER_LINES}")

    quoted = _quoted_frontmatter_lines(lines)
    for i, line in enumerate(lines):
        if i not in quoted and MARKDOWN.match(line):
            problems.append(f"line {i + 1}: markdown formatting ({line.strip()[:40]!r})")

    sections = 0
    open_source_at = None
    seen_middle: dict[str, int] = {}
    section_start = HEADER_LINES
    for i, line in enumerate(lines, 1):
        if i <= HEADER_LINES:
            continue
        if _is(line, source_tag):
            if open_source_at is not None:
                problems.append(f"line {open_source_at}: {source_tag} with no {terminator} before the next {source_tag} at line {i}")
            open_source_at = i
            seen_middle = {}
            body = "\n".join(lines[section_start:i - 1])
            not_found_list = "NOT FOUND" in line.upper() or len(re.findall(r"\bNOT FOUND\b", body)) >= 3
            if not LINK.search(line) and not not_found_list:
                problems.append(f"line {i}: {source_tag} has no link, path, or owner/repo ({line.strip()[:60]!r})")
        elif any(_is(line, m) for m in middle):
            tag = next(m for m in middle if _is(line, m))
            seen_middle[tag] = seen_middle.get(tag, 0) + 1
        elif _is(line, terminator):
            if open_source_at is None:
                problems.append(f"line {i}: {terminator} with no {source_tag} above it")
            for m in middle:
                if seen_middle.get(m, 0) != 1:
                    problems.append(f"section ending line {i}: {m} appears {seen_middle.get(m, 0)} times, need 1")
            if not line.split(":", 1)[-1].strip():
                problems.append(f"line {i}: {terminator} is empty")
            sections += 1
            words = sum(len(l.split()) for l in lines[section_start:i])
            if words > WORD_CAP + GRACE:
                problems.append(f"section ending line {i}: {words} words (cap {WORD_CAP})")
            open_source_at = None
            seen_middle = {}
            section_start = i
    if open_source_at is not None:
        problems.append(f"line {open_source_at}: {source_tag} at end of file with no {terminator}")

    tail = " ".join(lines[section_start:]).split()
    if sections and len(tail) > 80 and not re.search(r"\bNOT FOUND\b", " ".join(tail)):
        problems.append(f"after last {terminator}: {len(tail)} words of untagged text")
    if sections == 0:
        problems.append(f"no sections: no {terminator} lines in file")

    text = "\n".join(lines)
    nf = len(re.findall(r"\bNOT FOUND\b", text))
    return problems, f"{sections} sections, {nf} NOT FOUND, {len(text.split())} words"


# ----- self-test fixtures -------------------------------------------------

def _bad(term: str) -> str:
    return f"""JOB X. Topic: planted defects
Date: today
Sections: 3
NOT FOUND: 0
Three things below must be flagged.

Section one is fine on purpose
A claim with a quote.
SOURCE: Some Paper, Author 2020, https://example.org/paper
{term} yes - same content, different presentation

Section two has a markdown table and a SOURCE with no link
| a | b |
|---|---|
Another claim.
SOURCE: a paper I remember
{term} no

Section three has a SOURCE but no closing line, then the file ends
A third claim.
SOURCE: Real Paper, Author 2021, https://example.org/real
"""


def _good(term: str) -> str:
    return f"""JOB Y. Topic: planted non-defects
Date: today
Sections: 4
NOT FOUND: 3
Nothing below may be flagged.

A source in owner/repo plus path form
Quoted config from the repo.
SOURCE: UKGovernmentBEIS/inspect_ai README.md; docs/custom-scorers.qmd
{term} partly - the repo tests the scorer, not the topic

An unclosed quoted frontmatter then a closed one with a # line after it
Letta MemFS, quoted from docs:
---
name: persona
description: the agent persona block

That blank line ended the quote. A second, closed block:
---
name: second
---
# quoted template line
SOURCE: letta-ai/letta README.md
{term} no

A dataset source
Rows quoted from the dataset card.
SOURCE: dataset: https://huggingface.co/datasets/example/shorts
{term} yes - same clip, two titles

A NOT FOUND list, which may have no link
1) Thing one: NOT FOUND.
2) Thing two: NOT FOUND.
3) Thing three: NOT FOUND.
SOURCE: NOT FOUND items; basis is the fetches cited above.
{term} n/a
"""


MUST_CATCH = {
    "markdown table": "markdown formatting",
    "SOURCE without link": "no link",
    "SOURCE with no closing line": "no ",  # "...with no COSTS:" / "...with no SEPARATED FROM TOPIC?"
}


def self_test() -> int:
    rc = 0
    for require in (DEFAULT_REQUIRE, ["SOURCE:", "SEPARATED FROM TOPIC?"]):
        term = require[-1]
        print(f"trailer set: {require}")
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write(_bad(term))
        problems, _ = check(Path(f.name), require)
        missed = [n for n, needle in MUST_CATCH.items() if not any(needle in p for p in problems)]
        print(f"  planted defects: {len(problems)} flagged;", "all caught." if not missed else f"BROKEN — missed {missed}")
        rc |= bool(missed)
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write(_good(term))
        problems, _ = check(Path(f.name), require)
        print("  planted non-defects:", "nothing flagged." if not problems else f"BROKEN — false positives: {problems}")
        rc |= bool(problems)
    print("checker is", "TRUSTWORTHY for these cases." if rc == 0 else "NOT trustworthy.")
    return rc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--require", default=",".join(DEFAULT_REQUIRE), help="comma-separated required trailer tags, in order")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    require = [t.strip() for t in args.require.split(",") if t.strip()]
    rc = 0
    for arg in args.files:
        path = Path(arg)
        print(f"== {path.name}")
        if not path.exists():
            print("  MISSING")
            rc = 1
            continue
        problems, info = check(path, require)
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
