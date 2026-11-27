"""Wallpaper-derived Fimbulwinter theme tokens with contrast safeguards."""
from __future__ import annotations

import colorsys
import json
from pathlib import Path

from PIL import Image

PREFERRED = {"blue", "red", "purple", "black", "violet"}
TOLERATED = {"green", "white", "neutral"}
EXCLUDED = {"yellow", "brown", "orange", "pink"}
OBSIDIAN = "#090b12"


def _rgb(value: str) -> tuple[int, int, int]:
    value = value.removeprefix("#")
    if len(value) != 6:
        raise ValueError("Expected a six-digit RGB color")
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))


def classify_rgb(red: int, green: int, blue: int) -> str:
    hue, saturation, value = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
    degrees = hue * 360
    if saturation <= 0.17:
        return "black" if value <= 0.17 else ("white" if value >= 0.88 else "neutral")
    if degrees < 10 or degrees >= 350:
        return "red"
    if degrees < 35:
        return "brown" if value < 0.72 else "orange"
    if degrees < 65:
        return "yellow"
    if degrees < 165:
        return "green"
    if degrees < 245:
        return "blue"
    if degrees < 285:
        return "violet"
    if degrees < 320:
        return "purple"
    return "pink"


def luminance(color: str) -> float:
    channels = []
    for channel in _rgb(color):
        value = channel / 255
        channels.append(value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast(first: str, second: str) -> float:
    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def ensure_contrast(accent: str, background: str = OBSIDIAN, minimum: float = 3.0) -> str:
    if contrast(accent, background) >= minimum:
        return accent.lower()
    red, green, blue = _rgb(accent)
    hue, saturation, original_value = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
    candidates = []
    for step in range(101):
        value = step / 100
        rgb = colorsys.hsv_to_rgb(hue, saturation, value)
        candidate = "#" + "".join(f"{round(channel * 255):02x}" for channel in rgb)
        if contrast(candidate, background) >= minimum:
            candidates.append((abs(value - original_value), candidate))
    return min(candidates)[1] if candidates else "#ffffff"


def extract_palette(image_path: Path | str) -> dict[str, str]:
    """Sample decoded pixels and select a preferred accent, never using the filename."""
    path = Path(image_path)
    with Image.open(path) as source:
        image = source.convert("RGB")
        image.thumbnail((128, 128))
        quantized = image.quantize(colors=32)
        palette = quantized.convert("RGB")
        colors = palette.getcolors(maxcolors=32 * 128 * 128) or []
    totals: dict[str, int] = {}
    candidates: dict[str, list[tuple[int, str]]] = {}
    for count, rgb in colors:
        family = classify_rgb(*rgb)
        totals[family] = totals.get(family, 0) + count
        color = "#" + "".join(f"{channel:02x}" for channel in rgb)
        candidates.setdefault(family, []).append((count, color))
    if not totals:
        raise ValueError("The wallpaper produced no decoded color samples")
    total = sum(totals.values())
    excluded_fraction = sum(totals.get(name, 0) for name in EXCLUDED) / total
    if excluded_fraction > 0.25:
        raise ValueError("Wallpaper palette violates the Fenrir excluded-color policy")
    eligible = PREFERRED | TOLERATED
    family = max(eligible, key=lambda name: (totals.get(name, 0), name in PREFERRED))
    if totals.get(family, 0) == 0:
        raise ValueError("No preferred or tolerated accent color was detected")
    _, accent = max(candidates[family], key=lambda pair: pair[0])
    accent = ensure_contrast(accent)
    muted = "#a8afc4"
    return {
        "background": OBSIDIAN,
        "surface": "#151a28",
        "surface_alt": "#1d2434",
        "foreground": "#edf0fa",
        "muted": muted,
        "accent": accent,
        "accent_soft": accent + "66",
        "border": accent + "88",
        "selection": accent,
        "selection_foreground": "#ffffff" if contrast(accent, "#ffffff") > contrast(accent, "#000000") else "#000000",
        "accent_family": family,
        "accent_contrast": f"{contrast(accent, OBSIDIAN):.2f}",
    }


def write_theme(palette: dict[str, str], output_dir: Path | str) -> Path:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "theme.json").write_text(json.dumps(palette, indent=2) + "\n", encoding="utf-8")
    (output / "waybar.css").write_text(
        f":root {{ --fenrir-bg: {palette['background']}; --fenrir-surface: {palette['surface']}; "
        f"--fenrir-fg: {palette['foreground']}; --fenrir-muted: {palette['muted']}; "
        f"--fenrir-accent: {palette['accent']}; --fenrir-border: {palette['border']}; }}\n",
        encoding="utf-8",
    )
    (output / "gtk.css").write_text(
        f"@define-color fenrir_bg {palette['background']};\n"
        f"@define-color fenrir_surface {palette['surface']};\n"
        f"@define-color fenrir_fg {palette['foreground']};\n"
        f"@define-color fenrir_accent {palette['accent']};\n"
        f"@define-color fenrir_border {palette['border']};\n",
        encoding="utf-8",
    )
    (output / "kitty.conf").write_text(
        f"background {palette['background']}\nforeground {palette['foreground']}\n"
        f"selection_background {palette['accent']}\nselection_foreground {palette['selection_foreground']}\n"
        f"active_border_color {palette['accent']}\ninactive_border_color {palette['border']}\n"
        f"cursor {palette['accent']}\n",
        encoding="utf-8",
    )
    (output / "qt.qss").write_text(
        f"QWidget {{ color: {palette['foreground']}; background-color: {palette['background']}; }}\n"
        f"QPushButton {{ border: 1px solid {palette['border']}; border-radius: 8px; padding: 6px 12px; }}\n"
        f"QPushButton:hover {{ background-color: {palette.get('surface_alt', palette['surface'])}; }}\n",
        encoding="utf-8",
    )
    (output / "mako.conf").write_text(
        f"background-color={palette['surface']}cc\ntext-color={palette['foreground']}\n"
        f"border-color={palette['border']}\n",
        encoding="utf-8",
    )
    (output / "fuzzel.ini").write_text(
        "[colors]\n"
        f"background={palette['background'][1:]}cc\ntext={palette['foreground'][1:]}ff\n"
        f"match={palette['accent'][1:]}ff\nselection={palette['accent_soft'][1:]}ff\n"
        f"selection-text={palette['selection_foreground'][1:]}ff\n"
        f"border={palette['border'][1:]}aa\n",
        encoding="utf-8",
    )

    # Propagate the same generated tokens to each supported application.
    home = Path.home()
    destinations = {
        "waybar.css": home / ".config/waybar/fenrir-theme.css",
        "gtk.css": home / ".config/gtk-3.0/fenrir-theme.css",
    }
    for source_name, destination in destinations.items():
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + ".tmp")
        temporary.write_bytes((output / source_name).read_bytes())
        temporary.replace(destination)

    gtk4 = home / ".config/gtk-4.0"
    gtk4.mkdir(parents=True, exist_ok=True)
    (gtk4 / "fenrir-theme.css").write_bytes((output / "gtk.css").read_bytes())

    for source_name, relative in (
        ("kitty.conf", ".config/kitty/fenrir-theme.conf"),
        ("mako.conf", ".config/mako/fenrir-theme.conf"),
        ("fuzzel.ini", ".config/fuzzel/fenrir-theme.ini"),
    ):
        destination = home / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + ".tmp")
        temporary.write_bytes((output / source_name).read_bytes())
        temporary.replace(destination)
    return output
