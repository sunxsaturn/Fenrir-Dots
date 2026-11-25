import importlib.util
import unittest
from pathlib import Path

SERVER = Path(__file__).resolve().parents[1] / "apps" / "fenrir-doctor" / "server.py"
spec = importlib.util.spec_from_file_location("fenrir_doctor_server", SERVER)
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)

class StrictJSONTests(unittest.TestCase):
    def test_duplicate_keys_rejected(self):
        with self.assertRaises(server.BadJSON):
            server.strict_json(b'{"model":"one","model":"two"}')
    def test_non_finite_constant_rejected(self):
        with self.assertRaises(server.BadJSON):
            server.strict_json(b'{"value":NaN}')
    def test_valid_object(self):
        self.assertEqual(server.strict_json(b'{"message":"hello"}'), {"message":"hello"})

class SettingsTests(unittest.TestCase):
    def test_default_settings_are_location_private(self):
        settings = server.default_settings()
        self.assertEqual(settings["default_model"], "")
        self.assertIsNone(settings["weather"]["latitude"])
        self.assertIsNone(settings["weather"]["longitude"])
        self.assertEqual(settings["weather"]["location"], "")
        self.assertEqual(settings["wallpaper_target_count"], 5000)

    def test_unconfigured_weather_does_not_make_network_request(self):
        from unittest.mock import patch
        with patch.object(server, "read_settings", return_value=server.default_settings()), \
             patch.object(server.urllib.request, "urlopen", side_effect=AssertionError("network must not be used")):
            result = server.weather_snapshot()
        self.assertFalse(result["configured"])
        self.assertIn("settings", result["message"].lower())

    def test_weather_codes_have_readable_fallback(self):
        self.assertEqual(server.WEATHER_CODES[0], "Clear sky")
        self.assertEqual(server.WEATHER_CODES[95], "Thunderstorm")

    def test_system_snapshot_has_stable_local_fields(self):
        result = server.system_snapshot()
        self.assertIn("cpu_percent", result)
        self.assertIn("memory_percent", result)
        self.assertIn("disk_percent", result)
        self.assertGreaterEqual(result["disk_total_gib"], result["disk_used_gib"])

    def test_system_snapshot_prefers_discrete_amd_gpu_over_igpu(self):
        import shutil
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            igpu = root / "card0" / "device"
            dgpu = root / "card1" / "device"
            igpu.mkdir(parents=True)
            dgpu.mkdir(parents=True)
            for path, busy, vram, device_id, name in (
                (igpu, "12", str(512 * 1024**2), "0x164e", "AMD Raphael iGPU"),
                (dgpu, "67", str(12 * 1024**3), "0x73df", "AMD Radeon RX 6750 XT"),
            ):
                (path / "vendor").write_text("0x1002", encoding="ascii")
                (path / "gpu_busy_percent").write_text(busy, encoding="ascii")
                (path / "mem_info_vram_total").write_text(vram, encoding="ascii")
                (path / "device").write_text(device_id, encoding="ascii")
                (path / "product_name").write_text(name, encoding="utf-8")

            original_glob = Path.glob
            def fake_glob(path, pattern):
                if str(path) == "/sys/class/drm" and pattern == "card*/device":
                    return iter((igpu, dgpu))
                return original_glob(path, pattern)

            usage = shutil._ntuple_diskusage(total=100 * 1024**3, used=40 * 1024**3, free=60 * 1024**3)
            with patch.object(Path, "glob", fake_glob), patch.object(server.shutil, "disk_usage", return_value=usage):
                result = server.system_snapshot()

        self.assertEqual(result["gpu_percent"], 67.0)
        self.assertEqual(result["gpu_name"], "AMD Radeon RX 6750 XT")

