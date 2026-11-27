import hashlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "fenrir_wallpaper_library", ROOT / "bin" / "fenrir_wallpaper_library.py"
)
library = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(library)


class FakeResponse(io.BytesIO):
    def __init__(self, payload: bytes, *, status: int = 200, headers: dict | None = None):
        super().__init__(payload)
        self.status = status
        self.headers = headers or {}

    def getcode(self):
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def make_image() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (2560, 1440), "#18233a").save(output, format="JPEG", quality=90)
    return output.getvalue()


def make_registry():
    volume = {
        "id": "volume-01",
        "repository": "sunxsaturn/Fenrir-Wallpapers",
        "branch": "main",
        "images_path": "Fenrir Wallpapers/",
        "manifest_path": "manifest/index.json",
        "manifest_url": (
            "https://raw.githubusercontent.com/sunxsaturn/Fenrir-Wallpapers/"
            "main/manifest/index.json"
        ),
        "active": True,
    }
    return {
        "schema": library.REGISTRY_SCHEMA,
        "library_id": "fenrir-wallpapers",
        "hub_repository": library.HUB_REPOSITORY,
        "volumes": [volume],
    }


def make_item(payload: bytes):
    digest = hashlib.sha256(payload).hexdigest()
    return {
        "path": f"Fenrir Wallpapers/nordic-mythology-fantasy/{digest}.jpg",
        "sha256": digest,
        "file_size_bytes": len(payload),
        "mime_type": "image/jpeg",
        "width": 2560,
        "height": 1440,
        "title": "Test wallpaper",
        "creator": "Test creator",
        "credit": "Test credit",
        "attribution": "Test attribution",
        "source": "Test source",
        "source_page": "https://example.org/source",
        "license_identifier": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
    }


class FakeNetwork:
    def __init__(self, payload: bytes):
        self.image = payload
        self.registry = make_registry()
        self.item = make_item(payload)
        self.manifest = {
            "schema": library.MANIFEST_SCHEMA,
            "count": 1,
            "items": [self.item],
        }
        self.calls = []

    def __call__(self, request, timeout=45):
        url = request.full_url
        self.calls.append((url, dict(request.header_items())))
        if url == library.REGISTRY_URL:
            return FakeResponse(json.dumps(self.registry).encode())
        if url.endswith("/manifest/index.json"):
            return FakeResponse(json.dumps(self.manifest).encode())
        if url.endswith(self.item["path"].replace(" ", "%20")) or "/nordic-mythology-fantasy/" in url:
            headers = dict(request.header_items())
            range_header = headers.get("Range")
            if range_header:
                offset = int(range_header.split("=")[1].split("-")[0])
                return FakeResponse(
                    self.image[offset:],
                    status=206,
                    headers={"Content-Range": f"bytes {offset}-{len(self.image)-1}/{len(self.image)}"},
                )
            return FakeResponse(self.image)
        raise AssertionError(f"Unexpected URL: {url}")


class PublicLibrarySyncTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.destination = self.root / "Pictures" / "Wallpapers"
        self.payload = make_image()
        self.network = FakeNetwork(self.payload)
        self.environ = patch.dict(os.environ, {
            "XDG_STATE_HOME": str(self.root / "state"),
        }, clear=False)
        self.environ.start()

    def tearDown(self):
        self.environ.stop()
        self.temporary.cleanup()

    def test_dry_run_reads_registry_and_manifests_without_creating_files(self):
        result = library.sync_public_library(
            destination=self.destination,
            dry_run=True,
            opener=self.network,
        )
        self.assertEqual(result["active_volumes"], ["volume-01"])
        self.assertEqual(result["manifest_records"], 1)
        self.assertEqual(result["unique_images"], 1)
        self.assertEqual(result["selected_downloads"], 1)
        self.assertFalse(self.destination.exists())
        self.assertFalse((self.root / "state").exists())

    def test_sync_downloads_verified_image_and_writes_separate_attribution(self):
        result = library.sync_public_library(
            destination=self.destination,
            opener=self.network,
        )
        relative = Path("nordic-mythology-fantasy") / f"{self.network.item['sha256']}.jpg"
        installed = self.destination / relative
        self.assertTrue(installed.is_file())
        self.assertEqual(library._sha256_file(installed), self.network.item["sha256"])
        self.assertEqual(result["downloaded"], 1)
        self.assertEqual(result["failed"], 0)
        sidecar = json.loads(
            (self.destination / ".fenrir-public-library-attribution.json").read_text()
        )
        record = sidecar["items"][self.network.item["sha256"]]["paths"][0]
        self.assertEqual(record["creator"], "Test creator")
        self.assertEqual(record["license_identifier"], "CC BY 4.0")
        self.assertEqual(record["volume_id"], "volume-01")

    def test_second_sync_is_idempotent_and_does_not_download_again(self):
        first = library.sync_public_library(destination=self.destination, opener=self.network)
        calls_after_first = len(self.network.calls)
        second = library.sync_public_library(destination=self.destination, opener=self.network)
        self.assertEqual(first["downloaded"], 1)
        self.assertEqual(second["downloaded"], 0)
        self.assertEqual(second["already_present"], 1)
        self.assertEqual(len(self.network.calls), calls_after_first + 2)

    def test_registry_path_traversal_is_rejected(self):
        registry = make_registry()
        registry["volumes"][0]["images_path"] = "../outside/"
        with self.assertRaises(library.LibrarySyncError):
            library._validate_registry(registry)

    def test_image_path_traversal_is_rejected(self):
        volume = library._validate_registry(make_registry())[0]
        item = make_item(self.payload)
        item["path"] = "Fenrir Wallpapers/../outside/image.jpg"
        manifest = {"schema": library.MANIFEST_SCHEMA, "count": 1, "items": [item]}
        with self.assertRaises(library.LibrarySyncError):
            library._validate_manifest(manifest, volume)

    def test_manifest_count_mismatch_is_rejected_before_download(self):
        self.network.manifest["count"] = 2
        with self.assertRaises(library.LibrarySyncError):
            library.sync_public_library(destination=self.destination, opener=self.network)
        self.assertFalse(self.destination.exists())

    def test_symbolic_link_destination_is_rejected(self):
        real = self.root / "real"
        real.mkdir()
        self.destination.parent.mkdir(parents=True)
        self.destination.symlink_to(real, target_is_directory=True)
        with self.assertRaises(library.LibrarySyncError):
            library.sync_public_library(destination=self.destination, dry_run=True, opener=self.network)

    def test_mnt_storage_is_protected(self):
        with patch.object(library.Path, "is_symlink", return_value=False):
            with self.assertRaises(library.LibrarySyncError):
                library._validate_destination(Path("/mnt/storage/wallpapers"), create=False)

    def test_complete_partial_is_verified_and_installed_without_network(self):
        volume = library._validate_registry(make_registry())[0]
        item = library._validate_manifest(
            {"schema": library.MANIFEST_SCHEMA, "count": 1, "items": [self.network.item]},
            volume,
        )[0]
        cache = library._state_root() / volume["id"]
        cache.mkdir(parents=True)
        partial = cache / f"{item['sha256']}.part"
        partial.write_bytes(self.payload)
        self.destination.mkdir(parents=True)

        def unexpected_network(*_args, **_kwargs):
            raise AssertionError("A complete partial file must not trigger another HTTP request")

        path, outcome = library._download_image(
            item,
            state_dir=library._state_root(),
            destination=self.destination,
            timeout=45,
            opener=unexpected_network,
        )
        self.assertEqual(outcome, "downloaded")
        self.assertEqual(library._sha256_file(path), item["sha256"])
        self.assertFalse(partial.exists())

    def test_range_download_resumes_existing_partial_file(self):
        volume = library._validate_registry(make_registry())[0]
        item = library._validate_manifest(
            {"schema": library.MANIFEST_SCHEMA, "count": 1, "items": [self.network.item]},
            volume,
        )[0]
        cache = library._state_root() / volume["id"]
        cache.mkdir(parents=True)
        partial = cache / f"{item['sha256']}.part"
        partial.write_bytes(self.payload[:128])
        calls = []

        def resume_opener(request, timeout=45):
            calls.append(dict(request.header_items()))
            offset = 128
            return FakeResponse(
                self.payload[offset:],
                status=206,
                headers={"Content-Range": f"bytes {offset}-{len(self.payload)-1}/{len(self.payload)}"},
            )

        self.destination.mkdir(parents=True)
        path, outcome = library._download_image(
            item,
            state_dir=library._state_root(),
            destination=self.destination,
            timeout=45,
            opener=resume_opener,
        )
        self.assertTrue(path.is_file())
        self.assertEqual(outcome, "downloaded")
        self.assertEqual(calls[0]["Range"], "bytes=128-")
        self.assertFalse(partial.exists())


if __name__ == "__main__":
    unittest.main()


class PublicLibraryCliTests(unittest.TestCase):
    def test_cli_routes_sync_library_dry_run_and_json_output(self):
        import contextlib
        import sys
        from types import SimpleNamespace
        from unittest.mock import Mock

        from importlib.machinery import SourceFileLoader
        wallpaper_loader = SourceFileLoader(
            "fenrir_wallpaper_cli", str(ROOT / "bin" / "fenrir-wallpaper")
        )
        wallpaper_spec = importlib.util.spec_from_loader(
            wallpaper_loader.name, wallpaper_loader
        )
        wallpaper_cli = importlib.util.module_from_spec(wallpaper_spec)
        wallpaper_loader.exec_module(wallpaper_cli)
        report = {
            "active_volumes": ["volume-01", "volume-02"],
            "unique_images": 7,
            "already_present": 2,
            "selected_downloads": 5,
            "selected_download_bytes": 1024,
            "remaining_after_limit": 3,
            "downloaded": 0,
            "failed": 0,
            "dry_run": True,
        }
        sync = Mock(return_value=report)
        fake_module = SimpleNamespace(sync_public_library=sync)
        output = io.StringIO()
        with patch.dict(sys.modules, {"fenrir_wallpaper_library": fake_module}), patch.object(
            sys, "argv", [
                "fenrir-wallpaper", "sync-library", "--dry-run", "--limit", "5", "--json"
            ]
        ), contextlib.redirect_stdout(output):
            self.assertEqual(wallpaper_cli.main(), 0)
        sync.assert_called_once()
        kwargs = sync.call_args.kwargs
        self.assertTrue(kwargs["dry_run"])
        self.assertEqual(kwargs["limit"], 5)
        self.assertEqual(json.loads(output.getvalue())["active_volumes"], ["volume-01", "volume-02"])
