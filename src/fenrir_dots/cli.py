"""User-facing Fenrir Dots command entry points."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .glass import DEFAULT_OPACITY, reload_hyprland, set_glass
from .theme import extract_palette, write_theme
from .wallpaper_library import WallpaperSyncError, build_plan, sync_public_library


def _default_wallpaper_dir() -> Path:
    return Path.home() / "Pictures" / "Wallpapers"


def _state_dir() -> Path:
    return Path.home() / ".local" / "state" / "fenrir" / "wallpaper-sync"


def wallpaper_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fenrir-wallpaper")
    sub = parser.add_subparsers(dest="action", required=True)
    plan = sub.add_parser("sync-public-plan")
    plan.add_argument("--destination", type=Path, default=_default_wallpaper_dir())
    sync = sub.add_parser("sync-public")
    sync.add_argument("--destination", type=Path, default=_default_wallpaper_dir())
    args = parser.parse_args(argv)
    try:
        report = (
            build_plan(args.destination, _state_dir())
            if args.action == "sync-public-plan"
            else sync_public_library(args.destination, _state_dir())
        )
        report.pop("_missing", None)
        report.pop("_registry", None)
        print(json.dumps(report, indent=2))
        return 0
    except (WallpaperSyncError, OSError) as exc:
        print(f"fenrir-wallpaper: {exc}", file=sys.stderr)
        return 2


def theme_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fenrir-theme")
    sub = parser.add_subparsers(dest="action", required=True)
    apply = sub.add_parser("apply")
    apply.add_argument("wallpaper", type=Path)
    apply.add_argument("--output", type=Path, default=Path.home() / ".config" / "fenrir" / "theme")
    args = parser.parse_args(argv)
    try:
        palette = extract_palette(args.wallpaper)
        path = write_theme(palette, args.output)
        print(json.dumps({"theme_dir": str(path), "accent": palette["accent"], "family": palette["accent_family"]}))
        return 0
    except (OSError, ValueError) as exc:
        print(f"fenrir-theme: {exc}", file=sys.stderr)
        return 2


def glass_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fenrir-glass")
    parser.add_argument("action", choices=("enable", "disable", "status"))
    parser.add_argument("--opacity", type=float, default=DEFAULT_OPACITY)
    args = parser.parse_args(argv)
    path = Path.home() / ".config" / "hypr" / "fenrir-glass.lua"
    if args.action == "status":
        enabled = path.exists() and "fenrir-glass-default" in path.read_text(encoding="utf-8")
        print(json.dumps({"enabled": enabled, "config": str(path)}))
        return 0
    try:
        set_glass(args.action == "enable", args.opacity)
        reloaded = reload_hyprland()
        print(json.dumps({"enabled": args.action == "enable", "config": str(path), "hyprland_reloaded": reloaded}))
        return 0
    except (OSError, ValueError) as exc:
        print(f"fenrir-glass: {exc}", file=sys.stderr)
        return 2
