"""Safe XDG desktop-entry index and favorites for the Fenrir launcher."""
from __future__ import annotations

import argparse
import configparser
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Iterable

APP_ID = "org.fenrir.desktop.launcher"


def application_dirs(environ: dict[str, str] | None = None) -> list[Path]:
    env = os.environ if environ is None else environ
    data_home = Path(env.get("XDG_DATA_HOME") or (Path.home() / ".local/share"))
    data_dirs = env.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share")
    result = [data_home / "applications"]
    result.extend(Path(item) / "applications" for item in data_dirs.split(":") if item)
    # Preserve XDG search order while avoiding duplicate directory reads.
    return list(dict.fromkeys(result))


def _try_exec_available(value: str) -> bool:
    if not value:
        return True
    candidate = Path(value)
    if candidate.is_absolute() or "/" in value:
        return candidate.is_file() and os.access(candidate, os.X_OK)
    return shutil.which(value) is not None


def parse_desktop_file(path: Path, root: Path) -> dict | None:
    if path.is_symlink() or not path.is_file() or path.suffix != ".desktop":
        return None
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    try:
        with path.open("r", encoding="utf-8") as stream:
            parser.read_file(stream)
        entry = parser["Desktop Entry"]
    except (OSError, UnicodeError, configparser.Error, KeyError):
        return None

    if entry.get("Type", "Application") != "Application":
        return None
    if entry.getboolean("Hidden", fallback=False) or entry.getboolean("NoDisplay", fallback=False):
        return None
    name = entry.get("Name", "").strip()
    exec_value = entry.get("Exec", "").strip()
    if not name or not exec_value or not _try_exec_available(entry.get("TryExec", "").strip()):
        return None

    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        return None
    desktop_id = relative.replace("/", "-")
    if not desktop_id.endswith(".desktop"):
        return None
    desktop_id = desktop_id[:-8]
    categories = [item.strip() for item in entry.get("Categories", "").split(";") if item.strip()]
    return {
        "desktop_id": desktop_id,
        "name": name,
        "comment": entry.get("Comment", "").strip(),
        "icon": entry.get("Icon", "").strip(),
        "categories": categories,
    }


def load_favorites(path: Path) -> set[str]:
    try:
        values = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    if not isinstance(values, list):
        return set()
    return {value for value in values if isinstance(value, str) and value and "/" not in value and "\\\\" not in value}


def list_applications(
    directories: Iterable[Path] | None = None,
    favorites_path: Path | None = None,
) -> list[dict]:
    roots = list(directories if directories is not None else application_dirs())
    favorites_file = favorites_path or (
        Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
        / "fenrir/launcher-favorites.json"
    )
    favorites = load_favorites(favorites_file)
    found: dict[str, dict] = {}
    for root in roots:
        if not root.is_dir() or root.is_symlink():
            continue
        for current, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = sorted(
                name for name in dirs
                if not (Path(current) / name).is_symlink()
            )
            current_path = Path(current)
            for filename in sorted(files):
                if not filename.endswith(".desktop"):
                    continue
                path = current_path / filename
                record = parse_desktop_file(path, root)
                if record is not None:
                    found.setdefault(record["desktop_id"], record)
    for record in found.values():
        record["favorite"] = record["desktop_id"] in favorites
        record["search_text"] = " ".join(
            [record["name"], record["comment"], *record["categories"]]
        ).casefold()
    return sorted(
        found.values(),
        key=lambda item: (not item["favorite"], item["name"].casefold(), item["desktop_id"]),
    )


def toggle_favorite(desktop_id: str, *, favorites_path: Path | None = None) -> bool:
    if not desktop_id or "/" in desktop_id or "\\\\" in desktop_id or desktop_id.startswith("."):
        raise ValueError("invalid desktop application ID")
    favorites_file = favorites_path or (
        Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
        / "fenrir/launcher-favorites.json"
    )
    values = load_favorites(favorites_file)
    if desktop_id in values:
        values.remove(desktop_id)
        enabled = False
    else:
        values.add(desktop_id)
        enabled = True
    favorites_file.parent.mkdir(parents=True, exist_ok=True)
    temporary = favorites_file.with_name(favorites_file.name + ".tmp")
    temporary.write_text(json.dumps(sorted(values), indent=2) + "\\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, favorites_file)
    os.chmod(favorites_file.parent, 0o700)
    return enabled


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fenrir-applications")
    sub = parser.add_subparsers(dest="command", required=True)
    listing = sub.add_parser("list", help="list visible XDG applications")
    listing.add_argument("--json", action="store_true")
    favorite = sub.add_parser("favorite", help="manage launcher favorites")
    favorite.add_argument("action", choices=("toggle",))
    favorite.add_argument("desktop_id")
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            records = list_applications()
            if args.json:
                print(json.dumps(records, ensure_ascii=False))
            else:
                for item in records:
                    print(item["desktop_id"], item["name"])
            return 0
        enabled = toggle_favorite(args.desktop_id)
        print(json.dumps({"desktop_id": args.desktop_id, "favorite": enabled}))
        return 0
    except (OSError, ValueError) as exc:
        print(f"fenrir-applications: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
