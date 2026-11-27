import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SettingsUpdateTests(unittest.TestCase):
    def test_updates_managed_wallpaper_keys_and_preserves_custom_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "settings.toml"
            defaults = ROOT / "config/fenrir-settings.toml"
            target.write_text('[wallpaper]\ndirectory = "/custom/wallpapers"\ninterval_minutes = 30\n\n[theme]\nsurface_opacity = 0.60\n', encoding="utf-8")
            subprocess.run([sys.executable, str(ROOT / "scripts/update-settings.py"), str(target), str(defaults)], check=True)
            contents = target.read_text(encoding="utf-8")
            self.assertIn('directory = "/custom/wallpapers"', contents)
            self.assertIn("interval_minutes = 15", contents)
            self.assertNotIn("minimum_count", contents)
            self.assertIn("surface_opacity = 0.60", contents)


if __name__ == "__main__":
    unittest.main()
