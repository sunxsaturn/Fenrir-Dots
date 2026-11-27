import tempfile
import unittest
from pathlib import Path

from PIL import Image

from fenrir_dots.theme import (
    EXCLUDED, PREFERRED, TOLERATED, classify_rgb, contrast, ensure_contrast,
    extract_palette, write_theme,
)


class ThemeTests(unittest.TestCase):
    def test_requested_palette_policy(self):
        self.assertEqual(EXCLUDED, {"yellow", "orange", "brown"})
        self.assertTrue({"red", "purple", "blue", "white", "black"} <= PREFERRED)
        self.assertIn("green", TOLERATED)
        self.assertNotIn("pink", EXCLUDED)

    def test_color_families_include_the_requested_preferred_colors(self):
        self.assertEqual(classify_rgb(200, 15, 30), "red")
        self.assertEqual(classify_rgb(180, 20, 180), "purple")
        self.assertEqual(classify_rgb(20, 40, 180), "blue")
        self.assertEqual(classify_rgb(245, 245, 245), "white")
        self.assertEqual(classify_rgb(10, 10, 10), "black")
        self.assertEqual(classify_rgb(20, 190, 70), "green")
        self.assertEqual(classify_rgb(225, 90, 150), "pink")

    def test_only_yellow_orange_and_brown_are_excluded(self):
        expected = {
            (240, 190, 20): "yellow",
            (240, 110, 20): "orange",
            (160, 85, 35): "brown",
        }
        for rgb, family in expected.items():
            with self.subTest(rgb=rgb):
                self.assertEqual(classify_rgb(*rgb), family)
        with tempfile.TemporaryDirectory() as tmp:
            for name, color in (
                ("yellow", (240, 190, 20)),
                ("orange", (240, 110, 20)),
                ("brown", (160, 85, 35)),
            ):
                path = Path(tmp) / f"{name}.png"
                Image.new("RGB", (320, 180), color).save(path)
                with self.subTest(name=name), self.assertRaises(ValueError):
                    extract_palette(path)

    def test_white_is_a_preferred_accent_and_pink_is_not_forbidden(self):
        with tempfile.TemporaryDirectory() as tmp:
            white = Path(tmp) / "white.png"
            Image.new("RGB", (320, 180), (245, 245, 245)).save(white)
            self.assertEqual(extract_palette(white)["accent_family"], "white")
            pink_blue = Path(tmp) / "pink-blue.png"
            image = Image.new("RGB", (100, 100), (225, 90, 150))
            pixels = image.load()
            for y in range(100):
                for x in range(60):
                    pixels[x, y] = (20, 40, 180)
            image.save(pink_blue)
            self.assertEqual(extract_palette(pink_blue)["accent_family"], "blue")

    def test_accent_is_contrast_safe_on_obsidian(self):
        accent = ensure_contrast("#202060")
        self.assertGreaterEqual(contrast(accent, "#090b12"), 3.0)

    def test_preferred_family_beats_larger_tolerated_green_region(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "blue-green.png"
            image = Image.new("RGB", (100, 100), (0, 95, 25))
            pixels = image.load()
            for y in range(100):
                for x in range(20):
                    pixels[x, y] = (18, 42, 180)
            image.save(path)
            palette = extract_palette(path)
            self.assertEqual(palette["accent_family"], "blue")

    def test_palette_is_derived_from_decoded_pixels(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wallpaper.jpg"
            Image.new("RGB", (320, 180), (20, 40, 180)).save(path)
            palette = extract_palette(path)
            self.assertEqual(palette["accent_family"], "blue")
            self.assertEqual(palette["background"], "#090b12")

    def test_theme_writes_valid_newline_delimited_consumer_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            palette = {
                "background": "#090b12", "surface": "#151a28",
                "foreground": "#edf0fa", "muted": "#a8afc4",
                "accent": "#6999ee", "border": "#6999ee88",
                "selection_foreground": "#ffffff",
            }
            out = write_theme(palette, tmp)
            names = (
                "theme.json", "waybar.css", "gtk.css", "kitty.conf", "qt.qss",
                "qt6ct-colors.conf", "starship.toml", "mako.conf", "fuzzel.ini",
            )
            for name in names:
                with self.subTest(name=name):
                    data = (out / name).read_bytes()
                    self.assertIn(b"\n", data)
                    self.assertNotIn(b"\\n", data)
            css = (out / "waybar.css").read_text(encoding="utf-8")
            self.assertIn("window#waybar", css)
            self.assertIn("color:", css)


if __name__ == "__main__":
    unittest.main()
