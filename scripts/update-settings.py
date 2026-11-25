#!/usr/bin/env python3
"""Merge Fenrir-owned wallpaper policy keys while preserving user paths/preferences."""
from __future__ import annotations
import sys
from pathlib import Path

if len(sys.argv) != 3:
    raise SystemExit("usage: update-settings.py TARGET DEFAULTS")
target, defaults = map(Path, sys.argv[1:])
source = defaults.read_text(encoding="utf-8").splitlines()
try:
    existing = target.read_text(encoding="utf-8").splitlines()
except FileNotFoundError:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(defaults.read_text(encoding="utf-8"), encoding="utf-8")
    raise SystemExit(0)

managed = {"interval_minutes", "minimum_count", "minimum_width", "minimum_height", "preferred_width", "preferred_height", "orientation", "extensions"}
section_lines = []
in_wallpaper = False
for line in source:
    if line.strip() == "[wallpaper]":
        in_wallpaper = True
        continue
    if in_wallpaper and line.lstrip().startswith("["):
        break
    if in_wallpaper and "=" in line:
        key = line.split("=", 1)[0].strip()
        if key in managed:
            section_lines.append((key, line))
start = next((i for i,line in enumerate(existing) if line.strip() == "[wallpaper]"), None)
if start is None:
    existing.extend(["", "[wallpaper]"])
    start = len(existing)-1
end = next((i for i in range(start+1, len(existing)) if existing[i].lstrip().startswith("[")), len(existing))
current = {}
for i in range(start+1, end):
    line=existing[i]
    if "=" in line and not line.lstrip().startswith(("#", ";")):
        current[line.split("=",1)[0].strip()] = i
missing=[]
for key, value in section_lines:
    if key in current:
        existing[current[key]] = value
    else:
        missing.append(value)
existing[end:end] = missing
target.write_text("\n".join(existing).rstrip()+"\n", encoding="utf-8")
