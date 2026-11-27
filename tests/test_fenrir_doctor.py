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
    def test_release_fallbacks_match_current_component_versions(self):
        self.assertEqual(server.APP_VERSION, "0.16.0")
        self.assertEqual(
            server.LOCAL_RELEASES,
            {
                "Fenrir-Arch": "1.0.0",
                "Fenrir-Dots": "0.16.0",
                "Fenrir-Wallpaper-Catalog": "0.38.0",
            },
        )

    def test_private_catalog_release_uses_authenticated_git_tags(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temporary:
            catalog = Path(temporary) / "catalog-source"
            (catalog / ".git").mkdir(parents=True)
            completed = server.subprocess.CompletedProcess(
                args=["git"], returncode=0,
                stdout="abc123\trefs/tags/v0.38.0\ndef456\trefs/tags/v0.39.0\n",
                stderr="",
            )
            with patch.object(server, "CATALOG_SOURCE", catalog), patch.object(
                server, "installed_release_versions", return_value=dict(server.LOCAL_RELEASES),
            ), patch.object(
                server.subprocess, "run", return_value=completed,
            ) as run:
                result = server._latest_private_catalog_release()
            self.assertEqual(result["latest"], "0.39.0")
            self.assertTrue(result["update_available"])
            self.assertEqual(result["status"], "available")
            self.assertIn("/releases/tag/v0.39.0", result["url"])
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
                with patch.object(server, "wallpaper_portfolio_snapshot", return_value={"available": False, "read_only": True}):
                    result = server.wallpaper_snapshot()
            self.assertEqual(result["local_image_count"], 7)
            self.assertEqual(result["accepted_asset_count"], 12)
            self.assertEqual(result["palette_metrics"]["excluded_palette_color"], 3)
            self.assertEqual(result["palette_metrics"]["cached_files"], 9)

    def test_wallpaper_sync_rejects_symlinked_destination_components(self):
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            pictures = home / "Pictures"
            pictures.mkdir()
            linked = home / "Pictures-link"
            linked.symlink_to(pictures, target_is_directory=True)
            with patch.object(Path, "home", return_value=home):
                self.assertFalse(server.wallpaper_sync_destination_allowed(linked / "Wallpapers"))
                self.assertTrue(server.wallpaper_sync_destination_allowed(pictures / "Wallpapers"))

    def test_wallpaper_sync_is_confined_to_pictures_directory(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            with patch.object(Path, "home", return_value=home):
                self.assertTrue(server.wallpaper_sync_destination_allowed(home / "Pictures" / "Wallpapers"))
                self.assertFalse(server.wallpaper_sync_destination_allowed(home / "Downloads" / "Wallpapers"))
                self.assertFalse(server.wallpaper_sync_destination_allowed(Path("/mnt/storage/wallpapers")))

    def test_wallpaper_sync_preflight_is_read_only_and_target_free(self):
        import json
        import tempfile
        from types import SimpleNamespace
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "catalog.sqlite3"
            database.write_bytes(b"catalog fixture")
            quarantine = root / "quarantine"
            quarantine.mkdir(mode=0o700)
            destination = root / "Pictures" / "Wallpapers"
            payload = {
                "report": "org.fenrir.wallpaper-sync-preflight",
                "before_count": 500,
                "accepted_assets_examined": 12,
                "manifest_pages_examined": 1,
                "metadata_eligible_count": 8,
                "copy_ready_count": 6,
                "already_present_count": 2,
                "planned_new_copies": 6,
                "projected_local_count": 506,
                "plan_complete": True,
                "selection_scope": "all_accepted_assets",
                "has_more": False,
                "destination_parent_writable": True,
                "sync_allowed": True,
                "skipped": {"license_not_approved": 4},
                "read_only": True,
                "database_writes": 0,
                "files_written": 0,
                "directories_created": 0,
                "attribution_written": False,
                "palette_cache_written": False,
                "quarantine_files_read": 0,
                "downloads_started": 0,
                "acceptance_decisions_created": 0,
                "sync_started": False,
            }
            completed = SimpleNamespace(
                returncode=0, stdout=json.dumps(payload), stderr=""
            )
            with (
                patch.object(server, "CATALOG_DB", database),
                patch.object(server, "QUARANTINE_ROOT", quarantine),
                patch.object(server.shutil, "which", return_value="/usr/bin/fenrir-catalog"),
                patch.object(server, "current_wallpaper_directory", return_value=destination),
                patch.object(server, "wallpaper_sync_destination_allowed", return_value=True),
                patch.object(server.subprocess, "run", return_value=completed) as run,
            ):
                plan = server.wallpaper_sync_preflight()

        self.assertTrue(plan["read_only"])
        self.assertTrue(plan["sync_allowed"])
        self.assertEqual(plan["planned_new_copies"], 6)
        self.assertEqual(plan["skipped"], {"license_not_approved": 4})
        self.assertEqual(plan["selection_scope"], "all_accepted_assets")
        self.assertNotIn("target_count", plan)
        command = run.call_args.args[0]
        self.assertIn("sync-plan", command)
        self.assertIn("--max-plan-assets", command)
        self.assertEqual(command[command.index("--max-plan-assets") + 1], "20000")
        self.assertNotIn("--target-count", command)
        self.assertFalse(destination.exists())

    def test_wallpaper_sync_requires_successful_preflight_before_writes(self):
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "catalog.sqlite3"
            database.write_bytes(b"catalog fixture")
            quarantine = root / "quarantine"
            quarantine.mkdir(mode=0o700)
            destination = root / "Pictures" / "Wallpapers"
            with (
                patch.object(server, "WALLPAPER_SYNC", None),
                patch.object(server, "CATALOG_DB", database),
                patch.object(server, "QUARANTINE_ROOT", quarantine),
                patch.object(server.shutil, "which", return_value="/usr/bin/fenrir-catalog"),
                patch.object(server, "current_wallpaper_directory", return_value=destination),
                patch.object(server, "wallpaper_sync_destination_allowed", return_value=True),
                patch.object(server, "wallpaper_sync_preflight", return_value={
                    "sync_allowed": False, "plan_complete": False,
                }),
                patch.object(server.subprocess, "Popen") as process,
            ):
                with self.assertRaisesRegex(ValueError, "preflight blocked"):
                    server.start_wallpaper_sync()
            self.assertFalse(destination.exists())
            process.assert_not_called()

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
    def test_scheduler_queries_catalog_budget_before_each_automatic_provider_slice(self):
        import json
        import tempfile
        from types import SimpleNamespace
        from unittest.mock import patch

        provider_cases = (
            ("openverse", 2, 1),
            ("wikimedia_commons", 1, 2),
            ("wallhaven", 2, 1),
            ("cleveland_museum", 2, 1),
        )
        for source, max_queries, requests_per_page in provider_cases:
            with self.subTest(source=source), tempfile.TemporaryDirectory() as temporary:
                state = Path(temporary)
                database = state / "catalog.sqlite3"
                database.write_bytes(b"catalog")
                plan = {
                    "source_key": source,
                    "profile_key": "fenrir-nordic-fantasy-v1",
                    "provider_budget": {
                        "max_queries_per_slice": max_queries,
                        "max_pages_per_query": 2,
                        "api_requests_per_page": requests_per_page,
                        "max_api_requests_per_slice": 4,
                    },
                    "operation": "metadata_discovery_only",
                    "image_downloads": 0,
                    "rights_decisions": 0,
                    "acquisition_authorizations": 0,
                    "human_acceptances": 0,
                    "read_only": True,
                }
                created = {"campaign_id": "new-" + source}
                completed_plan = SimpleNamespace(returncode=0, stdout=json.dumps(plan), stderr="")
                completed_create = SimpleNamespace(returncode=0, stdout=json.dumps(created), stderr="")
                process = SimpleNamespace(pid=12345)
                with (
                    patch.object(server, "CATALOG_DB", database),
                    patch.object(server, "STATE", state),
                    patch.object(server, "DISCOVERY_STATE", state / "discovery.json"),
                    patch.object(server, "DISCOVERY_LOG", state / "discovery.log"),
                    patch.object(server.shutil, "which", return_value="/usr/bin/fenrir-catalog"),
                    patch.object(server.subprocess, "run", side_effect=[completed_plan, completed_create]) as run,
                    patch.object(server.subprocess, "Popen", return_value=process) as popen,
                    patch.object(server, "DISCOVERY_PROCESS", None),
                ):
                    result = server._start_wallpaper_discovery_unlocked(
                        source,
                        "fenrir-nordic-fantasy-v1",
                        "fenrir@example.org" if source == "wikimedia_commons" else None,
                        max_queries=None,
                    )
                plan_command = run.call_args_list[0].args[0]
                execute_command = popen.call_args.args[0]
                self.assertEqual(plan_command[1:3], ["campaign", "plan"])
                self.assertIn("--max-pages-per-query", plan_command)
                self.assertEqual(execute_command[execute_command.index("--max-queries") + 1], str(max_queries))
                self.assertEqual(execute_command[execute_command.index("--max-pages-per-query") + 1], "2")
                self.assertEqual(max_queries * 2 * requests_per_page, 4)
                self.assertEqual(result["provider_budget"]["max_api_requests_per_slice"], 4)
                if source == "wikimedia_commons":
                    self.assertIn("--contact", execute_command)
                else:
                    self.assertNotIn("--contact", execute_command)

    def test_scheduler_rejects_provider_budget_above_four_api_requests(self):
        import json
        import tempfile
        from types import SimpleNamespace
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            database = state / "catalog.sqlite3"
            database.write_bytes(b"catalog")
            unsafe = {
                "source_key": "openverse",
                "profile_key": "fenrir-nordic-fantasy-v1",
                "provider_budget": {
                    "max_queries_per_slice": 2,
                    "max_pages_per_query": 2,
                    "api_requests_per_page": 2,
                    "max_api_requests_per_slice": 4,
                },
                "operation": "metadata_discovery_only",
                "image_downloads": 0,
                "rights_decisions": 0,
                "acquisition_authorizations": 0,
                "human_acceptances": 0,
                "read_only": True,
            }
            completed = SimpleNamespace(returncode=0, stdout=json.dumps(unsafe), stderr="")
            with (
                patch.object(server, "CATALOG_DB", database),
                patch.object(server.shutil, "which", return_value="/usr/bin/fenrir-catalog"),
                patch.object(server.subprocess, "run", return_value=completed),
                patch.object(server.subprocess, "Popen") as popen,
                patch.object(server, "DISCOVERY_PROCESS", None),
            ):
                with self.assertRaisesRegex(ValueError, "four-request"):
                    server._start_wallpaper_discovery_unlocked(
                        "openverse", "fenrir-nordic-fantasy-v1", max_queries=None
                    )
            popen.assert_not_called()

    def test_portfolio_snapshot_is_read_only_and_target_free_without_attribution(self):
        import json
        import tempfile
        from types import SimpleNamespace
        from unittest.mock import patch

        payload = {
            "report": "org.fenrir.discovery-portfolio",
            "report_version": 1,
            "providers": [{"source_key": "openverse", "provider_budget": {}}],
            "profiles": [{"profile_key": "fenrir-nordic-fantasy-v1"}],
            "collection_status": {
                "local_qualifying_count": 500,
                "accepted_quality_eligible_count": 900,
                "attributed_catalog_asset_count": 0,
                "estimated_accepted_not_yet_local": 900,
                "recent_accepted_count": 12,
                "history_days": 30,
                "recent_acceptance_rate_per_day": 0.4,
                "status": "observed_trend",
                "note": "No wallpaper-count target or completion date is inferred.",
            },
            "read_only": True,
            "images_downloaded": 0,
            "rights_decisions_created": 0,
            "acquisition_authorizations_created": 0,
            "human_acceptances_created": 0,
            "files_modified": False,
        }
        with tempfile.TemporaryDirectory() as temporary:
            wallpaper_dir = Path(temporary)
            completed = SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")
            with (
                patch.object(server.shutil, "which", return_value="/usr/bin/fenrir-catalog"),
                patch.object(server.subprocess, "run", return_value=completed) as run,
            ):
                result = server.wallpaper_portfolio_snapshot(
                    500, wallpaper_dir, catalog_available=True
                )

        self.assertTrue(result["available"])
        self.assertTrue(result["read_only"])
        self.assertFalse(result["attribution_count_is_exact"])
        status = result["report"]["collection_status"]
        self.assertIsNone(status["estimated_accepted_not_yet_local"])
        self.assertNotIn("forecast", result["report"])
        command = run.call_args.args[0]
        self.assertIn("portfolio", command)
        self.assertIn("--local-image-count", command)
        self.assertNotIn("--target-count", command)
        self.assertEqual(command[command.index("--attributed-asset-count") + 1], "0")

    def test_portfolio_snapshot_uses_verified_attribution_sidecar(self):
        import json
        import tempfile
        from types import SimpleNamespace
        from unittest.mock import patch

        payload = {
            "report": "org.fenrir.discovery-portfolio",
            "report_version": 1,
            "providers": [{"source_key": "openverse", "provider_budget": {}}],
            "profiles": [{"profile_key": "fenrir-nordic-fantasy-v1"}],
            "collection_status": {
                "local_qualifying_count": 1000,
                "accepted_quality_eligible_count": 1200,
                "attributed_catalog_asset_count": 200,
                "estimated_accepted_not_yet_local": 1000,
                "recent_accepted_count": 30,
                "history_days": 30,
                "recent_acceptance_rate_per_day": 1.0,
                "status": "observed_trend",
                "note": "Observed inventory only.",
            },
            "read_only": True,
            "images_downloaded": 0,
            "rights_decisions_created": 0,
            "acquisition_authorizations_created": 0,
            "human_acceptances_created": 0,
            "files_modified": False,
        }
        with tempfile.TemporaryDirectory() as temporary:
            wallpaper_dir = Path(temporary)
            (wallpaper_dir / "fenrir-catalog-attribution.json").write_text(
                json.dumps({
                    "schema": "org.fenrir.wallpaper-catalog-local-install",
                    "version": 1,
                    "items": [{"asset_id": f"asset-{index}"} for index in range(200)],
                }),
                encoding="utf-8",
            )
            completed = SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")
            with patch.object(server.shutil, "which", return_value="/usr/bin/fenrir-catalog"), patch.object(
                server.subprocess, "run", return_value=completed
            ):
                result = server.wallpaper_portfolio_snapshot(
                    1000, wallpaper_dir, catalog_available=True
                )

        self.assertTrue(result["available"])
        self.assertTrue(result["attribution_count_is_exact"])
        self.assertEqual(result["attributed_asset_count"], 200)
        self.assertEqual(result["report"]["collection_status"]["estimated_accepted_not_yet_local"], 1000)
        self.assertNotIn("forecast", result["report"])

    def test_public_library_audit_snapshot_is_read_only_and_sanitized(self):
        import json
        from types import SimpleNamespace
        from unittest.mock import patch

        payload = {
            "report": "org.fenrir.public-wallpaper-library-audit",
            "report_version": 1,
            "population_state": "closed",
            "audit_status": "review_required",
            "no_fixed_image_target": True,
            "fixed_image_count_target": None,
            "acquisition_enabled": False,
            "registered_volume_count": 3,
            "active_volume_count": 3,
            "manifest_records": 1871,
            "unique_images": 1871,
            "duplicate_records": 0,
            "hash_metadata_conflicts": 0,
            "hash_path_mismatches": 0,
            "invalid_dimensions": 0,
            "below_desktop_resolution": 0,
            "manifested_image_bytes": 123456,
            "source_page_invalid": 0,
            "license_review_or_exclusion": 2,
            "repositories_over_storage_limit": 0,
            "repositories_storage_unknown": 0,
            "category_counts": {"arctic-blue-violet": 228},
            "category_balance": {
                "category_count": 9,
                "minimum_images": 111,
                "maximum_images": 228,
                "spread": 117,
                "counts": {"arctic-blue-violet": 228},
                "note": "Observed distribution only.",
            },
            "metadata_missing_counts": {"creator": 1},
            "metadata_fields_with_gaps": ["creator"],
            "license_counts": {
                "permitted_family": 1800, "excluded": 1,
                "manual_review": 1, "missing": 0,
            },
            "palette": {
                "family_record_counts": {"blue": 1000},
                "missing_records": 0,
                "invalid_color_values": 0,
                "excluded_yellow_orange_brown_records": 0,
                "preferred_family_records": 1700,
                "green_only_records": 100,
                "note": "Manifest dominant colors only.",
            },
            "storage_safety_limit_bytes": 10 * 1024**3,
            "volumes": [{
                "id": "volume-01",
                "repository": "sunxsaturn/Fenrir-Wallpapers",
                "status": "closed",
                "acquisition_enabled": False,
                "image_count": 134,
                "manifest_updated_at": "2026-11-26T21:10:04Z",
                "manifested_image_bytes": 1024,
                "category_counts": {"arctic-blue-violet": 20},
                "storage": {
                    "api_reported_size_kib": 1024,
                    "api_reported_size_bytes": 1024 * 1024,
                    "safety_limit_bytes": 10 * 1024**3,
                    "headroom_bytes": 10 * 1024**3 - 1024 * 1024,
                    "status": "within_safety_limit",
                    "detail": "test",
                },
            }],
            "read_only": True,
            "downloads_started": 0,
            "image_bytes_fetched": 0,
            "files_modified": False,
            "local_files_inspected": False,
        }
        completed = SimpleNamespace(
            returncode=0, stdout=json.dumps(payload), stderr=""
        )
        with (
            patch.object(server.shutil, "which", return_value="/usr/bin/fenrir-wallpaper"),
            patch.object(server.subprocess, "run", return_value=completed) as run,
        ):
            report = server.public_library_audit_snapshot()

        self.assertEqual(report["manifest_records"], 1871)
        self.assertEqual(report["unique_images"], 1871)
        self.assertEqual(report["population_state"], "closed")
        self.assertEqual(report["category_balance"]["spread"], 117)
        self.assertEqual(report["license_counts"]["manual_review"], 1)
        self.assertEqual(report["palette"]["missing_records"], 0)
        self.assertEqual(report["volumes"][0]["storage"]["status"], "within_safety_limit")
        self.assertTrue(report["read_only"])
        self.assertEqual(run.call_args.args[0], [
            "/usr/bin/fenrir-wallpaper", "audit-library", "--json"
        ])

    def test_all_catalog_discovery_profiles_are_available_to_doctor(self):
        self.assertEqual(
            server.DISCOVERY_PROFILES,
            {
                "fenrir-nordic-fantasy-v1",
                "fenrir-cinematic-nature-v1",
                "fenrir-cosmic-sci-fi-v1",
                "fenrir-arctic-blue-v1",
                "fenrir-architecture-monochrome-v1",
                "fenrir-red-violet-dark-fantasy-v1",
                "fenrir-deep-ocean-bioluminescence-v1",
                "fenrir-obsidian-abstract-v1",
            },
        )

    def test_schedule_accepts_all_profiles_and_rejects_unknown_profile(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temporary:
            schedule_file = Path(temporary) / "schedule.json"
            with patch.object(server, "DISCOVERY_SCHEDULE_FILE", schedule_file):
                for profile in sorted(server.DISCOVERY_PROFILES):
                    schedule = server._default_wallpaper_discovery_schedule()
                    schedule["profile"] = profile
                    server.atomic_json(schedule_file, schedule)
                    self.assertEqual(server.read_wallpaper_discovery_schedule()["profile"], profile)
                invalid = server._default_wallpaper_discovery_schedule()
                invalid["profile"] = "not-a-real-profile"
                server.atomic_json(schedule_file, invalid)
                loaded = server.read_wallpaper_discovery_schedule()
        self.assertEqual(loaded["last_status"], "invalid")

    def test_catalog_integrity_snapshot_uses_read_only_quick_check(self):
        import sqlite3
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "catalog.sqlite3"
            connection = sqlite3.connect(database)
            connection.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
            connection.commit()
            connection.close()
            with patch.object(server, "CATALOG_DB", database):
                result = server.catalog_integrity_snapshot()
        self.assertTrue(result["available"])
        self.assertEqual(result["integrity"], "ok")
        self.assertIn("quick_check passed", result["detail"])

    def test_catalog_integrity_snapshot_rejects_symlink(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target.sqlite3"
            target.write_bytes(b"not a database")
            link = root / "catalog.sqlite3"
            link.symlink_to(target)
            with patch.object(server, "CATALOG_DB", link):
                result = server.catalog_integrity_snapshot()
        self.assertFalse(result["available"])
        self.assertIn("symbolic link", result["detail"])

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
            self.assertEqual(result["max_queries_per_run"], 100)
            self.assertEqual(result["downloads_started"], False)
            self.assertEqual(result["rights_decisions_created"], 0)
            self.assertEqual(result["acceptances_created"], 0)
            self.assertEqual(command[command.index("--source") + 1], "wallhaven")
            self.assertEqual(command[command.index("--max-queries") + 1], "100")
            self.assertEqual(command[command.index("--max-pages-per-query") + 1], "2")
            self.assertNotIn("--contact", command)

    def test_acquisition_queue_snapshot_uses_read_only_catalog_report(self):
        import tempfile
        from types import SimpleNamespace
        from unittest.mock import patch

        report = {
            "report": "org.fenrir.acquisition-campaign-queue",
            "read_only": True,
            "downloads_started": 0,
            "rights_decisions_created": 0,
            "acquisition_authorizations_created": 0,
            "human_acceptances_created": 0,
            "total_campaign_assets": 4,
            "ready_for_authorization_count": 1,
            "authorized_batch_ready_count": 2,
            "blocked_count": 1,
            "items": [],
        }
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "catalog.sqlite3"
            database.write_bytes(b"local catalog fixture")
            completed = SimpleNamespace(
                returncode=0,
                stdout=__import__("json").dumps(report),
                stderr="",
            )
            with (
                patch.object(server, "wallpaper_campaign_snapshot", return_value={
                    "campaign": {
                        "campaign_id": "campaign-queue-test",
                        "source_key": "openverse",
                        "profile_key": "fenrir-nordic-fantasy-v1",
                        "status": "paused",
                    }
                }),
                patch.object(server, "CATALOG_DB", database),
                patch.object(server.shutil, "which", return_value="/usr/bin/fenrir-catalog"),
                patch.object(server.subprocess, "run", return_value=completed) as run,
            ):
                result = server.wallpaper_acquisition_queue_snapshot()

        command = run.call_args.args[0]
        self.assertIn("catalog", command)
        self.assertIn("acquisition", command)
        self.assertIn("campaign-queue", command)
        self.assertEqual(command[command.index("--limit") + 1], "100")
        self.assertEqual(command[command.index("--offset") + 1], "0")
        self.assertNotIn("run", command)
        self.assertNotIn("download", command)
        self.assertNotIn("--allowed-host", command)
        self.assertEqual(run.call_args.kwargs["timeout"], 20)
        self.assertEqual(result["queue"]["total_campaign_assets"], 4)
        self.assertEqual(result["queue"]["downloads_started"], 0)
        self.assertTrue(result["read_only"])
        self.assertEqual(result["downloads_started"], 0)

    def test_acquisition_queue_snapshot_does_not_call_catalog_without_campaign(self):
        from unittest.mock import patch

        with (
            patch.object(server, "wallpaper_campaign_snapshot", return_value={
                "campaign": None,
                "error": "No campaign state",
            }),
            patch.object(server.subprocess, "run") as run,
        ):
            result = server.wallpaper_acquisition_queue_snapshot()

        self.assertIsNone(result["queue"])
        self.assertIn("No campaign", result["detail"])
        self.assertTrue(result["read_only"])
        run.assert_not_called()

    def test_acquisition_queue_snapshot_rejects_non_read_only_catalog_response(self):
        import tempfile
        from types import SimpleNamespace
        from unittest.mock import patch

        unsafe = {
            "report": "org.fenrir.acquisition-campaign-queue",
            "read_only": False,
            "downloads_started": 1,
        }
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "catalog.sqlite3"
            database.write_bytes(b"local catalog fixture")
            completed = SimpleNamespace(
                returncode=0,
                stdout=__import__("json").dumps(unsafe),
                stderr="",
            )
            with (
                patch.object(server, "wallpaper_campaign_snapshot", return_value={
                    "campaign": {"campaign_id": "campaign-queue-test"}
                }),
                patch.object(server, "CATALOG_DB", database),
                patch.object(server.shutil, "which", return_value="/usr/bin/fenrir-catalog"),
                patch.object(server.subprocess, "run", return_value=completed),
            ):
                result = server.wallpaper_acquisition_queue_snapshot()

        self.assertIsNone(result["queue"])
        self.assertIn("read-only contract", result["detail"])
        self.assertTrue(result["read_only"])
        self.assertEqual(result["downloads_started"], 0)

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



class WallpaperRightsReviewTests(unittest.TestCase):
    def test_rights_snapshot_uses_read_only_command_and_redacts_source_urls(self):
        import json
        import tempfile
        from types import SimpleNamespace
        from unittest.mock import patch

        report = {
            "queue": "human-rights-review",
            "read_only": True,
            "automatic_rights_decision": False,
            "automatic_acquisition_authorization": False,
            "status_counts": {"unknown": 2, "review_required": 1, "eligible": 3},
            "count": 1,
            "next_cursor": "opaque",
            "results": [{
                "id": "asset-1",
                "title": "Northern lights",
                "source_key": "openverse",
                "source_url": "https://example.invalid/source",
                "download_url": "https://example.invalid/download",
                "rights_status": "unknown",
                "license_identifier": "CC-BY-4.0",
                "metadata_gaps": ["missing_creator"],
                "evidence_count": 2,
                "policy_assessment": {"decision": "eligible"},
                "latest_human_review": {
                    "decision": "review_required",
                    "reviewer": "Reviewer A",
                    "recorded_at": "2026-11-26T10:00:00Z",
                    "evidence_url": "https://example.invalid/private-evidence",
                },
            }],
        }
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "catalog.sqlite3"
            database.write_bytes(b"catalog")
            completed = SimpleNamespace(returncode=0, stdout=json.dumps(report), stderr="")
            with (
                patch.object(server, "CATALOG_DB", database),
                patch.object(server.shutil, "which", return_value="/usr/bin/fenrir-catalog"),
                patch.object(server.subprocess, "run", return_value=completed) as run,
            ):
                result = server.wallpaper_rights_review_snapshot()

        command = run.call_args.args[0]
        self.assertEqual(command[1:4], ["catalog", "rights", "queue"])
        self.assertEqual(command[command.index("--limit") + 1], "100")
        self.assertEqual(run.call_args.kwargs["timeout"], 20)
        self.assertEqual(result["queue"]["total_count"], 6)
        self.assertTrue(result["queue"]["has_more"])
        item = result["queue"]["items"][0]
        self.assertEqual(item["asset_id"], "asset-1")
        self.assertNotIn("source_url", item)
        self.assertNotIn("download_url", item)
        self.assertNotIn("evidence_url", json.dumps(item))
        self.assertTrue(result["read_only"])
        self.assertEqual(result["rights_decisions_created"], 0)
        self.assertEqual(result["acquisition_authorizations_created"], 0)

    def test_rights_snapshot_fails_closed_on_non_read_only_report(self):
        import json
        import tempfile
        from types import SimpleNamespace
        from unittest.mock import patch

        unsafe = {
            "queue": "human-rights-review",
            "read_only": False,
            "automatic_rights_decision": False,
            "automatic_acquisition_authorization": False,
            "status_counts": {},
            "results": [],
        }
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "catalog.sqlite3"
            database.write_bytes(b"catalog")
            completed = SimpleNamespace(returncode=0, stdout=json.dumps(unsafe), stderr="")
            with (
                patch.object(server, "CATALOG_DB", database),
                patch.object(server.shutil, "which", return_value="/usr/bin/fenrir-catalog"),
                patch.object(server.subprocess, "run", return_value=completed),
            ):
                result = server.wallpaper_rights_review_snapshot()
        self.assertFalse(result["available"])
        self.assertIn("read-only contract", result["detail"])
        self.assertEqual(result["rights_decisions_created"], 0)

    def test_rights_studio_starts_loopback_board_and_reuses_live_session(self):
        import io
        import tempfile
        from unittest.mock import Mock, patch

        token = "A" * 43
        stdout = io.StringIO("Fenrir Rights Review Board: http://127.0.0.1:32123/s/" + token + "/\n")
        process = Mock()
        process.stdout = stdout
        process.poll.return_value = None

        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "catalog.sqlite3"
            database.write_bytes(b"catalog")
            with (
                patch.object(server, "CATALOG_DB", database),
                patch.object(server, "RIGHTS_STUDIO_PROCESS", None),
                patch.object(server, "RIGHTS_STUDIO_URL", None),
                patch.object(server.shutil, "which", return_value="/usr/bin/fenrir-catalog"),
                patch.object(server.subprocess, "Popen", return_value=process) as popen,
                patch.object(server.select, "select", return_value=([stdout], [], [])),
            ):
                first = server.start_wallpaper_rights_review_studio()
                second = server.start_wallpaper_rights_review_studio()
                command = popen.call_args.args[0]
                self.assertTrue(first["started"])
                self.assertFalse(second["started"])
                self.assertTrue(second["already_running"])
                self.assertEqual(first["url"], second["url"])
                self.assertIn("rights", command)
                self.assertIn("board", command)
                self.assertIn("--no-browser", command)
                self.assertIn("--quarantine-root", command)
                self.assertEqual(command[command.index("--quarantine-root") + 1], str(server.QUARANTINE_ROOT))
                self.assertEqual(command[command.index("--port") + 1], "0")
                self.assertEqual(popen.call_count, 1)
                server.stop_wallpaper_rights_review_studio()

        process.terminate.assert_called_once()

    def test_rights_studio_rejects_non_loopback_board_url(self):
        import io
        import tempfile
        from unittest.mock import Mock, patch

        stdout = io.StringIO("Fenrir Rights Review Board: http://example.com/s/" + "B" * 43 + "/\\n")
        process = Mock()
        process.stdout = stdout
        process.poll.return_value = None
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "catalog.sqlite3"
            database.write_bytes(b"catalog")
            with (
                patch.object(server, "CATALOG_DB", database),
                patch.object(server, "RIGHTS_STUDIO_PROCESS", None),
                patch.object(server, "RIGHTS_STUDIO_URL", None),
                patch.object(server.shutil, "which", return_value="/usr/bin/fenrir-catalog"),
                patch.object(server.subprocess, "Popen", return_value=process),
                patch.object(server.select, "select", return_value=([stdout], [], [])),
            ):
                with self.assertRaisesRegex(RuntimeError, "non-loopback"):
                    server.start_wallpaper_rights_review_studio()
        process.terminate.assert_called_once()



class WallpaperDiscoverySchedulerTests(unittest.TestCase):
    def test_schedule_defaults_to_disabled(self):
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            with patch.object(server, "STATE", state), patch.object(
                server, "DISCOVERY_SCHEDULE_FILE", state / "schedule.json"
            ):
                result = server.wallpaper_discovery_schedule_snapshot()
        self.assertFalse(result["enabled"])
        self.assertEqual(result["interval_minutes"], 360)
        self.assertEqual(result["run_mode"], "continuous")
        self.assertEqual(result["last_status"], "disabled")

    def test_enable_starts_only_one_bounded_slice_and_persists_schedule(self):
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            with patch.object(server, "STATE", state), patch.object(
                server, "DISCOVERY_SCHEDULE_FILE", state / "schedule.json"
            ), patch.object(server, "_start_wallpaper_discovery_unlocked", return_value={
                "campaign_id": "campaign-1", "started": True,
            }) as start:
                result = server.configure_wallpaper_discovery_schedule({
                    "enabled": True,
                    "source": "openverse",
                    "profile": "fenrir-nordic-fantasy-v1",
                    "interval_minutes": 360,
                })
                saved = server.strict_json((state / "schedule.json").read_bytes())

        self.assertTrue(result["enabled"])
        self.assertEqual(result["campaign_id"], "campaign-1")
        self.assertEqual(saved["interval_minutes"], 360)
        self.assertEqual(saved["last_status"], "running")
        start.assert_called_once_with("openverse", "fenrir-nordic-fantasy-v1", None, max_queries=None)

    def test_enable_rejects_unsupported_run_mode_without_starting(self):
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            with patch.object(server, "STATE", state), patch.object(
                server, "DISCOVERY_SCHEDULE_FILE", state / "schedule.json"
            ), patch.object(server, "_start_wallpaper_discovery_unlocked") as start:
                with self.assertRaisesRegex(ValueError, "mode"):
                    server.configure_wallpaper_discovery_schedule({
                        "enabled": True,
                        "run_mode": "unbounded",
                        "source": "openverse",
                        "profile": "fenrir-nordic-fantasy-v1",
                    })
        start.assert_not_called()

    def test_enable_rejects_unsupported_interval_without_starting(self):
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            with patch.object(server, "STATE", state), patch.object(
                server, "DISCOVERY_SCHEDULE_FILE", state / "schedule.json"
            ), patch.object(server, "_start_wallpaper_discovery_unlocked") as start:
                with self.assertRaisesRegex(ValueError, "interval"):
                    server.configure_wallpaper_discovery_schedule({
                        "enabled": True, "source": "openverse",
                        "profile": "fenrir-nordic-fantasy-v1",
                        "interval_minutes": 5,
                    })
        start.assert_not_called()

    def test_commons_schedule_requires_contact_identifier(self):
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            with patch.object(server, "STATE", state), patch.object(
                server, "DISCOVERY_SCHEDULE_FILE", state / "schedule.json"
            ), patch.object(server, "_start_wallpaper_discovery_unlocked") as start:
                with self.assertRaisesRegex(ValueError, "contact"):
                    server.configure_wallpaper_discovery_schedule({
                        "enabled": True, "source": "wikimedia_commons",
                        "profile": "fenrir-nordic-fantasy-v1",
                        "interval_minutes": 360,
                    })
        start.assert_not_called()

    def test_pause_leaves_an_active_slice_alone(self):
        import tempfile
        from unittest.mock import patch

        class ActiveProcess:
            def poll(self):
                return None

        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            schedule_file = state / "schedule.json"
            schedule = server._default_wallpaper_discovery_schedule()
            schedule.update({
                "enabled": True, "campaign_id": "campaign-1",
                "last_status": "running", "next_run_at": 999999999,
            })
            server.atomic_json(schedule_file, schedule)
            active = ActiveProcess()
            with patch.object(server, "STATE", state), patch.object(
                server, "DISCOVERY_SCHEDULE_FILE", schedule_file
            ), patch.object(server, "DISCOVERY_PROCESS", active):
                result = server.configure_wallpaper_discovery_schedule({"enabled": False})
        self.assertFalse(result["enabled"])
        self.assertEqual(result["last_status"], "paused")
        self.assertEqual(result["campaign_id"], "campaign-1")

    def test_tick_waits_until_due(self):
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            schedule = server._default_wallpaper_discovery_schedule()
            schedule.update({
                "enabled": True, "run_mode": "scheduled", "next_run_at": 2000,
                "campaign_id": "campaign-1", "last_status": "scheduled",
            })
            server.atomic_json(state / "schedule.json", schedule)
            with patch.object(server, "STATE", state), patch.object(
                server, "DISCOVERY_SCHEDULE_FILE", state / "schedule.json"
            ), patch.object(server, "wallpaper_campaign_snapshot", return_value={
                "process_running": False,
                "campaign": {"campaign_id": "campaign-1", "status": "paused"},
            }), patch.object(server, "_start_wallpaper_discovery_unlocked") as start:
                result = server.wallpaper_discovery_scheduler_tick(now=1999)
        self.assertTrue(result["enabled"])
        start.assert_not_called()

    def test_tick_runs_one_slice_and_schedules_next_interval(self):
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            schedule = server._default_wallpaper_discovery_schedule()
            schedule.update({
                "enabled": True, "run_mode": "scheduled", "interval_minutes": 360,
                "next_run_at": 1000, "campaign_id": "campaign-1",
                "last_status": "scheduled",
            })
            server.atomic_json(state / "schedule.json", schedule)
            with patch.object(server, "STATE", state), patch.object(
                server, "DISCOVERY_SCHEDULE_FILE", state / "schedule.json"
            ), patch.object(server, "wallpaper_campaign_snapshot", return_value={
                "process_running": False,
                "campaign": {"campaign_id": "campaign-1", "status": "paused"},
            }), patch.object(server, "_start_wallpaper_discovery_unlocked", return_value={
                "campaign_id": "campaign-1", "started": True,
            }) as start:
                result = server.wallpaper_discovery_scheduler_tick(now=1000)
                saved = server.strict_json((state / "schedule.json").read_bytes())
        self.assertTrue(result["enabled"])
        self.assertEqual(saved["last_run_at"], 1000)
        self.assertEqual(saved["next_run_at"], 1000 + 360 * 60)
        start.assert_called_once_with("openverse", "fenrir-nordic-fantasy-v1", None, campaign_id="campaign-1", max_queries=None)

    def test_continuous_mode_starts_next_slice_without_waiting_for_interval(self):
        import tempfile
        from unittest.mock import patch

        queue = [
            {"source": "openverse", "profile": "fenrir-nordic-fantasy-v1", "contact": None},
            {"source": "wallhaven", "profile": "fenrir-cosmic-sci-fi-v1", "contact": None},
        ]
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            schedule = server._default_wallpaper_discovery_schedule()
            schedule.update({
                "enabled": True,
                "run_mode": "continuous",
                "queue": queue,
                "queue_index": 0,
                "campaign_ids": ["campaign-openverse", "campaign-wallhaven"],
                "completed_indices": [],
                "campaign_id": "campaign-openverse",
                "next_run_at": 999999,
                "last_status": "scheduled",
            })
            server.atomic_json(state / "schedule.json", schedule)
            with patch.object(server, "STATE", state), patch.object(
                server, "DISCOVERY_SCHEDULE_FILE", state / "schedule.json"
            ), patch.object(server, "wallpaper_campaign_snapshot", return_value={
                "process_running": False,
                "campaign": {"campaign_id": "campaign-openverse", "status": "paused"},
            }), patch.object(server, "_start_wallpaper_discovery_unlocked", return_value={
                "campaign_id": "campaign-wallhaven", "started": True,
            }) as start:
                result = server.wallpaper_discovery_scheduler_tick(now=1000)
                saved = server.strict_json((state / "schedule.json").read_bytes())

        self.assertTrue(result["enabled"])
        self.assertEqual(result["run_mode"], "continuous")
        self.assertEqual(result["queue_index"], 1)
        self.assertEqual(saved["next_run_at"], 1000)
        start.assert_called_once_with(
            "wallhaven", "fenrir-cosmic-sci-fi-v1", None,
            campaign_id="campaign-wallhaven", max_queries=None,
        )

    def test_completed_campaign_stops_for_human_review(self):
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            schedule = server._default_wallpaper_discovery_schedule()
            schedule.update({"enabled": True, "campaign_id": "campaign-1"})
            server.atomic_json(state / "schedule.json", schedule)
            with patch.object(server, "STATE", state), patch.object(
                server, "DISCOVERY_SCHEDULE_FILE", state / "schedule.json"
            ), patch.object(server, "wallpaper_campaign_snapshot", return_value={
                "process_running": False,
                "campaign": {"campaign_id": "campaign-1", "status": "completed"},
            }), patch.object(server, "_start_wallpaper_discovery_unlocked") as start:
                result = server.wallpaper_discovery_scheduler_tick(now=999999999)
        self.assertFalse(result["enabled"])
        self.assertEqual(result["last_status"], "needs_review")
        self.assertIn("Human rights review", result["pause_reason"])
        start.assert_not_called()

    def test_failed_campaign_disables_scheduler(self):
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            schedule = server._default_wallpaper_discovery_schedule()
            schedule.update({"enabled": True, "campaign_id": "campaign-1"})
            server.atomic_json(state / "schedule.json", schedule)
            with patch.object(server, "STATE", state), patch.object(
                server, "DISCOVERY_SCHEDULE_FILE", state / "schedule.json"
            ), patch.object(server, "wallpaper_campaign_snapshot", return_value={
                "process_running": False,
                "campaign": {"campaign_id": "campaign-1", "status": "failed", "error_summary": "provider unavailable"},
            }):
                result = server.wallpaper_discovery_scheduler_tick(now=999999999)
        self.assertFalse(result["enabled"])
        self.assertEqual(result["last_status"], "paused_error")
        self.assertIn("provider unavailable", result["last_error"])

    def test_running_process_is_never_started_in_parallel(self):
        import tempfile
        from unittest.mock import patch

        class ActiveProcess:
            def poll(self):
                return None

        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            schedule = server._default_wallpaper_discovery_schedule()
            schedule.update({"enabled": True, "campaign_id": "campaign-1"})
            server.atomic_json(state / "schedule.json", schedule)
            with patch.object(server, "STATE", state), patch.object(
                server, "DISCOVERY_SCHEDULE_FILE", state / "schedule.json"
            ), patch.object(server, "DISCOVERY_PROCESS", ActiveProcess()), patch.object(
                server, "wallpaper_campaign_snapshot", return_value={
                    "process_running": True,
                    "campaign": {"status": "running"},
                }
            ), patch.object(server, "_start_wallpaper_discovery_unlocked") as start:
                result = server.wallpaper_discovery_scheduler_tick(now=999999999)
        self.assertTrue(result["enabled"])
        self.assertEqual(result["last_status"], "running")
        start.assert_not_called()

    def test_campaign_queue_accepts_full_32_source_profile_matrix(self):
        sources = ("openverse", "wikimedia_commons", "wallhaven", "cleveland_museum")
        profiles = (
            "fenrir-nordic-fantasy-v1",
            "fenrir-cinematic-nature-v1",
            "fenrir-cosmic-sci-fi-v1",
            "fenrir-arctic-blue-v1",
            "fenrir-architecture-monochrome-v1",
            "fenrir-red-violet-dark-fantasy-v1",
            "fenrir-deep-ocean-bioluminescence-v1",
            "fenrir-obsidian-abstract-v1",
        )
        queue = [
            {
                "source": source,
                "profile": profile,
                "contact": "fenrir@example.org" if source == "wikimedia_commons" else None,
            }
            for source in sources
            for profile in profiles
        ]
        validated = server._validate_wallpaper_campaign_queue(queue)
        self.assertEqual(len(validated), 32)
        self.assertTrue(any(item["source"] == "cleveland_museum" for item in validated))
        with self.assertRaisesRegex(ValueError, "32 unique"):
            server._validate_wallpaper_campaign_queue(queue + [queue[0]])

    def test_campaign_queue_validation_rejects_duplicates_and_requires_commons_contact(self):
        queue = [
            {"source": "openverse", "profile": "fenrir-nordic-fantasy-v1"},
            {"source": "wallhaven", "profile": "fenrir-nordic-fantasy-v1"},
        ]
        validated = server._validate_wallpaper_campaign_queue(queue)
        self.assertEqual(len(validated), 2)
        with self.assertRaisesRegex(ValueError, "only once"):
            server._validate_wallpaper_campaign_queue(queue + [queue[0]])
        with self.assertRaisesRegex(ValueError, "contact"):
            server._validate_wallpaper_campaign_queue([
                {"source": "wikimedia_commons", "profile": "fenrir-nordic-fantasy-v1"}
            ])
        with self.assertRaises(ValueError):
            server._validate_wallpaper_campaign_queue([
                {"source": {"invalid": "type"}, "profile": "fenrir-nordic-fantasy-v1"}
            ])

    def test_queue_enable_persists_unique_campaigns_and_starts_first_item(self):
        import tempfile
        from unittest.mock import patch

        queue = [
            {"source": "openverse", "profile": "fenrir-nordic-fantasy-v1", "contact": None},
            {"source": "wallhaven", "profile": "fenrir-cosmic-sci-fi-v1", "contact": None},
            {"source": "wikimedia_commons", "profile": "fenrir-arctic-blue-v1", "contact": "fenrir@example.org"},
        ]
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            with patch.object(server, "STATE", state), patch.object(
                server, "DISCOVERY_SCHEDULE_FILE", state / "schedule.json"
            ), patch.object(server, "_start_wallpaper_discovery_unlocked", return_value={
                "campaign_id": "queue-campaign-1", "started": True,
            }) as start:
                result = server.configure_wallpaper_discovery_schedule({
                    "enabled": True, "queue": queue, "interval_minutes": 180,
                })
                saved = server.strict_json((state / "schedule.json").read_bytes())

        self.assertTrue(result["enabled"])
        self.assertEqual(result["queue_total"], 3)
        self.assertEqual(result["queue_index"], 0)
        self.assertEqual(result["queue_current"], {
            "source": "openverse",
            "profile": "fenrir-nordic-fantasy-v1",
            "contact_configured": False,
            "completed": False,
            "has_saved_campaign": True,
        })
        self.assertNotIn("contact", result["queue"][2])
        self.assertTrue(result["queue"][2]["contact_configured"])
        self.assertEqual(saved["schema_version"], 4)
        self.assertEqual(saved["run_mode"], "continuous")
        self.assertEqual(saved["queue"], queue)
        self.assertEqual(saved["queue_index"], 0)
        self.assertEqual(saved["campaign_ids"], ["queue-campaign-1", None, None])
        self.assertEqual(saved["completed_indices"], [])
        start.assert_called_once_with(
            "openverse", "fenrir-nordic-fantasy-v1", None, max_queries=None
        )

    def test_completed_campaign_advances_to_next_queued_item(self):
        import tempfile
        from unittest.mock import patch

        queue = [
            {"source": "openverse", "profile": "fenrir-nordic-fantasy-v1", "contact": None},
            {"source": "wikimedia_commons", "profile": "fenrir-arctic-blue-v1", "contact": "fenrir@example.org"},
        ]
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            schedule = server._default_wallpaper_discovery_schedule()
            schedule.update({
                "enabled": True, "queue": queue, "queue_index": 0,
                "interval_minutes": 180,
                "campaign_id": "campaign-1", "last_status": "scheduled",
                "next_run_at": 1000,
                "campaign_ids": ["campaign-1", None],
                "completed_indices": [],
            })
            server.atomic_json(state / "schedule.json", schedule)
            with patch.object(server, "STATE", state), patch.object(
                server, "DISCOVERY_SCHEDULE_FILE", state / "schedule.json"
            ), patch.object(server, "wallpaper_campaign_snapshot", return_value={
                "process_running": False,
                "campaign": {"campaign_id": "campaign-1", "status": "completed"},
            }), patch.object(server, "_start_wallpaper_discovery_unlocked", return_value={
                "campaign_id": "campaign-2", "started": True,
            }) as start:
                result = server.wallpaper_discovery_scheduler_tick(now=1000)
                saved = server.strict_json((state / "schedule.json").read_bytes())

        self.assertTrue(result["enabled"])
        self.assertEqual(result["queue_index"], 1)
        self.assertEqual(result["queue_position"], 2)
        self.assertEqual(result["source"], "wikimedia_commons")
        self.assertEqual(result["profile"], "fenrir-arctic-blue-v1")
        self.assertEqual(result["campaign_id"], "campaign-2")
        self.assertEqual(saved["next_run_at"], 1000)  # Continuous mode starts the next turn immediately.
        start.assert_called_once_with(
            "wikimedia_commons", "fenrir-arctic-blue-v1", "fenrir@example.org",
            campaign_id=None, max_queries=None,
        )

    def test_final_queued_campaign_stops_for_human_review(self):
        import tempfile
        from unittest.mock import patch

        queue = [{"source": "openverse", "profile": "fenrir-nordic-fantasy-v1", "contact": None}]
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            schedule = server._default_wallpaper_discovery_schedule()
            schedule.update({
                "enabled": True, "queue": queue, "queue_index": 0,
                "campaign_id": "campaign-1",
                "campaign_ids": ["campaign-1"],
                "completed_indices": [],
            })
            server.atomic_json(state / "schedule.json", schedule)
            with patch.object(server, "STATE", state), patch.object(
                server, "DISCOVERY_SCHEDULE_FILE", state / "schedule.json"
            ), patch.object(server, "wallpaper_campaign_snapshot", return_value={
                "process_running": False,
                "campaign": {"campaign_id": "campaign-1", "status": "completed"},
            }), patch.object(server, "_start_wallpaper_discovery_unlocked") as start:
                result = server.wallpaper_discovery_scheduler_tick(now=1000)
                saved = server.strict_json((state / "schedule.json").read_bytes())

        self.assertFalse(result["enabled"])
        self.assertEqual(result["last_status"], "needs_review")
        self.assertTrue(result["queue_completed"])
        self.assertEqual(result["queue_index"], 1)
        self.assertIsNone(saved["next_run_at"])
        self.assertIn("Human rights review", result["pause_reason"])
        start.assert_not_called()

    def test_paused_queue_resumes_without_restarting_completed_campaigns(self):
        import tempfile
        from unittest.mock import patch

        queue = [
            {"source": "openverse", "profile": "fenrir-nordic-fantasy-v1", "contact": None},
            {"source": "wallhaven", "profile": "fenrir-cosmic-sci-fi-v1", "contact": None},
        ]
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            schedule = server._default_wallpaper_discovery_schedule()
            schedule.update({
                "enabled": False, "queue": queue, "queue_index": 1,
                "source": "wallhaven", "profile": "fenrir-cosmic-sci-fi-v1",
                "campaign_ids": ["campaign-1", "campaign-2"],
                "completed_indices": [],
                "last_status": "paused",
            })
            server.atomic_json(state / "schedule.json", schedule)
            with patch.object(server, "STATE", state), patch.object(
                server, "DISCOVERY_SCHEDULE_FILE", state / "schedule.json"
            ), patch.object(server, "wallpaper_campaign_snapshot", return_value={
                "process_running": False,
                "campaign": {"campaign_id": "campaign-1", "status": "paused"},
            }), patch.object(server, "_start_wallpaper_discovery_unlocked", return_value={
                "campaign_id": "campaign-2", "started": True,
            }) as start:
                result = server.configure_wallpaper_discovery_schedule({
                    "enabled": True, "resume_existing_queue": True,
                })

        self.assertTrue(result["enabled"])
        self.assertEqual(result["queue_index"], 1)
        self.assertEqual(result["campaign_id"], "campaign-2")
        start.assert_called_once_with(
            "wallhaven", "fenrir-cosmic-sci-fi-v1", None,
            campaign_id="campaign-2", max_queries=None,
        )

    def test_resume_skips_campaign_completed_while_queue_was_paused(self):
        import tempfile
        from unittest.mock import patch

        queue = [
            {"source": "openverse", "profile": "fenrir-nordic-fantasy-v1", "contact": None},
            {"source": "wallhaven", "profile": "fenrir-cosmic-sci-fi-v1", "contact": None},
        ]
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            schedule = server._default_wallpaper_discovery_schedule()
            schedule.update({
                "enabled": False, "queue": queue, "queue_index": 0,
                "campaign_ids": ["campaign-1", None],
                "completed_indices": [],
                "last_status": "paused",
            })
            server.atomic_json(state / "schedule.json", schedule)
            with patch.object(server, "STATE", state), patch.object(
                server, "DISCOVERY_SCHEDULE_FILE", state / "schedule.json"
            ), patch.object(server, "wallpaper_campaign_snapshot", return_value={
                "process_running": False,
                "campaign": {"campaign_id": "campaign-1", "status": "completed"},
            }), patch.object(server, "_start_wallpaper_discovery_unlocked", return_value={
                "campaign_id": "campaign-2", "started": True,
            }) as start:
                result = server.configure_wallpaper_discovery_schedule({
                    "enabled": True, "resume_existing_queue": True,
                })

        self.assertTrue(result["enabled"])
        self.assertEqual(result["queue_index"], 1)
        self.assertEqual(result["source"], "wallhaven")
        self.assertEqual(result["campaign_id"], "campaign-2")
        start.assert_called_once_with(
            "wallhaven", "fenrir-cosmic-sci-fi-v1", None,
            campaign_id=None, max_queries=None,
        )

    def test_scheduler_rotates_after_each_bounded_slice_and_resumes_saved_campaign_ids(self):
        import tempfile
        from unittest.mock import patch

        queue = [
            {"source": "openverse", "profile": "fenrir-nordic-fantasy-v1", "contact": None},
            {"source": "wallhaven", "profile": "fenrir-cosmic-sci-fi-v1", "contact": None},
            {"source": "wikimedia_commons", "profile": "fenrir-arctic-blue-v1", "contact": "fenrir@example.org"},
        ]
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            schedule = server._default_wallpaper_discovery_schedule()
            schedule.update({
                "enabled": True,
                "queue": queue,
                "queue_index": 0,
                "campaign_ids": ["campaign-openverse", "campaign-wallhaven", "campaign-commons"],
                "completed_indices": [],
                "campaign_id": "campaign-openverse",
                "interval_minutes": 60,
                "next_run_at": 1000,
            })
            server.atomic_json(state / "schedule.json", schedule)
            with patch.object(server, "STATE", state), patch.object(
                server, "DISCOVERY_SCHEDULE_FILE", state / "schedule.json"
            ), patch.object(server, "wallpaper_campaign_snapshot", return_value={
                "process_running": False,
                "campaign": {
                    "campaign_id": "campaign-openverse",
                    "status": "paused",
                },
            }), patch.object(server, "_start_wallpaper_discovery_unlocked", return_value={
                "campaign_id": "campaign-wallhaven", "started": True,
            }) as start:
                result = server.wallpaper_discovery_scheduler_tick(now=1000)
                saved = server.strict_json((state / "schedule.json").read_bytes())

        self.assertTrue(result["enabled"])
        self.assertEqual(result["queue_index"], 1)
        self.assertEqual(result["source"], "wallhaven")
        self.assertEqual(saved["campaign_ids"], [
            "campaign-openverse", "campaign-wallhaven", "campaign-commons"
        ])
        self.assertEqual(saved["completed_indices"], [])
        start.assert_called_once_with(
            "wallhaven", "fenrir-cosmic-sci-fi-v1", None,
            campaign_id="campaign-wallhaven", max_queries=None,
        )

    def test_scheduler_returns_to_the_saved_cursor_for_an_unfinished_campaign(self):
        import tempfile
        from unittest.mock import patch

        queue = [
            {"source": "openverse", "profile": "fenrir-nordic-fantasy-v1", "contact": None},
            {"source": "wallhaven", "profile": "fenrir-cosmic-sci-fi-v1", "contact": None},
            {"source": "wikimedia_commons", "profile": "fenrir-arctic-blue-v1", "contact": "fenrir@example.org"},
        ]
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            schedule = server._default_wallpaper_discovery_schedule()
            schedule.update({
                "enabled": True,
                "queue": queue,
                "queue_index": 2,
                "campaign_ids": ["campaign-openverse", "campaign-wallhaven", "campaign-commons"],
                "completed_indices": [],
                "campaign_id": "campaign-commons",
                "interval_minutes": 60,
                "next_run_at": 1000,
            })
            server.atomic_json(state / "schedule.json", schedule)
            with patch.object(server, "STATE", state), patch.object(
                server, "DISCOVERY_SCHEDULE_FILE", state / "schedule.json"
            ), patch.object(server, "wallpaper_campaign_snapshot", return_value={
                "process_running": False,
                "campaign": {
                    "campaign_id": "campaign-commons",
                    "status": "paused",
                },
            }), patch.object(server, "_start_wallpaper_discovery_unlocked", return_value={
                "campaign_id": "campaign-openverse", "started": True,
            }) as start:
                result = server.wallpaper_discovery_scheduler_tick(now=1000)

        self.assertEqual(result["queue_index"], 0)
        self.assertEqual(result["source"], "openverse")
        start.assert_called_once_with(
            "openverse", "fenrir-nordic-fantasy-v1", None,
            campaign_id="campaign-openverse", max_queries=None,
        )

    def test_legacy_scheduler_state_migrates_to_an_empty_queue(self):
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            legacy = server._default_wallpaper_discovery_schedule()
            legacy["schema_version"] = 1
            legacy.pop("queue")
            legacy.pop("queue_index")
            server.atomic_json(state / "schedule.json", legacy)
            with patch.object(server, "DISCOVERY_SCHEDULE_FILE", state / "schedule.json"):
                loaded = server.read_wallpaper_discovery_schedule()

        self.assertEqual(loaded["queue"], [])
        self.assertEqual(loaded["queue_index"], 0)
        self.assertEqual(loaded["source"], "openverse")
        self.assertEqual(loaded["run_mode"], "scheduled")

    def test_legacy_schema_v2_queue_migrates_campaign_id_to_active_entry(self):
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            legacy = {
                "schema_version": 2,
                "enabled": False,
                "source": "wallhaven",
                "profile": "fenrir-cosmic-sci-fi-v1",
                "contact": None,
                "interval_minutes": 360,
                "next_run_at": None,
                "last_run_at": None,
                "last_status": "paused",
                "pause_reason": None,
                "last_error": None,
                "campaign_id": "legacy-active-campaign",
                "queue": [
                    {"source": "openverse", "profile": "fenrir-nordic-fantasy-v1", "contact": None},
                    {"source": "wallhaven", "profile": "fenrir-cosmic-sci-fi-v1", "contact": None},
                ],
                "queue_index": 1,
            }
            schedule_file = state / "schedule.json"
            server.atomic_json(schedule_file, legacy)
            with patch.object(server, "DISCOVERY_SCHEDULE_FILE", schedule_file):
                migrated = server.read_wallpaper_discovery_schedule()

        self.assertEqual(migrated["campaign_ids"], [None, "legacy-active-campaign"])
        self.assertEqual(migrated["completed_indices"], [])
        self.assertEqual(migrated["queue_index"], 1)
        self.assertEqual(migrated["campaign_id"], "legacy-active-campaign")
        self.assertEqual(migrated["run_mode"], "scheduled")

    def test_corrupt_scheduler_state_fails_closed(self):
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            schedule_file = state / "schedule.json"
            schedule_file.write_text('{"schema_version":1,"enabled":"yes"}', encoding="utf-8")
            with patch.object(server, "DISCOVERY_SCHEDULE_FILE", schedule_file):
                result = server.wallpaper_discovery_schedule_snapshot()
        self.assertFalse(result["enabled"])
        self.assertEqual(result["last_status"], "invalid")
        self.assertIn("invalid", result["pause_reason"].lower())




class PublicWallpaperLibraryTests(unittest.TestCase):
    def test_public_library_preview_uses_read_only_cli_and_validates_report(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        import json
        import tempfile

        payload = {
            "dry_run": True,
            "active_volumes": ["volume-01", "volume-02", "volume-03"],
            "manifest_records": 1000,
            "unique_images": 980,
            "already_present": 100,
            "planned_downloads": 880,
            "selected_downloads": 880,
            "selected_download_bytes": 1024 * 1024 * 1024,
            "remaining_after_limit": 0,
        }
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "Pictures" / "Wallpapers"
            completed = SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")
            with (
                patch.object(server.shutil, "which", return_value="/usr/bin/fenrir-wallpaper"),
                patch.object(server, "current_wallpaper_directory", return_value=destination),
                patch.object(server.subprocess, "run", return_value=completed) as run,
            ):
                result = server.public_library_preview()

        command = run.call_args.args[0]
        self.assertEqual(command, ["/usr/bin/fenrir-wallpaper", "sync-library", "--dry-run", "--json"])
        self.assertTrue(result["read_only"])
        self.assertEqual(result["active_volumes"], ["volume-01", "volume-02", "volume-03"])
        self.assertEqual(result["selected_downloads"], 880)
        self.assertEqual(result["selected_download_bytes"], 1024 * 1024 * 1024)
        self.assertFalse(destination.exists())
        self.assertEqual(run.call_args.kwargs["timeout"], 180)

    def test_public_library_preview_rejects_non_dry_run_report(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        import json

        payload = {
            "dry_run": False,
            "active_volumes": ["volume-01"],
            "manifest_records": 1,
            "unique_images": 1,
            "already_present": 0,
            "planned_downloads": 1,
            "selected_downloads": 1,
            "selected_download_bytes": 1024,
            "remaining_after_limit": 0,
        }
        with patch.object(server.shutil, "which", return_value="/usr/bin/fenrir-wallpaper"), patch.object(
            server.subprocess, "run",
            return_value=SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr=""),
        ):
            with self.assertRaisesRegex(ValueError, "invalid public-library preview"):
                server.public_library_preview()

    def test_public_library_sync_requires_explicit_confirmation(self):
        from unittest.mock import patch

        with patch.object(server, "public_library_preview") as preview, patch.object(
            server.subprocess, "Popen"
        ) as process:
            with self.assertRaisesRegex(ValueError, "Explicit confirmation"):
                server.start_public_library_sync(False, 0, 0)
        preview.assert_not_called()
        process.assert_not_called()

    def test_public_library_sync_refuses_to_overlap_catalog_sync(self):
        from unittest.mock import patch

        catalog_process = type("Process", (), {"poll": lambda self: None})()
        with patch.object(server, "WALLPAPER_SYNC", catalog_process), patch.object(
            server, "public_library_preview"
        ) as preview, patch.object(server.subprocess, "Popen") as process:
            with self.assertRaisesRegex(ValueError, "private Catalog synchronization is running"):
                server.start_public_library_sync(True, 12, 12345)
        preview.assert_not_called()
        process.assert_not_called()

    def test_public_library_sync_rechecks_preview_and_starts_fixed_command(self):
        import tempfile
        from types import SimpleNamespace
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "state"
            log_path = state / "public-library-sync.log"
            fake_process = SimpleNamespace(pid=4567, poll=lambda: None)
            preview = {
                "available": True,
                "read_only": True,
                "active_volumes": ["volume-01", "volume-02", "volume-03"],
                "selected_downloads": 12,
                "selected_download_bytes": 12_345,
                "destination": str(root / "Pictures" / "Wallpapers"),
            }
            with (
                patch.object(server, "PUBLIC_LIBRARY_SYNC", None),
                patch.object(server, "WALLPAPER_SYNC", None),
                patch.object(server, "STATE", state),
                patch.object(server, "PUBLIC_LIBRARY_SYNC_LOG", log_path),
                patch.object(server.shutil, "which", return_value="/usr/bin/fenrir-wallpaper"),
                patch.object(server, "public_library_preview", return_value=preview) as plan,
                patch.object(server.subprocess, "Popen", return_value=fake_process) as popen,
            ):
                result = server.start_public_library_sync(True, 12, 12_345)

            self.assertTrue(result["started"])
            self.assertEqual(result["pid"], 4567)
            self.assertEqual(result["selected_downloads"], 12)
            self.assertTrue(log_path.is_file())
            self.assertEqual(
                popen.call_args.args[0],
                ["/usr/bin/fenrir-wallpaper", "sync-library", "--json"],
            )
            self.assertIs(popen.call_args.kwargs["stdin"], server.subprocess.DEVNULL)
            self.assertIs(popen.call_args.kwargs["stderr"], server.subprocess.STDOUT)
            plan.assert_called_once()

    def test_public_library_sync_rejects_changed_registry_totals_since_preview(self):
        from unittest.mock import patch

        preview = {
            "selected_downloads": 13,
            "selected_download_bytes": 13_000,
        }
        with patch.object(server, "PUBLIC_LIBRARY_SYNC", None), patch.object(
            server, "WALLPAPER_SYNC", None
        ), patch.object(server.shutil, "which", return_value="/usr/bin/fenrir-wallpaper"), patch.object(
            server, "public_library_preview", return_value=preview
        ), patch.object(server.subprocess, "Popen") as process:
            with self.assertRaisesRegex(ValueError, "changed after preview"):
                server.start_public_library_sync(True, 12, 12_000)
        process.assert_not_called()

    def test_public_library_sync_returns_without_starting_when_everything_is_present(self):
        from unittest.mock import patch

        preview = {"selected_downloads": 0, "selected_download_bytes": 0, "message": "all present"}
        with patch.object(server, "PUBLIC_LIBRARY_SYNC", None), patch.object(
            server, "WALLPAPER_SYNC", None
        ), patch.object(server.shutil, "which", return_value="/usr/bin/fenrir-wallpaper"), patch.object(
            server, "public_library_preview", return_value=preview
        ), patch.object(server.subprocess, "Popen") as process:
            result = server.start_public_library_sync(True, 0, 0)
        self.assertFalse(result["started"])
        process.assert_not_called()

    def test_public_library_status_reports_running_process_and_private_log_tail(self):
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temporary:
            log_path = Path(temporary) / "public-library-sync.log"
            log_path.write_text("Verified volume-01 image 1/10\n", encoding="utf-8")
            process = type("Process", (), {"poll": lambda self: None})()
            with patch.object(server, "PUBLIC_LIBRARY_SYNC", process), patch.object(
                server, "PUBLIC_LIBRARY_SYNC_LOG", log_path
            ), patch.object(server.shutil, "which", return_value="/usr/bin/fenrir-wallpaper"):
                result = server.public_library_sync_snapshot()
        self.assertTrue(result["available"])
        self.assertTrue(result["running"])
        self.assertIn("Verified volume-01", result["log"])


if __name__ == "__main__":
    unittest.main()
