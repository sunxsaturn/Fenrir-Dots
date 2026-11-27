import unittest

from fenrir_dots.wallpaper_library import (
    MANIFEST_SCHEMA,
    LIBRARY_ID,
    PREFERRED,
    TOLERATED,
    EXCLUDED,
    WallpaperSyncError,
    _safe_path,
    _validate_manifest,
    _validate_registry,
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
