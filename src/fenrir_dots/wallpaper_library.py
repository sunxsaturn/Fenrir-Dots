"""All-volume, integrity-checked public wallpaper synchronization for Fenrir."""
from __future__ import annotations

import fcntl
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

from PIL import Image

REGISTRY_URL = "https://raw.githubusercontent.com/sunxsaturn/Fenrir-Wallpapers/main/manifest/volumes.json"
REGISTRY_SCHEMA = "org.fenrir.wallpaper-library-volumes.v2"
MANIFEST_SCHEMA = "org.fenrir.public-wallpapers.index.v2"
LIBRARY_ID = "fenrir-wallpapers-v2"
MAX_IMAGE_BYTES = 100 * 1024 * 1024
MAX_IMAGE_PIXELS = 100_000_000
ALLOWED_MIME = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
USER_AGENT = "Fenrir-Desktop-Public-Library/2.0"
CATEGORY_IDS = {
    "nordic-landscapes", "medieval-landscapes", "fantasy", "epic-battles",
    "mountains", "astronomy", "planets", "knights-in-battle", "swords",
    "magic", "nordic-mythology",
}
PREFERRED = {"red", "purple", "blue", "white", "black", "violet"}
TOLERATED = {"green", "neutral", "pink"}
EXCLUDED = set()


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


