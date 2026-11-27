#!/usr/bin/env python3
"""Registry-driven, integrity-checked synchronization of Fenrir's public wallpaper volumes."""
from __future__ import annotations

import colorsys
import fcntl
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import re
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Callable

REGISTRY_URL = (
    "https://raw.githubusercontent.com/sunxsaturn/Fenrir-Wallpapers/"
    "main/manifest/volumes.json"
)
HUB_REPOSITORY = "sunxsaturn/Fenrir-Wallpapers"
REGISTRY_SCHEMA = "org.fenrir.wallpaper-library-volumes.v1"
MANIFEST_SCHEMA = "org.fenrir.public-wallpapers.index.v1"
USER_AGENT = "Fenrir-Desktop-Wallpaper-Library/1.0"
MAX_JSON_BYTES = 64 * 1024 * 1024
MAX_IMAGE_BYTES = 100 * 1024 * 1024
MIN_WIDTH = 2560
MIN_HEIGHT = 1440
MIME_EXTENSIONS = {
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "image/webp": {".webp"},
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
VOLUME_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]{1,128}$")
CATEGORY_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,95}$")


class LibrarySyncError(RuntimeError):
    """Raised when a public library registry or manifest is unsafe or invalid."""


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise LibrarySyncError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _decode_json(payload: bytes, source: str) -> dict:
    if len(payload) > MAX_JSON_BYTES:
        raise LibrarySyncError(f"{source} exceeds the {MAX_JSON_BYTES} byte metadata limit")
    try:
        value = json.loads(payload.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LibrarySyncError(f"{source} is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise LibrarySyncError(f"{source} must contain a JSON object")
    return value


def _request(url: str, *, timeout: int, opener: Callable) :
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json, image/*;q=0.9, */*;q=0.1",
        },
    )
    return opener(request, timeout=timeout)


def _fetch_json(url: str, *, timeout: int, opener: Callable, label: str) -> dict:
    try:
        with _request(url, timeout=timeout, opener=opener) as response:
            payload = response.read(MAX_JSON_BYTES + 1)
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        raise LibrarySyncError(f"Could not fetch {label}: {exc}") from exc
    return _decode_json(payload, label)


def _raw_url(repository: str, branch: str, path: str) -> str:
    encoded_branch = urllib.parse.quote(branch, safe="/")
    encoded_path = urllib.parse.quote(path, safe="/")
    return f"https://raw.githubusercontent.com/{repository}/{encoded_branch}/{encoded_path}"


def _safe_relative_path(raw: object, images_path: str) -> tuple[str, str]:
    if not isinstance(raw, str) or not raw or "\\" in raw or raw.startswith("/"):
        raise LibrarySyncError("Manifest contains an unsafe image path")
    path = PurePosixPath(raw)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise LibrarySyncError(f"Manifest contains path traversal: {raw!r}")
    prefix = PurePosixPath(images_path.rstrip("/"))
    try:
        relative = path.relative_to(prefix)
    except ValueError as exc:
        raise LibrarySyncError(f"Image path is outside the registered image root: {raw!r}") from exc
    if len(relative.parts) < 2:
        raise LibrarySyncError(f"Image path must contain a category directory: {raw!r}")
    category = relative.parts[0]
    if not CATEGORY_RE.fullmatch(category):
        raise LibrarySyncError(f"Invalid wallpaper category directory: {category!r}")
    suffix = Path(relative.name).suffix.lower()
    return relative.as_posix(), suffix


