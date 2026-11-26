"""Safe settings and hardware helpers for Fenrir Settings.

All persistent edits are scoped to Fenrir-managed settings or generated files.
Existing files receive timestamped backups and are replaced atomically.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import tomllib
from datetime import datetime
from pathlib import Path
from typing import Any

CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
STATE_HOME = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
FENRIR_CONFIG = CONFIG_HOME / "fenrir" / "settings.toml"

ALLOWED_SETTINGS: dict[str, set[str]] = {
    "wallpaper": {"directory", "interval_minutes", "monitor_mode", "history_depth"},
    "theme": {"surface_opacity", "blur_enabled", "dynamic_colors", "preset"},
    "display": {"preferred_width", "preferred_height", "preferred_refresh", "scale"},
    "hyprland": {"layout", "workspace_count", "animations"},
    "waybar": {"show_workspaces", "show_window", "show_network", "show_audio", "show_system", "show_tray", "position"},
    "keyboard": {"layout", "variant"},
    "session": {"keep_awake"},
    "gaming": {"gamemode", "mangohud", "gamescope", "fps_limit"},
}

DEFAULTS: dict[str, dict[str, Any]] = {
    "wallpaper": {"directory": "~/Pictures/Wallpapers", "interval_minutes": 15, "monitor_mode": "shared", "history_depth": 20},
    "theme": {"surface_opacity": 0.60, "blur_enabled": True, "dynamic_colors": True, "preset": "obsidian"},
    "display": {"preferred_width": 2560, "preferred_height": 1440, "preferred_refresh": 155, "scale": 1.0},
    "hyprland": {"layout": "dwindle", "workspace_count": 10, "animations": True},
    "waybar": {"show_workspaces": True, "show_window": True, "show_network": True, "show_audio": True, "show_system": True, "show_tray": True, "position": "top"},
    "keyboard": {"layout": "us", "variant": "intl"},
    "session": {"keep_awake": True},
    "gaming": {"gamemode": True, "mangohud": False, "gamescope": False, "fps_limit": 0},
}


def _run(args: list[str], *, timeout: int = 5, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, timeout=timeout, check=check)


def load_settings(path: Path = FENRIR_CONFIG) -> dict[str, Any]:
    try:
        parsed = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        parsed = {}
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"Fenrir settings file is invalid: {exc}") from exc
    result = {section: values.copy() for section, values in DEFAULTS.items()}
    for section, values in parsed.items():
        if isinstance(values, dict):
            result.setdefault(section, {}).update(values)
    return result


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return "[" + ", ".join(json.dumps(item, ensure_ascii=False) for item in value) + "]"
    raise ValueError(f"Unsupported TOML value: {type(value).__name__}")


def _atomic_write(path: Path, content: str, *, backup: bool = True) -> Path | None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = None
    if backup and path.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup_dir = STATE_HOME / "fenrir" / "settings-backups" / stamp
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / path.name
        shutil.copy2(path, backup_path)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_name, 0o600 if "state" in path.parts or "config" in path.parts else 0o644)
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise
    return backup_path


def set_setting(section: str, key: str, value: Any, path: Path = FENRIR_CONFIG) -> Path | None:
    if section not in ALLOWED_SETTINGS or key not in ALLOWED_SETTINGS[section]:
        raise ValueError(f"Setting is not managed by Fenrir: [{section}] {key}")
    validate_setting(section, key, value)
    current = load_settings(path)
    current.setdefault(section, {})[key] = value
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        lines = []

    header = f"[{section}]"
    start = next((i for i, line in enumerate(lines) if line.strip() == header), None)
    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(header)
        start = len(lines) - 1
    end = next((i for i in range(start + 1, len(lines)) if re.match(r"^\s*\[[^\]]+\]", lines[i])), len(lines))
    replacement = f"{key} = {_toml_value(value)}"
    key_line = next((i for i in range(start + 1, end) if re.match(rf"^\s*{re.escape(key)}\s*=", lines[i])), None)
    if key_line is None:
        lines.insert(end, replacement)
    else:
        lines[key_line] = replacement
    return _atomic_write(path, "\n".join(lines).rstrip() + "\n")


def validate_setting(section: str, key: str, value: Any) -> None:
    if section == "wallpaper" and key == "interval_minutes":
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 1440:
            raise ValueError("Wallpaper interval must be between 1 and 1440 minutes")
    elif section == "wallpaper" and key == "directory":
        if not isinstance(value, str) or not value.strip() or "\n" in value:
            raise ValueError("Wallpaper directory must be a non-empty path")
    elif section == "wallpaper" and key == "monitor_mode":
        if value not in {"shared", "independent"}:
            raise ValueError("Wallpaper monitor mode must be shared or independent")
    elif section == "wallpaper" and key == "history_depth":
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
            raise ValueError("Wallpaper no-repeat history depth must be between 0 and 100")
    elif section == "theme" and key == "surface_opacity":
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0.35 <= value <= 0.85:
            raise ValueError("Glass opacity must be between 0.35 and 0.85")
    elif section == "theme" and key == "preset":
        if value not in {"obsidian", "arctic", "violet", "emerald"}:
            raise ValueError("Unknown Fenrir theme preset")
    elif section == "display" and key in {"preferred_width", "preferred_height"}:
        if not isinstance(value, int) or value < 640 or value > 16384:
            raise ValueError("Display dimensions must be between 640 and 16384 pixels")
    elif section == "display" and key == "preferred_refresh":
        if not isinstance(value, (int, float)) or not 30 <= value <= 1000:
            raise ValueError("Refresh target must be between 30 and 1000 Hz")
    elif section == "display" and key == "scale":
        if not isinstance(value, (int, float)) or not 0.5 <= value <= 3.0:
            raise ValueError("Display scale must be between 0.5 and 3.0")
    elif section == "waybar" and key == "position":
        if value not in {"top", "bottom"}:
            raise ValueError("Waybar position must be top or bottom")
    elif section == "hyprland" and key == "layout":
        if value not in {"dwindle", "master"}:
            raise ValueError("Supported layouts are Dwindle and Master")
    elif section == "gaming" and key == "fps_limit":
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 1000:
            raise ValueError("FPS limit must be 0 (unlimited) or between 1 and 1000")
    elif section == "hyprland" and key == "workspace_count":
        if not isinstance(value, int) or not 1 <= value <= 20:
            raise ValueError("Workspace count must be between 1 and 20")
    elif section == "keyboard":
        allowed = {"layout": {"us", "us,br", "br"}, "variant": {"intl", "", "abnt2"}}
        if value not in allowed[key]:
            raise ValueError("Unsupported keyboard layout or variant")
    elif isinstance(value, bool):
        return
    else:
        raise ValueError(f"Unsupported value for [{section}] {key}")


def get_monitors() -> list[dict[str, Any]]:
    try:
        result = _run(["hyprctl", "-j", "monitors", "all"], timeout=6)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"Could not query Hyprland monitor information: {exc}") from exc
    try:
        monitors = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Hyprland returned invalid monitor JSON") from exc
    return monitors if isinstance(monitors, list) else []


def supported_mode(monitor: dict[str, Any], width: int, height: int, refresh: float) -> str | None:
    modes = monitor.get("availableModes") or monitor.get("available_modes") or []
    for mode in modes:
        match = re.fullmatch(r"(\d+)x(\d+)@([\d.]+)Hz?", str(mode), re.IGNORECASE)
        if not match:
            continue
        w, h, hz = int(match.group(1)), int(match.group(2)), float(match.group(3))
        if w == width and h == height and abs(hz - refresh) <= 0.02:
            return str(mode)
    return None


def apply_monitor(name: str, width: int = 2560, height: int = 1440, refresh: float = 155.0, scale: float = 1.0) -> tuple[bool, str]:
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", name):
        raise ValueError("Invalid monitor connector name")
    validate_setting("display", "preferred_width", width)
    validate_setting("display", "preferred_height", height)
    validate_setting("display", "preferred_refresh", refresh)
    validate_setting("display", "scale", scale)
    monitors = get_monitors()
    selected = next((item for item in monitors if item.get("name") == name), None)
    if selected is None:
        raise RuntimeError(f"Monitor {name} is not currently connected")
    mode = supported_mode(selected, width, height, refresh)
    if mode is None:
        current = selected.get("currentMode") or "the compositor's preferred mode"
        return False, f"{width}×{height} at {refresh:g} Hz is not advertised by {name}. Keeping {current}; no mode change was made."
    try:
        lua_mode = re.sub(r"Hz$", "", mode, flags=re.IGNORECASE)
        expression = f'hl.monitor({{ output = "{name}", mode = "{lua_mode}", position = "auto", scale = {scale:g} }})'
        _run(["hyprctl", "eval", expression], timeout=6)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"Hyprland rejected monitor mode {mode}: {exc}") from exc
    return True, f"Applied {mode} on {name} at scale {scale:g}."


ACTIONS = {
    "terminal": "kitty",
    "launcher": "fuzzel",
    "files": "thunar",
    "browser": "firefox-nightly",
    "manual_lock": "hyprlock",
    "next_wallpaper": "fenrir-wallpaper next",
    "settings": "fenrir-settings",
    "welcome": "fenrir-welcome",
}


def save_custom_keybind(key: str, action: str) -> Path:
    """Add/update a safe predefined action in a generated Hyprland Lua file."""
    key = " ".join(key.upper().split())
    if not re.fullmatch(r"(?:SUPER|ALT|CTRL|SHIFT)(?:\s*\+\s*(?:SUPER|ALT|CTRL|SHIFT|[A-Z0-9]|LEFT|RIGHT|UP|DOWN|RETURN|SPACE|TAB|ESC))*", key):
        raise ValueError("Use a simple key such as SUPER + CTRL + T")
    if action not in ACTIONS:
        raise ValueError("Unknown Fenrir keybind action")
    target = CONFIG_HOME / "hypr" / "fenrir-custom.lua"
    data_path = CONFIG_HOME / "fenrir" / "keybinds.json"
    try:
        data = json.loads(data_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    except json.JSONDecodeError as exc:
        raise ValueError(f"Custom keybind database is invalid: {exc}") from exc
    data[key] = action
    content = "-- Generated by Fenrir Settings. Safe predefined actions only.\n"
    for binding, command in sorted(data.items()):
        # All values originate from the strict key regex and ACTIONS whitelist.
        escaped_key = binding.replace('"', '\\"')
        escaped_command = ACTIONS[command].replace('"', '\\"')
        content += f'hl.bind("{escaped_key}", hl.dsp.exec_cmd("{escaped_command}"))\n'
    _atomic_write(data_path, json.dumps(data, indent=2) + "\n")
    _atomic_write(target, content)
    return target


def write_runtime_settings() -> Path:
    data = load_settings()
    layout = data["hyprland"].get("layout", "dwindle")
    keyboard_layout = data["keyboard"].get("layout", "us")
    keyboard_variant = data["keyboard"].get("variant", "intl")
    blur = bool(data["theme"].get("blur_enabled", True))
    animations = bool(data["hyprland"].get("animations", True))
    if layout not in {"dwindle", "master"} or keyboard_layout not in {"us", "us,br", "br"} or keyboard_variant not in {"intl", "", "abnt2"}:
        raise ValueError("Runtime settings contain an unsupported layout or keyboard mapping")
    content = (
        "-- Generated by Fenrir Settings. Do not edit while the app is running.\n"
        f'hl.config({{ general = {{ layout = "{layout}" }}, input = {{ kb_layout = "{keyboard_layout}", kb_variant = "{keyboard_variant}" }}, decoration = {{ blur = {{ enabled = {str(blur).lower()} }} }} }})\n'
        f'hl.animation({{ leaf = "global", enabled = {str(animations).lower()}, speed = 8, bezier = "default" }})\n'
    )
    target = CONFIG_HOME / "hypr" / "fenrir-settings.lua"
    _atomic_write(target, content)
    return target


def write_workspace_bindings(count: int) -> Path:
    validate_setting("hyprland", "workspace_count", count)
    lines = ["-- Generated by Fenrir Settings. Workspace shortcuts."]
    for index in range(1, count + 1):
        key = str(index) if index <= 9 else ("0" if index == 10 else f"ALT + {index - 10}")
        lines.append(f'hl.bind("SUPER + {key}", hl.dsp.focus({{ workspace = {index} }}))')
        lines.append(f'hl.bind("SUPER + SHIFT + {key}", hl.dsp.window.move({{ workspace = {index} }}))')
    target = CONFIG_HOME / "hypr" / "fenrir-workspaces.lua"
    _atomic_write(target, "\n".join(lines) + "\n")
    return target


def apply_layout(layout: str) -> None:
    if layout not in {"dwindle", "master"}:
        raise ValueError("Unsupported Hyprland layout")
    data = load_settings()
    data["hyprland"]["layout"] = layout
    set_setting("hyprland", "layout", layout)
    write_runtime_settings()
    expression = f'hl.config({{ general = {{ layout = "{layout}" }} }})'
    try:
        _run(["hyprctl", "eval", expression], timeout=4)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"Hyprland could not apply layout: {exc}") from exc


def apply_keyboard(layout: str, variant: str) -> None:
    validate_setting("keyboard", "layout", layout)
    validate_setting("keyboard", "variant", variant)
    set_setting("keyboard", "layout", layout)
    set_setting("keyboard", "variant", variant)
    write_runtime_settings()
    expression = f'hl.config({{ input = {{ kb_layout = "{layout}", kb_variant = "{variant}" }} }})'
    try:
        _run(["hyprctl", "eval", expression], timeout=4)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"Hyprland could not apply keyboard layout: {exc}") from exc


def set_keep_awake(enabled: bool) -> None:
    if not isinstance(enabled, bool):
        raise ValueError("Keep-awake must be a boolean")
    action = "enable" if enabled else "disable"
    try:
        _run(["systemctl", "--user", action, "--now", "fenrir-stay-awake.service"], timeout=8)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"Could not change the keep-awake service: {exc}") from exc
    set_setting("session", "keep_awake", enabled)


def update_waybar_modules(settings: dict[str, Any]) -> None:
    path = CONFIG_HOME / "waybar" / "config.jsonc"
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not read Waybar JSON configuration: {exc}") from exc
    left = ["hyprland/workspaces"] if settings.get("show_workspaces", True) else []
    if settings.get("show_window", True):
        left.append("hyprland/window")
    center = ["clock"]
    right = []
    if settings.get("show_network", True): right.append("network")
    if settings.get("show_audio", True): right.append("pulseaudio")
    if settings.get("show_system", True): right.extend(["cpu", "memory"])
    if settings.get("show_tray", True): right.append("tray")
    position = settings.get("position", "top")
    validate_setting("waybar", "position", position)
    config["position"] = position
    config["modules-left"], config["modules-center"], config["modules-right"] = left, center, right
    _atomic_write(path, json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    try:
        _run(["pkill", "-USR2", "waybar"], timeout=3, check=False)
    except OSError:
        pass


def set_startup_app(name: str, desktop_id: str, enabled: bool) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+\.desktop", desktop_id):
        raise ValueError("Invalid desktop entry id")
    if name not in {"Discord", "Spotify", "Fenrir Doctor", "Sun AI", "EasyEffects"}:
        raise ValueError("Unsupported startup application")
    autostart = CONFIG_HOME / "autostart"
    target = autostart / desktop_id
    if enabled:
        source_candidates = [
            Path("/usr/share/applications") / desktop_id,
            Path.home() / ".local/share/applications" / desktop_id,
            Path("/var/lib/flatpak/exports/share/applications") / desktop_id,
            Path.home() / ".local/share/flatpak/exports/share/applications" / desktop_id,
        ]
        source = next((candidate for candidate in source_candidates if candidate.is_file()), None)
        if source is None:
            raise RuntimeError(f"Desktop launcher is not installed: {desktop_id}")
        _atomic_write(target, source.read_text(encoding="utf-8"))
    elif target.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup_dir = STATE_HOME / "fenrir" / "settings-backups" / stamp
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, backup_dir / target.name)
        target.unlink()


def configure_gaming(gamemode: bool, mangohud: bool, fps_limit: int, gamescope: bool = False) -> None:
    if not 0 <= fps_limit <= 1000:
        raise ValueError("FPS limit must be 0 (unlimited) or between 1 and 1000")
    config_dir = CONFIG_HOME / "MangoHud"
    config_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write(config_dir / "MangoHud.conf", f"fps\nframetime\ngpu_stats\ncpu_stats\nram\nvram\nposition=top-left\nbackground_alpha=0.35\nfont_size=22\nno_display={'false' if mangohud else 'true'}\nfps_limit={fps_limit}\n")
    gamemode_dir = CONFIG_HOME / "gamemode"
    gamemode_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write(gamemode_dir / "gamemode.ini", "[general]\nrenice=10\nioprio=0\nsoftrealtime=off\n")
    set_setting("gaming", "gamemode", bool(gamemode))
    set_setting("gaming", "mangohud", bool(mangohud))
    set_setting("gaming", "gamescope", bool(gamescope))
    set_setting("gaming", "fps_limit", int(fps_limit))
    profile = {"gamemode": bool(gamemode), "mangohud": bool(mangohud), "gamescope": bool(gamescope), "fps_limit": int(fps_limit)}
    _atomic_write(CONFIG_HOME / "fenrir" / "gaming.json", json.dumps(profile, indent=2) + "\n")
    _atomic_write(CONFIG_HOME / "fenrir" / "steam-launch-options.txt", "fenrir-game %command%\n")


def service_state(unit: str, user: bool = True) -> str:
    allowed = {"fenrir-wallpaper.service", "fenrir-doctor.service", "fenrir-stay-awake.service", "pipewire.service", "pipewire.socket", "wireplumber.service", "sun-ai.service", "NetworkManager.service", "bluetooth.service"}
    if unit not in allowed:
        raise ValueError("Unsupported Fenrir service")
    args = ["systemctl"] + (["--user"] if user else []) + ["is-active", unit]
    try:
        result = _run(args, timeout=5, check=False)
        return result.stdout.strip() or result.stderr.strip() or "unknown"
    except OSError as exc:
        return str(exc)


def control_service(unit: str, action: str, user: bool = True) -> None:
    if action not in {"start", "stop", "restart"}:
        raise ValueError("Unsupported service action")
    allowed = {"fenrir-wallpaper.service", "fenrir-stay-awake.service", "pipewire.service", "pipewire.socket", "wireplumber.service", "sun-ai.service", "NetworkManager.service", "bluetooth.service"}
    if unit not in allowed:
        raise ValueError("Unsupported Fenrir service")
    command = ["systemctl"] + (["--user"] if user else []) + [action, unit]
    if not user:
        command = ["pkexec", *command]
    _run(command, timeout=15)


def audio_nodes() -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    output = audio_status()
    sinks: list[tuple[str, str]] = []
    sources: list[tuple[str, str]] = []
    section = None
    for line in output.splitlines():
        if "Sinks:" in line:
            section = "sink"
            continue
        if "Sources:" in line:
            section = "source"
            continue
        if any(label in line for label in ("Filters:", "Streams:", "Devices:")):
            section = None
        if section:
            match = re.search(r"(\d+)\.\s+(.+?)(?:\s+\[vol:.*\])?$", line.strip())
            if match:
                item = (match.group(1), match.group(2).strip())
                (sinks if section == "sink" else sources).append(item)
    return sinks, sources


def set_default_audio_node(node_id: str) -> None:
    if not node_id.isdigit():
        raise ValueError("Invalid PipeWire node identifier")
    _run(["wpctl", "set-default", node_id], timeout=5)


def wallpaper_status() -> dict[str, Any]:
    try:
        result = _run(["fenrir-wallpaper", "status", "--json"], timeout=20)
        data = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Wallpaper status unavailable: {exc}") from exc
    return data


def audio_status() -> str:
    try:
        return _run(["wpctl", "status"], timeout=5).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        return f"Audio status unavailable: {exc}"


def restore_defaults() -> Path | None:
    content = "\n".join(
        [f"[{section}]\n" + "\n".join(f"{key} = {_toml_value(value)}" for key, value in values.items())
         for section, values in DEFAULTS.items()]
    ) + "\n"
    backup = _atomic_write(FENRIR_CONFIG, content)
    write_runtime_settings()
    write_workspace_bindings(DEFAULTS["hyprland"]["workspace_count"])
    return backup
