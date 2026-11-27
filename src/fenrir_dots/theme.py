"""Wallpaper-derived Fimbulwinter accent palette for Fenrir Dots."""
from __future__ import annotations

import argparse
import colorsys
import json
import os
import tempfile
from pathlib import Path

BASE = "#090b12"
FOREGROUND = "#e8e9f2"
PREFERRED = {"blue", "red", "purple", "violet", "black"}
EXCLUDED = {"yellow", "brown", "orange", "pink"}


def classify_rgb(red: int, green: int, blue: int) -> str:
    if any(type(v) is not int or not 0 <= v <= 255 for v in (red, green, blue)):
        raise ValueError("RGB channels must be integers from 0 through 255")
    hue, saturation, value = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
    degrees = hue * 360
    if value <= 0.16 and saturation <= 0.45:
        return "black"
    if saturation <= 0.14:
        return "white" if value >= 0.88 else "neutral"
    if degrees < 15 or degrees >= 350:
        return "red"
    if degrees < 40:
        return "brown" if value < 0.72 else "orange"
    if degrees < 66:
        return "yellow"
    if degrees < 165:
        return "green"
    if degrees < 250:
        return "blue"
    if degrees < 285:
        return "violet"
    if degrees < 325:
        return "purple"
    return "pink"


def luminance(color: str) -> float:
    channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(first: str, second: str) -> float:
    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def _readable_accent(color: str) -> str:
    """Lighten a wallpaper accent minimally while preserving its hue family."""
    if contrast_ratio(color, BASE) >= 3.0:
        return color.lower()
    channels = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    for step in range(1, 256):
        # Blend toward white; this preserves the original hue better than
        # changing hue or returning white for a low-contrast dark blue.
        candidate_channels = [
            round(value + (255 - value) * step / 255)
            for value in channels
        ]
        candidate = "#" + "".join(f"{value:02x}" for value in candidate_channels)
        if contrast_ratio(candidate, BASE) >= 3.0:
            return candidate
    return "#ffffff"


def dominant_colors(image_path: Path, limit: int = 8) -> list[str]:
    try:
        from PIL import Image
        with Image.open(image_path) as source:
            sample = source.convert("RGB").resize((96, 96))
            quantized = sample.quantize(colors=limit).convert("RGB")
            entries = quantized.getcolors(maxcolors=limit * limit) or []
    except Exception as exc:
        raise ValueError(f"Could not extract wallpaper colors: {exc}") from exc
    entries.sort(key=lambda entry: entry[0], reverse=True)
    return ["#" + "".join(f"{part:02x}" for part in rgb) for _count, rgb in entries]


def choose_accent(colors: list[str]) -> str:
    candidates: list[tuple[int, int, str]] = []
    for index, color in enumerate(colors):
        if len(color) != 7 or color[0] != "#":
            continue
        rgb = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))
        family = classify_rgb(*rgb)
        if family in EXCLUDED:
            continue
        if family in PREFERRED:
            score = 3
        elif family == "green":
            score = 2
        else:
            score = 1
        candidates.append((score, -index, color))
    if not candidates:
        return "#9b87f5"
    selected = max(candidates)[2]
    return _readable_accent(selected)


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    except Exception:
        try:
            os.unlink(name)
        except OSError:
            pass
        raise


def apply_palette(image_path: Path, home: Path | None = None) -> dict:
    home = home or Path.home()
    colors = dominant_colors(image_path)
    accent = choose_accent(colors)
    palette = {
        "schema": "org.fenrir.wallpaper-palette.v1",
        "source": str(image_path),
        "accent": accent,
        "dominant_colors": colors,
        "theme": "fimbulwinter-obsidian",
    }
    config = home / ".config"
    _atomic_text(config / "fenrir/current-palette.json", json.dumps(palette, indent=2) + "\n")
    _atomic_text(config / "kitty/fenrir-palette.conf",
                 f"cursor {accent}\nselection_background {accent}\nselection_foreground #ffffff\n")
    _atomic_text(config / "waybar/fenrir-palette.css",
                 f"@define-color fenrir_accent {accent};\n")
    gtk = (
        f"@define-color fenrir_accent {accent};\n"
        f"*:focus-visible {{ outline-color: {accent}; }}\n"
    )
    _atomic_text(config / "gtk-3.0/fenrir-palette.css", gtk)
    _atomic_text(config / "gtk-4.0/fenrir-palette.css", gtk)
    _atomic_text(config / "hypr/fenrir-palette.conf",
                 f"general {{ col.active_border = rgba({accent[1:]}ff); }}\n")
    _atomic_text(config / "fuzzel/fenrir-palette.ini",
                 f"border={accent}ff\nselection={accent}66\n")
    return palette


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fenrir-theme")
    sub = parser.add_subparsers(dest="command", required=True)
    apply_parser = sub.add_parser("apply", help="derive the accent from a wallpaper")
    apply_parser.add_argument("image", type=Path)
    status = sub.add_parser("status", help="show the last generated wallpaper palette")
    args = parser.parse_args(argv)
    try:
        if args.command == "apply":
            result = apply_palette(args.image.expanduser())
            print(json.dumps(result, indent=2))
        else:
            path = Path.home() / ".config/fenrir/current-palette.json"
            print(path.read_text(encoding="utf-8") if path.exists() else "No wallpaper palette has been generated.")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Fenrir theme error: {exc}", file=__import__("sys").stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