class DoctorUtilityTests(unittest.TestCase):
    def test_private_catalog_release_uses_authenticated_git_tags(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temporary:
            catalog = Path(temporary) / "catalog-source"
            (catalog / ".git").mkdir(parents=True)
            completed = server.subprocess.CompletedProcess(
                args=["git"], returncode=0,
                stdout="abc123\trefs/tags/v0.21.0\ndef456\trefs/tags/v0.22.0\n",
                stderr="",
            )
            with patch.object(server, "CATALOG_SOURCE", catalog), patch.object(
                server.subprocess, "run", return_value=completed,
            ) as run:
                result = server._latest_private_catalog_release()
            self.assertEqual(result["latest"], "0.22.0")
            self.assertTrue(result["update_available"])
            self.assertEqual(result["status"], "available")
            self.assertIn("/releases/tag/v0.22.0", result["url"])
            self.assertEqual(run.call_args.kwargs["env"]["GIT_TERMINAL_PROMPT"], "0")

    def test_private_catalog_auth_failure_is_not_reported_as_no_release(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temporary:
            catalog = Path(temporary) / "catalog-source"
            (catalog / ".git").mkdir(parents=True)
            completed = server.subprocess.CompletedProcess(
                args=["git"], returncode=128, stdout="",
                stderr="fatal: Authentication failed",
            )
            with patch.object(server, "CATALOG_SOURCE", catalog), patch.object(
                server.subprocess, "run", return_value=completed,
            ):
                result = server._latest_private_catalog_release()
            self.assertEqual(result["status"], "unavailable")
            self.assertFalse(result["update_available"])
            self.assertIn("Authentication failed", result["detail"])

    def test_installed_version_manifest_overrides_fallback_values(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / "installed-versions.json"
            manifest.write_text(
                '{"Fenrir-Arch":"0.6.0","Fenrir-Dots":"0.6.0","Fenrir-Wallpaper-Catalog":"0.20.0"}',
                encoding="utf-8",
            )
            with patch.object(server, "INSTALLED_VERSIONS_FILE", manifest):
                versions = server.installed_release_versions()
            self.assertEqual(versions["Fenrir-Arch"], "0.6.0")
            self.assertEqual(versions["Fenrir-Dots"], "0.6.0")
            self.assertEqual(versions["Fenrir-Wallpaper-Catalog"], "0.20.0")

    def test_installed_version_manifest_ignores_unknown_and_invalid_entries(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / "installed-versions.json"
            manifest.write_text(
                '{"Fenrir-Arch":"0.6.0","Unknown":"9.9.9","Fenrir-Dots":"latest"}',
                encoding="utf-8",
            )
            with patch.object(server, "INSTALLED_VERSIONS_FILE", manifest):
                versions = server.installed_release_versions()
            self.assertEqual(versions["Fenrir-Arch"], "0.6.0")
            self.assertEqual(versions["Fenrir-Dots"], server.LOCAL_RELEASES["Fenrir-Dots"])
            self.assertNotIn("Unknown", versions)

    def test_installed_version_manifest_rejects_symlink_and_oversized_file(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target.json"
            target.write_text('{"Fenrir-Arch":"9.9.9"}', encoding="utf-8")
            link = root / "manifest.json"
            link.symlink_to(target)
            with patch.object(server, "INSTALLED_VERSIONS_FILE", link):
                versions = server.installed_release_versions()
            self.assertEqual(versions, server.LOCAL_RELEASES)

            oversized = root / "oversized.json"
            oversized.write_text(" " * 4097, encoding="utf-8")
            with patch.object(server, "INSTALLED_VERSIONS_FILE", oversized):
                versions = server.installed_release_versions()
            self.assertEqual(versions, server.LOCAL_RELEASES)

    def test_release_version_comparison(self):
        self.assertGreater(server._version_key("0.10.0"), server._version_key("0.9.9"))
        self.assertEqual(server._version_key("v1.2.3"), (1, 2, 3))

    def test_wallpaper_snapshot_uses_catalog_palette_index(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wallpaper_dir = root / "Pictures" / "Wallpapers"
            wallpaper_dir.mkdir(parents=True)
            database = root / "catalog.sqlite3"
            database.write_bytes(b"catalog")
            quarantine = root / "quarantine"
            quarantine.mkdir()
            facets = server.subprocess.CompletedProcess(
                args=["fenrir-catalog"], returncode=0,
                stdout='{"accepted_asset_count":12}', stderr="",
            )
            palette = server.subprocess.CompletedProcess(
                args=["fenrir-catalog"], returncode=0,
                stdout='{"count":7,"excluded_palette_color":3,"below_resolution_or_wrong_orientation":2,"invalid_files":1,"checked_files":4,"cached_files":9,"palette_policy":"fenrir-wallpaper-palette-v1"}',
                stderr="",
            )
            with patch.object(server, "CATALOG_DB", database), \
                 patch.object(server, "QUARANTINE_ROOT", quarantine), \
                 patch.object(server.shutil, "which", return_value="/home/test/.local/bin/fenrir-catalog"), \
                 patch.object(server, "current_wallpaper_directory", return_value=wallpaper_dir), \
                 patch.object(server, "wallpaper_sync_destination_allowed", return_value=True), \
                 patch.object(server.subprocess, "run", side_effect=[facets, palette]):
                result = server.wallpaper_snapshot()
            self.assertEqual(result["local_image_count"], 7)
            self.assertEqual(result["accepted_asset_count"], 12)
            self.assertEqual(result["palette_metrics"]["excluded_palette_color"], 3)
            self.assertEqual(result["palette_metrics"]["cached_files"], 9)

    def test_wallpaper_sync_is_confined_to_pictures_directory(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            with patch.object(Path, "home", return_value=home):
                self.assertTrue(server.wallpaper_sync_destination_allowed(home / "Pictures" / "Wallpapers"))
                self.assertFalse(server.wallpaper_sync_destination_allowed(home / "Downloads" / "Wallpapers"))
                self.assertFalse(server.wallpaper_sync_destination_allowed(Path("/mnt/storage/wallpapers")))

    def test_release_snapshot_caches_github_checks(self):
        from unittest.mock import patch
        original_cache, original_time = server.RELEASE_CACHE, server.RELEASE_CACHE_AT
        try:
            server.RELEASE_CACHE = None
            server.RELEASE_CACHE_AT = 0.0
            with patch.object(server, "_latest_release", side_effect=lambda name: {
                "repository": name, "current": "0.5.0", "latest": "0.5.0",
                "update_available": False, "status": "available",
            }) as fetch:
                first = server.updates_snapshot()
                second = server.updates_snapshot()
            self.assertEqual(first, second)
            self.assertEqual(fetch.call_count, len(server.LOCAL_RELEASES))
        finally:
            server.RELEASE_CACHE, server.RELEASE_CACHE_AT = original_cache, original_time

    def test_diagnostic_snapshot_reports_named_groups(self):
        from unittest.mock import patch
        with patch.object(server, "_command_result", return_value=(True, "ok")), \
             patch.object(server.shutil, "disk_usage", return_value=server.shutil._ntuple_diskusage(total=100, used=50, free=50)):
            result = server.diagnostics_snapshot()
        names = {item["name"] for item in result["checks"]}
        self.assertIn("Hyprland", names)
        self.assertIn("PipeWire audio", names)
        self.assertIn("Wallpaper Catalog", names)
        self.assertEqual(result["summary"]["total"], len(result["checks"]))

    def test_backup_restore_creates_rollback_snapshot(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            backup = home / ".local/state/fenrir/backups/test-backup/.config/hypr"
            backup.mkdir(parents=True)
            (backup / "hyprland.lua").write_text("-- old config", encoding="utf-8")
            current = home / ".config/hypr"
            current.mkdir(parents=True)
            (current / "hyprland.lua").write_text("-- current config", encoding="utf-8")
            with patch.object(Path, "home", return_value=home):
                result = server.restore_backup("test-backup")
            self.assertEqual((current / "hyprland.lua").read_text(encoding="utf-8"), "-- old config")
            self.assertIsNotNone(result["rollback_backup"])
            rollback = home / ".local/state/fenrir/backups" / result["rollback_backup"] / ".config/hypr/hyprland.lua"
            self.assertEqual(rollback.read_text(encoding="utf-8"), "-- current config")

    def test_restore_rejects_invalid_backup_id(self):
        with self.assertRaises(ValueError):
            server.restore_backup("../outside")

    def test_restore_rejects_nested_symlink_before_changing_files(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            backup = home / ".local/state/fenrir/backups/test-backup/.config/hypr"
            backup.mkdir(parents=True)
            (backup / "hyprland.lua").write_text("-- old config", encoding="utf-8")
            current = home / ".config/hypr"
            current.mkdir(parents=True)
            outside = home / "outside.txt"
            outside.write_text("do not overwrite", encoding="utf-8")
            (current / "linked.lua").symlink_to(outside)
            with patch.object(Path, "home", return_value=home):
                with self.assertRaisesRegex(ValueError, "symbolic link"):
                    server.restore_backup("test-backup")
            self.assertEqual(outside.read_text(encoding="utf-8"), "do not overwrite")
            self.assertFalse((current / "hyprland.lua").exists())


class WallpaperDiscoveryTests(unittest.TestCase):
    def test_wallhaven_starts_full_profile_metadata_only_campaign_without_contact(self):
        import tempfile
        from types import SimpleNamespace
        from unittest.mock import Mock, patch

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "state"
            state.mkdir()
            catalog_db = root / "catalog.sqlite3"
            catalog_db.write_bytes(b"test database placeholder")
            discovery_state = state / "wallpaper-discovery.json"
            discovery_log = state / "wallpaper-discovery.log"
            process = Mock(pid=4321)
            created = SimpleNamespace(
                returncode=0,
                stdout='{"campaign_id":"wallhaven-campaign-test"}',
                stderr="",
            )

            with (
                patch.object(server, "STATE", state),
                patch.object(server, "CATALOG_DB", catalog_db),
                patch.object(server, "DISCOVERY_STATE", discovery_state),
                patch.object(server, "DISCOVERY_LOG", discovery_log),
                patch.object(server, "DISCOVERY_PROCESS", None),
                patch.object(server.shutil, "which", return_value="/usr/bin/fenrir-catalog"),
                patch.object(server.subprocess, "run", return_value=created),
                patch.object(server.subprocess, "Popen", return_value=process) as popen,
            ):
                result = server.start_wallpaper_discovery(
                    "wallhaven",
                    "fenrir-nordic-fantasy-v1",
                )

            command = popen.call_args.args[0]
            self.assertTrue(result["started"])
            self.assertEqual(result["campaign_id"], "wallhaven-campaign-test")
            self.assertEqual(result["downloads_started"], False)
            self.assertEqual(result["max_queries_per_run"], 100)
            self.assertEqual(result["rights_decisions_created"], 0)
            self.assertEqual(result["acceptances_created"], 0)
            self.assertEqual(command[command.index("--source") + 1], "wallhaven")
            self.assertEqual(command[command.index("--max-queries") + 1], "100")
            self.assertEqual(command[command.index("--max-pages-per-query") + 1], "2")
            self.assertNotIn("--contact", command)

    def test_wallhaven_rejects_commons_contact_parameter(self):
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            catalog_db = root / "catalog.sqlite3"
            catalog_db.write_bytes(b"test database placeholder")
            discovery_state = root / "wallpaper-discovery.json"
            with (
                patch.object(server, "CATALOG_DB", catalog_db),
                patch.object(server, "DISCOVERY_STATE", discovery_state),
                patch.object(server, "DISCOVERY_PROCESS", None),
                patch.object(server.shutil, "which", return_value="/usr/bin/fenrir-catalog"),
            ):
                with self.assertRaisesRegex(ValueError, "only for Wikimedia Commons"):
                    server.start_wallpaper_discovery(
                        "wallhaven",
                        "fenrir-nordic-fantasy-v1",
                        contact="unexpected@example.org",
                    )


if __name__ == "__main__":
    unittest.main()
