"""Recover a list item's shared introduction from its original evidence."""
import re

MARKER = re.compile(r"(?m)^[ \t]*(?:[-–—−•\uf02d\uf0b7]|\d+\))[ \t]+")
NEXT_CLAUSE = re.compile(r"(?m)^[ \t]*\d+(?:\.\d+)*\.[ \t]+")


def scoped_item(text, quote):
    """Return exact introduction and item, for clauses beginning with a list."""
    markers = list(MARKER.finditer(text))
    if not markers:
        return None
    intro = text[:markers[0].start()].strip()
    if not intro.endswith(":") or not intro or len(intro) > 800:
        return None
    matches = []
    boundary = NEXT_CLAUSE.search(text, markers[0].start())
    limit = boundary.start() if boundary else len(text)
    for index, marker in enumerate(markers):
        if marker.start() >= limit:
            break
        end = min(markers[index + 1].start(), limit) if index + 1 < len(markers) else limit
        item = text[marker.start():end].strip()
        if quote in item:
            matches.append(item)
    return (intro, matches[0]) if len(matches) == 1 else None
