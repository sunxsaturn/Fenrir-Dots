import tempfile
import unittest
from pathlib import Path

from PIL import Image

from fenrir_dots.rotation import choose_next_wallpaper, eligible_images


class RotationTests(unittest.TestCase):
    def test_only_landscape_images_at_minimum_resolution_are_selected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "wallpapers"
            root.mkdir()
            Image.new("RGB", (2560, 1440), "blue").save(root / "valid.jpg")
            Image.new("RGB", (1920, 1080), "blue").save(root / "small.jpg")
            Image.new("RGB", (1440, 2560), "blue").save(root / "portrait.jpg")
            self.assertEqual([p.name for p in eligible_images(root)], ["valid.jpg"])

    def test_selected_wallpaper_is_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "wallpapers"
            root.mkdir()
            Image.new("RGB", (2560, 1440), "blue").save(root / "valid.jpg")
            state = Path(tmp) / "state" / "current.json"
            selected = choose_next_wallpaper(root, state_file=state)
            self.assertTrue(selected.is_file())
            self.assertEqual(selected.as_posix(), __import__("json").loads(state.read_text())["path"])


if __name__ == "__main__":
    unittest.main()
