"""Lightweight local wallpaper rotation and wallpaper-derived theme updates."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from .theme import EXCLUDED, apply_palette, classify_rgb

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
MIN_WIDTH, MIN_HEIGHT = 2560, 1440
STATE_PATH = Path.home() / ".local/state/fenrir/wallpaper-rotation.json"


def _eligible(path: Path) -> bool:
    try:
        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            return False
        with Image.open(path) as image:
            if image.width < MIN_WIDTH or image.height < MIN_HEIGHT or image.width <= image.height:
                return False
            sample = image.convert("RGB").resize((64, 64))
            quantized = sample.quantize(colors=8).convert("RGB")
            palette = quantized.getcolors(maxcolors=4096) or []
            excluded_pixels = sum(
                count for count, rgb in palette
                if classify_rgb(*rgb) in EXCLUDED
            )
            return excluded_pixels / 4096 <= 0.08
    except (OSError, ValueError):
        return False


def candidates(directory: Path) -> list[Path]:
    if not directory.exists() or directory.is_symlink():
        return []
    return sorted(
        (path for path in directory.rglob("*") if _eligible(path)),
        key=lambda path: str(path).casefold(),
    )


def _save_state(path: Path) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".wallpaper-rotation.", dir=STATE_PATH.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({"last": str(path), "selected_at": int(__import__("time").time())}, stream)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, STATE_PATH)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def rotate(directory: Path | None = None) -> Path | None:
    directory = (directory or Path.home() / "Pictures/Wallpapers").expanduser()
    if str(directory) == "/mnt/storage" or str(directory).startswith("/mnt/storage/"):
        raise ValueError("Fenrir will not read or modify /mnt/storage")
    options = candidates(directory)
    if not options:
        return None
    last = ""
    if STATE_PATH.is_file() and not STATE_PATH.is_symlink():
        try:
            last = json.loads(STATE_PATH.read_text(encoding="utf-8")).get("last", "")
        except (OSError, ValueError, TypeError):
            last = ""
    selected = next((path for path in options if str(path) > last), options[0])
    hyprpaper = subprocess.run(
        ["hyprctl", "hyprpaper", "wallpaper", f",{selected}"],
        check=False, capture_output=True, text=True,
    )
    if hyprpaper.returncode != 0:
        raise RuntimeError(
            f"Hyprpaper refused the wallpaper: {hyprpaper.stderr.strip() or hyprpaper.stdout.strip()}"
        )
    apply_palette(selected)
    _save_state(selected)
    subprocess.run(
        ["notify-send", "Fenrir Wallpaper", selected.name],
        check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return selected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fenrir-wallpaper-rotate")
    parser.add_argument("--directory", type=Path)
    args = parser.parse_args(argv)
    try:
        selected = rotate(args.directory)
        if selected is None:
            print("No eligible wallpapers found; rotation will retry on its next scheduled run.")
        else:
            print(selected)
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Fenrir wallpaper rotation error: {exc}", file=__import__("sys").stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
