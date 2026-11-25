#!/usr/bin/env python3
"""Validated, atomic settings storage and runtime configuration for Fenrir."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import tomllib
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, dict[str, Any]] = {
    "wallpaper": {
        "directory": "~/Pictures/Wallpapers",
        "interval_minutes": 15,
        "minimum_count": 5000,
        "minimum_width": 2560,
        "minimum_height": 1440,
        "preferred_width": 3840,
        "preferred_height": 2160,
    },
    "theme": {"surface_opacity": 0.60, "dynamic_colors": True, "blur_enabled": True, "blur_size": 6},
    "monitor": {"target_width": 2560, "target_height": 1440, "target_refresh": 155.0, "scale": 1.0},
    "hyprland": {"gaps_inner": 5, "gaps_outer": 12, "border_size": 2, "layout": "dwindle"},
    "session": {"allow_screen_off": False, "auto_lock": False, "auto_suspend": False},
    "keyboard": {"layout": "us", "variant": "intl"},
    "waybar": {"enabled": True, "layout": "default"},
    "gaming": {"mangohud": True, "gamemode_hint": True},
    "welcome": {"completed": False},
    "startup": {"applications": []},
}


def config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")).expanduser()


def settings_path() -> Path:
    return config_home() / "fenrir" / "settings.toml"


def _merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def load_settings(path: Path | None = None) -> dict[str, Any]:
    target = path or settings_path()
    if not target.exists():
        return deepcopy(DEFAULTS)
    try:
        parsed = tomllib.loads(target.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"Cannot read Fenrir settings safely: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Fenrir settings root must be a TOML table")
    return validate_settings(_merge(DEFAULTS, parsed))


def validate_settings(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Settings must be a mapping")
    value = _merge(DEFAULTS, data)
    wallpaper = value["wallpaper"]
    if not isinstance(wallpaper["directory"], str) or not wallpaper["directory"].strip():
        raise ValueError("Wallpaper directory cannot be empty")
    wallpaper["interval_minutes"] = int(wallpaper["interval_minutes"])
    if not 1 <= wallpaper["interval_minutes"] <= 1440:
        raise ValueError("Wallpaper interval must be between 1 and 1440 minutes")
    theme = value["theme"]
    theme["surface_opacity"] = float(theme["surface_opacity"])
    if not 0.45 <= theme["surface_opacity"] <= 0.85:
        raise ValueError("Fimbulwinter surface opacity must be between 0.45 and 0.85")
    theme["blur_size"] = int(theme["blur_size"])
    if not 0 <= theme["blur_size"] <= 20:
        raise ValueError("Blur size must be between 0 and 20")
    monitor = value["monitor"]
    monitor["scale"] = float(monitor["scale"])
    monitor["target_refresh"] = float(monitor["target_refresh"])
    if not 0.5 <= monitor["scale"] <= 3.0:
        raise ValueError("Monitor scale must be between 0.5 and 3.0")
    if not 30 <= monitor["target_refresh"] <= 360:
        raise ValueError("Target refresh rate must be between 30 and 360 Hz")
    hypr = value["hyprland"]
    for key, low, high in (("gaps_inner", 0, 40), ("gaps_outer", 0, 80), ("border_size", 0, 10)):
        hypr[key] = int(hypr[key])
        if not low <= hypr[key] <= high:
            raise ValueError(f"{key} must be between {low} and {high}")
    if hypr["layout"] not in {"dwindle", "master"}:
        raise ValueError("Unsupported Hyprland layout")
    for section, keys in (("theme", ("dynamic_colors", "blur_enabled")), ("session", ("allow_screen_off", "auto_lock", "auto_suspend")), ("waybar", ("enabled",)), ("gaming", ("mangohud", "gamemode_hint")), ("welcome", ("completed",))):
        for key in keys:
            if not isinstance(value[section][key], bool):
                raise ValueError(f"{section}.{key} must be true or false")
    if value["keyboard"]["layout"] not in {"us", "br", "gb"}:
        raise ValueError("Unsupported keyboard layout")
    if value["keyboard"]["variant"] not in {"intl", "altgr-intl", "", "abnt2"}:
        raise ValueError("Unsupported keyboard variant")
    if value["waybar"]["layout"] not in {"default", "compact"}:
        raise ValueError("Unsupported Waybar layout")
    apps = value["startup"].get("applications", [])
    if not isinstance(apps, list) or not all(isinstance(x, str) for x in apps):
        raise ValueError("startup.applications must be a list of command strings")
    return value


def _toml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_scalar(item) for item in value) + "]"
    raise TypeError(f"Unsupported TOML setting type: {type(value).__name__}")


def serialize_toml(data: dict[str, Any]) -> str:
    lines: list[str] = []
    for section, values in data.items():
        if not isinstance(values, dict):
            continue
        lines.extend((f"[{section}]",))
        for key, value in values.items():
            lines.append(f"{key} = {_toml_scalar(value)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def save_settings(data: dict[str, Any], path: Path | None = None) -> Path:
    target = path or settings_path()
    checked = validate_settings(data)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(target.parent, 0o700)
    if target.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = target.with_name(f"{target.name}.backup-{stamp}")
        shutil.copy2(target, backup)
        os.chmod(backup, 0o600)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(serialize_toml(checked))
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, target)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return target


def render_hypridle(data: dict[str, Any]) -> str:
    session = data["session"]
    listeners: list[str] = []
    if session["auto_lock"]:
        listeners.append("listener {\n    timeout = 300\n    on-timeout = loginctl lock-session\n}")
    if session["allow_screen_off"]:
        listeners.append("listener {\n    timeout = 900\n    on-timeout = hyprctl dispatch dpms off\n    on-resume = hyprctl dispatch dpms on\n}")
    if not listeners:
        return (
            "# Generated by Fenrir Settings.\n"
            "# Automatic idle locking and display power-off are disabled.\n"
            "# Manual locking remains available with Super+L.\n"
        )
    body = ["# Generated by Fenrir Settings. Only explicitly enabled idle actions appear here.", "general {", "    after_sleep_cmd = hyprctl dispatch dpms on", "}", "", *listeners]
    return "\n".join(body) + "\n"


def render_hyprland_settings(data: dict[str, Any]) -> str:
    hypr = data["hyprland"]
    theme = data["theme"]
    layout = "dwindle" if hypr["layout"] == "dwindle" else "master"
    blur_enabled = "true" if theme["blur_enabled"] else "false"
    return (
        "-- Generated by Fenrir Settings. Edit through the graphical control center.\n"
        "hl.config({\n"
        f"    general = {{ gaps_in = {hypr['gaps_inner']}, gaps_out = {hypr['gaps_outer']}, border_size = {hypr['border_size']}, layout = \"{layout}\" }},\n"
        f"    decoration = {{ blur = {{ enabled = {blur_enabled}, size = {theme['blur_size']} }} }},\n"
        "})\n"
    )


def backup_managed_file(path: Path, home: Path) -> Path | None:
    """Keep a private, timestamped copy before Fenrir replaces a managed config."""
    if not path.is_file() or path.is_symlink():
        return None
    state = home / ".local" / "state" / "fenrir" / "backups"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    relative = path.relative_to(home / ".config")
    destination = state / stamp / relative
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    shutil.copy2(path, destination)
    os.chmod(destination, 0o600)
    return destination


def write_runtime_files(data: dict[str, Any], home: Path | None = None) -> None:
    root = home or Path.home()
    config = (Path(os.environ["XDG_CONFIG_HOME"]).expanduser() if os.environ.get("XDG_CONFIG_HOME") and home is None else root / ".config")
    destinations = {
        config / "hypr" / "hypridle.conf": (render_hypridle(data), 0o600),
        config / "hypr" / "fenrir-settings.lua": (render_hyprland_settings(data), 0o600),
    }
    layout = data["waybar"]["layout"]
    css = "/* Fenrir Settings managed layout */\nwindow#waybar { margin: 0 12px; }\n" if layout == "default" else "/* Fenrir Settings managed layout */\nwindow#waybar { margin: 0 3px; border-radius: 8px; }\n#workspaces, #window, #clock, #network, #pulseaudio, #cpu, #memory, #tray { margin: 2px 1px; padding: 3px 7px; }\n"
    destinations[config / "waybar" / "fenrir-layout.css"] = (css, 0o644)
    backup_home = root if home is not None else Path.home()
    for path, (content, mode) in destinations.items():
        backup_managed_file(path, backup_home)
        atomic_write(path, content, mode)


def atomic_write(path: Path, content: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp_name, mode)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def query_monitors() -> list[dict[str, Any]]:
    try:
        result = subprocess.run(["hyprctl", "-j", "monitors", "all"], capture_output=True, text=True, check=True, timeout=5)
        raw = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return []
    monitors = []
    for item in raw if isinstance(raw, list) else []:
        name = item.get("name")
        if not name:
            continue
        modes = item.get("availableModes") or []
        current = item.get("currentMode") or {}
        if isinstance(current, dict):
            current_mode = current.get("width") and current.get("height") and current.get("refreshRate")
            if current_mode:
                current = f"{current['width']}x{current['height']}@{float(current['refreshRate']):g}Hz"
            else:
                current = "preferred"
        monitors.append({"name": str(name), "modes": [str(x) for x in modes], "current": str(current)})
    return monitors


def mode_for_target(modes: list[str], width: int = 2560, height: int = 1440, refresh: float = 155.0, current: str = "preferred") -> tuple[str, bool]:
    def normalized(mode: str) -> tuple[int, int, float] | None:
        match = re.search(r"(\d+)x(\d+)@([0-9.]+)", mode)
        return (int(match.group(1)), int(match.group(2)), float(match.group(3))) if match else None
    for mode in modes:
        parsed = normalized(mode)
        if parsed and parsed[0] == width and parsed[1] == height and abs(parsed[2] - refresh) < 0.02:
            return mode, True
    if current and current != "preferred" and (not modes or current in modes):
        return current, False
    if modes:
        return modes[0], False
    return "preferred", False


def apply_monitor(output: str, mode: str, scale: float = 1.0) -> None:
    if not output or not re.fullmatch(r"[A-Za-z0-9_.-]+", output):
        raise ValueError("Invalid monitor output name")
    if mode != "preferred" and not re.fullmatch(r"\d+x\d+@[0-9.]+(?:Hz)?", mode):
        raise ValueError("Invalid monitor mode")
    if not 0.5 <= float(scale) <= 3.0:
        raise ValueError("Monitor scale must be between 0.5 and 3.0")
    subprocess.run(["hyprctl", "keyword", "monitor", f"{output},{mode},auto,{float(scale):g}"], check=True, timeout=5)