def _validate_registry(registry: dict) -> list[dict]:
    if registry.get("schema") != REGISTRY_SCHEMA:
        raise LibrarySyncError("The Fenrir volume registry schema is unsupported")
    if registry.get("library_id") != "fenrir-wallpapers":
        raise LibrarySyncError("The volume registry identifies an unexpected library")
    if registry.get("hub_repository") != HUB_REPOSITORY:
        raise LibrarySyncError("The volume registry points to an unexpected hub repository")
    volumes = registry.get("volumes")
    if not isinstance(volumes, list) or not volumes:
        raise LibrarySyncError("The volume registry has no volumes")
    active = []
    seen_ids = set()
    for volume in volumes:
        if not isinstance(volume, dict):
            raise LibrarySyncError("The volume registry contains a malformed volume")
        if volume.get("active") is not True:
            continue
        volume_id = volume.get("id")
        repository = volume.get("repository")
        branch = volume.get("branch")
        images_path = volume.get("images_path")
        manifest_path = volume.get("manifest_path")
        if not isinstance(volume_id, str) or not VOLUME_ID_RE.fullmatch(volume_id):
            raise LibrarySyncError("The volume registry contains an invalid volume ID")
        if volume_id in seen_ids:
            raise LibrarySyncError(f"Duplicate volume ID: {volume_id}")
        seen_ids.add(volume_id)
        if not isinstance(repository, str) or not REPOSITORY_RE.fullmatch(repository):
            raise LibrarySyncError(f"Invalid repository for volume {volume_id}")
        if not isinstance(branch, str) or not BRANCH_RE.fullmatch(branch) or ".." in branch.split("/"):
            raise LibrarySyncError(f"Invalid branch for volume {volume_id}")
        if not isinstance(images_path, str) or not images_path.endswith("/") or "\\" in images_path:
            raise LibrarySyncError(f"Invalid image root for volume {volume_id}")
        _safe_registry_path(images_path.rstrip("/"))
        if not isinstance(manifest_path, str) or not manifest_path:
            raise LibrarySyncError(f"Invalid manifest path for volume {volume_id}")
        _safe_registry_path(manifest_path)
        manifest_url = _raw_url(repository, branch, manifest_path)
        advertised_url = volume.get("manifest_url")
        if advertised_url is not None and advertised_url != manifest_url:
            raise LibrarySyncError(f"Manifest URL does not match the registered repository for {volume_id}")
        active.append({
            "id": volume_id,
            "repository": repository,
            "branch": branch,
            "images_path": images_path,
            "manifest_path": manifest_path,
            "manifest_url": manifest_url,
            "acquisition_enabled": volume.get("acquisition_enabled") is True,
            "status": str(volume.get("status", "unknown")),
        })
    if not active:
        raise LibrarySyncError("The volume registry has no active image volumes")
    return active


def _safe_registry_path(value: str) -> None:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise LibrarySyncError(f"Unsafe repository path in volume registry: {value!r}")


def _validate_manifest(manifest: dict, volume: dict) -> list[dict]:
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise LibrarySyncError(f"Unsupported manifest schema in {volume['id']}")
    items = manifest.get("items")
    count = manifest.get("count")
    if not isinstance(items, list) or type(count) is not int or count != len(items):
        raise LibrarySyncError(f"Manifest count does not match its item list in {volume['id']}")
    if len(items) > 100_000:
        raise LibrarySyncError(f"Manifest in {volume['id']} exceeds the 100,000 item safety limit")
    seen_paths = set()
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            raise LibrarySyncError(f"Malformed image record in {volume['id']}")
        relative, suffix = _safe_relative_path(item.get("path"), volume["images_path"])
        if relative in seen_paths:
            raise LibrarySyncError(f"Duplicate image path in {volume['id']}: {relative}")
        seen_paths.add(relative)
        digest = item.get("sha256")
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            raise LibrarySyncError(f"Invalid SHA-256 in {volume['id']}: {relative}")
        size = item.get("file_size_bytes")
        if type(size) is not int or not 1 <= size <= MAX_IMAGE_BYTES:
            raise LibrarySyncError(f"Invalid or oversized image length in {volume['id']}: {relative}")
        mime = item.get("mime_type")
        if not isinstance(mime, str) or suffix not in MIME_EXTENSIONS.get(mime, set()):
            raise LibrarySyncError(f"Image extension and MIME type disagree in {volume['id']}: {relative}")
        normalized.append({
            "volume": volume,
            "relative_path": relative,
            "sha256": digest,
            "size": size,
            "mime_type": mime,
            "record": item,
            "url": _raw_url(volume["repository"], volume["branch"], f"{volume['images_path']}{relative}"),
        })
    return normalized


def _assert_no_symlink_components(path: Path) -> None:
    absolute = Path(os.path.abspath(path.expanduser()))
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current = current / component
        try:
            if current.is_symlink():
                raise LibrarySyncError(f"Refusing a path that contains a symbolic link: {current}")
        except OSError as exc:
            raise LibrarySyncError(f"Cannot inspect path component {current}: {exc}") from exc


def _validate_destination(destination: Path, *, create: bool) -> Path:
    destination = destination.expanduser()
    if not destination.is_absolute():
        destination = Path.cwd() / destination
    destination = Path(os.path.abspath(destination))
    if destination == Path("/mnt/storage") or Path("/mnt/storage") in destination.parents:
        raise LibrarySyncError("Public library synchronization is not allowed inside /mnt/storage")
    _assert_no_symlink_components(destination)
    if destination.exists() and not destination.is_dir():
        raise LibrarySyncError(f"Wallpaper destination is not a directory: {destination}")
    if create:
        destination.mkdir(parents=True, exist_ok=True)
        _assert_no_symlink_components(destination)
    return destination


