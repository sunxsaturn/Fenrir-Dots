import json
import tempfile
import unittest
from pathlib import Path

from fenrir_dots.applications import list_applications, toggle_favorite


class ApplicationIndexTests(unittest.TestCase):
    def write_entry(self, root: Path, relative: str, body: str):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return path

    def test_indexes_xdg_application_entries_without_executing_exec_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "applications"
            self.write_entry(root, "utilities/terminal.desktop", """[Desktop Entry]
Type=Application
Name=Terminal
Comment=Command line
Exec=sh -c 'touch /tmp/should-not-run'
Icon=utilities-terminal
Categories=System;Utility;
""")
            items = list_applications([root], Path(tmp) / "favorites.json")
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["desktop_id"], "utilities-terminal")
            self.assertEqual(items[0]["name"], "Terminal")
            self.assertEqual(items[0]["categories"], ["System", "Utility"])

    def test_ignores_hidden_nodisplay_and_unavailable_tryexec_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "applications"
            self.write_entry(root, "hidden.desktop", "[Desktop Entry]\nType=Application\nName=Hidden\nExec=hidden\nHidden=true\n")
            self.write_entry(root, "nodisplay.desktop", "[Desktop Entry]\nType=Application\nName=Internal\nExec=hidden\nNoDisplay=true\n")
            self.write_entry(root, "missing.desktop", "[Desktop Entry]\nType=Application\nName=Missing\nExec=missing\nTryExec=fenrir-command-that-does-not-exist\n")
            self.assertEqual(list_applications([root], Path(tmp) / "favorites.json"), [])

    def test_xdg_priority_deduplicates_desktop_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp) / "first", Path(tmp) / "second"
            self.write_entry(first, "sample.desktop", "[Desktop Entry]\nType=Application\nName=First\nExec=sample\n")
            self.write_entry(second, "sample.desktop", "[Desktop Entry]\nType=Application\nName=Second\nExec=sample\n")
            items = list_applications([first, second], Path(tmp) / "favorites.json")
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["name"], "First")

    def test_favorites_are_persisted_with_private_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state" / "favorites.json"
            self.assertTrue(toggle_favorite("org.example.App", favorites_path=path))
            self.assertEqual(json.loads(path.read_text()), ["org.example.App"])
            self.assertFalse(toggle_favorite("org.example.App", favorites_path=path))
            self.assertEqual(json.loads(path.read_text()), [])
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)

    def test_rejects_path_like_favorite_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                toggle_favorite("../outside", favorites_path=Path(tmp) / "favorites.json")


if __name__ == "__main__":
    unittest.main()
