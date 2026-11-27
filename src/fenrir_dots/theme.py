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
    preferred_present = [name for name in PREFERRED if totals.get(name, 0) > 0]
    eligible = preferred_present or [name for name in TOLERATED if totals.get(name, 0) > 0]
    if not eligible:
        raise ValueError("No preferred or tolerated accent color was detected")
    # A preferred hue must beat even a larger green/neutral area; tolerated
    # colors are fallbacks only when the image has no preferred hue at all.
    family = max(eligible, key=lambda name: (totals.get(name, 0), name))
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
    """Write a single palette and propagate it without replacing unrelated user settings."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "theme.json").write_text(json.dumps(palette, indent=2) + "\\n", encoding="utf-8")

    bg, surface = palette["background"], palette["surface"]
    fg, muted, accent = palette["foreground"], palette["muted"], palette["accent"]
    border = palette["border"]
    accent_soft = palette.get("accent_soft", accent + "66")
    accent_fg = palette.get("accent_foreground", "#ffffff")
    selection_fg = palette["selection_foreground"]

    (output / "waybar.css").write_text(
        f"window#waybar {{ background: {bg}cc; color: {fg}; border-bottom: 1px solid {border}; }}\\n"
        f"#workspaces, #window, #clock, #network, #wireplumber, #battery, #tray {{ "
        f"background: {surface}cc; color: {fg}; border-color: {border}; }}\\n"
        f"#workspaces button.active {{ color: {accent}; }}\\n"
        f"#workspaces button:hover {{ background: {accent_soft}; color: {accent_fg}; }}\\n",
        encoding="utf-8",
    )
    (output / "gtk.css").write_text(
        f"@define-color fenrir_bg {bg};\\n"
        f"@define-color fenrir_surface {surface};\\n"
        f"@define-color fenrir_fg {fg};\\n"
        f"@define-color fenrir_muted {muted};\\n"
        f"@define-color fenrir_accent {accent};\\n"
        f"@define-color fenrir_border {border};\\n"
        "window, dialog { background-color: @fenrir_bg; color: @fenrir_fg; }\\n"
        "headerbar, .background, popover, menu { background-color: @fenrir_surface; color: @fenrir_fg; }\\n"
        "button { background-color: @fenrir_surface; color: @fenrir_fg; border: 1px solid @fenrir_border; }\\n"
        "button:hover, button:checked { background-color: @fenrir_accent; color: #ffffff; }\\n"
        "entry, textview, list, row { background-color: @fenrir_surface; color: @fenrir_fg; }\\n",
        encoding="utf-8",
    )
    (output / "kitty.conf").write_text(
        f"background {bg}\\nforeground {fg}\\n"
        f"selection_background {accent}\\nselection_foreground {selection_fg}\\n"
        f"active_border_color {accent}\\ninactive_border_color {border}\\n"
        f"cursor {accent}\\n",
        encoding="utf-8",
    )
    (output / "qt.qss").write_text(
        f"QWidget {{ color: {fg}; background-color: {bg}; }}\\n"
        f"QPushButton {{ border: 1px solid {border}; border-radius: 8px; padding: 6px 12px; }}\\n"
        f"QPushButton:hover {{ background-color: {palette.get('surface_alt', surface)}; }}\\n",
        encoding="utf-8",
    )

    # Qt6ct reads QPalette roles in the exact Qt enum order. Keep all 22
    # active/inactive/disabled roles in sync with the wallpaper-derived accent.
    def argb(value: str) -> str:
        value = value.lower()
        return value if len(value) == 9 else "#ff" + value.removeprefix("#")

    active_roles = [
        fg, surface, "#35415b", "#2a344b", "#080b12", "#202a3e",
        fg, "#ffffff", fg, bg, bg, "#03050a",
        accent, selection_fg, "#69b9ed", accent, palette.get("surface_alt", surface),
        bg, surface, fg, muted, accent,
    ]
    inactive_roles = [
        muted, surface, "#303a50", "#252e43", "#080a10", "#1d2638",
        fg, "#ffffff", fg, bg, bg, "#03050a",
        accent, selection_fg, "#69b9ed", accent, palette.get("surface_alt", surface),
        bg, surface, fg, muted, accent,
    ]
    disabled_roles = [
        muted, "#171c29", "#252b39", "#1d2432", "#080a10", "#151b27",
        muted, muted, muted, "#0d1018", "#0d1018", "#03050a",
        "#414a60", "#a0a8ba", "#52617c", "#505b72", "#141a26",
        "#0d1018", "#171c29", muted, "#737d93", "#414a60",
    ]
    qt_colors = "[ColorScheme]\\n"
    qt_colors += "active_colors=" + ",".join(argb(value) for value in active_roles) + "\\n"
    qt_colors += "inactive_colors=" + ",".join(argb(value) for value in inactive_roles) + "\\n"
    qt_colors += "disabled_colors=" + ",".join(argb(value) for value in disabled_roles) + "\\n"
    (output / "qt6ct-colors.conf").write_text(qt_colors, encoding="utf-8")

    starship = (
        'format = "$directory$git_branch$git_status$python$cmd_duration$line_break$character"\\n'
        "add_newline = true\\n"
        f'[directory]\\nstyle = "bold {accent}"\\ntruncation_length = 3\\n'
        f'[git_branch]\\nstyle = "bold {accent}"\\n'
        f'[git_status]\\nstyle = "bold {accent}"\\n'
        f'[python]\\nstyle = "bold {accent}"\\n'
        f'[cmd_duration]\\nstyle = "dimmed {muted}"\\n'
        f'[character]\\nsuccess_symbol = "[❯](bold {accent})"\\n'
        'error_symbol = "[❯](bold #ff607a)"\\n'
    )
    (output / "starship.toml").write_text(starship, encoding="utf-8")

    (output / "mako.conf").write_text(
        f"background-color={surface}cc\\ntext-color={fg}\\nborder-color={border}\\n",
        encoding="utf-8",
    )
    (output / "fuzzel.ini").write_text(
        "[colors]\\n"
        f"background={bg[1:]}cc\\ntext={fg[1:]}ff\\n"
        f"match={accent[1:]}ff\\nselection={accent_soft[1:]}\\n"
        f"selection-text={selection_fg[1:]}ff\\nborder={accent[1:]}aa\\n",
        encoding="utf-8",
    )

    home = Path.home()
    default_output = home / ".config" / "fenrir" / "theme"
    if output.resolve() != default_output.resolve():
        return output

    def atomic_write(destination: Path, content: str) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + ".fenrir-tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(destination)

    def replace_keys(path: Path, updates: dict[str, str], section: str | None = None) -> None:
        """Update only selected config keys while preserving unrelated settings."""
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        target_start, target_end = 0, len(lines)
        if section:
            header = f"[{section}]"
            try:
                target_start = lines.index(header) + 1
                target_end = next(
                    (index for index in range(target_start, len(lines))
                     if lines[index].strip().startswith("[") and lines[index].strip().endswith("]")),
                    len(lines),
                )
            except ValueError:
                if lines and lines[-1].strip():
                    lines.append("")
                lines.append(header)
                target_start = len(lines)
                target_end = len(lines)
        found = set()
        for index in range(target_start, target_end):
            stripped = lines[index].strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                lines[index] = f"{key}={updates[key]}"
                found.add(key)
        missing = [f"{key}={value}" for key, value in updates.items() if key not in found]
        lines[target_end:target_end] = missing
        atomic_write(path, "\\n".join(lines).rstrip() + "\\n")

    # Waybar and GTK consume a generated stylesheet via stable import files.
    atomic_write(home / ".config/waybar/fenrir-theme.css", (output / "waybar.css").read_text())
    atomic_write(home / ".config/gtk-3.0/fenrir-theme.css", (output / "gtk.css").read_text())
    atomic_write(home / ".config/gtk-4.0/fenrir-theme.css", (output / "gtk.css").read_text())

    # Kitty, Mako and Fuzzel configs are adjusted in-place only for color keys.
    atomic_write(home / ".config/kitty/fenrir-theme.conf", (output / "kitty.conf").read_text())
    replace_keys(home / ".config/kitty/kitty.conf", {
        "background": bg, "foreground": fg, "selection_background": accent,
        "selection_foreground": selection_fg, "active_border_color": accent,
        "inactive_border_color": border, "cursor": accent,
    })
    replace_keys(home / ".config/mako/config", {
        "background-color": surface + "cc", "text-color": fg, "border-color": border,
    })
    replace_keys(home / ".config/fuzzel/fuzzel.ini", {
        "background": bg[1:] + "cc", "text": fg[1:] + "ff", "match": accent[1:] + "ff",
        "selection": accent_soft[1:], "selection-text": selection_fg[1:] + "ff",
        "border": accent[1:] + "aa",
    }, section="colors")

    qt_config = home / ".config/qt6ct/qt6ct.conf"
    replace_keys(qt_config, {
        "custom_palette": "true",
        "color_scheme_path": str(output / "qt6ct-colors.conf"),
        "style": "Fusion",
    }, section="Appearance")

    hyprland_theme = (
        "-- Generated by fenrir-theme from the active wallpaper.\\n"
        "hl.config({ general = { col = { active_border = \"rgba("
        + accent[1:] + "ff) rgba(" + accent[1:] + "88) 45deg\", "
        + "inactive_border = \"rgba(" + border[1:] + ")\", } } })\\n"
    )
    atomic_write(home / ".config/hypr/fenrir-theme.lua", hyprland_theme)
    return output
