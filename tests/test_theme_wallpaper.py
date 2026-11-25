import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str):
    path = ROOT / relative_path
    from importlib.machinery import SourceFileLoader
    loader = SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


theme = load_module("fenrir_theme", "bin/fenrir-theme")
wallpaper = load_module("fenrir_wallpaper", "bin/fenrir-wallpaper")


class FenrirThemeTests(unittest.TestCase):
    def test_palette_updates_managed_colors_and_preserves_layout(self):
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "config"
            (config / "fuzzel").mkdir(parents=True)
            (config / "mako").mkdir(parents=True)
            (config / "fenrir").mkdir(parents=True)
            (config / "waybar").mkdir()
            (config / "kitty").mkdir()
            (config / "gtk-3.0").mkdir()
            (config / "gtk-4.0").mkdir()
            (config / "fenrir" / "settings.toml").write_text(
                "[theme]\nsurface_opacity = 0.60\n", encoding="utf-8"
            )
            (config / "fuzzel" / "fuzzel.ini").write_text(
                "font=Inter:size=11\nwidth=44\n[colors]\nbackground=000000ff\ntext=ffffffff\n[border]\nradius=13\n",
                encoding="utf-8",
            )
            (config / "mako" / "config").write_text(
                "font=Inter 10\nmax-visible=5\nbackground-color=#000000ff\n", encoding="utf-8"
            )

            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config)}, clear=False), patch.dict(
                os.environ, {"HYPRLAND_INSTANCE_SIGNATURE": ""}, clear=False
            ):
                theme.write_palette({
                    "accent": "#336699",
                    "accent_soft": "#1a334c",
                    "foreground": "#e8e9f2",
                    "muted": "#9699ab",
                    "border": "#336699",
                })

            palette = json.loads((config / "fenrir" / "palette.json").read_text(encoding="utf-8"))
            self.assertEqual(palette["surface_opacity"], 0.60)
            self.assertIn("rgba(9, 11, 18, 0.60)", (config / "waybar" / "palette.css").read_text())
            fuzzel = (config / "fuzzel" / "fuzzel.ini").read_text()
            self.assertIn("width=44", fuzzel)
            self.assertIn("radius=13", fuzzel)
            self.assertIn("match=336699ff", fuzzel)
            self.assertIn("background=090b1299", fuzzel)
            mako = (config / "mako" / "config").read_text()
            self.assertIn("max-visible=5", mako)
            self.assertIn("background-color=#090b1299", mako)
            self.assertIn("border-color=#336699", mako)

    def test_live_hyprland_border_uses_lua_eval_not_legacy_keyword(self):
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "config"
            (config / "fenrir").mkdir(parents=True)
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config), "HYPRLAND_INSTANCE_SIGNATURE": "session"}, clear=False), patch.object(
                theme.subprocess, "run"
            ) as run:
                theme.write_palette({
                    "accent": "#336699",
                    "accent_soft": "#1a334c",
                    "foreground": "#e8e9f2",
                    "muted": "#9699ab",
                    "border": "#336699",
                })
            commands = [call.args[0] for call in run.call_args_list]
            self.assertTrue(any(command[:2] == ["hyprctl", "eval"] for command in commands))
            self.assertFalse(any(command[:2] == ["hyprctl", "keyword"] for command in commands))
            eval_command = next(command for command in commands if command[:2] == ["hyprctl", "eval"])
            self.assertIn("rgba(336699ff)", eval_command[2])
            self.assertIn("rgba(1a334cff)", eval_command[2])

    def test_dynamic_accent_excludes_yellow_orange_and_brown(self):
        from PIL import Image
        for color in ("#ffff00", "#ff8000", "#8b4513"):
            with tempfile.TemporaryDirectory() as temp:
                image = Path(temp) / "warm.png"
                Image.new("RGB", (160, 160), color).save(image, format="PNG")
                colors = theme.extract(image)
                self.assertEqual(colors["accent"], theme.DEFAULTS["accent"])

    def test_dynamic_accent_selects_allowed_color_when_warm_hue_dominates(self):
        from PIL import Image, ImageDraw
        with tempfile.TemporaryDirectory() as temp:
            image = Path(temp) / "mixed.png"
            canvas = Image.new("RGB", (160, 160), "#ffff00")
            draw = ImageDraw.Draw(canvas)
            draw.rectangle((0, 0, 63, 159), fill="#c02020")
            canvas.save(image, format="PNG")
            colors = theme.extract(image)
            self.assertEqual(colors["accent"], "#c02020")
            self.assertNotIn(
                theme.classify_rgb(*tuple(int(colors["accent"][i:i+2], 16) for i in (1, 3, 5))),
                theme.EXCLUDED_FAMILIES,
            )

    def test_surface_opacity_is_clamped_to_readable_range(self):
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "config"
            (config / "fenrir").mkdir(parents=True)
            (config / "fenrir" / "settings.toml").write_text(
                "[theme]\nsurface_opacity = 0.10\n", encoding="utf-8"
            )
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config)}, clear=False):
                self.assertEqual(theme.configured_surface_opacity(), 0.35)


