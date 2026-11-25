from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from apps.fenrir_settings.settings_core import (
    DEFAULTS, load_settings, mode_for_target, render_hypridle, save_settings,
    validate_settings, write_runtime_files,
)

class SettingsCoreTests(unittest.TestCase):
    def test_defaults_are_safe_and_match_fimbulwinter_baseline(self):
        settings = validate_settings(DEFAULTS)
        self.assertEqual(settings["wallpaper"]["interval_minutes"], 15)
        self.assertEqual(settings["theme"]["surface_opacity"], 0.60)
        self.assertFalse(settings["session"]["allow_screen_off"])
        self.assertFalse(settings["session"]["auto_lock"])
        self.assertFalse(settings["session"]["auto_suspend"])

    def test_validation_rejects_unreasonable_interval_and_opacity(self):
        data = validate_settings(DEFAULTS)
        data["wallpaper"]["interval_minutes"] = 0
        with self.assertRaises(ValueError):
            validate_settings(data)
        data = validate_settings(DEFAULTS)
        data["theme"]["surface_opacity"] = 0.1
        with self.assertRaises(ValueError):
            validate_settings(data)

    def test_roundtrip_keeps_unknown_user_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.toml"
            data = validate_settings(DEFAULTS)
            data["custom"] = {"note": "preserve me"}
            save_settings(data, path)
            loaded = load_settings(path)
            self.assertEqual(loaded["custom"]["note"], "preserve me")
            self.assertEqual(loaded["theme"]["surface_opacity"], 0.60)

    def test_updates_make_a_private_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.toml"
            save_settings(DEFAULTS, path)
            data = load_settings(path)
            data["wallpaper"]["interval_minutes"] = 20
            save_settings(data, path)
            backups = list(Path(directory).glob("settings.toml.backup-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(backups[0].stat().st_mode & 0o777, 0o600)
            self.assertEqual(load_settings(path)["wallpaper"]["interval_minutes"], 20)

    def test_idle_defaults_never_lock_or_power_off(self):
        content = render_hypridle(validate_settings(DEFAULTS))
        self.assertNotIn("on-timeout", content)
        self.assertNotIn("dpms off", content)
        self.assertNotIn("lock-session", content)
        self.assertIn("Automatic idle locking and display power-off are disabled", content)

    def test_idle_actions_only_appear_when_enabled(self):
        data = validate_settings(DEFAULTS)
        data["session"]["auto_lock"] = True
        data["session"]["allow_screen_off"] = True
        content = render_hypridle(data)
        self.assertIn("loginctl lock-session", content)
        self.assertIn("dpms off", content)

    def test_monitor_prefers_155_only_when_advertised(self):
        mode, exact = mode_for_target(["2560x1440@144Hz", "2560x1440@155.00Hz", "1920x1080@60Hz"])
        self.assertEqual(mode, "2560x1440@155.00Hz")
        self.assertTrue(exact)
        mode, exact = mode_for_target(["2560x1440@144Hz", "1920x1080@60Hz"], current="2560x1440@144Hz")
        self.assertEqual(mode, "2560x1440@144Hz")
        self.assertFalse(exact)

    def test_runtime_files_are_created(self):
        with tempfile.TemporaryDirectory() as directory:
            write_runtime_files(validate_settings(DEFAULTS), Path(directory))
            root = Path(directory) / ".config"
            self.assertTrue((root / "hypr" / "hypridle.conf").is_file())
            self.assertTrue((root / "hypr" / "fenrir-settings.lua").is_file())
            self.assertTrue((root / "waybar" / "fenrir-layout.css").is_file())
            managed = root / "hypr" / "fenrir-settings.lua"
            managed.write_text("# user generated config before Fenrir update\n", encoding="utf-8")
            write_runtime_files(validate_settings(DEFAULTS), Path(directory))
            backups = list((Path(directory) / ".local" / "state" / "fenrir" / "backups").rglob("fenrir-settings.lua"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(encoding="utf-8"), "# user generated config before Fenrir update\n")

if __name__ == "__main__":
    unittest.main()
