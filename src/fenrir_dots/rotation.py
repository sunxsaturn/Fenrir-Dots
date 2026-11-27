"""Local wallpaper rotation and active-monitor application."""
from __future__ import annotations

import json
import os
import secrets
import subprocess
from pathlib import Path

from PIL import Image


def _reject_protected_path(path: Path) -> None:
    resolved = Path(os.path.abspath(path))
    if resolved == Path("/mnt/storage") or Path("/mnt/storage") in resolved.parents:
        raise ValueError("Fenrir wallpaper rotation may not read /mnt/storage")
    current = Path(resolved.anchor)
    for part in resolved.parts[1:]:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"Refusing a symlinked wallpaper path: {current}")


def eligible_images(directory: Path | str) -> list[Path]:
    root = Path(directory)
    _reject_protected_path(root)
    if not root.is_dir():
        return []
    result = []
    for path in root.rglob("*"):
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"} or not path.is_file():
            continue
        _reject_protected_path(path)
        try:
            with Image.open(path) as image:
                width, height = image.size
                image.verify()
            if width >= 2560 and height >= 1440 and width >= height:
                result.append(path)
        except (OSError, ValueError):
            continue
    return sorted(result)


def choose_next_wallpaper(
    directory: Path | str,
    *,
    state_file: Path | str | None = None,
) -> Path:
    candidates = eligible_images(directory)
    if not candidates:
        raise FileNotFoundError("No validated landscape wallpapers (2560×1440 minimum) were found")
    state = Path(state_file or Path.home() / ".local/state/fenrir/wallpaper/current.json")
    _reject_protected_path(state)
    current = None
    try:
        current = json.loads(state.read_text(encoding="utf-8")).get("path")
    except (OSError, json.JSONDecodeError, AttributeError):
        pass
    choices = [path for path in candidates if str(path) != current]
    selected = secrets.choice(choices or candidates)
    state.parent.mkdir(parents=True, exist_ok=True)
    temporary = state.with_name(state.name + ".tmp")
    temporary.write_text(json.dumps({"path": str(selected)}, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, state)
    return selected


def apply_next_wallpaper(directory: Path | str) -> Path:
    selected = choose_next_wallpaper(directory)
    monitors = subprocess.run(
        ["hyprctl", "monitors", "-j"], check=True, capture_output=True, text=True, timeout=10
    )
    data = json.loads(monitors.stdout)
    names = [item.get("name") for item in data if isinstance(item, dict) and item.get("name")]
    if not names:
        raise RuntimeError("Hyprland reported no active monitors")
    subprocess.run(
        ["hyprctl", "hyprpaper", "preload", str(selected)],
        check=True, capture_output=True, text=True, timeout=15,
    )
    for monitor in names:
        subprocess.run(
            ["hyprctl", "hyprpaper", "wallpaper", f"{monitor},{selected}"],
            check=True, capture_output=True, text=True, timeout=15,
        )
    subprocess.run(
        ["fenrir-theme", "apply", str(selected)],
        check=True, capture_output=True, text=True, timeout=20,
    )
    subprocess.run(
        ["pkill", "-USR1", "waybar"], check=False, capture_output=True, text=True, timeout=5
    )
    return selected
