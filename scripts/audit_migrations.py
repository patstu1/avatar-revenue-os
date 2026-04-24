"""Audit Alembic migration chain — find roots, tips, duplicates, and trace chains."""

import os
import re

VERSIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "packages", "db", "alembic", "versions")

revs = {}
for f in os.listdir(VERSIONS_DIR):
    if not f.endswith(".py") or f.startswith("__"):
        continue
    path = os.path.join(VERSIONS_DIR, f)
    content = open(path).read()

    rev_m = re.search(r'revision[:\s=str]*["\']([^"\']+)["\']', content)
    if not rev_m:
        continue
    rev = rev_m.group(1)

    down = None
    tuple_m = re.search(r"down_revision\s*=\s*\(([^)]+)\)", content)
    if tuple_m:
        down = "MERGE:" + tuple_m.group(1).strip()
    elif "down_revision" in content:
        line = [l for l in content.split("\n") if "down_revision" in l][0]
        if "None" in line:
            down = None
        else:
            dm = re.search(r'["\']([^"\']+)["\']', line.split("down_revision")[1])
            if dm:
                down = dm.group(1)

    revs[rev] = {"down": down, "file": f}

# Find roots and tips
roots = [r for r, v in revs.items() if v["down"] is None]
all_downs = set()
for v in revs.values():
    d = v["down"]
    if d and not d.startswith("MERGE"):
        all_downs.add(d)
tips = [r for r in revs if r not in all_downs]

print(f"Total migrations: {len(revs)}")
print(f"\nRoots ({len(roots)}):")
for r in sorted(roots):
    print(f"  {r} -> {revs[r]['file']}")
print(f"\nTips/Heads ({len(tips)}):")
for t in sorted(tips):
    print(f"  {t} -> {revs[t]['file']}")

# Duplicates
from collections import Counter

rev_ids = [r for r in revs]
dupes = [r for r, c in Counter(rev_ids).items() if c > 1]
if dupes:
    print(f"\nDUPLICATE REVISION IDS: {dupes}")

# Trace from main root
fwd = {}
for r, v in revs.items():
    d = v["down"]
    if d and not d.startswith("MERGE"):
        fwd.setdefault(d, []).append(r)

print("\n=== CHAIN from 364023ff491f ===")


def trace(start, depth=0, visited=None):
    if visited is None:
        visited = set()
    if start in visited:
        return
    visited.add(start)
    info = revs.get(start, {})
    print(f"{'  ' * depth}{start} ({info.get('file', '?')})")
    for nxt in fwd.get(start, []):
        trace(nxt, depth + 1, visited)


if "364023ff491f" in revs:
    trace("364023ff491f")
