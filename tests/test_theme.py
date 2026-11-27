import tempfile
import unittest
from pathlib import Path

from PIL import Image

from fenrir_dots.theme import classify_rgb, contrast, ensure_contrast, extract_palette, write_theme


class ThemeTests(unittest.TestCase):
    def test_color_families_include_pink_exclusion(self):
        self.assertEqual(classify_rgb(20, 40, 180), "blue")
        self.assertEqual(classify_rgb(180, 20, 180), "purple")
        self.assertEqual(classify_rgb(225, 90, 150), "pink")

    def test_accent_is_contrast_safe_on_obsidian(self):
        accent = ensure_contrast("#202060")
        self.assertGreaterEqual(contrast(accent, "#090b12"), 3.0)

    def test_palette_is_derived_from_decoded_pixels(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wallpaper.jpg"
            Image.new("RGB", (320, 180), (20, 40, 180)).save(path)
            palette = extract_palette(path)
            self.assertEqual(palette["accent_family"], "blue")
            self.assertEqual(palette["background"], "#090b12")

    def test_theme_writes_consumer_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = write_theme({"background":"#090b12","surface":"#151a28","foreground":"#edf0fa","muted":"#a8afc4","accent":"#6999ee","border":"#6999ee88","selection_foreground":"#ffffff"},tmp)
            for name in ("theme.json","waybar.css","gtk.css","kitty.conf","qt.qss"):
                self.assertTrue((out/name).is_file())


if __name__ == "__main__":
    unittest.main()
