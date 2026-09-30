"""Parse uiautomator XML into something you can search."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from xml.etree import ElementTree

_BOUNDS_RE = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")


@dataclass(frozen=True)
class Node:
    """One element in the on-screen view hierarchy."""

    class_name: str = ""
    text: str = ""
    resource_id: str = ""
    content_desc: str = ""
    package: str = ""
    bounds: tuple[int, int, int, int] = (0, 0, 0, 0)
    clickable: bool = False
    enabled: bool = True
    checked: bool = False
    scrollable: bool = False
    depth: int = 0

    @property
    def center(self) -> tuple[int, int]:
        x1, y1, x2, y2 = self.bounds
        return (x1 + x2) // 2, (y1 + y2) // 2

    @property
    def width(self) -> int:
        return self.bounds[2] - self.bounds[0]

    @property
    def height(self) -> int:
        return self.bounds[3] - self.bounds[1]

    @property
    def area(self) -> int:
        return max(0, self.width) * max(0, self.height)

    @property
    def label(self) -> str:
        """Whatever a human would call this element."""
        return self.text or self.content_desc or self.resource_id.rpartition("/")[2]

    def __str__(self) -> str:
        bits = [self.class_name.rpartition(".")[2] or "?"]
        if self.text:
            bits.append(f"text={self.text!r}")
        if self.content_desc:
            bits.append(f"desc={self.content_desc!r}")
        if self.resource_id:
            bits.append(f"id={self.resource_id}")
        if self.clickable:
            bits.append("clickable")
        return f"{' '.join(bits)} @{self.center}"


def parse_bounds(raw: str) -> tuple[int, int, int, int]:
    match = _BOUNDS_RE.search(raw or "")
    if not match:
        return (0, 0, 0, 0)
    return tuple(int(g) for g in match.groups())  # type: ignore[return-value]


def parse(xml: str) -> list[Node]:
    """Flatten a uiautomator dump into a depth-ordered list of nodes."""
    root = ElementTree.fromstring(xml)
    nodes: list[Node] = []

    def walk(element, depth: int) -> None:
        if element.tag == "node":
            attrs = element.attrib
            nodes.append(
                Node(
                    class_name=attrs.get("class", ""),
                    text=attrs.get("text", ""),
                    resource_id=attrs.get("resource-id", ""),
                    content_desc=attrs.get("content-desc", ""),
                    package=attrs.get("package", ""),
                    bounds=parse_bounds(attrs.get("bounds", "")),
                    clickable=attrs.get("clickable") == "true",
                    enabled=attrs.get("enabled") != "false",
                    checked=attrs.get("checked") == "true",
                    scrollable=attrs.get("scrollable") == "true",
                    depth=depth,
                )
            )
        for child in element:
            walk(child, depth + 1)

    walk(root, 0)
    return nodes


@dataclass
class Selector:
    """Criteria for locating a node. Every field set must match."""

    text: str | None = None
    text_contains: str | None = None
    resource_id: str | None = None
    id_endswith: str | None = None
    desc: str | None = None
    desc_contains: str | None = None
    class_name: str | None = None
    package: str | None = None
    clickable: bool | None = None
    enabled: bool | None = None
    checked: bool | None = None
    ignore_case: bool = True

    def _eq(self, actual: str, expected: str) -> bool:
        return actual.casefold() == expected.casefold() if self.ignore_case else actual == expected

    def _in(self, needle: str, haystack: str) -> bool:
        if self.ignore_case:
            return needle.casefold() in haystack.casefold()
        return needle in haystack

    def matches(self, node: Node) -> bool:
        checks = (
            (self.text is None or self._eq(node.text, self.text)),
            (self.text_contains is None or self._in(self.text_contains, node.text)),
            (self.resource_id is None or self._eq(node.resource_id, self.resource_id)),
            (self.id_endswith is None or node.resource_id.endswith(self.id_endswith)),
            (self.desc is None or self._eq(node.content_desc, self.desc)),
            (self.desc_contains is None or self._in(self.desc_contains, node.content_desc)),
            (self.class_name is None or self._in(self.class_name, node.class_name)),
            (self.package is None or self._eq(node.package, self.package)),
            (self.clickable is None or node.clickable == self.clickable),
            (self.enabled is None or node.enabled == self.enabled),
            (self.checked is None or node.checked == self.checked),
        )
        return all(checks)

    def describe(self) -> str:
        set_fields = {
            name: value
            for name, value in vars(self).items()
            if value is not None and name != "ignore_case"
        }
        return ", ".join(f"{k}={v!r}" for k, v in set_fields.items()) or "<any node>"


def find_all(nodes: list[Node], selector: Selector) -> list[Node]:
    return [n for n in nodes if selector.matches(n)]


def find(nodes: list[Node], selector: Selector) -> Node | None:
    """First match, preferring the smallest -- innermost elements are the real target."""
    matches = find_all(nodes, selector)
    if not matches:
        return None
    return min(matches, key=lambda n: (n.area if n.area else 1 << 30, -n.depth))


def find_tappable(nodes: list[Node], selector: Selector) -> Node | None:
    """Find a match, walking outward to a clickable ancestor if needed.

    Labels are often non-clickable TextViews inside a clickable row, so tapping
    the text's own centre still works -- but only if the row actually covers it.
    """
    target = find(nodes, selector)
    if target is None:
        return None
    if target.clickable:
        return target
    cx, cy = target.center
    containers = [
        n
        for n in nodes
        if n.clickable
        and n.bounds[0] <= cx <= n.bounds[2]
        and n.bounds[1] <= cy <= n.bounds[3]
    ]
    if not containers:
        return target
    return min(containers, key=lambda n: n.area if n.area else 1 << 30)


def summarize(nodes: list[Node], *, only_interesting: bool = True, limit: int = 60) -> str:
    """A compact, readable rendering of the screen -- handy for logs."""
    rows = [
        n
        for n in nodes
        if not only_interesting or n.text or n.content_desc or n.clickable
    ]
    lines = [f"  {'  ' * min(n.depth, 8)}{n}" for n in rows[:limit]]
    if len(rows) > limit:
        lines.append(f"  ... and {len(rows) - limit} more")
    return "\n".join(lines) or "  <nothing labelled on screen>"
