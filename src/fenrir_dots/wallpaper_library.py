"""Registry-driven, rights-evidence-aware Fenrir public wallpaper sync.

The public client downloads only committed manifest entries. It does not
discover assets, grant rights, acquire from providers or publish Catalog data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Callable

REGISTRY_URL = (
    "https://raw.githubusercontent.com/sunxsaturn/Fenrir-Wallpapers/"
    "main/manifest/volumes.json"
)
REGISTRY_SCHEMA = "org.fenrir.wallpaper-library-volumes.v2"
MANIFEST_SCHEMA = "org.fenrir.public-wallpapers.index.v2"
TARGET = 5000
MIN_WIDTH, MIN_HEIGHT = 2560, 1440
MAX_JSON_BYTES = 32 * 1024 * 1024
MAX_IMAGE_BYTES = 20 * 1024 * 1024
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
CATEGORY_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ALLOWED_LICENSES = {"cc0", "public domain", "public-domain"}
EXCLUDED_FAMILIES = {"yellow", "brown", "orange", "pink"}
PREFERRED_FAMILIES = {"blue", "red", "purple", "violet", "black"}
CATEGORY_TARGETS = {
    "nordic-landscapes": 455,
    "medieval-landscapes": 455,
    "fantasy": 455,
    "epic-battles": 455,
    "mountains": 455,
    "astronomy": 455,
    "planets": 454,
    "knights-in-battle": 454,
    "swords": 454,
    "magic": 454,
    "nordic-mythology": 454,
}


class LibrarySyncError(RuntimeError):
    """A registry, manifest, storage or transfer operation failed safely."""


def _json_bytes(url: str, *, opener: Callable = urllib.request.urlopen) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "Fenrir-Desktop-Wallpaper-Library/2"})
    try:
        with opener(request, timeout=45) as response:
            payload = response.read(MAX_JSON_BYTES + 1)
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        raise LibrarySyncError(f"Could not fetch {url}: {exc}") from exc
    if len(payload) > MAX_JSON_BYTES:
        raise LibrarySyncError("Registry or manifest exceeds the metadata size limit")
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LibrarySyncError(f"Invalid UTF-8 JSON from {url}: {exc}") from exc
    if not isinstance(value, dict):
        raise LibrarySyncError("Registry and manifests must be JSON objects")
    return value


def _safe_path(value: object) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value or value.startswith("/"):
        raise LibrarySyncError("Manifest contains an unsafe relative path")
    path = PurePosixPath(value)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise LibrarySyncError(f"Unsafe manifest path: {value!r}")
    return path


def _raw_url(repository: str, branch: str, path: str) -> str:
    if not REPO_RE.fullmatch(repository):
        raise LibrarySyncError("Invalid registered gallery repository")
    if not isinstance(branch, str) or not re.fullmatch(r"[A-Za-z0-9._/-]{1,128}", branch):
        raise LibrarySyncError("Invalid registered gallery branch")
    encoded_branch = urllib.parse.quote(branch, safe="/")
    encoded_path = urllib.parse.quote(path, safe="/")
    return f"https://raw.githubusercontent.com/{repository}/{encoded_branch}/{encoded_path}"


def _validate_registry(registry: dict) -> list[dict]:
    if registry.get("schema") != REGISTRY_SCHEMA:
        raise LibrarySyncError("Unsupported Fenrir wallpaper registry schema")
    if registry.get("library_id") != "fenrir-wallpapers-generation-2":
        raise LibrarySyncError("Unexpected wallpaper library identity")
    if registry.get("hub_repository") != "sunxsaturn/Fenrir-Wallpapers":
        raise LibrarySyncError("Unexpected wallpaper hub repository")
    population = registry.get("population")
    policy = registry.get("policy")
    if not isinstance(population, dict) or not isinstance(policy, dict):
        raise LibrarySyncError("Registry population or policy block is missing")
    if population.get("fixed_image_count_target") != TARGET:
        raise LibrarySyncError("Registry target does not equal 5,000")
    if population.get("category_targets") != CATEGORY_TARGETS:
        raise LibrarySyncError("Registry category quotas are not the canonical balanced 5,000-image split")
    if policy.get("allowed_rights") != ["CC0", "Public Domain"]:
        raise LibrarySyncError("Registry rights policy is not the strict CC0/Public Domain policy")
    if policy.get("excluded_dominant_colors") != ["yellow", "brown", "orange", "pink"]:
        raise LibrarySyncError("Registry palette exclusions do not match the desktop policy")

    volumes = registry.get("volumes")
    if not isinstance(volumes, list) or not volumes:
        raise LibrarySyncError("Registry contains no volumes")
    active: list[dict] = []
    seen_ids: set[str] = set()
    seen_repositories: set[str] = set()
    for volume in volumes:
        if not isinstance(volume, dict) or volume.get("active") is not True:
            continue
        volume_id = volume.get("id")
        repository = volume.get("repository")
        if not isinstance(volume_id, str) or not re.fullmatch(r"volume-[0-9]{2}", volume_id):
            raise LibrarySyncError("Invalid volume ID")
        if volume_id in seen_ids:
            raise LibrarySyncError(f"Duplicate volume ID: {volume_id}")
        if not isinstance(repository, str) or not REPO_RE.fullmatch(repository):
            raise LibrarySyncError(f"Invalid repository in {volume_id}")
        if repository in seen_repositories:
            raise LibrarySyncError(f"Gallery repository is registered more than once: {repository}")
        seen_ids.add(volume_id)
        seen_repositories.add(repository)
        images_path = volume.get("images_path")
        manifest_path = volume.get("manifest_path")
        if not isinstance(images_path, str) or not images_path.endswith("/"):
            raise LibrarySyncError(f"Invalid images_path in {volume_id}")
        _safe_path(images_path.rstrip("/"))
        manifest_relative = _safe_path(manifest_path)
        if not isinstance(volume.get("branch"), str):
            raise LibrarySyncError(f"Missing branch for {volume_id}")
        active.append({
            "id": volume_id,
            "repository": repository,
            "branch": volume["branch"],
            "images_path": images_path,
            "manifest_path": manifest_relative.as_posix(),
            "target_images": volume.get("target_images"),
        })
    if not active:
        raise LibrarySyncError("Registry contains no active gallery volumes")
    return active


def _validate_item(item: object, volume: dict, policy: dict) -> dict:
    if not isinstance(item, dict):
        raise LibrarySyncError(f"Malformed image record in {volume['id']}")
    raw_path = _safe_path(item.get("path"))
    prefix = PurePosixPath(volume["images_path"].rstrip("/"))
    try:
        relative = raw_path.relative_to(prefix)
    except ValueError as exc:
        raise LibrarySyncError(f"Image path is outside {volume['id']} image root") from exc
    if len(relative.parts) != 2:
        raise LibrarySyncError("Each image must be directly inside a category directory")
    category = relative.parts[0]
    if category not in CATEGORY_TARGETS:
        raise LibrarySyncError(f"Unknown gallery category: {category}")
    digest = item.get("sha256")
    if not isinstance(digest, str) or not SHA_RE.fullmatch(digest):
        raise LibrarySyncError("Invalid image SHA-256")
    if relative.stem != digest:
        raise LibrarySyncError("Image filename must be its lowercase SHA-256 digest")
    size = item.get("file_size_bytes")
    if type(size) is not int or not 1 <= size <= min(MAX_IMAGE_BYTES, policy.get("max_image_bytes", MAX_IMAGE_BYTES)):
        raise LibrarySyncError(f"Invalid or oversized image byte length: {relative}")
    mime = item.get("mime_type")
    extensions = {"image/jpeg": {".jpg", ".jpeg"}, "image/png": {".png"}, "image/webp": {".webp"}}
    if mime not in extensions or relative.suffix.lower() not in extensions[mime]:
        raise LibrarySyncError(f"Image extension and MIME type do not agree: {relative}")
    width, height = item.get("width"), item.get("height")
    if type(width) is not int or type(height) is not int or width < MIN_WIDTH or height < MIN_HEIGHT or width <= height:
        raise LibrarySyncError(f"Image does not meet landscape resolution requirement: {relative}")

    license_id = " ".join(str(item.get("license_identifier", "")).strip().lower().split())
    if license_id not in ALLOWED_LICENSES:
        raise LibrarySyncError(f"Unapproved license label for {relative}: {license_id!r}")
    approval = item.get("publication_approval")
    if not isinstance(approval, dict) or approval.get("approved") is not True:
        raise LibrarySyncError(f"Missing explicit public publication approval for {relative}")
    for key in ("reviewer", "reviewed_at", "evidence_url"):
        if not isinstance(approval.get(key), str) or not approval[key].strip():
            raise LibrarySyncError(f"Publication approval is missing {key} for {relative}")
    evidence_url = approval["evidence_url"]
    if not evidence_url.startswith("https://"):
        raise LibrarySyncError(f"Publication evidence URL must use HTTPS for {relative}")
    for key in ("title", "creator", "source", "source_page", "attribution", "license_url"):
        if not isinstance(item.get(key), str) or not item[key].strip():
            raise LibrarySyncError(f"Manifest item is missing required provenance field {key}: {relative}")
    if not item["source_page"].startswith("https://") or not item["license_url"].startswith("https://"):
        raise LibrarySyncError(f"Provenance URLs must use HTTPS for {relative}")
    colors = item.get("dominant_colors")
    if not isinstance(colors, list) or not colors:
        raise LibrarySyncError(f"Manifest item has no dominant color metadata: {relative}")
    return {
        **item,
        "path": raw_path.as_posix(),
        "relative_path": relative.as_posix(),
        "category": category,
    }


def fetch_inventory(*, opener: Callable = urllib.request.urlopen) -> tuple[dict, list[dict]]:
    registry = _json_bytes(REGISTRY_URL, opener=opener)
    volumes = _validate_registry(registry)
    all_items: list[dict] = []
    seen_hashes: set[str] = set()
    counts = {category: 0 for category in CATEGORY_TARGETS}
    manifest_records = 0
    for volume in volumes:
        url = _raw_url(volume["repository"], volume["branch"], volume["manifest_path"])
        manifest = _json_bytes(url, opener=opener)
        if manifest.get("schema") != MANIFEST_SCHEMA:
            raise LibrarySyncError(f"Unsupported manifest schema in {volume['id']}")
        if manifest.get("volume_id") != volume["id"]:
            raise LibrarySyncError(f"Volume ID mismatch in {volume['id']} manifest")
        items = manifest.get("items")
        count = manifest.get("count")
        if not isinstance(items, list) or type(count) is not int or count != len(items):
            raise LibrarySyncError(f"Manifest count mismatch in {volume['id']}")
        manifest_records += count
        for raw in items:
            item = _validate_item(raw, volume, registry["policy"])
            if item["sha256"] in seen_hashes:
                raise LibrarySyncError(f"Duplicate image content hash across volumes: {item['sha256']}")
            seen_hashes.add(item["sha256"])
            counts[item["category"]] += 1
            item["volume_id"] = volume["id"]
            item["repository"] = volume["repository"]
            item["branch"] = volume["branch"]
            all_items.append(item)

    population = registry["population"]
    complete = (
        population.get("state") == "complete"
        and len(all_items) == TARGET
        and counts == CATEGORY_TARGETS
        and len(seen_hashes) == TARGET
    )
    inventory = {
        "generation": registry.get("generation"),
        "target": TARGET,
        "manifest_records": manifest_records,
        "unique_images": len(seen_hashes),
        "active_volumes": [v["id"] for v in volumes],
        "category_counts": counts,
        "category_targets": CATEGORY_TARGETS,
        "complete": complete,
        "population_state": population.get("state"),
    }
    return inventory, all_items


def _safe_destination(path: Path) -> None:
    resolved = path.expanduser()
    if str(resolved) == "/mnt/storage" or str(resolved).startswith("/mnt/storage/"):
        raise LibrarySyncError("Wallpaper destinations under /mnt/storage are protected")
    current = resolved
    while current != current.parent:
        if current.is_symlink():
            raise LibrarySyncError(f"Wallpaper destination contains a symbolic link: {current}")
        current = current.parent
    if resolved.exists() and resolved.is_symlink():
        raise LibrarySyncError("Wallpaper destination must not be a symbolic link")


def _free_bytes(path: Path) -> int:
    probe = path
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return shutil.disk_usage(probe).free


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _verify_image(path: Path, item: dict) -> None:
    try:
        from PIL import Image
        from .theme import classify_rgb
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"}:
                raise LibrarySyncError(f"Unsupported decoded image format: {path}")
            if image.size != (item["width"], item["height"]):
                raise LibrarySyncError(f"Decoded image dimensions mismatch: {path}")
            sample = image.convert("RGB").resize((64, 64))
            quantized = sample.quantize(colors=8).convert("RGB")
            palette = quantized.getcolors(maxcolors=4096) or []
            families = set()
            for _count, pixel in palette:
                families.add(classify_rgb(*pixel))
            blocked = families & EXCLUDED_FAMILIES
            if blocked:
                raise LibrarySyncError(
                    f"Decoded pixels contain excluded dominant color families {sorted(blocked)}: {path}"
                )
    except LibrarySyncError:
        raise
    except Exception as exc:
        raise LibrarySyncError(f"Could not decode or inspect image {path}: {exc}") from exc


def _download(item: dict, destination: Path, state_dir: Path, *, opener: Callable = urllib.request.urlopen) -> None:
    target = destination / item["relative_path"]
    _safe_destination(target)
    if target.exists():
        if target.is_file() and target.stat().st_size == item["file_size_bytes"] and _sha256(target) == item["sha256"]:
            _verify_image(target, item)
            return
        raise LibrarySyncError(f"Refusing to overwrite a conflicting existing file: {target}")

    target.parent.mkdir(parents=True, exist_ok=True)
    partial = state_dir / f"{item['sha256']}.part"
    state_dir.mkdir(parents=True, exist_ok=True)
    existing = partial.stat().st_size if partial.exists() else 0
    if existing > item["file_size_bytes"]:
        partial.unlink()
        existing = 0
    url = _raw_url(item["repository"], item["branch"], item["path"])
    headers = {"User-Agent": "Fenrir-Desktop-Wallpaper-Library/2"}
    if existing:
        headers["Range"] = f"bytes={existing}-"
    request = urllib.request.Request(url, headers=headers)
    try:
        response = opener(request, timeout=90)
        status = getattr(response, "status", response.getcode())
        if existing and status == 206:
            mode = "ab"
        else:
            mode = "wb"
            existing = 0
        with response, partial.open(mode) as stream:
            total = existing
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > item["file_size_bytes"] or total > MAX_IMAGE_BYTES:
                    raise LibrarySyncError(f"Transfer exceeded the declared image size: {target}")
                stream.write(chunk)
            stream.flush()
            os.fsync(stream.fileno())
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        raise LibrarySyncError(f"Image transfer interrupted and retained for resume: {target}: {exc}") from exc

    if partial.stat().st_size != item["file_size_bytes"]:
        raise LibrarySyncError(f"Downloaded image has the wrong byte size; partial retained: {target}")
    if _sha256(partial) != item["sha256"]:
        raise LibrarySyncError(f"Downloaded image failed SHA-256 verification: {target}")
    _verify_image(partial, item)
    if target.exists():
        raise LibrarySyncError(f"Target appeared during transfer; refusing to overwrite: {target}")
    os.replace(partial, target)


def sync_library(
    *,
    dry_run: bool = False,
    destination: Path | None = None,
    state_dir: Path | None = None,
    opener: Callable = urllib.request.urlopen,
    allow_incomplete: bool = False,
) -> dict:
    destination = (destination or Path.home() / "Pictures" / "Wallpapers").expanduser()
    state_dir = (state_dir or Path.home() / ".local/state/fenrir/wallpaper-sync").expanduser()
    _safe_destination(destination)
    _safe_destination(state_dir)

    inventory, items = fetch_inventory(opener=opener)
    if not inventory["complete"] and not dry_run and not allow_incomplete:
        raise LibrarySyncError(
            "The public 5,000-image generation is not complete. No images were downloaded."
        )

    already_present = 0
    planned_bytes = 0
    missing: list[dict] = []
    for item in items:
        target = destination / item["relative_path"]
        _safe_destination(target)
        if target.exists():
            if target.is_file() and target.stat().st_size == item["file_size_bytes"] and _sha256(target) == item["sha256"]:
                already_present += 1
            else:
                raise LibrarySyncError(f"Refusing to overwrite conflicting existing wallpaper: {target}")
        else:
            missing.append(item)
            planned_bytes += item["file_size_bytes"]

    dest_free = _free_bytes(destination)
    state_free = _free_bytes(state_dir)
    required = planned_bytes + 32 * 1024 * 1024
    storage = {
        "destination_available_bytes": dest_free,
        "destination_required_bytes": planned_bytes,
        "state_available_bytes": state_free,
        "state_required_bytes": planned_bytes,
        "sufficient": dest_free >= required and state_free >= required,
    }
    report = {
        "dry_run": dry_run,
        **inventory,
        "planned_downloads": len(missing),
        "already_present": already_present,
        "selected_download_bytes": planned_bytes,
        "remaining_after_limit": 0,
        "storage_preflight": storage,
        "downloaded": 0,
        "failed": 0,
    }
    if not dry_run:
        if not storage["sufficient"]:
            raise LibrarySyncError(
                "Insufficient storage for the complete public library. "
                f"Destination {dest_free} free / {planned_bytes} required; "
                f"resumable state {state_free} free / {planned_bytes} required."
            )
        destination.mkdir(parents=True, exist_ok=True)
        for item in missing:
            try:
                _download(item, destination, state_dir, opener=opener)
                report["downloaded"] += 1
            except Exception:
                report["failed"] += 1
                raise

        final_missing = 0
        for item in items:
            target = destination / item["relative_path"]
            if not target.is_file() or target.stat().st_size != item["file_size_bytes"] or _sha256(target) != item["sha256"]:
                final_missing += 1
        report["final_missing"] = final_missing
        if final_missing != 0:
            raise LibrarySyncError(f"Final wallpaper inventory still has {final_missing} missing or invalid images")
    return report


def audit_library(*, opener: Callable = urllib.request.urlopen) -> dict:
    inventory, _items = fetch_inventory(opener=opener)
    return {"audit": "manifest-only", **inventory}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fenrir-wallpaper")
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit-library", help="validate the public registry and manifests")
    audit.add_argument("--json", action="store_true")

    sync = sub.add_parser("sync-library", help="verify and synchronize every active public image")
    sync.add_argument("--dry-run", action="store_true")
    sync.add_argument("--json", action="store_true")
    sync.add_argument("--directory", type=Path)
    sync.add_argument("--state-dir", type=Path)
    sync.add_argument("--allow-incomplete", action="store_true", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "audit-library":
            report = audit_library()
        else:
            report = sync_library(
                dry_run=args.dry_run,
                destination=args.directory,
                state_dir=args.state_dir,
                allow_incomplete=args.allow_incomplete,
            )
        print(json.dumps(report, indent=2) if args.json else report)
        return 0
    except (LibrarySyncError, OSError, ValueError) as exc:
        print(f"Fenrir wallpaper error: {exc}", file=__import__("sys").stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
