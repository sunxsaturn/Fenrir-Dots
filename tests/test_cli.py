import contextlib
import io
import tempfile
import unittest
import tomllib
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from fenrir_dots.cli import glass_main, theme_main


class DesktopCliTests(unittest.TestCase):
    def test_version_metadata_is_aligned_and_decimal_canonical(self):
        root = Path(__file__).resolve().parents[1]
        from fenrir_dots import __version__
        pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        version = (root / "VERSION").read_text(encoding="utf-8").strip()
        self.assertRegex(version, r"^[0-9]\.[0-9]\.[0-9]$")
        self.assertEqual(version, __version__)
        self.assertEqual(pyproject["project"]["version"], __version__)

    def test_installer_glass_command_accepts_opacity_option(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with (
                patch("fenrir_dots.cli.Path.home", return_value=Path(tmp)),
                patch("fenrir_dots.cli.set_glass") as set_glass,
                patch("fenrir_dots.cli.reload_hyprland", return_value=True),
                contextlib.redirect_stdout(output),
            ):
                result = glass_main(["enable", "--opacity", "0.60"])
            self.assertEqual(result, 0)
            set_glass.assert_called_once_with(True, 0.6)
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
