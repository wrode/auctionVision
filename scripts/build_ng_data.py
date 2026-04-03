#!/usr/bin/env python3
"""Build the complete Nordiska Galleriet retail data file from console-captured JSON strings.

This reads the NG_DATA lines from a text file and builds the final JSON.
"""
import json
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT = DATA_DIR / "retail_nordiska_galleriet.json"

# All captured NG_DATA entries as raw JSON strings
# Each entry is: {"designer": "...", "count": N, "items": [...]}

raw_entries = []

# We already have BM and String in the existing file — load those
if OUTPUT.exists():
    with open(OUTPUT) as f:
        raw_entries = json.load(f)
    print(f"Loaded {len(raw_entries)} existing pages")


def add_page(designer, items):
    """Add a page if not already present."""
    for entry in raw_entries:
        if entry["designer"] == designer:
            print(f"  Skipping {designer} (already exists)")
            return
    raw_entries.append({"designer": designer, "count": len(items), "items": items})
    print(f"  Added {designer}: {len(items)} items")


# Read remaining pages from stdin (pipe in the JSON lines)
if not sys.stdin.isatty():
    for line in sys.stdin:
        line = line.strip()
        if line.startswith("NG_DATA:"):
            data = json.loads(line[8:])
            add_page(data["designer"], data["items"])
        elif line.startswith("{"):
            try:
                data = json.loads(line)
                if "designer" in data and "items" in data:
                    add_page(data["designer"], data["items"])
            except json.JSONDecodeError:
                pass

with open(OUTPUT, "w") as f:
    json.dump(raw_entries, f, ensure_ascii=False, indent=2)

total_items = sum(p["count"] for p in raw_entries)
print(f"\nSaved {len(raw_entries)} pages, {total_items} total items to {OUTPUT}")
