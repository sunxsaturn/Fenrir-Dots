import hashlib
import io
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

from fenrir_dots.wallpaper_library import (
    MANIFEST_SCHEMA,
    LIBRARY_ID,
    PREFERRED,
    TOLERATED,
    EXCLUDED,
    WallpaperSyncError,
    MAX_IMAGE_PIXELS,
    _RawGitHubRedirect,
    _assert_raw_github_response,
    _safe_path,
    _validate_manifest,
    _validate_registry,
    _verify_image,
)

CATEGORIES = [
    "nordic-landscapes", "medieval-landscapes", "fantasy", "epic-battles",
    "mountains", "astronomy", "planets", "knights-in-battle", "swords",
    "magic", "nordic-mythology",
]


class WallpaperLibraryTests(unittest.TestCase):
    def test_sync_policy_matches_fimbulwinter_palette_v3(self):
        self.assertEqual(EXCLUDED, {"yellow", "orange", "brown"})
        self.assertTrue({"red", "purple", "blue", "white", "black"} <= PREFERRED)
        self.assertIn("green", TOLERATED)
        self.assertNotIn("pink", EXCLUDED)
    def registry(self, state="published", legacy_reused=0):
        return {
            "schema": "org.fenrir.wallpaper-library-volumes.v2",
            "library_id": LIBRARY_ID,
            "population": {
                "state": state, "target_unique_images": 5000,
                "published_unique_images": 5000, "legacy_images_reused": legacy_reused,
            },
            "categories": [
                {"id": category, "target_count": 455 if index < 6 else 454}
                for index, category in enumerate(CATEGORIES)
            ],
            "volumes": [{
                "id": "volume-01", "repository": "sunxsaturn/Fenrir-Wallpapers",
                "branch": "main", "manifest_path": "manifest/index.json",
                "images_path": "images/", "active": True,
            }],
        }

    def record(self, license_identifier="CC0"):
        digest = "a" * 64
        return {
            "path": "images/nordic-landscapes/" + digest + ".jpg",
            "sha256": digest,
            "file_size_bytes": 1024,
            "mime_type": "image/jpeg",
            "width": 3840,
            "height": 2160,
            "category": "nordic-landscapes",
            "license_identifier": license_identifier,
            "creator": "Artist",
            "source_page": "https://example.org/source",
            "rights_evidence_id": "rights:123",
            "source_terms_evidence_id": "terms:123",
            "palette_policy": "fenrir-wallpaper-palette-v3",
        }

    def test_raw_github_redirect_handler_rejects_origin_changes(self):
        handler = _RawGitHubRedirect()
        request = urllib.request.Request(
            "https://raw.githubusercontent.com/sunxsaturn/Fenrir-Wallpapers/main/index.json"
        )
        accepted = handler.redirect_request(
            request, io.BytesIO(), 302, "Found", {},
            "https://raw.githubusercontent.com/sunxsaturn/Fenrir-Wallpapers/main/manifest.json",
        )
        self.assertEqual(
            accepted.full_url,
            "https://raw.githubusercontent.com/sunxsaturn/Fenrir-Wallpapers/main/manifest.json",
        )
        for destination in (
            "https://evil.example/manifest.json",
            "http://raw.githubusercontent.com/sunxsaturn/Fenrir-Wallpapers/main/manifest.json",
            "https://raw.githubusercontent.com:8443/sunxsaturn/Fenrir-Wallpapers/main/manifest.json",
            "https://user@raw.githubusercontent.com/sunxsaturn/Fenrir-Wallpapers/main/manifest.json",
        ):
            with self.subTest(destination=destination):
                with self.assertRaises(WallpaperSyncError):
                    handler.redirect_request(
                        request, io.BytesIO(), 302, "Found", {}, destination
                    )

    def test_final_metadata_and_image_responses_must_remain_on_raw_github_https(self):
        class Response:
            def __init__(self, url):
                self.url = url

            def geturl(self):
                return self.url

        expected = "https://raw.githubusercontent.com/sunxsaturn/Fenrir-Wallpapers/main/index.json"
        _assert_raw_github_response(Response(expected), expected)
        for final_url in (
            "http://raw.githubusercontent.com/sunxsaturn/Fenrir-Wallpapers/main/index.json",
            "https://evil.example/index.json",
            "https://raw.githubusercontent.com:8443/index.json",
            "https://user@raw.githubusercontent.com/index.json",
        ):
            with self.subTest(final_url=final_url):
                with self.assertRaises(WallpaperSyncError):
                    _assert_raw_github_response(Response(final_url), expected)

    def test_manifest_rejects_images_above_decoded_pixel_ceiling(self):
        volume = {"id": "volume-01", "images_path": "images/"}
        item = self.record()
        item["width"], item["height"] = 10_001, 10_000
        manifest = {
            "schema": MANIFEST_SCHEMA, "library_id": LIBRARY_ID,
            "volume_id": "volume-01", "count": 1, "items": [item],
        }
        self.assertGreater(item["width"] * item["height"], MAX_IMAGE_PIXELS)
        with self.assertRaisesRegex(WallpaperSyncError, "100-megapixel"):
            _validate_manifest(manifest, volume)

    def test_image_verification_rejects_large_dimensions_before_pixel_conversion(self):
        class OversizedImage:
            format = "JPEG"
            size = (10_001, 10_000)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def verify(self):
                return None

            def convert(self, mode):
                raise AssertionError("conversion must not run for an oversized image")

        payload = b"test image placeholder"
        digest = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oversized.jpg"
            path.write_bytes(payload)
            item = {
                "sha256": digest, "file_size_bytes": len(payload),
                "path": "images/nordic-landscapes/" + digest + ".jpg",
                "mime_type": "image/jpeg", "width": 10_001, "height": 10_000,
            }
            with patch("fenrir_dots.wallpaper_library.Image.open", return_value=OversizedImage()):
                with self.assertRaisesRegex(WallpaperSyncError, "100-megapixel"):
                    _verify_image(path, item)

    def test_registry_requires_all_5000_to_be_published(self):
        self.assertEqual(len(_validate_registry(self.registry())), 1)
        with self.assertRaises(WallpaperSyncError):
            _validate_registry(self.registry(state="building"))

    def test_registry_rejects_legacy_image_reuse(self):
        with self.assertRaises(WallpaperSyncError):
            _validate_registry(self.registry(legacy_reused=1))

    def test_registry_rejects_wrong_category_quota(self):
        registry = self.registry()
        registry["categories"][0]["target_count"] = 454
        with self.assertRaises(WallpaperSyncError):
            _validate_registry(registry)

    def test_manifest_accepts_only_pd_or_cc0_records_with_full_evidence(self):
        volume = {"id": "volume-01", "images_path": "images/"}
        item = self.record()
        manifest = {
            "schema": MANIFEST_SCHEMA, "library_id": LIBRARY_ID,
            "volume_id": "volume-01", "count": 1, "items": [item],
        }
        self.assertEqual(len(_validate_manifest(manifest, volume)), 1)
        manifest["items"][0]["license_identifier"] = "CC BY-SA 4.0"
        with self.assertRaises(WallpaperSyncError):
            _validate_manifest(manifest, volume)

    def test_manifest_requires_source_terms_and_palette_evidence(self):
        volume = {"id": "volume-01", "images_path": "images/"}
        item = self.record()
        item.pop("source_terms_evidence_id")
        manifest = {
            "schema": MANIFEST_SCHEMA, "library_id": LIBRARY_ID,
            "volume_id": "volume-01", "count": 1, "items": [item],
        }
        with self.assertRaises(WallpaperSyncError):
            _validate_manifest(manifest, volume)

    def test_manifest_filename_must_be_content_addressed(self):
        volume = {"id": "volume-01", "images_path": "images/"}
        item = self.record()
        item["path"] = "images/nordic-landscapes/not-the-hash.jpg"
        manifest = {
            "schema": MANIFEST_SCHEMA, "library_id": LIBRARY_ID,
            "volume_id": "volume-01", "count": 1, "items": [item],
        }
        with self.assertRaises(WallpaperSyncError):
            _validate_manifest(manifest, volume)

    def test_manifest_requires_landscape_resolution_metadata(self):
        volume = {"id": "volume-01", "images_path": "images/"}
        item = self.record()
        item["width"], item["height"] = 1920, 1080
        manifest = {
            "schema": MANIFEST_SCHEMA, "library_id": LIBRARY_ID,
            "volume_id": "volume-01", "count": 1, "items": [item],
        }
        with self.assertRaises(WallpaperSyncError):
            _validate_manifest(manifest, volume)

    def test_unsafe_data_path_is_rejected(self):
        with self.assertRaises(WallpaperSyncError):
            _safe_path(__import__("pathlib").Path("/mnt/storage/Wallpapers"))


if __name__ == "__main__":
    unittest.main()
