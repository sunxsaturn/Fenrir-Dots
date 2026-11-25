#!/usr/bin/env python3
"""Apply Fenrir's preferred monitor mode only when the connector advertises it."""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
import time
import os
import tomllib
from pathlib import Path
from typing import Any

MODE_RE = re.compile(r"(\d+)x(\d+)@([\d.]+)Hz?", re.IGNORECASE)


def query_monitors() -> list[dict[str, Any]]:
    last_error = None
    for _ in range(8):
        try:
            result = subprocess.run(["hyprctl", "-j", "monitors", "all"], capture_output=True, text=True, check=True, timeout=6)
            data = json.loads(result.stdout)
            if isinstance(data, list) and data:
                return data
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
            last_error = exc
        time.sleep(1)
    if last_error:
        raise RuntimeError(f"Hyprland monitor query did not become available: {last_error}")
    return []


def choose_mode(monitor: dict[str, Any], width: int, height: int, refresh: float) -> str | None:
    for raw in monitor.get("availableModes", []):
        match = MODE_RE.fullmatch(str(raw))
        if match and int(match.group(1)) == width and int(match.group(2)) == height:
            if abs(float(match.group(3)) - refresh) <= 0.02:
                return str(raw)
    return None


def apply(preferred_width: int, preferred_height: int, preferred_refresh: float, scale: float) -> list[str]:
    messages = []
    for monitor in query_monitors():
        name = str(monitor.get("name", ""))
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", name):
            continue
        mode = choose_mode(monitor, preferred_width, preferred_height, preferred_refresh)
        if mode is None:
            current = monitor.get("currentMode") or "preferred mode"
            messages.append(f"{name}: {preferred_width}x{preferred_height}@{preferred_refresh:g}Hz not advertised; keeping {current}.")
            continue
        lua_mode = re.sub(r"Hz$", "", mode, flags=re.IGNORECASE)
        expression = f'hl.monitor({{ output = "{name}", mode = "{lua_mode}", position = "auto", scale = {scale:g} }})'
        result = subprocess.run(["hyprctl", "eval", expression], capture_output=True, text=True, check=True, timeout=6)
        messages.append(f"{name}: applied {mode} (scale {scale:g}).")
    return messages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--refresh", type=float)
    parser.add_argument("--scale", type=float)
    args = parser.parse_args()
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    try:
        stored = tomllib.loads((config_home / "fenrir/settings.toml").read_text(encoding="utf-8")).get("display", {})
    except (OSError, tomllib.TOMLDecodeError):
        stored = {}
    width = args.width if args.width is not None else int(stored.get("preferred_width", 2560))
    height = args.height if args.height is not None else int(stored.get("preferred_height", 1440))
    refresh = args.refresh if args.refresh is not None else float(stored.get("preferred_refresh", 155))
    scale = args.scale if args.scale is not None else float(stored.get("scale", 1.0))
    if not (640 <= width <= 16384 and 640 <= height <= 16384 and 30 <= refresh <= 1000 and 0.5 <= scale <= 3.0):
        parser.error("requested monitor values are outside safe limits")
    try:
        messages = apply(width, height, refresh, scale)
        if not messages:
            print("No connected Hyprland outputs were found; current compositor defaults remain unchanged.")
        for message in messages:
            print(message)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"fenrir-monitor: {exc}", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