class FenrirWallpaperTests(unittest.TestCase):
    def test_random_picker_excludes_unsupported_files_and_current_wallpaper(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "wallpapers"
            root.mkdir()
            first = root / "first.jpg"
            second = root / "second.png"
            from PIL import Image
            Image.new("RGB", (2560, 1440), "#304860").save(first, format="JPEG")
            Image.new("RGB", (3840, 2160), "#405060").save(second, format="PNG")
            (root / "ignored.txt").write_text("not an image")
            (root / "ignored.gif").write_bytes(b"gif")
            try:
                (root / "alias.webp").symlink_to(second)
            except OSError:
                pass
            config = Path(temp) / "config"
            (config / "fenrir").mkdir(parents=True)
            (config / "fenrir" / "settings.toml").write_text(
                f'[wallpaper]\ndirectory = "{root}"\nminimum_width = 2560\nminimum_height = 1440\nminimum_count = 5000\ninterval_minutes = 15\n', encoding="utf-8"
            )
            state = Path(temp) / "state" / "fenrir"
            state.mkdir(parents=True)
            (state / "wallpaper.json").write_text(
                json.dumps({"path": str(first.resolve())}), encoding="utf-8"
            )
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config), "XDG_STATE_HOME": str(Path(temp) / "state")}, clear=False), patch.object(
                wallpaper, "resolution_policy", return_value=(2560, 1440, 2)
            ), patch.object(wallpaper.random, "choice", side_effect=lambda options: options[0]):
                selected = wallpaper.next_wallpaper()
            self.assertEqual(selected.resolve(), second.resolve())

    def test_wallpaper_scanner_rejects_portrait_and_sub_1440p_images(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "wallpapers"
            root.mkdir()
            Image.new("RGB", (1920, 1080), "#112233").save(root / "small.jpg", format="JPEG")
            Image.new("RGB", (1440, 2560), "#223344").save(root / "portrait.png", format="PNG")
            Image.new("RGB", (2560, 1440), "#334455").save(root / "valid.webp", format="WEBP")
            config = Path(temp) / "config"
            (config / "fenrir").mkdir(parents=True)
            (config / "fenrir" / "settings.toml").write_text(
                f'[wallpaper]\ndirectory = "{root}"\nminimum_width = 2560\nminimum_height = 1440\nminimum_count = 5000\ninterval_minutes = 15\n',
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config), "XDG_STATE_HOME": str(Path(temp) / "state")}, clear=False):
                valid, rejected, total, _palette_excluded, _scores = wallpaper.validated_wallpapers()
            self.assertEqual(total, 3)
            self.assertEqual(rejected, 2)
            self.assertEqual([p.name for p in valid], ["valid.webp"])

    def test_rotation_works_below_5000_target_without_falsely_marking_it_complete(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "wallpapers"
            root.mkdir()
            image = root / "one.jpg"
            Image.new("RGB", (2560, 1440), "#112233").save(image, format="JPEG")
            config = Path(temp) / "config"
            (config / "fenrir").mkdir(parents=True)
            (config / "fenrir" / "settings.toml").write_text(
                f'[wallpaper]\ndirectory = "{root}"\nminimum_count = 5000\n', encoding="utf-8"
            )
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config), "XDG_STATE_HOME": str(Path(temp) / "state")}, clear=False):
                selected = wallpaper.next_wallpaper()
                self.assertEqual(selected.resolve(), image.resolve())
                valid, _, _, _, _ = wallpaper.validated_wallpapers()
                self.assertEqual(len(valid), 1)
                self.assertGreater(wallpaper.resolution_policy()[2], len(valid))

    def test_rotation_excludes_yellow_orange_and_brown_dominant_palettes(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "wallpapers"
            root.mkdir()
            Image.new("RGB", (2560, 1440), "#c02020").save(root / "red.png", format="PNG")
            Image.new("RGB", (2560, 1440), "#ffff00").save(root / "yellow.png", format="PNG")
            Image.new("RGB", (2560, 1440), "#ff8000").save(root / "orange.png", format="PNG")
            Image.new("RGB", (2560, 1440), "#8b4513").save(root / "brown.png", format="PNG")
            config = Path(temp) / "config"
            (config / "fenrir").mkdir(parents=True)
            (config / "fenrir" / "settings.toml").write_text(
                f'[wallpaper]\ndirectory = "{root}"\nminimum_width = 2560\nminimum_height = 1440\n',
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config), "XDG_STATE_HOME": str(Path(temp) / "state")}, clear=False):
                valid, rejected, total, palette_excluded, _scores = wallpaper.validated_wallpapers()
            self.assertEqual(total, 4)
            self.assertEqual([path.name for path in valid], ["red.png"])
            self.assertEqual(rejected, 3)
            self.assertEqual(palette_excluded, 3)

    def test_random_rotation_weights_preferred_colors_above_green(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "wallpapers"
            root.mkdir()
            Image.new("RGB", (2560, 1440), "#c02020").save(root / "red.png", format="PNG")
            Image.new("RGB", (2560, 1440), "#208040").save(root / "green.png", format="PNG")
            config = Path(temp) / "config"
            (config / "fenrir").mkdir(parents=True)
            (config / "fenrir" / "settings.toml").write_text(
                f'[wallpaper]\ndirectory = "{root}"\nminimum_width = 2560\nminimum_height = 1440\n',
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config), "XDG_STATE_HOME": str(Path(temp) / "state")}, clear=False), patch.object(
                wallpaper.random, "choices", side_effect=lambda options, weights, k: [options[weights.index(max(weights))]]
            ) as choose:
                selected = wallpaper.next_wallpaper()
            self.assertEqual(selected.name, "red.png")
            self.assertEqual(choose.call_args.kwargs["k"], 1)
            self.assertEqual(max(choose.call_args.kwargs["weights"]), 2)
            self.assertEqual(min(choose.call_args.kwargs["weights"]), 1)

    def test_wallpaper_index_invalidates_old_dimension_only_cache(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "wallpapers"
            root.mkdir()
            image = root / "yellow.png"
            Image.new("RGB", (2560, 1440), "#ffff00").save(image, format="PNG")
            config = Path(temp) / "config"
            (config / "fenrir").mkdir(parents=True)
            (config / "fenrir" / "settings.toml").write_text(
                f'[wallpaper]\ndirectory = "{root}"\nminimum_width = 2560\nminimum_height = 1440\n',
                encoding="utf-8",
            )
            state = Path(temp) / "state" / "fenrir"
            state.mkdir(parents=True)
            (state / "wallpaper-index.json").write_text(
                json.dumps({"version": 1, "items": {str(image.resolve()): {"size": image.stat().st_size, "mtime_ns": image.stat().st_mtime_ns, "width": 2560, "height": 1440, "valid": True}}}),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config), "XDG_STATE_HOME": str(Path(temp) / "state")}, clear=False):
                valid, rejected, total, palette_excluded, _scores = wallpaper.validated_wallpapers()
            self.assertEqual(valid, [])
            self.assertEqual(total, 1)
            self.assertEqual(rejected, 1)
            self.assertEqual(palette_excluded, 1)
            index = json.loads((state / "wallpaper-index.json").read_text(encoding="utf-8"))
            self.assertEqual(index["version"], wallpaper.INDEX_VERSION)
            self.assertEqual(index["palette_policy"], wallpaper.PALETTE_POLICY_ID)

    def test_rotation_refuses_empty_qualifying_library(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "wallpapers"
            root.mkdir()
            config = Path(temp) / "config"
            (config / "fenrir").mkdir(parents=True)
            (config / "fenrir" / "settings.toml").write_text(
                f'[wallpaper]\ndirectory = "{root}"\nminimum_count = 5000\n', encoding="utf-8"
            )
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config), "XDG_STATE_HOME": str(Path(temp) / "state")}, clear=False):
                with self.assertRaisesRegex(RuntimeError, "No qualifying wallpapers"):
                    wallpaper.next_wallpaper()

    def test_status_reports_5000_wallpaper_target(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "wallpapers"
            root.mkdir()
            Image.new("RGB", (2560, 1440), "#112233").save(root / "one.jpg", format="JPEG")
            config = Path(temp) / "config"
            (config / "fenrir").mkdir(parents=True)
            (config / "fenrir" / "settings.toml").write_text(
                f'[wallpaper]\ndirectory = "{root}"\nminimum_count = 5000\ninterval_minutes = 15\n', encoding="utf-8"
            )
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config), "XDG_STATE_HOME": str(Path(temp) / "state")}, clear=False):
                valid, _, _, _, _ = wallpaper.validated_wallpapers()
                self.assertEqual(len(valid), 1)
                self.assertEqual(wallpaper.resolution_policy()[2], 5000)

    def test_catalog_collection_sync_uses_configured_rotation_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / "config"
            (config / "fenrir").mkdir(parents=True)
            wallpapers = root / "Pictures" / "Wallpapers"
            (config / "fenrir" / "settings.toml").write_text(
                f'[wallpaper]\ndirectory = "{wallpapers}"\ninterval_minutes = 15\n',
                encoding="utf-8",
            )
            database = root / "catalog" / "catalog.sqlite3"
            database.parent.mkdir()
            database.write_bytes(b"test database placeholder")
            quarantine = root / "catalog" / "quarantine"
            quarantine.mkdir()
            executable = root / "bin" / "fenrir-catalog"
            executable.parent.mkdir()
            executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            executable.chmod(0o755)

            completed = wallpaper.subprocess.CompletedProcess(
                args=["fenrir-catalog"],
                returncode=0,
                stdout=json.dumps({
                    "installed": 2,
                    "already_present": 1,
                    "skipped": {"low_resolution": 3},
                    "collection_id": "collection-winter",
                }),
                stderr="",
            )
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config)}, clear=False), patch.object(
                wallpaper.shutil, "which", return_value=str(executable)
            ), patch.object(
                wallpaper.subprocess, "run", return_value=completed
            ) as run, patch.object(
                wallpaper,
                "validated_wallpapers",
                return_value=([wallpapers / "one.jpg"], 1, 4, 0, {}),
            ):
                result = wallpaper.sync_catalog_collection(
                    "collection-winter",
                    target_count=5000,
                    database=database,
                    quarantine_root=quarantine,
                )

            command = run.call_args.args[0]
            self.assertIn("catalog", command)
            self.assertIn("library", command)
            self.assertIn("sync", command)
            self.assertIn("--collection-id", command)
            self.assertEqual(command[command.index("--collection-id") + 1], "collection-winter")
            self.assertEqual(command[command.index("--destination") + 1], str(wallpapers))
            self.assertEqual(result["catalog_sync"]["installed"], 2)
            self.assertTrue(result["wallpaper_index"]["refreshed"])
            self.assertEqual(result["wallpaper_index"]["valid_count"], 1)
            self.assertTrue(result["rotation_uses_new_images_on_next_cycle"])
            self.assertFalse(result["rights_or_acceptance_changed"])

    def test_catalog_collection_sync_requires_an_explicit_collection_id(self):
        with self.assertRaisesRegex(RuntimeError, "--collection-id"):
            wallpaper.sync_catalog_collection("")

    def test_wallpaper_studio_launches_catalog_picker_with_private_cache_path(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            catalog = home / ".local" / "share" / "fenrir" / "catalog"
            catalog.mkdir(parents=True)
            database = catalog / "catalog.sqlite3"
            database.write_bytes(b"catalog database")
            quarantine = catalog / "quarantine"
            quarantine.mkdir(mode=0o700)
            quarantine.chmod(0o700)
            executable = root / "bin" / "fenrir-catalog"
            executable.parent.mkdir()
            executable.write_text("#!/bin/sh\\nexit 0\\n", encoding="utf-8")
            executable.chmod(0o700)
            cache_home = root / "cache"

            with patch.object(wallpaper.Path, "home", return_value=home), patch.dict(
                os.environ,
                {"XDG_CACHE_HOME": str(cache_home), "USER": "Studio curator"},
                clear=False,
            ), patch.object(wallpaper.shutil, "which", return_value=str(executable)), patch.object(
                wallpaper.subprocess, "Popen"
            ) as popen:
                wallpaper.launch_wallpaper_studio()

            command = popen.call_args.args[0]
            self.assertEqual(command[:4], [
                str(executable), "catalog", "library", "picker"
            ])
            self.assertEqual(command[command.index("--database") + 1], str(database))
            self.assertEqual(command[command.index("--quarantine-root") + 1], str(quarantine))
            cache_root = Path(command[command.index("--cache-root") + 1])
            self.assertEqual(cache_root, cache_home / "fenrir" / "catalog" / "thumbnails")
            self.assertEqual(cache_root.stat().st_mode & 0o777, 0o700)
            self.assertEqual(command[command.index("--reviewer") + 1], "Studio curator")
            self.assertTrue(popen.call_args.kwargs["start_new_session"])
            self.assertTrue(popen.call_args.kwargs["close_fds"])

    def test_wallpaper_cli_studio_action_launches_the_visual_workbench(self):
        import sys
        with patch.object(sys, "argv", ["fenrir-wallpaper", "studio"]), patch.object(
            wallpaper, "launch_wallpaper_studio"
        ) as launch:
            self.assertEqual(wallpaper.main(), 0)
        launch.assert_called_once_with()

    def test_apply_records_wallpaper_state_atomically(self):
        with tempfile.TemporaryDirectory() as temp:
            image = Path(temp) / "wallpaper.jpg"
            image.write_bytes(b"test-image")
            state_home = Path(temp) / "state"
            with patch.dict(os.environ, {"XDG_STATE_HOME": str(state_home)}, clear=False), patch.object(
                wallpaper, "get_monitors", return_value=["DP-1"]
            ), patch.object(wallpaper.subprocess, "run") as run, patch.object(
                wallpaper.shutil, "which", return_value=None
            ), patch.object(wallpaper.time, "sleep"):
                wallpaper.apply(image)
            state_file = state_home / "fenrir" / "wallpaper.json"
            saved = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(saved["path"], str(image.resolve()))
            self.assertFalse(state_file.with_name(state_file.name + f".tmp-{os.getpid()}").exists())
            self.assertTrue(any(call.args[0][:3] == ["hyprctl", "hyprpaper", "wallpaper"] for call in run.call_args_list))


if __name__ == "__main__":
    unittest.main()
