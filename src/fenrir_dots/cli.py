"""User-facing Fenrir Dots command entry points."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .glass import DEFAULT_OPACITY, reload_hyprland, set_glass
from .theme import extract_palette, write_theme
from .wallpaper_library import WallpaperSyncError, build_plan, sync_public_library
from .rotation import apply_next_wallpaper


def _default_wallpaper_dir() -> Path:
    return Path.home() / "Pictures" / "Wallpapers"


def _state_dir() -> Path:
    return Path.home() / ".local" / "state" / "fenrir" / "wallpaper-sync"


def wallpaper_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fenrir-wallpaper")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("next", help="choose and apply the next local wallpaper")
    plan = sub.add_parser("sync-public-plan")
    plan.add_argument("--destination", type=Path, default=_default_wallpaper_dir())
    sync = sub.add_parser("sync-public")
    sync.add_argument("--destination", type=Path, default=_default_wallpaper_dir())
    args = parser.parse_args(argv)
    try:
        if args.action == "next":
            chosen = apply_next_wallpaper(_default_wallpaper_dir())
            print(json.dumps({"wallpaper": str(chosen), "applied": True}))
            return 0
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


# Stable installer/Doctor contract: read-only plan followed by a full verified sync.
def wallpaper_main() -> int:
    import argparse
    import json
    from pathlib import Path
    from .wallpaper_library import build_plan, sync_public_library
    from .rotation import apply_next_wallpaper

    destination = Path.home() / "Pictures" / "Wallpapers"
    state_dir = Path.home() / ".local" / "state" / "fenrir" / "wallpaper-sync"
    parser = argparse.ArgumentParser(prog="fenrir-wallpaper", description="Fenrir wallpaper rotation and public library")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("next", help="apply the next locally installed wallpaper")
    plan = commands.add_parser("sync-public-plan", aliases=["audit-library"], help="read-only inventory and storage preflight")
    plan.add_argument("--json", action="store_true")
    sync = commands.add_parser("sync-public", help="download and verify every image in the published 5000-image gallery")
    sync.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.command == "next":
        selected = apply_next_wallpaper(destination)
        print(str(selected))
        return 0

    if args.command in {"sync-public-plan", "audit-library"}:
        result = build_plan(destination, state_dir)
        for key in ("_missing", "_registry", "_items"):
            result.pop(key, None)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    result = sync_public_library(destination, state_dir)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def theme_main() -> int:
    import argparse
    import json
    from pathlib import Path
    from .theme import extract_palette, write_theme

    parser = argparse.ArgumentParser(prog="fenrir-theme", description="derive the shared Fimbulwinter palette from a wallpaper")
    parser.add_argument("image", type=Path)
    args = parser.parse_args()
    palette = extract_palette(args.image)
    output = write_theme(palette, Path.home() / ".config" / "fenrir" / "theme")
    print(json.dumps({"palette": palette, "theme_directory": str(output)}, indent=2))
    return 0


def glass_main() -> int:
    import argparse
    from .glass import set_glass, reload_hyprland

    parser = argparse.ArgumentParser(prog="fenrir-glass", description="toggle Fimbulwinter Glass")
    parser.add_argument("action", choices=("enable", "disable", "status"))
    args = parser.parse_args()
    if args.action == "status":
        from pathlib import Path
        state = Path.home() / ".config" / "hypr" / "fenrir-glass.lua"
        print("enabled" if state.is_file() and "active_opacity = 0.80" in state.read_text(encoding="utf-8") else "disabled")
        return 0
    set_glass(args.action == "enable", 0.80)
    reload_hyprland()
    print("Fimbulwinter Glass " + ("enabled at 80%" if args.action == "enable" else "disabled"))
    return 0
