import json
import tempfile
import unittest
from pathlib import Path

from fenrir_dots.glass import apply


class GlassPreferenceTests(unittest.TestCase):
    def test_default_is_enabled_at_eighty_percent(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            enabled, opacity = apply("status", home)
            self.assertTrue(enabled)
            self.assertEqual(opacity, 0.8)
            self.assertIn("background_opacity 0.80",
                          (home / ".config/kitty/fenrir-glass.conf").read_text())

    def test_toggle_off_restores_opaque_surfaces(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            enabled, _ = apply("toggle", home)
            self.assertFalse(enabled)
            settings = json.loads((home / ".config/fenrir/appearance.json").read_text())
            self.assertFalse(settings["glass"]["enabled"])
            self.assertIn("background_opacity 1.00",
                          (home / ".config/kitty/fenrir-glass.conf").read_text())

    def test_toggle_on_again(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            apply("off", home)
            enabled, opacity = apply("on", home)
            self.assertTrue(enabled)
            self.assertEqual(opacity, 0.8)

    def test_gtk_waybar_and_hyprland_adapters_are_written(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            apply("on", home)
            for relative in (
                ".config/gtk-3.0/fenrir-glass.css",
                ".config/gtk-4.0/fenrir-glass.css",
                ".config/waybar/fenrir-glass.css",
                ".config/hypr/fenrir-glass.conf",
            ):
                self.assertTrue((home / relative).is_file(), relative)


if __name__ == "__main__":
    unittest.main()
