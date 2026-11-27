import tempfile
import unittest
from pathlib import Path

from fenrir_dots.glass import render_glass, set_glass


class GlassTests(unittest.TestCase):
    def test_enabled_mode_uses_sixty_percent_opacity_and_blur(self):
        result = render_glass(True)
        self.assertIn('opacity = "0.60 override 0.60 override 1.0 override"', result)
        self.assertIn("enabled = true", result)
        self.assertIn('name = "fenrir-glass-default"', result)

    def test_disabled_mode_removes_rules(self):
        self.assertNotIn("fenrir-glass-default", render_glass(False))

    def test_unsafe_opacity_is_rejected(self):
        with self.assertRaises(ValueError):
            render_glass(True, 0.2)

    def test_toggle_writes_user_config_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = set_glass(False, config_path=Path(tmp)/"hypr"/"fenrir-glass.lua")
            self.assertTrue(path.is_file())
            self.assertIn("disabled", path.read_text())


if __name__ == "__main__":
    unittest.main()
