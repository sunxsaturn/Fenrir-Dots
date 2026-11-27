import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from fenrir_dots.cli import glass_main, theme_main


class DesktopCliTests(unittest.TestCase):
    def test_installer_glass_command_accepts_opacity_option(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with (
                patch("fenrir_dots.cli.Path.home", return_value=Path(tmp)),
                patch("fenrir_dots.cli.set_glass") as set_glass,
                patch("fenrir_dots.cli.reload_hyprland", return_value=True),
                contextlib.redirect_stdout(output),
            ):
                result = glass_main(["enable", "--opacity", "0.80"])
            self.assertEqual(result, 0)
            set_glass.assert_called_once_with(True, 0.8)
            self.assertIn('"enabled": true', output.getvalue())

    def test_rotation_theme_command_accepts_apply_subcommand(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wallpaper = home / "wallpaper.png"
            Image.new("RGB", (320, 180), (20, 40, 180)).save(wallpaper)
            output = io.StringIO()
            with (
                patch("fenrir_dots.cli.Path.home", return_value=home),
                contextlib.redirect_stdout(output),
            ):
                result = theme_main(["apply", str(wallpaper)])
            self.assertEqual(result, 0)
            self.assertTrue((home / ".config/fenrir/theme/theme.json").is_file())
            self.assertIn('"accent_family": "blue"', output.getvalue())


if __name__ == "__main__":
    unittest.main()