def _state_root() -> Path:
    configured = os.environ.get("XDG_STATE_HOME")
    root = Path(configured).expanduser() if configured else Path.home() / ".local/state"
    return root / "fenrir" / "public-library-sync"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _local_hash_index(destination: Path) -> dict[str, list[Path]]:
    found: dict[str, list[Path]] = {}
    if not destination.is_dir():
        return found
    for parent, directories, filenames in os.walk(destination, followlinks=False):
        parent_path = Path(parent)
        directories[:] = [
            name for name in directories
            if not (parent_path / name).is_symlink()
        ]
        for filename in filenames:
            path = parent_path / filename
            if path.is_symlink() or path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                continue
            candidate = path.stem.lower()
            if SHA256_RE.fullmatch(candidate):
                found.setdefault(candidate, []).append(path)
    return found


@lru_cache(maxsize=1)
def _image_inspector():
    script = Path(__file__).with_name("fenrir-wallpaper")
    if not script.is_file() or script.is_symlink():
        raise LibrarySyncError("The Fenrir wallpaper validator is missing")
    loader = importlib.machinery.SourceFileLoader("fenrir_wallpaper_validation", str(script))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise LibrarySyncError("Could not load the Fenrir wallpaper validator")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module.inspect_image


def _verify_image(path: Path, expected_mime: str, expected_size: int, expected_sha: str) -> dict:
    if path.stat().st_size != expected_size:
        raise LibrarySyncError("Downloaded image byte size does not match its manifest")
    if _sha256_file(path) != expected_sha:
        raise LibrarySyncError("Downloaded image SHA-256 does not match its manifest")
    details = _image_inspector()(path)
    if not isinstance(details, dict):
        raise LibrarySyncError("Downloaded image failed Fenrir's decoded-image validation")
    if details.get("width", 0) < MIN_WIDTH or details.get("height", 0) < MIN_HEIGHT:
        raise LibrarySyncError("Downloaded image is below Fenrir's minimum 2560×1440 resolution")
    if details.get("width", 0) <= details.get("height", 0):
        raise LibrarySyncError("Downloaded image is not landscape")
    if details.get("palette_eligible") is not True:
        raise LibrarySyncError("Downloaded image violates Fenrir's wallpaper palette policy")
    from PIL import Image
    with Image.open(path) as image:
        formats = {
            "image/jpeg": "JPEG",
            "image/png": "PNG",
            "image/webp": "WEBP",
        }
        if image.format != formats[expected_mime]:
            raise LibrarySyncError("Downloaded image format does not match its manifest MIME type")
    return details


def _metadata_entry(image: dict, relative_path: str) -> dict:
    source = image["record"]
    return {
        "path": relative_path,
        "sha256": image["sha256"],
        "file_size_bytes": image["size"],
        "mime_type": image["mime_type"],
        "title": source.get("title", ""),
        "creator": source.get("creator", ""),
        "credit": source.get("credit", ""),
        "attribution": source.get("attribution", ""),
        "source": source.get("source", ""),
        "source_page": source.get("source_page", ""),
        "license_identifier": source.get("license_identifier", ""),
        "license_url": source.get("license_url", ""),
        "repository": image["volume"]["repository"],
        "volume_id": image["volume"]["id"],
    }


def _merge_sidecar(existing: dict, image: dict, relative_path: str) -> None:
    digest = image["sha256"]
    entry = existing.setdefault("items", {}).setdefault(digest, {
        "sha256": digest,
        "paths": [],
        "provenance": [],
    })
    path_record = _metadata_entry(image, relative_path)
    if path_record not in entry["paths"]:
        entry["paths"].append(path_record)
    provenance = {
        key: path_record[key]
        for key in (
            "repository", "volume_id", "source", "source_page",
            "creator", "credit", "attribution",
            "license_identifier", "license_url",
        )
    }
    if provenance not in entry["provenance"]:
        entry["provenance"].append(provenance)


def _read_sidecar(destination: Path) -> dict:
    path = destination / ".fenrir-public-library-attribution.json"
    if not path.exists():
        return {"schema": "org.fenrir.public-wallpaper-attribution.v1", "items": {}}
    _assert_no_symlink_components(path)
    if not path.is_file():
        raise LibrarySyncError("Public-library attribution sidecar is not a regular file")
    try:
        content = path.read_bytes()
        value = _decode_json(content, "public-library attribution sidecar")
    except OSError as exc:
        raise LibrarySyncError(f"Cannot read public-library attribution sidecar: {exc}") from exc
    if value.get("schema") != "org.fenrir.public-wallpaper-attribution.v1":
        raise LibrarySyncError("Public-library attribution sidecar has an unknown schema")
    if not isinstance(value.get("items"), dict):
        raise LibrarySyncError("Public-library attribution sidecar has an invalid item map")
    return value


