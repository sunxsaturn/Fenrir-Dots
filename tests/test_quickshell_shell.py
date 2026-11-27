import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / "quickshell" / "fenrir" / "shell.qml"


class QuickshellShellTests(unittest.TestCase):
    def test_native_multi_monitor_shell_is_deployed(self):
        source = SHELL.read_text(encoding="utf-8")
        installer = (ROOT / "scripts" / "install-dots.sh").read_text(encoding="utf-8")
        hyprland = (ROOT / "config" / "hypr" / "hyprland.lua").read_text(encoding="utf-8")
        self.assertIn("Variants", source)
        self.assertIn("Quickshell.screens", source)
        self.assertIn('quickshell --config ', hyprland)
        self.assertIn('quickshell', installer)
        self.assertIn('quickshell/fenrir/shell.qml', installer)

    def test_shell_contains_custom_panel_dock_and_control_center(self):
        source = SHELL.read_text(encoding="utf-8")
        self.assertIn("PanelWindow", source)
        self.assertIn("FloatingWindow", source)
        self.assertIn("fenrir-top", source)
        self.assertIn("fenrir-dock", source)
        self.assertIn("Norse Cinematic", source)
        self.assertIn("Norse Performance", source)

    def test_installer_requires_official_quickshell_and_version_019(self):
        installer = (ROOT / "scripts" / "install-dots.sh").read_text(encoding="utf-8")
        self.assertIn('command -v quickshell', installer)
        self.assertIn('== "0.20.0"', installer)
        self.assertIn('quickshell-config', installer)

    def test_quickshell_consumes_live_dwte_palette_with_fallback(self):
        source = SHELL.read_text(encoding="utf-8")
        for required in (
            "FileView",
            'Quickshell.env("HOME")',
            "/.config/fenrir/theme/theme.json",
            "watchChanges: true",
            "onFileChanged: reload()",
            "JSON.parse(themeFile.text())",
            "selection_foreground",
            "root.palette.accent",
            "root.palette.background",
            "function tint(token, opacity)",
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)

    def test_shell_keeps_safe_palette_fallback_when_theme_file_is_missing_or_invalid(self):
        source = SHELL.read_text(encoding="utf-8")
        self.assertIn('background: "#090b12"', source)
        self.assertIn('accent: "#8b5cf6"', source)
        self.assertIn("invalid theme.json; keeping the last valid palette", source)
        self.assertIn("printErrors: false", source)

    def test_system_center_uses_native_quickshell_services_and_controls(self):
        source = SHELL.read_text(encoding="utf-8")
        for required in (
            "Quickshell.Services.Mpris",
            "Quickshell.Services.Notifications",
            "Quickshell.Services.Pipewire",
            "Quickshell.Services.SystemTray",
            "Quickshell.Networking",
            "Quickshell.Bluetooth",
            "NotificationServer",
            "trackedNotifications",
            "PwObjectTracker",
            "Mpris.players",
            "SystemTray.items",
            "Networking.wifiEnabled",
            "Bluetooth.defaultAdapter",
            "focuswindow address:",
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)

    def test_quickshell_is_the_single_notification_server(self):
        installer = (ROOT / "scripts" / "install-dots.sh").read_text(encoding="utf-8")
        hyprland = (ROOT / "config" / "hypr" / "hyprland.lua").read_text(encoding="utf-8")
        self.assertIn("migrate_legacy_mako", installer)
        self.assertIn('rm -f "$HOME/.config/autostart/fenrir-mako.desktop"', installer)
        self.assertNotIn('hl.exec_cmd("mako")', hyprland)
        self.assertNotIn("fenrir-mako.desktop", installer.split("for desktop in", 1)[1].split("done", 1)[0])

    def test_installer_uses_versioned_managed_quickshell_directory(self):
        installer = (ROOT / "scripts" / "install-dots.sh").read_text(encoding="utf-8")
        self.assertIn('== "0.20.0"', installer)
        self.assertIn("fenrir-system-v0-20", installer)


    def test_native_application_launcher_uses_xdg_index_and_quickshell_ipc(self):
        source = SHELL.read_text(encoding="utf-8")
        hyprland = (ROOT / "config" / "hypr" / "hyprland.lua").read_text(encoding="utf-8")
        installer = (ROOT / "scripts" / "install-dots.sh").read_text(encoding="utf-8")
        for required in (
            "IpcHandler",
            'target: "fenrir"',
            "toggleLauncher(): void",
            "fenrir-applications",
            '["gtk-launch", desktopId]',
            "filteredApplications",
            "launcherSearch",
            "Favorites",
            'text: modelData.favorite ? "★" : "☆"',
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)
        self.assertIn('qs ipc call fenrir toggleLauncher', hyprland)
        self.assertIn("fenrir-applications", installer)

    def test_launcher_index_does_not_execute_desktop_exec_as_shell_text(self):
        source = (ROOT / "src" / "fenrir_dots" / "applications.py").read_text(encoding="utf-8")
        self.assertNotIn("subprocess", source)
        self.assertNotIn("shell=True", source)
        self.assertNotIn("os.system", source)


    def test_native_application_launcher_uses_xdg_index_and_quickshell_ipc(self):
        source = SHELL.read_text(encoding="utf-8")
        hyprland = (ROOT / "config" / "hypr" / "hyprland.lua").read_text(encoding="utf-8")
        installer = (ROOT / "scripts" / "install-dots.sh").read_text(encoding="utf-8")
        for required in (
            "IpcHandler",
            'target: "fenrir"',
            "toggleLauncher(): void",
            "fenrir-applications",
            '["gtk-launch", desktopId]',
            "filteredApplications",
            "launcherSearch",
            "Favorites",
            'text: modelData.favorite ? "★" : "☆"',
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)
        self.assertIn('qs ipc call fenrir toggleLauncher', hyprland)
        self.assertIn('fenrir-applications', installer)

    def test_launcher_index_does_not_execute_desktop_exec_as_shell_text(self):
        source = (ROOT / "src" / "fenrir_dots" / "applications.py").read_text(encoding="utf-8")
        self.assertNotIn("subprocess", source)
        self.assertNotIn("shell=True", source)
        self.assertNotIn("os.system", source)

    def test_shell_launches_only_fixed_application_commands(self):
        source = SHELL.read_text(encoding="utf-8")
        for command in ('["fuzzel"]', '["kitty"]', '["thunar"]',
                        '["firefox"]', '["qpwgraph"]', '["fenrir-doctor"]'):
            with self.subTest(command=command):
                self.assertIn(command, source)
        self.assertNotIn("eval(", source)
        self.assertNotIn("Qt.exec", source)


if __name__ == "__main__":
    unittest.main()
