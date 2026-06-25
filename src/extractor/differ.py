"""Line-by-line content diffing for change detection."""
from __future__ import annotations

import difflib


def diff_content(old: str, new: str) -> dict:
    """
    Compare two markdown strings line by line.

    Returns:
        {"changed": bool, "added": list[str], "removed": list[str]}
    """
    old_lines = old.splitlines()
    new_lines = new.splitlines()

    added: list[str] = []
    removed: list[str] = []

    for line in difflib.unified_diff(old_lines, new_lines, lineterm=""):
        if line.startswith("+") and not line.startswith("+++"):
            added.append(line[1:])
        elif line.startswith("-") and not line.startswith("---"):
            removed.append(line[1:])

    return {
        "changed": bool(added or removed),
        "added": added,
        "removed": removed,
    }
