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

    def test_installer_requires_official_quickshell_and_version_018(self):
        installer = (ROOT / "scripts" / "install-dots.sh").read_text(encoding="utf-8")
        self.assertIn('command -v quickshell', installer)
        self.assertIn('== "0.18.0"', installer)
        self.assertIn('quickshell-config', installer)

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