class _RawGitHubRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        parsed = urllib.parse.urlparse(new_url)
        try:
            port = parsed.port
        except ValueError as exc:
            raise WallpaperSyncError("Gallery redirect contains an invalid port") from exc
        if (
            parsed.scheme != "https"
            or parsed.hostname != "raw.githubusercontent.com"
            or port not in (None, 443)
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise WallpaperSyncError("Gallery redirect outside the approved HTTPS origin was blocked")
        return super().redirect_request(request, file_pointer, code, message, headers, new_url)


def _request(url: str, *, opener: Callable, headers: dict[str, str] | None = None):
    parsed = urllib.parse.urlparse(url)
    try:
        port = parsed.port
    except ValueError as exc:
        raise WallpaperSyncError("Public gallery URL contains an invalid port") from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname != "raw.githubusercontent.com"
        or port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise WallpaperSyncError("Public gallery requests must use raw.githubusercontent.com over HTTPS")
    request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json, image/*"}
    request_headers.update(headers or {})
    request = urllib.request.Request(url, headers=request_headers)
    if opener is urllib.request.urlopen:
        return urllib.request.build_opener(_RawGitHubRedirect()).open(request, timeout=45)
    return opener(request, timeout=45)


def _response_url(response, expected: str) -> str:
    geturl = getattr(response, "geturl", None)
    return geturl() if callable(geturl) else expected


def _assert_raw_github_response(response, expected: str) -> None:
    final_url = _response_url(response, expected)
    parsed = urllib.parse.urlparse(final_url)
    expected_parsed = urllib.parse.urlparse(expected)
    try:
        port = parsed.port
    except ValueError as exc:
        raise WallpaperSyncError("Gallery response URL contains an invalid port") from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname != expected_parsed.hostname
        or port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise WallpaperSyncError("Gallery response escaped the approved raw.githubusercontent.com HTTPS origin")


def _fetch_json(url: str, opener: Callable) -> dict:
    try:
        with _request(url, opener=opener, headers={"Accept": "application/json"}) as response:
            _assert_raw_github_response(response, url)
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
    if not isinstance(repository, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise WallpaperSyncError("Invalid public gallery repository")
    if not isinstance(branch, str) or not branch or branch.startswith("/") or ".." in branch.split("/"):
        raise WallpaperSyncError("Invalid public gallery branch")
    if not isinstance(path, str) or not path or path.startswith("/") or ".." in PurePosixPath(path).parts:
        raise WallpaperSyncError("Invalid public gallery path")
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
    if (
        population.get("state") != "published"
        or population.get("target_unique_images") != 5000
        or population.get("published_unique_images") != 5000
        or population.get("unique_sha256_count") != 5000
        or population.get("legacy_images_reused") != 0
    ):
        raise WallpaperSyncError(
            "The 5000-image public library is incomplete, has non-unique SHA-256s, "
            "or reports legacy image reuse"
        )
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
        if not isinstance(path, str) or not path.startswith(volume["images_path"]) or "\\\\" in path:
            raise WallpaperSyncError("Image path is outside the registered images root")
        relative = PurePosixPath(path)
        if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
            raise WallpaperSyncError("Unsafe image path in manifest")
        if len(relative.parts) != 3 or relative.parts[0] != "images" or relative.parts[1] not in CATEGORY_IDS:
            raise WallpaperSyncError("Image path must be images/category/sha256.ext")
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
        if not all(item.get(field) for field in (
            "creator", "source_page", "rights_evidence_id", "source_terms_evidence_id"
        )):
            raise WallpaperSyncError("Missing creator, source, rights or source-terms evidence in image record")
        if not isinstance(item.get("source_page"), str) or not item["source_page"].startswith("https://"):
            raise WallpaperSyncError("Wallpaper source page must use HTTPS")
        width, height = item.get("width"), item.get("height")
        if type(width) is not int or type(height) is not int or width < 1 or height < 1:
            raise WallpaperSyncError("Wallpaper manifest dimensions must be positive integers")
        if width * height > MAX_IMAGE_PIXELS:
            raise WallpaperSyncError("Wallpaper manifest exceeds the 100-megapixel decoded-image limit")
        if relative.stem != digest:
            raise WallpaperSyncError("Content-addressed image filename must equal its SHA-256")
        if item.get("palette_policy") != "fenrir-wallpaper-palette-advisory-v4":
            raise WallpaperSyncError("Image has not passed the current Fenrir wallpaper palette policy")
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
            if width * height > MAX_IMAGE_PIXELS:
                raise WallpaperSyncError("Decoded image exceeds the 100-megapixel safety limit")
            # The client verifies bytes and decoded format; palette is advisory metadata.
    except WallpaperSyncError:
        raise
    except Exception as exc:
        raise WallpaperSyncError(f"Image decode failed for {item['path']}: {exc}") from exc
    expected_format = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}[item["mime_type"]]
    if (image_format != expected_format or width < 1 or height < 1
            or width != item["width"] or height != item["height"]):
        raise WallpaperSyncError(f"Image format or decoded dimensions rejected for {item['path']}")


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
    expected = {entry["id"]: entry["target_count"] for entry in registry["categories"]}
    if category_counts != expected:
        raise WallpaperSyncError("Published manifest category counts do not match the registry quotas")
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
    category_counts = {category: 0 for category in CATEGORY_IDS}
    for item in items:
        category_counts[item["category"]] += 1
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
    largest = max((item["file_size_bytes"] for item in missing), default=0)
    dest_probe = _nearest_existing(destination)
    state_probe = _nearest_existing(state_dir)
    destination_free = shutil.disk_usage(dest_probe).free
    state_free = shutil.disk_usage(state_probe).free
    destination_required = required + largest
    state_required = largest
    same_filesystem = dest_probe.stat().st_dev == state_probe.stat().st_dev
    storage_sufficient = destination_free >= destination_required and (
        same_filesystem or state_free >= state_required
    )
    return {
        "dry_run": True,
        "active_volumes": [v["id"] for v in _validate_registry(registry)],
        "unique_images": len(items),
        "category_counts": category_counts,
        "already_present": present,
        "planned_downloads": len(missing),
        "selected_download_bytes": required,
        "destination_available_bytes": destination_free,
        "destination_required_bytes": destination_required,
        "state_available_bytes": state_free,
        "state_required_bytes": state_required,
        "same_filesystem_for_destination_and_state": same_filesystem,
        "storage_sufficient": storage_sufficient,
        "conflicts": conflicts,
        "_missing": missing,
        "_registry": registry,
        "_items": items,
    }


def _nearest_existing(path: Path) -> Path:
    current = path
    while not current.exists() and current != current.parent:
        current = current.parent
    return current


def _stream_response(response, stream, *, starting_size: int, expected_size: int) -> int:
    total = starting_size
    while True:
        chunk = response.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > expected_size or total > MAX_IMAGE_BYTES:
            raise WallpaperSyncError("Server sent more bytes than the manifest declared")
        stream.write(chunk)
    stream.flush()
    os.fsync(stream.fileno())
    return total


def _download(item: dict, state_dir: Path, destination: Path, opener: Callable) -> None:
    digest, expected_size = item["sha256"], item["file_size_bytes"]
    partial = state_dir / f"{digest}.part"
    partial.parent.mkdir(parents=True, exist_ok=True)
    _safe_path(partial)
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
    try:
        resumed = False
        if offset:
            with _request(url, opener=opener, headers={"Range": f"bytes={offset}-"}) as response:
                _assert_raw_github_response(response, url)
                status = getattr(response, "status", None) or response.getcode()
                content_range = response.headers.get("Content-Range", "")
                if status == 206 and content_range.startswith(f"bytes {offset}-") and content_range.endswith(f"/{expected_size}"):
                    with partial.open("ab") as stream:
                        total = _stream_response(response, stream, starting_size=offset, expected_size=expected_size)
                    if total != expected_size:
                        raise WallpaperSyncError(f"Resumed transfer is incomplete for {item['path']}; partial retained")
                    resumed = True
                else:
                    # Invalid/ignored Range response: discard only the untrusted partial and restart.
                    partial.unlink(missing_ok=True)
                    offset = 0
        if not resumed:
            with _request(url, opener=opener) as response:
                _assert_raw_github_response(response, url)
                with partial.open("wb") as stream:
                    total = _stream_response(response, stream, starting_size=0, expected_size=expected_size)
                if total != expected_size:
                    raise WallpaperSyncError(f"Download is incomplete for {item['path']}; partial retained")
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        raise WallpaperSyncError(f"Download interrupted for {item['path']}: {exc}") from exc

    if not partial.is_file() or partial.stat().st_size != expected_size:
        raise WallpaperSyncError(f"Incomplete download for {item['path']}; verified partial retained")
    _verify_image(partial, item)

    fd, temporary_name = tempfile.mkstemp(prefix=".fenrir-install-", dir=target.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        shutil.copyfile(partial, temporary)
        _verify_image(temporary, item)
        if target.exists():
            raise WallpaperSyncError(f"Refusing to overwrite existing file: {target}")
        try:
            # A hard-link install is atomic and fails if another process created the target.
            os.link(temporary, target)
        except FileExistsError as exc:
            raise WallpaperSyncError(f"Refusing to overwrite existing file: {target}") from exc
        partial.unlink(missing_ok=True)
    finally:
        temporary.unlink(missing_ok=True)


def _write_attribution(state_dir: Path, items: list[dict]) -> None:
    attribution = {
        "schema": "org.fenrir.public-wallpaper-attribution.v1",
        "unique_images": len(items),
        "items": [{
            "sha256": item["sha256"],
            "path": item["path"],
            "volume": item["_volume"]["id"],
            "repository": item["_volume"]["repository"],
            "creator": item["creator"],
            "credit": item.get("credit", ""),
            "source_page": item["source_page"],
            "license_identifier": item["license_identifier"],
            "rights_evidence_id": item["rights_evidence_id"],
            "source_terms_evidence_id": item["source_terms_evidence_id"],
        } for item in items],
    }
    target = state_dir / "public-attribution.json"
    if target.exists():
        try:
            existing = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WallpaperSyncError("Existing public attribution metadata is invalid and was preserved") from exc
        if existing != attribution:
            raise WallpaperSyncError("Existing public attribution metadata differs and was preserved")
        return
    fd, temporary_name = tempfile.mkstemp(prefix=".fenrir-attribution-", dir=state_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(attribution, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary_name, target)
    except FileExistsError:
        raise WallpaperSyncError("Public attribution file appeared during synchronization and was preserved")
    finally:
        Path(temporary_name).unlink(missing_ok=True)

def sync_public_library(
    destination: Path | str,
    state_dir: Path | str,
    *,
    registry_url: str = REGISTRY_URL,
    opener: Callable = urllib.request.urlopen,
) -> dict:
    destination, state_dir = Path(destination).expanduser().absolute(), Path(state_dir).expanduser().absolute()
    _safe_destination(destination, state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    lock_path = state_dir / "sync.lock"
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise WallpaperSyncError("Another Fenrir public wallpaper synchronization is already running") from exc
        plan = build_plan(destination, state_dir, registry_url=registry_url, opener=opener)
        if plan["conflicts"]:
            raise WallpaperSyncError("Conflicting existing image files were preserved; review the read-only plan")
        if not plan["storage_sufficient"]:
            raise WallpaperSyncError(
                "Insufficient free space for the complete public wallpaper library "
                f"(destination requires {plan['destination_required_bytes']} bytes; "
                f"resume cache requires {plan['state_required_bytes']} bytes)"
            )
        destination.mkdir(parents=True, exist_ok=True)
        downloaded, failures = 0, []
        for item in plan["_missing"]:
            try:
                _download(item, state_dir, destination, opener)
                downloaded += 1
            except (WallpaperSyncError, OSError) as exc:
                failures.append({"path": item["path"], "error": str(exc)})
                break
        final = build_plan(destination, state_dir, registry_url=registry_url, opener=opener)
        complete = final["planned_downloads"] == 0 and not failures
        if complete:
            _write_attribution(state_dir, plan["_items"])
        report = {
            "dry_run": False,
            "unique_images": final["unique_images"],
            "category_counts": final["category_counts"],
            "downloaded": downloaded,
            "already_present": final["already_present"],
            "planned_downloads": final["planned_downloads"],
            "failures": failures,
            "complete": complete,
            "attribution_file": str(state_dir / "public-attribution.json") if complete else None,
        }
        if not complete:
            raise WallpaperSyncError(json.dumps(report, indent=2))
        return report
