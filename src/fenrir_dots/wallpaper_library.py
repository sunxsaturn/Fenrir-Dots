"""All-volume, integrity-checked public wallpaper synchronization for Fenrir."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Callable

from PIL import Image

REGISTRY_URL = "https://raw.githubusercontent.com/sunxsaturn/Fenrir-Wallpapers/main/manifest/volumes.json"
REGISTRY_SCHEMA = "org.fenrir.wallpaper-library-volumes.v2"
MANIFEST_SCHEMA = "org.fenrir.public-wallpapers.index.v2"
LIBRARY_ID = "fenrir-wallpapers-v2"
MIN_WIDTH, MIN_HEIGHT = 2560, 1440
MAX_IMAGE_BYTES = 100 * 1024 * 1024
ALLOWED_MIME = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
USER_AGENT = "Fenrir-Desktop-Public-Library/2.0"
CATEGORY_IDS = {
    "nordic-landscapes", "medieval-landscapes", "fantasy", "epic-battles",
    "mountains", "astronomy", "planets", "knights-in-battle", "swords",
    "magic", "nordic-mythology",
}
PREFERRED = {"blue", "red", "purple", "black", "violet"}
TOLERATED = {"green", "white", "neutral"}
EXCLUDED = {"yellow", "brown", "orange", "pink"}


class WallpaperSyncError(RuntimeError):
    pass


def _safe_path(path: Path) -> None:
    absolute = Path(os.path.abspath(path))
    if absolute == Path("/mnt/storage") or Path("/mnt/storage") in absolute.parents:
        raise WallpaperSyncError("Wallpaper destination/cache may not be inside /mnt/storage")
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        if current.is_symlink():
            raise WallpaperSyncError(f"Refusing a symlinked destination component: {current}")


def _request(url: str, *, opener: Callable, headers: dict[str, str] | None = None):
    request_headers = {"User-Agent": USER_AGENT}
    request_headers.update(headers or {})
    return opener(urllib.request.Request(url, headers=request_headers), timeout=45)


def _fetch_json(url: str, opener: Callable) -> dict:
    try:
        with _request(url, opener=opener, headers={"Accept": "application/json"}) as response:
            raw = response.read(16 * 1024 * 1024 + 1)
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        raise WallpaperSyncError(f"Could not fetch {url}: {exc}") from exc
    if len(raw) > 16 * 1024 * 1024:
        raise WallpaperSyncError("Gallery metadata exceeds the 16 MiB safety limit")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WallpaperSyncError(f"Invalid JSON from {url}: {exc}") from exc
    if not isinstance(value, dict):
        raise WallpaperSyncError("Gallery metadata must be a JSON object")
    return value


def _raw_url(repository: str, branch: str, path: str) -> str:
    if not repository or "/" not in repository:
        raise WallpaperSyncError("Invalid public gallery repository")
    return "https://raw.githubusercontent.com/" + repository + "/" + urllib.parse.quote(branch, safe="/") + "/" + urllib.parse.quote(path, safe="/")


def _validate_registry(registry: dict) -> list[dict]:
    if registry.get("schema") != REGISTRY_SCHEMA or registry.get("library_id") != LIBRARY_ID:
        raise WallpaperSyncError("Unsupported public gallery registry")
    population = registry.get("population")
    if not isinstance(population, dict) or population.get("target_unique_images") != 5000:
        raise WallpaperSyncError("The public gallery must declare the fixed 5000-image target")
    categories = registry.get("categories")
    if not isinstance(categories, list) or len(categories) != 11:
        raise WallpaperSyncError("The registry must contain exactly eleven categories")
    ids = set()
    total = 0
    for entry in categories:
        if not isinstance(entry, dict) or entry.get("id") not in CATEGORY_IDS:
            raise WallpaperSyncError("The registry contains an unknown category")
        category_id, count = entry["id"], entry.get("target_count")
        if category_id in ids or type(count) is not int or count not in {454, 455}:
            raise WallpaperSyncError("Invalid or duplicate category quota")
        ids.add(category_id)
        total += count
    if ids != CATEGORY_IDS or total != 5000 or sorted(x["target_count"] for x in categories).count(455) != 6:
        raise WallpaperSyncError("The category quotas must sum to 5000 (six 455s and five 454s)")
    if population.get("state") != "published" or population.get("published_unique_images") != 5000:
        raise WallpaperSyncError("The 5000-image public library is not fully published yet")
    volumes = registry.get("volumes")
    if not isinstance(volumes, list) or not volumes:
        raise WallpaperSyncError("The registry has no gallery volumes")
    result, seen_ids, seen_repos = [], set(), set()
    for volume in volumes:
        if not isinstance(volume, dict):
            raise WallpaperSyncError("Malformed volume record")
        if volume.get("active") is not True:
            continue
        volume_id, repo, branch, manifest_path = (
            volume.get("id"), volume.get("repository"), volume.get("branch"), volume.get("manifest_path")
        )
        if not all(isinstance(x, str) and x for x in (volume_id, repo, branch, manifest_path)):
            raise WallpaperSyncError("Incomplete active volume registration")
        if volume_id in seen_ids or repo in seen_repos:
            raise WallpaperSyncError("Duplicate volume ID or repository")
        if ".." in PurePosixPath(manifest_path).parts or manifest_path.startswith("/"):
            raise WallpaperSyncError("Unsafe manifest path in registry")
        seen_ids.add(volume_id)
        seen_repos.add(repo)
        result.append({
            "id": volume_id, "repository": repo, "branch": branch,
            "images_path": volume.get("images_path", "images/"),
            "manifest_path": manifest_path,
        })
    if not result:
        raise WallpaperSyncError("The registry has no active volumes")
    return result


def _validate_manifest(manifest: dict, volume: dict) -> list[dict]:
    if manifest.get("schema") != MANIFEST_SCHEMA or manifest.get("library_id") != LIBRARY_ID:
        raise WallpaperSyncError(f"Unsupported manifest schema for {volume['id']}")
    if manifest.get("volume_id") != volume["id"]:
        raise WallpaperSyncError(f"Volume identity mismatch for {volume['id']}")
    items = manifest.get("items")
    if not isinstance(items, list) or type(manifest.get("count")) is not int or manifest["count"] != len(items):
        raise WallpaperSyncError(f"Manifest count mismatch for {volume['id']}")
    normalized = []
    seen_paths, seen_hashes = set(), set()
    for item in items:
        if not isinstance(item, dict):
            raise WallpaperSyncError("Malformed image manifest entry")
        path, digest, size, mime = item.get("path"), item.get("sha256"), item.get("file_size_bytes"), item.get("mime_type")
        if not isinstance(path, str) or not path.startswith(volume["images_path"]):
            raise WallpaperSyncError("Image path is outside the registered images root")
        relative = PurePosixPath(path)
        if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
            raise WallpaperSyncError("Unsafe image path in manifest")
        if len(relative.parts) < 3 or relative.parts[1] not in CATEGORY_IDS:
            raise WallpaperSyncError("Image path must be images/category/filename")
        category = relative.parts[1]
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise WallpaperSyncError("Invalid image SHA-256")
        if type(size) is not int or size < 1 or size > MAX_IMAGE_BYTES:
            raise WallpaperSyncError("Invalid or oversized image byte count")
        if mime not in ALLOWED_MIME or relative.suffix.lower() != ALLOWED_MIME[mime]:
            raise WallpaperSyncError("Image MIME type and extension do not agree")
        if path in seen_paths or digest in seen_hashes:
            raise WallpaperSyncError("Duplicate image path or hash within volume")
        if item.get("category") != category:
            raise WallpaperSyncError("Manifest category does not match image path")
        if item.get("license_identifier") not in {"Public Domain", "CC0"}:
            raise WallpaperSyncError("Only Public Domain and CC0 assets may enter the public gallery")
        if not all(item.get(field) for field in ("creator", "source_page", "rights_evidence_id")):
            raise WallpaperSyncError("Missing creator, source or rights evidence in image record")
        seen_paths.add(path)
        seen_hashes.add(digest)
        normalized.append({**item, "_volume": volume})
    return normalized


def _palette_family(rgb: tuple[int, int, int]) -> str:
    import colorsys
    hue, saturation, value = colorsys.rgb_to_hsv(*(channel / 255 for channel in rgb))
    degrees = hue * 360
    if saturation <= 0.17:
        return "black" if value <= 0.17 else ("white" if value >= 0.88 else "neutral")
    if degrees < 10 or degrees >= 350: return "red"
    if degrees < 35: return "brown" if value < 0.72 else "orange"
    if degrees < 65: return "yellow"
    if degrees < 165: return "green"
    if degrees < 245: return "blue"
    if degrees < 285: return "violet"
    if degrees < 320: return "purple"
    return "pink"


def _verify_image(path: Path, item: dict) -> None:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    if size != item["file_size_bytes"] or digest.hexdigest() != item["sha256"]:
        raise WallpaperSyncError(f"Integrity mismatch for {item['path']}")
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            image_format = image.format
            width, height = image.size
            thumbnail = image.convert("RGB")
            thumbnail.thumbnail((128, 128))
            samples = list(thumbnail.getdata())
    except Exception as exc:
        raise WallpaperSyncError(f"Image decode failed for {item['path']}: {exc}") from exc
    expected_format = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}[item["mime_type"]]
    if image_format != expected_format or width < MIN_WIDTH or height < MIN_HEIGHT or width < height:
        raise WallpaperSyncError(f"Image format or dimensions rejected for {item['path']}")
    counts: dict[str, int] = {}
    for sample in samples:
        family = _palette_family(sample)
        counts[family] = counts.get(family, 0) + 1
    total = max(1, len(samples))
    excluded = sum(counts.get(name, 0) for name in EXCLUDED) / total
    accepted = sum(counts.get(name, 0) for name in PREFERRED | TOLERATED) / total
    if excluded > 0.25 or accepted < 0.08:
        raise WallpaperSyncError(f"Image palette rejected for {item['path']}")


def _safe_destination(destination: Path, state_dir: Path) -> None:
    _safe_path(destination)
    _safe_path(state_dir)
    if destination == state_dir or destination in state_dir.parents or state_dir in destination.parents:
        raise WallpaperSyncError("Wallpaper destination and resumable state directory must be separate")


def _fetch_all(registry_url: str, opener: Callable) -> tuple[list[dict], dict]:
    registry = _fetch_json(registry_url, opener)
    volumes = _validate_registry(registry)
    all_items, global_hashes = [], set()
    for volume in volumes:
        url = _raw_url(volume["repository"], volume["branch"], volume["manifest_path"])
        manifest = _fetch_json(url, opener)
        for item in _validate_manifest(manifest, volume):
            digest = item["sha256"]
            if digest in global_hashes:
                raise WallpaperSyncError("Global duplicate SHA-256 across public volumes")
            global_hashes.add(digest)
            all_items.append(item)
    if len(all_items) != 5000:
        raise WallpaperSyncError(f"Expected exactly 5000 public images, found {len(all_items)}")
    category_counts = {category: 0 for category in CATEGORY_IDS}
    for item in all_items:
        category_counts[item["category"]] += 1
    expected = {category: 455 if index < 6 else 454 for index, category in enumerate(sorted(CATEGORY_IDS))}
    if category_counts != expected:
        raise WallpaperSyncError("Published manifest category counts do not match the balanced target")
    return all_items, registry


def build_plan(
    destination: Path | str,
    state_dir: Path | str,
    *,
    registry_url: str = REGISTRY_URL,
    opener: Callable = urllib.request.urlopen,
) -> dict:
    destination, state_dir = Path(destination), Path(state_dir)
    _safe_destination(destination, state_dir)
    items, registry = _fetch_all(registry_url, opener)
    present, missing, conflicts = 0, [], []
    for item in items:
        relative = PurePosixPath(item["path"]).relative_to("images")
        target = destination.joinpath(*relative.parts)
        _safe_path(target)
        if target.is_file():
            if target.stat().st_size == item["file_size_bytes"]:
                digest = hashlib.sha256(target.read_bytes()).hexdigest()
                if digest == item["sha256"]:
                    present += 1
                else:
                    conflicts.append(str(target))
            else:
                conflicts.append(str(target))
        elif target.exists():
            conflicts.append(str(target))
        else:
            missing.append(item)
    if conflicts:
        raise WallpaperSyncError("Refusing to overwrite conflicting existing files: " + ", ".join(conflicts[:5]))
    required = sum(item["file_size_bytes"] for item in missing)
    dest_probe = destination if destination.exists() else destination.parent
    state_probe = state_dir if state_dir.exists() else state_dir.parent
    while not dest_probe.exists() and dest_probe != dest_probe.parent: dest_probe = dest_probe.parent
    while not state_probe.exists() and state_probe != state_probe.parent: state_probe = state_probe.parent
    destination_free = shutil.disk_usage(dest_probe).free
    state_free = shutil.disk_usage(state_probe).free
    return {
        "dry_run": True,
        "active_volumes": [v["id"] for v in _validate_registry(registry)],
        "unique_images": len(items),
        "already_present": present,
        "planned_downloads": len(missing),
        "selected_download_bytes": required,
        "destination_available_bytes": destination_free,
        "destination_required_bytes": required,
        "state_available_bytes": state_free,
        "state_required_bytes": required,
        "storage_sufficient": destination_free >= required and state_free >= required,
        "_missing": missing,
        "_registry": registry,
    }


def _download(item: dict, state_dir: Path, destination: Path, opener: Callable) -> None:
    digest, expected_size = item["sha256"], item["file_size_bytes"]
    partial = state_dir / f"{digest}.part"
    partial.parent.mkdir(parents=True, exist_ok=True)
    target_relative = PurePosixPath(item["path"]).relative_to("images")
    target = destination.joinpath(*target_relative.parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    _safe_path(target)
    if target.exists():
        raise WallpaperSyncError(f"Refusing to overwrite existing file: {target}")
    offset = partial.stat().st_size if partial.exists() else 0
    if offset > expected_size:
        partial.unlink()
        offset = 0
    url = _raw_url(item["_volume"]["repository"], item["_volume"]["branch"], item["path"])
    headers = {"Range": f"bytes={offset}-"} if offset else {}
    try:
        with _request(url, opener=opener, headers=headers) as response:
            status = getattr(response, "status", response.getcode())
            if offset and status != 206:
                partial.unlink(missing_ok=True)
                offset = 0
                with _request(url, opener=opener) as retry:
                    with partial.open("wb") as stream:
                        shutil.copyfileobj(retry, stream, 1024 * 1024)
            else:
                mode = "ab" if offset and status == 206 else "wb"
                with partial.open(mode) as stream:
                    shutil.copyfileobj(response, stream, 1024 * 1024)
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        raise WallpaperSyncError(f"Download interrupted for {item['path']}: {exc}") from exc
    if partial.stat().st_size != expected_size:
        raise WallpaperSyncError(f"Incomplete download for {item['path']}; verified partial retained")
    _verify_image(partial, item)
    temporary = target.with_name(target.name + ".fenrir-tmp")
    try:
        shutil.copyfile(partial, temporary)
        _verify_image(temporary, item)
        if target.exists():
            raise WallpaperSyncError(f"Refusing to overwrite existing file: {target}")
        os.replace(temporary, target)
        partial.unlink(missing_ok=True)
    finally:
        temporary.unlink(missing_ok=True)


def sync_public_library(
    destination: Path | str,
    state_dir: Path | str,
    *,
    registry_url: str = REGISTRY_URL,
    opener: Callable = urllib.request.urlopen,
) -> dict:
    plan = build_plan(destination, state_dir, registry_url=registry_url, opener=opener)
    if not plan["storage_sufficient"]:
        raise WallpaperSyncError("Insufficient free space for the complete public wallpaper library")
    destination, state_dir = Path(destination), Path(state_dir)
    destination.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    failures = []
    for item in plan["_missing"]:
        try:
            _download(item, state_dir, destination, opener)
            downloaded += 1
        except WallpaperSyncError as exc:
            failures.append({"path": item["path"], "error": str(exc)})
            break
    final = build_plan(destination, state_dir, registry_url=registry_url, opener=opener)
    report = {
        "dry_run": False,
        "unique_images": final["unique_images"],
        "downloaded": downloaded,
        "already_present": final["already_present"],
        "planned_downloads": final["planned_downloads"],
        "failures": failures,
        "complete": final["planned_downloads"] == 0 and not failures,
    }
    if not report["complete"]:
        raise WallpaperSyncError(json.dumps(report, indent=2))
    return report
