"""User-facing Fenrir Dots command entry points."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .glass import DEFAULT_OPACITY, reload_hyprland, set_glass
from .rotation import apply_next_wallpaper
from .theme import extract_palette, write_theme
from .wallpaper_library import WallpaperSyncError, build_plan, sync_public_library


def _default_wallpaper_dir() -> Path:
    return Path.home() / "Pictures" / "Wallpapers"


def _state_dir() -> Path:
    return Path.home() / ".local" / "state" / "fenrir" / "wallpaper-sync"


def wallpaper_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fenrir-wallpaper",
        description="Fenrir wallpaper rotation and verified public-library synchronization",
    )
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("next", help="choose and apply the next local wallpaper")
    plan = commands.add_parser("sync-public-plan", help="read-only public-library preflight")
    plan.add_argument("--destination", type=Path, default=_default_wallpaper_dir())
    sync = commands.add_parser("sync-public", help="sync and verify every published public image")
    sync.add_argument("--destination", type=Path, default=_default_wallpaper_dir())
    args = parser.parse_args(argv)

    try:
        if args.action == "next":
            chosen = apply_next_wallpaper(_default_wallpaper_dir())
            print(json.dumps({"wallpaper": str(chosen), "applied": True}))
            return 0
        if args.action == "sync-public-plan":
            result = build_plan(args.destination, _state_dir())
        else:
            result = sync_public_library(args.destination, _state_dir())
        for key in ("_missing", "_registry", "_items"):
            result.pop(key, None)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (WallpaperSyncError, OSError, ValueError, RuntimeError) as exc:
        print(f"fenrir-wallpaper: {exc}", file=sys.stderr)
        return 2


def theme_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fenrir-theme",
        description="derive and apply shared Fimbulwinter tokens from a wallpaper",
    )
    commands = parser.add_subparsers(dest="action", required=True)
    apply = commands.add_parser("apply", help="derive and apply a wallpaper palette")
    apply.add_argument("wallpaper", type=Path)
    apply.add_argument(
        "--output",
        type=Path,
        default=Path.home() / ".config" / "fenrir" / "theme",
    )
    args = parser.parse_args(argv)
    try:
        palette = extract_palette(args.wallpaper)
        output = write_theme(palette, args.output)
        print(json.dumps({
            "theme_directory": str(output),
            "accent": palette["accent"],
            "accent_family": palette["accent_family"],
            "contrast": palette["accent_contrast"],
        }, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(f"fenrir-theme: {exc}", file=sys.stderr)
        return 2


def glass_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fenrir-glass",
        description="enable, disable or inspect Fimbulwinter Glass",
    )
    parser.add_argument("action", choices=("enable", "disable", "status"))
    parser.add_argument("--opacity", type=float, default=DEFAULT_OPACITY)
    args = parser.parse_args(argv)
    path = Path.home() / ".config" / "hypr" / "fenrir-glass.lua"

    if args.action == "status":
        enabled = path.is_file() and "fenrir-glass-default" in path.read_text(encoding="utf-8")
        print(json.dumps({"enabled": enabled, "config": str(path)}))
        return 0

    try:
        set_glass(args.action == "enable", args.opacity)
        reloaded = reload_hyprland()
        print(json.dumps({
            "enabled": args.action == "enable",
            "opacity": args.opacity if args.action == "enable" else 1.0,
            "config": str(path),
            "hyprland_reloaded": reloaded,
        }, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(f"fenrir-glass: {exc}", file=sys.stderr)
        return 2
