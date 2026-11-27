import unittest

from fenrir_dots.theme import classify_rgb, choose_accent, contrast_ratio


class ThemePaletteTests(unittest.TestCase):
    def test_required_color_families(self):
        self.assertEqual(classify_rgb(0, 0, 255), "blue")
        self.assertEqual(classify_rgb(255, 0, 0), "red")
        self.assertEqual(classify_rgb(128, 0, 255), "violet")
        self.assertEqual(classify_rgb(255, 105, 180), "pink")
        self.assertEqual(classify_rgb(255, 255, 0), "yellow")
        self.assertEqual(classify_rgb(150, 75, 0), "brown")
        self.assertEqual(classify_rgb(0, 128, 0), "green")

    def test_preferred_colors_win_over_green(self):
        self.assertEqual(choose_accent(["#008000", "#0000ff"]), "#0000ff")

    def test_excluded_colors_are_not_selected(self):
        self.assertNotEqual(choose_accent(["#ffff00", "#ff7800", "#ff69b4"]), "#ffff00")
        self.assertNotEqual(choose_accent(["#ffff00", "#ff7800", "#ff69b4"]), "#ff7800")

    def test_accent_contrast_is_maintained(self):
        self.assertGreaterEqual(contrast_ratio(choose_accent(["#02030a"]), "#090b12"), 3.0)


if __name__ == "__main__":
    unittest.main()