def _write_sidecar(destination: Path, value: dict) -> None:
    path = destination / ".fenrir-public-library-attribution.json"
    _assert_no_symlink_components(path)
    fd, temporary_name = tempfile.mkstemp(prefix=".fenrir-library-attribution-", dir=destination)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            os.fchmod(handle.fileno(), 0o600)
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass


def _install_without_overwrite(partial: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    _assert_no_symlink_components(target)
    if target.exists():
        raise LibrarySyncError(f"Refusing to overwrite an existing file: {target}")
    fd, temporary_name = tempfile.mkstemp(prefix=".fenrir-library-image-", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as output, partial.open("rb") as source:
            shutil.copyfileobj(source, output, length=1024 * 1024)
            output.flush()
            os.fsync(output.fileno())
            os.fchmod(output.fileno(), 0o644)
        # A hard-link creation is atomic and fails rather than replacing an existing user file.
        os.link(temporary_name, target)
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass


def _download_image(
    image: dict,
    *,
    state_dir: Path,
    destination: Path,
    timeout: int,
    opener: Callable,
) -> tuple[Path, str]:
    volume = image["volume"]
    cache = state_dir / volume["id"]
    _assert_no_symlink_components(cache)
    cache.mkdir(parents=True, exist_ok=True)
    partial = cache / f"{image['sha256']}.part"
    _assert_no_symlink_components(partial)
    if partial.exists() and (partial.is_symlink() or not partial.is_file()):
        raise LibrarySyncError(f"Unsafe resumable download file: {partial}")
    offset = partial.stat().st_size if partial.exists() else 0
    if offset > image["size"]:
        partial.unlink()
        offset = 0
    if offset == image["size"]:
        _verify_image(partial, image["mime_type"], image["size"], image["sha256"])
        target = destination / PurePosixPath(image["relative_path"])
        _assert_no_symlink_components(target)
        if target.exists():
            if target.is_file() and not target.is_symlink() and target.stat().st_size == image["size"] and _sha256_file(target) == image["sha256"]:
                partial.unlink(missing_ok=True)
                return target, "already_present"
            raise LibrarySyncError(f"Refusing to overwrite an existing file: {target}")
        _install_without_overwrite(partial, target)
        partial.unlink(missing_ok=True)
        return target, "downloaded"

    request = urllib.request.Request(
        image["url"],
        headers={
            "User-Agent": USER_AGENT,
            "Accept": image["mime_type"],
            **({"Range": f"bytes={offset}-"} if offset else {}),
        },
    )
    try:
        with opener(request, timeout=timeout) as response:
            status = getattr(response, "status", response.getcode())
            if offset and status == 206:
                content_range = response.headers.get("Content-Range", "")
                if not content_range.startswith(f"bytes {offset}-"):
                    raise LibrarySyncError("Server returned an invalid range for a resumable image")
                mode = "ab"
            elif status == 200:
                mode = "wb"
            else:
                raise LibrarySyncError(f"Unexpected HTTP status {status} while downloading an image")
            written = partial.stat().st_size if mode == "ab" and partial.exists() else 0
            with partial.open(mode) as output:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > image["size"] or written > MAX_IMAGE_BYTES:
                        raise LibrarySyncError("Image download exceeded its manifest byte-size limit")
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
    except LibrarySyncError:
        raise
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        # Keep partial bytes so the next invocation can resume with HTTP Range.
        raise LibrarySyncError(f"Image transfer failed and can be resumed: {exc}") from exc

    if not partial.exists() or partial.stat().st_size != image["size"]:
        actual = partial.stat().st_size if partial.exists() else 0
        raise LibrarySyncError(f"Incomplete image transfer: received {actual} of {image['size']} bytes")
    try:
        _verify_image(partial, image["mime_type"], image["size"], image["sha256"])
    except Exception:
        partial.unlink(missing_ok=True)
        raise

    target = destination / PurePosixPath(image["relative_path"])
    _assert_no_symlink_components(target)
    if target.exists():
        if target.is_file() and not target.is_symlink() and target.stat().st_size == image["size"] and _sha256_file(target) == image["sha256"]:
            partial.unlink(missing_ok=True)
            return target, "already_present"
        raise LibrarySyncError(f"Refusing to overwrite an existing file: {target}")
    _install_without_overwrite(partial, target)
    partial.unlink(missing_ok=True)
    return target, "downloaded"


def _manifest_palette_families(value: object) -> tuple[set[str], int]:
    """Classify supplied dominant-color hex values without fetching image bytes."""
    if not isinstance(value, list) or not value:
        return set(), 0
    families: set[str] = set()
    invalid = 0
    for raw in value:
        if not isinstance(raw, str):
            invalid += 1
            continue
        match = re.fullmatch(r"#?([0-9a-fA-F]{6})", raw.strip())
        if not match:
            invalid += 1
            continue
        encoded = match.group(1)
        red, green, blue = (
            int(encoded[index:index + 2], 16) / 255.0
            for index in (0, 2, 4)
        )
        hue, saturation, brightness = colorsys.rgb_to_hsv(red, green, blue)
        degrees = hue * 360.0
        if saturation < 0.16:
            if brightness <= 0.15:
                family = "black"
            elif brightness >= 0.86:
                family = "white"
            else:
                family = "neutral"
        elif 15.0 <= degrees < 45.0:
            family = "brown" if brightness <= 0.58 else "orange"
        elif 45.0 <= degrees < 72.0:
            family = "yellow"
        elif 72.0 <= degrees < 165.0:
            family = "green"
        elif 165.0 <= degrees < 195.0:
            family = "cyan"
        elif 195.0 <= degrees < 260.0:
            family = "blue"
        elif 260.0 <= degrees < 330.0:
            family = "purple"
        else:
            family = "red"
        families.add(family)
    return families, invalid


def _license_classification(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        return "missing"
    normalized = value.casefold().replace("_", " ").replace("-", " ")
    if (
        re.search(r"\\b(?:nc|nd)\\b", normalized)
        or "noncommercial" in normalized
        or "non commercial" in normalized
        or "no derivative" in normalized
        or "all rights reserved" in normalized
    ):
        return "excluded"
    if "public domain" in normalized or "cc0" in normalized or "cc 0" in normalized:
        return "permitted_family"
    if "cc by" in normalized or "creative commons attribution" in normalized:
        return "permitted_family"
    return "manual_review"


def audit_public_library(
    *,
    registry_url: str = REGISTRY_URL,
    opener: Callable | None = None,
    timeout: int = 45,
) -> dict:
    """Audit all active public manifests and GitHub repository metadata, never image bytes."""
    if type(timeout) is not int or not 5 <= timeout <= 300:
        raise LibrarySyncError("Network timeout must be between 5 and 300 seconds")
    opener = opener or urllib.request.urlopen
    registry = _fetch_json(
        registry_url, timeout=timeout, opener=opener, label="Fenrir volume registry"
    )
    volumes = _validate_registry(registry)
    volume_reports: list[dict] = []
    category_counts: dict[str, int] = {}
    metadata_gaps = {
        field: 0 for field in (
            "title", "creator", "credit", "attribution",
            "source", "source_page", "license_identifier", "license_url",
        )
    }
    palette_families: dict[str, int] = {}
    license_counts = {
        "permitted_family": 0,
        "excluded": 0,
        "manual_review": 0,
        "missing": 0,
    }
    seen_hashes: dict[str, dict] = {}
    duplicate_samples: list[dict] = []
    hash_metadata_conflicts = 0
    hash_path_mismatches = 0
    below_desktop_resolution = 0
    invalid_dimensions = 0
    palette_missing = 0
    palette_invalid = 0
    palette_excluded = 0
    palette_preferred = 0
    palette_green_only = 0
    source_page_invalid = 0
    manifest_records = 0
    manifested_bytes = 0
    policy = registry.get("policy")
    policy = policy if isinstance(policy, dict) else {}
    storage_limit = policy.get("github_repository_size_safety_limit_bytes")
    if type(storage_limit) is not int or storage_limit < 1:
        storage_limit = None

    for volume in volumes:
        manifest = _fetch_json(
            volume["manifest_url"], timeout=timeout, opener=opener,
            label=f"volume {volume['id']} manifest",
        )
        images = _validate_manifest(manifest, volume)
        volume_categories: dict[str, int] = {}
        volume_bytes = 0
        volume_palette_missing = 0
        volume_palette_excluded = 0
        volume_license_issues = 0

        for image in images:
            record = image["record"]
            digest = image["sha256"]
            volume_bytes += image["size"]
            manifested_bytes += image["size"]
            manifest_records += 1
            category = image["relative_path"].split("/", 1)[0]
            category_counts[category] = category_counts.get(category, 0) + 1
            volume_categories[category] = volume_categories.get(category, 0) + 1

            filename = PurePosixPath(image["relative_path"]).name
            if PurePosixPath(filename).stem != digest:
                hash_path_mismatches += 1

            width, height = record.get("width"), record.get("height")
            if (
                isinstance(width, bool) or not isinstance(width, int)
                or isinstance(height, bool) or not isinstance(height, int)
                or width < 1 or height < 1
            ):
                invalid_dimensions += 1
            elif width < MIN_WIDTH or height < MIN_HEIGHT or width <= height:
                below_desktop_resolution += 1

            for field in metadata_gaps:
                value = record.get(field)
                if not isinstance(value, str) or not value.strip():
                    metadata_gaps[field] += 1
            source_page = record.get("source_page")
            if isinstance(source_page, str) and source_page.strip():
                parsed_source = urllib.parse.urlparse(source_page)
                if parsed_source.scheme != "https" or not parsed_source.netloc:
                    source_page_invalid += 1

            families, invalid_colors = _manifest_palette_families(record.get("dominant_colors"))
            if not families:
                palette_missing += 1
                volume_palette_missing += 1
            palette_invalid += invalid_colors
            for family in families:
                palette_families[family] = palette_families.get(family, 0) + 1
            if families.intersection({"yellow", "orange", "brown"}):
                palette_excluded += 1
                volume_palette_excluded += 1
            elif families:
                if families.intersection({"red", "purple", "blue", "white", "black"}):
                    palette_preferred += 1
                elif families == {"green"}:
                    palette_green_only += 1

            license_status = _license_classification(record.get("license_identifier"))
            license_counts[license_status] += 1
            if license_status != "permitted_family":
                volume_license_issues += 1

            previous = seen_hashes.get(digest)
            if previous is not None:
                if previous["size"] != image["size"] or previous["mime_type"] != image["mime_type"]:
                    hash_metadata_conflicts += 1
                if len(duplicate_samples) < 100:
                    duplicate_samples.append({
                        "sha256": digest,
                        "first_volume": previous["volume_id"],
                        "duplicate_volume": volume["id"],
                        "path": image["relative_path"],
                    })
            else:
                seen_hashes[digest] = {
                    "volume_id": volume["id"],
                    "size": image["size"],
                    "mime_type": image["mime_type"],
                }

        storage_report = {
            "api_reported_size_kib": None,
            "api_reported_size_bytes": None,
            "safety_limit_bytes": storage_limit,
            "headroom_bytes": None,
            "status": "unknown",
            "detail": "GitHub repository size was not retrieved.",
        }
        api_url = f"https://api.github.com/repos/{volume['repository']}"
        try:
            repository_metadata = _fetch_json(
                api_url,
                timeout=timeout,
                opener=opener,
                label=f"GitHub repository metadata for {volume['id']}",
            )
            size_kib = repository_metadata.get("size")
            if isinstance(size_kib, bool) or not isinstance(size_kib, int) or size_kib < 0:
                raise LibrarySyncError("GitHub repository metadata has an invalid size value")
            size_bytes = size_kib * 1024
            headroom = max(0, storage_limit - size_bytes) if storage_limit else None
            if storage_limit is None:
                storage_status = "limit_not_configured"
            elif size_bytes > storage_limit:
                storage_status = "over_safety_limit"
            else:
                storage_status = "within_safety_limit"
            storage_report = {
                "api_reported_size_kib": size_kib,
                "api_reported_size_bytes": size_bytes,
                "safety_limit_bytes": storage_limit,
                "headroom_bytes": headroom,
                "status": storage_status,
                "detail": "GitHub API repository size in KiB, converted to bytes; approximate storage indicator.",
            }
        except (LibrarySyncError, OSError, urllib.error.URLError, TimeoutError) as exc:
            storage_report["detail"] = str(exc)[:200]

        volume_reports.append({
            "id": volume["id"],
            "repository": volume["repository"],
            "status": volume["status"],
            "acquisition_enabled": volume["acquisition_enabled"],
            "image_count": len(images),
            "manifest_updated_at": manifest.get("updated_at"),
            "manifested_image_bytes": volume_bytes,
            "category_counts": dict(sorted(volume_categories.items())),
            "palette_missing": volume_palette_missing,
            "palette_excluded": volume_palette_excluded,
            "license_review_or_exclusion": volume_license_issues,
            "storage": storage_report,
        })

    registered = registry.get("volumes", [])
    registered_count = len(registered) if isinstance(registered, list) else len(volumes)
    acquisition_enabled = any(item["acquisition_enabled"] for item in volumes)
    all_registered_active = registered_count == len(volumes)
    duplicate_count = manifest_records - len(seen_hashes)
    population = registry.get("population")
    population = population if isinstance(population, dict) else {}
    population_closed = (
        not acquisition_enabled
        and all_registered_active
        and population.get("state") == "closed"
    )
    category_values = list(category_counts.values())
    category_balance = {
        "category_count": len(category_values),
        "minimum_images": min(category_values) if category_values else 0,
        "maximum_images": max(category_values) if category_values else 0,
        "spread": max(category_values) - min(category_values) if category_values else 0,
        "counts": dict(sorted(category_counts.items())),
        "note": "Observed distribution only; there is no equalization target.",
    }
    palette_report = {
        "family_record_counts": dict(sorted(palette_families.items())),
        "missing_records": palette_missing,
        "invalid_color_values": palette_invalid,
        "excluded_yellow_orange_brown_records": palette_excluded,
        "preferred_family_records": palette_preferred,
        "green_only_records": palette_green_only,
        "note": "Classified from manifest dominant_colors metadata only; actual pixels are checked when image bytes are downloaded.",
    }
    storage_over_limit = sum(
        1 for volume in volume_reports
        if volume["storage"]["status"] == "over_safety_limit"
    )
    storage_unavailable = sum(
        1 for volume in volume_reports
        if volume["storage"]["status"] == "unknown"
    )
    structural_issues = (
        duplicate_count + hash_metadata_conflicts + hash_path_mismatches
        + invalid_dimensions + below_desktop_resolution + palette_missing
        + palette_invalid + palette_excluded + source_page_invalid
        + license_counts["excluded"] + license_counts["manual_review"]
        + license_counts["missing"]
        + sum(metadata_gaps.values())
        + storage_over_limit
    )
    return {
        "report": "org.fenrir.public-wallpaper-library-audit",
        "report_version": 1,
        "population_state": "closed" if population_closed else "open",
        "audit_status": "clean" if structural_issues == 0 else "review_required",
        "no_fixed_image_target": population.get("fixed_image_count_target") is None,
        "fixed_image_count_target": None,
        "registered_volume_count": registered_count,
        "active_volume_count": len(volumes),
        "acquisition_enabled": acquisition_enabled,
        "volumes": volume_reports,
        "manifest_records": manifest_records,
        "unique_images": len(seen_hashes),
        "duplicate_records": duplicate_count,
        "hash_metadata_conflicts": hash_metadata_conflicts,
        "duplicate_samples": duplicate_samples,
        "hash_path_mismatches": hash_path_mismatches,
        "invalid_dimensions": invalid_dimensions,
        "below_desktop_resolution": below_desktop_resolution,
        "manifested_image_bytes": manifested_bytes,
        "category_counts": dict(sorted(category_counts.items())),
        "category_balance": category_balance,
        "metadata_missing_counts": metadata_gaps,
        "metadata_fields_with_gaps": [field for field, value in metadata_gaps.items() if value],
        "source_page_invalid": source_page_invalid,
        "license_counts": license_counts,
        "license_review_or_exclusion": (
            license_counts["excluded"] + license_counts["manual_review"] + license_counts["missing"]
        ),
        "palette": palette_report,
        "storage_safety_limit_bytes": storage_limit,
        "repositories_over_storage_limit": storage_over_limit,
        "repositories_storage_unknown": storage_unavailable,
        "read_only": True,
        "downloads_started": 0,
        "image_bytes_fetched": 0,
        "files_modified": False,
        "local_files_inspected": False,
        "note": (
            "Audit reads the live registry, committed manifests and GitHub repository metadata only. "
            "It does not fetch wallpaper bytes or inspect the local directory. Manifest colors are metadata hints; "
            "pixel-level palette and exact SHA-256 checks happen during desktop sync."
        ),
    }


def sync_public_library(
    *,
    destination: Path,
    dry_run: bool = False,
    limit: int | None = None,
    timeout: int = 45,
    registry_url: str = REGISTRY_URL,
    opener: Callable | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict:
    """Synchronize every active registered volume into one wallpaper directory."""
    if limit is not None and (type(limit) is not int or limit < 1):
        raise LibrarySyncError("--limit must be a positive integer")
    if type(timeout) is not int or not 5 <= timeout <= 300:
        raise LibrarySyncError("Network timeout must be between 5 and 300 seconds")
    opener = opener or urllib.request.urlopen
    progress = progress or (lambda _message: None)
    root = _validate_destination(Path(destination), create=False)

    registry = _fetch_json(registry_url, timeout=timeout, opener=opener, label="Fenrir volume registry")
    volumes = _validate_registry(registry)
    all_images = []
    for volume in volumes:
        manifest = _fetch_json(
            volume["manifest_url"], timeout=timeout, opener=opener,
            label=f"volume {volume['id']} manifest",
        )
        all_images.extend(_validate_manifest(manifest, volume))

    # Content hashes are globally unique; retain every source's attribution but fetch each hash once.
    unique: dict[str, dict] = {}
    for image in all_images:
        existing = unique.get(image["sha256"])
        if existing is None:
            unique[image["sha256"]] = image
        else:
            if existing["size"] != image["size"] or existing["mime_type"] != image["mime_type"]:
                raise LibrarySyncError(f"Conflicting metadata for duplicate SHA-256 {image['sha256']}")
            existing.setdefault("duplicates", []).append(image)

    local_hashes = _local_hash_index(root)
    sidecar = _read_sidecar(root) if not dry_run and root.exists() else {
        "schema": "org.fenrir.public-wallpaper-attribution.v1", "items": {}
    }
    pending = []
    already_present = 0
    already_bytes = 0
    for image in unique.values():
        digest = image["sha256"]
        matches = []
        for candidate in local_hashes.get(digest, []):
            if candidate.is_file() and not candidate.is_symlink():
                try:
                    if candidate.stat().st_size == image["size"] and _sha256_file(candidate) == digest:
                        matches.append(candidate)
                except OSError:
                    continue
        expected = root / PurePosixPath(image["relative_path"])
        if expected.is_file() and not expected.is_symlink() and expected not in matches:
            try:
                if expected.stat().st_size == image["size"] and _sha256_file(expected) == digest:
                    matches.append(expected)
            except OSError:
                pass
        if matches:
            already_present += 1
            already_bytes += image["size"]
            if not dry_run:
                for path in matches[:1]:
                    _merge_sidecar(sidecar, image, path.relative_to(root).as_posix())
                for duplicate in image.get("duplicates", []):
                    _merge_sidecar(sidecar, duplicate, matches[0].relative_to(root).as_posix())
        else:
            pending.append(image)

    total_pending = len(pending)
    to_process = pending[:limit] if limit is not None else pending
    planned_bytes = sum(item["size"] for item in to_process)
    result = {
        "registry": registry_url,
        "destination": str(root),
        "active_volumes": [volume["id"] for volume in volumes],
        "manifest_records": len(all_images),
        "unique_images": len(unique),
        "already_present": already_present,
        "already_present_bytes": already_bytes,
        "planned_downloads": total_pending,
        "selected_downloads": len(to_process),
        "selected_download_bytes": planned_bytes,
        "remaining_after_limit": total_pending - len(to_process),
        "downloaded": 0,
        "downloaded_bytes": 0,
        "failed": 0,
        "errors": [],
        "dry_run": dry_run,
    }
    if dry_run:
        return result

    root = _validate_destination(root, create=True)
    state_root = _state_root()
    _assert_no_symlink_components(state_root)
    state_root.mkdir(parents=True, exist_ok=True)
    _assert_no_symlink_components(state_root)
    lock_path = state_root / "sync.lock"
    _assert_no_symlink_components(lock_path)
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise LibrarySyncError("Another Fenrir public-library synchronization is already running") from exc
        try:
            for index, image in enumerate(to_process, start=1):
                progress(f"Downloading {index}/{len(to_process)}: {image['relative_path']}")
                try:
                    path, outcome = _download_image(
                        image, state_dir=state_root, destination=root,
                        timeout=timeout, opener=opener,
                    )
                    if outcome == "downloaded":
                        result["downloaded"] += 1
                        result["downloaded_bytes"] += image["size"]
                        result["already_present_bytes"] += 0
                    else:
                        result["already_present"] += 1
                    _merge_sidecar(sidecar, image, path.relative_to(root).as_posix())
                    for duplicate in image.get("duplicates", []):
                        _merge_sidecar(sidecar, duplicate, path.relative_to(root).as_posix())
                except Exception as exc:
                    result["failed"] += 1
                    if len(result["errors"]) < 100:
                        result["errors"].append({
                            "sha256": image["sha256"],
                            "path": image["relative_path"],
                            "error": str(exc)[:1000],
                        })
            _write_sidecar(root, sidecar)
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    return result
