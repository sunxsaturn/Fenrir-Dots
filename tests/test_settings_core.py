from __future__ import annotations
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SETTINGS_APP = ROOT / "apps/fenrir-settings"
sys.path.insert(0, str(SETTINGS_APP))
import core  # noqa: E402


class SettingsCoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / "config"
        self.state = self.root / "state"
        self.config.mkdir()
        core.CONFIG_HOME = self.config
        core.STATE_HOME = self.state
        self.settings = self.config / "fenrir" / "settings.toml"
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text(
            "# User settings\n[wallpaper]\ndirectory = \"~/Wallpapers Custom\"\ninterval_minutes = 15\nkeep_me = true\n"
            "[theme]\nsurface_opacity = 0.60\nblur_enabled = true\ndynamic_colors = true\npreset = \"obsidian\"\n",
            encoding="utf-8",
        )

    def test_setting_update_is_validated_backed_up_and_preserves_unmanaged_keys(self):
        backup = core.set_setting("wallpaper", "interval_minutes", 30, self.settings)
        content = self.settings.read_text(encoding="utf-8")
        self.assertIn('directory = "~/Wallpapers Custom"', content)
        self.assertIn("keep_me = true", content)
        self.assertIn("interval_minutes = 30", content)
        self.assertTrue(backup and backup.is_file())

    def test_multi_monitor_rotation_settings_are_validated_and_persisted(self):
        core.set_setting("wallpaper", "monitor_mode", "independent", self.settings)
        core.set_setting("wallpaper", "history_depth", 30, self.settings)
        loaded = core.load_settings(self.settings)
        self.assertEqual(loaded["wallpaper"]["monitor_mode"], "independent")
        self.assertEqual(loaded["wallpaper"]["history_depth"], 30)
        with self.assertRaises(ValueError):
            core.set_setting("wallpaper", "monitor_mode", "span", self.settings)
        with self.assertRaises(ValueError):
            core.set_setting("wallpaper", "history_depth", 101, self.settings)

    def test_invalid_settings_are_rejected_without_mutating_file(self):
        before = self.settings.read_text(encoding="utf-8")
        with self.assertRaises(ValueError):
            core.set_setting("wallpaper", "interval_minutes", 0, self.settings)
        self.assertEqual(self.settings.read_text(encoding="utf-8"), before)
        with self.assertRaises(ValueError):
            core.validate_setting("theme", "surface_opacity", 0.95)

    def test_settings_load_defaults_and_persisted_values(self):
        data = core.load_settings(self.settings)
        self.assertEqual(data["display"]["preferred_refresh"], 155)
        self.assertEqual(data["keyboard"]["variant"], "intl")
        self.assertEqual(data["wallpaper"]["directory"], "~/Wallpapers Custom")

    def test_monitor_mode_requires_exact_resolution_and_target_refresh(self):
        monitor = {"availableModes": ["1920x1080@165.00Hz", "2560x1440@154.00Hz", "2560x1440@155.00Hz"]}
        self.assertEqual(core.supported_mode(monitor, 2560, 1440, 155), "2560x1440@155.00Hz")
        self.assertIsNone(core.supported_mode(monitor, 2560, 1440, 160))

    def test_unsupported_monitor_target_keeps_existing_mode_unchanged(self):
        fake = [{"name": "DP-1", "currentMode": "2560x1440@144.00Hz", "availableModes": ["2560x1440@144.00Hz"]}]
        with mock.patch.object(core, "get_monitors", return_value=fake), mock.patch.object(core, "_run") as command:
            applied, message = core.apply_monitor("DP-1", 2560, 1440, 155, 1.0)
        self.assertFalse(applied)
        self.assertIn("Keeping 2560x1440@144.00Hz", message)
        command.assert_not_called()

    def test_supported_monitor_mode_uses_current_lua_api(self):
        fake = [{"name": "DP-1", "currentMode": "2560x1440@144.00Hz", "availableModes": ["2560x1440@155.00Hz"]}]
        with mock.patch.object(core, "get_monitors", return_value=fake), mock.patch.object(core, "_run") as command:
            applied, message = core.apply_monitor("DP-1", 2560, 1440, 155, 1.0)
        self.assertTrue(applied)
        self.assertIn("Applied 2560x1440@155.00Hz", message)
        args = command.call_args.args[0]
        self.assertEqual(args[:2], ["hyprctl", "eval"])
        self.assertIn('hl.monitor({ output = "DP-1"', args[2])

    def test_custom_keybinds_are_restricted_and_generated_separately(self):
        path = core.save_custom_keybind("SUPER + CTRL + T", "terminal")
        self.assertTrue(path.is_file())
        self.assertIn('hl.bind("SUPER + CTRL + T"', path.read_text(encoding="utf-8"))
        with self.assertRaises(ValueError):
            core.save_custom_keybind('SUPER + T"; os.execute("bad")', "terminal")
        with self.assertRaises(ValueError):
            core.save_custom_keybind("SUPER + CTRL + X", "raw_shell")

    def test_workspace_count_generates_only_bounded_user_bindings(self):
        path = core.write_workspace_bindings(12)
        content = path.read_text(encoding="utf-8")
        self.assertIn('hl.bind("SUPER + 1"', content)
        self.assertIn('hl.bind("SUPER + 0"', content)
        self.assertIn('hl.bind("SUPER + ALT + 2"', content)
        with self.assertRaises(ValueError):
            core.write_workspace_bindings(50)

    def test_waybar_modules_and_panel_position_are_applied(self):
        waybar = self.config / "waybar" / "config.jsonc"
        waybar.parent.mkdir(parents=True)
        waybar.write_text(json.dumps({"position": "top", "modules-left": [], "modules-center": [], "modules-right": []}), encoding="utf-8")
        values = {"show_workspaces": False, "show_window": True, "show_network": False, "show_audio": True, "show_system": False, "show_tray": False, "position": "bottom"}
        with mock.patch.object(core, "_run"):
            core.update_waybar_modules(values)
        changed = json.loads(waybar.read_text(encoding="utf-8"))
        self.assertEqual(changed["position"], "bottom")
        self.assertEqual(changed["modules-left"], ["hyprland/window"])
        self.assertEqual(changed["modules-right"], ["pulseaudio"])

    def test_audio_node_parser_finds_sinks_and_sources(self):
        status = """Audio\n ├─ Sinks:\n │  * 52. USB Audio Output [vol: 0.50]\n │    53. HDMI Audio\n ├─ Sources:\n │  * 63. USB Microphone [vol: 0.80]\n ├─ Filters:\n"""
        with mock.patch.object(core, "audio_status", return_value=status):
            sinks, sources = core.audio_nodes()
        self.assertEqual(sinks, [("52", "USB Audio Output"), ("53", "HDMI Audio")])
        self.assertEqual(sources, [("63", "USB Microphone")])

    def test_service_control_is_allowlisted(self):
        with mock.patch.object(core, "_run") as command:
            core.control_service("pipewire.socket", "restart", user=True)
        self.assertEqual(command.call_args.args[0], ["systemctl", "--user", "restart", "pipewire.socket"])
        with self.assertRaises(ValueError):
            core.control_service("ssh.service", "stop", user=False)

    def test_gaming_profile_emits_safe_launch_wrapper_config(self):
        with mock.patch.object(core, "CONFIG_HOME", self.config), mock.patch.object(core, "STATE_HOME", self.state):
            core.configure_gaming(True, True, 144, True)
        profile = json.loads((self.config / "fenrir/gaming.json").read_text())
        self.assertEqual(profile, {"gamemode": True, "mangohud": True, "gamescope": True, "fps_limit": 144})
        self.assertEqual((self.config / "fenrir/steam-launch-options.txt").read_text(), "fenrir-game %command%\n")
        self.assertIn("fps_limit=144", (self.config / "MangoHud/MangoHud.conf").read_text())


if __name__ == "__main__":
    unittest.main()
