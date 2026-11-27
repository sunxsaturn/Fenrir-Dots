#!/usr/bin/env python3
"""GTK4 Fenrir Settings. Changes are validated, backed up and applied live where safe."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import core  # noqa: E402


class FenrirSettings(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.fenrir.Settings", flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.settings = core.load_settings()
        self.pages: dict[str, Gtk.Box] = {}
        self.status: Gtk.Label | None = None

    def do_activate(self):
        self.window = Gtk.ApplicationWindow(application=self)
        self.window.set_title("Fenrir Settings")
        self.window.set_default_size(1060, 760)
        self.window.add_css_class("fenrir-window")
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        header = Gtk.HeaderBar()
        title = Gtk.Label(label="Fenrir Settings")
        title.add_css_class("title-2")
        header.set_title_widget(title)
        defaults = Gtk.Button(label="Restore defaults")
        defaults.connect("clicked", self.restore_defaults)
        header.pack_end(defaults)
        outer.append(header)

        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        sidebar = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        sidebar.add_css_class("navigation-sidebar")
        sidebar.set_size_request(220, -1)
        stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=120)
        stack.set_hexpand(True)
        stack.set_vexpand(True)
        nav = [
            ("overview", "Overview"), ("appearance", "Appearance"), ("wallpaper", "Wallpapers"),
            ("display", "Display"), ("hyprland", "Hyprland & Workspaces"),
            ("keybinds", "Keybinds"), ("waybar", "Waybar"),
            ("audio", "Audio"), ("startup", "Startup applications"),
            ("gaming", "Gaming & Performance"), ("keyboard", "Keyboard"),
            ("services", "System services"), ("power", "Screen & Power"),
        ]
        self.sidebar = sidebar
        self._navigation = {}
        for name, label in nav:
            row = Gtk.ListBoxRow()
            self._navigation[name] = row
            text = Gtk.Label(label=label, xalign=0)
            text.set_margin_top(12); text.set_margin_bottom(12)
            text.set_margin_start(14); text.set_margin_end(12)
            row.set_child(text)
            sidebar.append(row)
            page = self.build_page(name)
            stack.add_named(page, name)
        sidebar.connect("row-selected", lambda _box, row: stack.set_visible_child_name(nav[row.get_index()][0]) if row else None)
        sidebar.select_row(sidebar.get_row_at_index(0))
        body.append(sidebar)
        separator = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        body.append(separator)
        body.append(stack)
        outer.append(body)
        self.status = Gtk.Label(label="Settings are stored in ~/.config/fenrir/settings.toml. Changes are backed up before writing.", xalign=0)
        self.status.set_margin_start(18); self.status.set_margin_end(18)
        self.status.set_margin_top(8); self.status.set_margin_bottom(8)
        self.status.add_css_class("dim-label")
        outer.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        outer.append(self.status)
        self.window.set_child(outer)
        self.window.present()

    def build_page(self, name: str) -> Gtk.Widget:
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        page.set_margin_top(24); page.set_margin_bottom(24); page.set_margin_start(28); page.set_margin_end(28)
        scroller = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        scroller.set_child(page)
        if name == "overview": self.page_overview(page)
        elif name == "appearance": self.page_appearance(page)
        elif name == "wallpaper": self.page_wallpaper(page)
        elif name == "display": self.page_display(page)
        elif name == "hyprland": self.page_hyprland(page)
        elif name == "keybinds": self.page_keybinds(page)
        elif name == "waybar": self.page_waybar(page)
        elif name == "audio": self.page_audio(page)
        elif name == "startup": self.page_startup(page)
        elif name == "gaming": self.page_gaming(page)
        elif name == "keyboard": self.page_keyboard(page)
        elif name == "services": self.page_services(page)
        elif name == "power": self.page_power(page)
        return scroller

    def heading(self, page: Gtk.Box, title: str, description: str):
        label = Gtk.Label(label=title, xalign=0)
        label.add_css_class("title-1")
        page.append(label)
        desc = Gtk.Label(label=description, xalign=0, wrap=True)
        desc.add_css_class("dim-label")
        page.append(desc)

    def group(self, page: Gtk.Box, title: str) -> Gtk.Box:
        frame = Gtk.Frame()
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_top(14); content.set_margin_bottom(14); content.set_margin_start(16); content.set_margin_end(16)
        label = Gtk.Label(label=title, xalign=0)
        label.add_css_class("heading")
        content.append(label)
        frame.set_child(content)
        page.append(frame)
        return content

    def row(self, box: Gtk.Box, label: str, widget: Gtk.Widget, detail: str | None = None):
        line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        labels.set_hexpand(True)
        name = Gtk.Label(label=label, xalign=0)
        labels.append(name)
        if detail:
            desc = Gtk.Label(label=detail, xalign=0, wrap=True)
            desc.add_css_class("dim-label")
            labels.append(desc)
        line.append(labels)
        line.append(widget)
        box.append(line)

    def button(self, box: Gtk.Box, label: str, callback, suggested: bool = False):
        button = Gtk.Button(label=label)
        if suggested: button.add_css_class("suggested-action")
        button.connect("clicked", callback)
        box.append(button)
        return button

    def set_status(self, message: str, error: bool = False):
        if self.status:
            self.status.set_text(message)
            self.status.remove_css_class("error")
            self.status.remove_css_class("success")
            self.status.add_css_class("error" if error else "success")

    def save(self, section: str, values: dict):
        try:
            backup = None
            for key, value in values.items():
                backup = core.set_setting(section, key, value) or backup
            self.settings = core.load_settings()
            self.set_status(f"Saved [{section}]. Backup: {backup if backup else 'no existing file to back up'}")
            return True
        except Exception as exc:
            self.set_status(str(exc), True)
            return False

    def run_command(self, args: list[str], success: str):
        try:
            subprocess.run(args, check=True, timeout=15, capture_output=True, text=True)
            self.set_status(success)
        except (OSError, subprocess.SubprocessError) as exc:
            self.set_status(str(exc), True)

    def page_overview(self, page):
        self.heading(
            page,
            "Fenrir Control Center",
            "A single starting point for your desktop: wallpaper library, display, Fimbulwinter Glass, audio, gaming, services and diagnostics.",
        )
        quick = self.group(page, "Quick actions")
        self.button(quick, "Open Wallpaper Studio", self.open_wallpaper_studio, True)
        self.button(quick, "Open Fenrir Doctor", self.open_doctor)
        self.button(quick, "Choose next wallpaper", lambda *_: self.run_command(
            ["fenrir-wallpaper", "next"],
            "Wallpaper rotation updated.",
        ))

        status = self.group(page, "Desktop health")
        self._overview_status = Gtk.Label(
            label="Refresh to inspect the current wallpaper library and service state.",
            xalign=0,
            wrap=True,
        )
        status.append(self._overview_status)
        self.button(status, "Refresh overview", self.refresh_overview)

        shortcuts = self.group(page, "Configuration")
        for label, target in (
            ("Wallpaper library and rotation", "wallpaper"),
            ("Displays and monitors", "display"),
            ("Fimbulwinter Glass", "appearance"),
            ("Audio devices", "audio"),
            ("Gaming and performance", "gaming"),
            ("System services", "services"),
        ):
            self.button(shortcuts, label, lambda _button, name=target: self.select_page(name))

    def select_page(self, name: str):
        row = self._navigation.get(name)
        if row is not None:
            self.sidebar.select_row(row)

    def open_doctor(self, *_):
        try:
            subprocess.run(
                ["systemctl", "--user", "start", "fenrir-doctor.service"],
                check=True,
                timeout=15,
                capture_output=True,
                text=True,
            )
            subprocess.Popen(
                ["xdg-open", "http://127.0.0.1:8765"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                close_fds=True,
            )
            self.set_status("Fenrir Doctor dashboard opened without starting the optional Ollama runtime.")
        except (OSError, subprocess.SubprocessError) as exc:
            self.set_status(str(exc), True)

    def refresh_overview(self, *_):
        lines = []
        try:
            data = core.wallpaper_status()
            lines.append(
                f"Wallpaper library: {data['valid_count']:,} qualifying / {data['file_count']:,} files; "
                f"{data['rejected_count']:,} rejected; target {data['minimum_count']:,}."
            )
            lines.append(
                f"Rotation: {data.get('interval_minutes', 15)} min; "
                f"{data.get('monitor_mode', 'shared')} monitor mode; "
                f"no-repeat history {data.get('history_depth', 20)}."
            )
        except Exception as exc:
            lines.append(f"Wallpaper library: unavailable ({exc})")
        for unit in ("fenrir-wallpaper.service", "fenrir-doctor.service", "pipewire.service"):
            try:
                lines.append(f"{unit}: {core.service_state(unit, user=True)}")
            except Exception as exc:
                lines.append(f"{unit}: unavailable ({exc})")
        self._overview_status.set_text("\n".join(lines))
        self.set_status("Fenrir overview refreshed.")

    def page_appearance(self, page):
        self.heading(page, "Appearance & Fimbulwinter Glass", "Obsidian surfaces, moderate blur and wallpaper-derived accents. Frosted surfaces default to 60% opacity (40% transparency).")
        box = self.group(page, "Glass surfaces")
        opacity = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.35, 0.85, 0.01)
        opacity.set_value(float(self.settings["theme"].get("surface_opacity", 0.60)))
        opacity.set_digits(2); opacity.set_hexpand(True)
        self.row(box, "Surface opacity", opacity, "Higher values are more opaque; 0.60 is the Fenrir default.")
        blur = Gtk.CheckButton(label="Enable compositor blur", active=bool(self.settings["theme"].get("blur_enabled", True)))
        preset = Gtk.ComboBoxText()
        for ident, label in [("obsidian", "Obsidian"), ("arctic", "Arctic blue"), ("violet", "Violet"), ("emerald", "Emerald")]: preset.append(ident, label)
        preset.set_active_id(self.settings["theme"].get("preset", "obsidian"))
        self.row(box, "Theme preset", preset)
        dynamic = Gtk.CheckButton(label="Derive accent colors from the active wallpaper", active=bool(self.settings["theme"].get("dynamic_colors", True)))
        box.append(blur); box.append(dynamic)
        def apply(*_):
            if not self.save("theme", {"surface_opacity": round(opacity.get_value(), 2), "blur_enabled": blur.get_active(), "dynamic_colors": dynamic.get_active(), "preset": preset.get_active_id()}): return
            try:
                core.write_runtime_settings()
                expression = f'hl.config({{ decoration = {{ blur = {{ enabled = {str(blur.get_active()).lower()} }} }} }})'
                subprocess.run(["hyprctl", "eval", expression], check=True, timeout=5, capture_output=True, text=True)
                state = core.STATE_HOME / "fenrir" / "wallpaper.json"
                try: wallpaper = json.loads(state.read_text()).get("path")
                except Exception: wallpaper = None
                if dynamic.get_active() and wallpaper:
                    subprocess.run(["fenrir-theme", "--wallpaper", wallpaper], check=False, timeout=30)
                else:
                    subprocess.run(["fenrir-theme"], check=False, timeout=30)
                self.set_status("Appearance saved, compositor blur applied and the selected palette refreshed.")
            except (OSError, subprocess.SubprocessError) as exc: self.set_status(str(exc), True)
        self.button(page, "Apply appearance", apply, True)

    def page_wallpaper(self, page):
        self.heading(page, "Wallpapers", "Rotation runs every 15 minutes by default. The default collection goal is 20,000 qualifying landscape images (5,000 or 10,000 are also selectable). Only readable images at least 2560×1440 count; rotation uses qualifying images already present and never waits for the goal.")
        box = self.group(page, "Library")
        directory = Gtk.Entry(text=str(self.settings["wallpaper"].get("directory", "~/Pictures/Wallpapers")))
        directory.set_hexpand(True)
        self.row(box, "Wallpaper folder", directory)
        choose = Gtk.Button(label="Choose folder…")
        def pick(*_):
            dialog = Gtk.FileChooserNative(title="Choose wallpaper folder", transient_for=self.window, action=Gtk.FileChooserAction.SELECT_FOLDER, accept_label="Select", cancel_label="Cancel")
            dialog.connect("response", lambda d, response: (directory.set_text(d.get_file().get_path()) if response == Gtk.ResponseType.ACCEPT and d.get_file() else None, d.destroy()))
            dialog.show()
        choose.connect("clicked", pick); box.append(choose)
        interval = Gtk.SpinButton.new_with_range(1, 1440, 1)
        interval.set_value(int(self.settings["wallpaper"].get("interval_minutes", 15)))
        self.row(box, "Rotation interval (minutes)", interval, "15 minutes is the default; range 1–1440.")
        monitor_mode = Gtk.ComboBoxText()
        monitor_mode.append("shared", "Use one wallpaper on every monitor")
        monitor_mode.append("independent", "Choose a different wallpaper per monitor")
        monitor_mode.set_active_id(self.settings["wallpaper"].get("monitor_mode", "shared"))
        self.row(box, "Multi-monitor behavior", monitor_mode, "Independent mode matches image aspect ratio to each display.")
        history_depth = Gtk.SpinButton.new_with_range(0, 100, 1)
        history_depth.set_value(int(self.settings["wallpaper"].get("history_depth", 20)))
        self.row(box, "No-repeat history", history_depth, "Avoid the last N images on each monitor; 0 disables the cooldown.")
        def save_wallpaper(*_):
            folder = Path(directory.get_text()).expanduser()
            if not folder.exists() or not folder.is_dir():
                self.set_status("Choose an existing readable folder before saving.", True); return
            if not self.save("wallpaper", {"directory": directory.get_text(), "interval_minutes": interval.get_value_as_int(), "monitor_mode": monitor_mode.get_active_id(), "history_depth": history_depth.get_value_as_int()}): return
            self.run_command(["systemctl", "--user", "restart", "fenrir-wallpaper.service"], "Wallpaper folder and interval applied; rotation restarts with the new settings.")
        self.button(page, "Save wallpaper settings", save_wallpaper, True)
        studio_box = self.group(page, "Wallpaper Studio")
        studio_intro = Gtk.Label(
            label="Curate accepted wallpapers, inspect rights and provenance, preview 16:9 through 32:9 display fits, and sync new collection additions into the rotation library.",
            xalign=0,
            wrap=True,
        )
        studio_intro.add_css_class("dim-label")
        studio_box.append(studio_intro)
        self.button(studio_box, "Open Wallpaper Studio", self.open_wallpaper_studio, True)
        public_box = self.group(page, "Public multi-volume wallpaper library")
        public_intro = Gtk.Label(
            label="Preview or synchronize the public Fenrir-Wallpapers hub and every active registered volume. This is separate from the private Catalog and only adds hash-verified images; it never overwrites or deletes existing files.",
            xalign=0,
            wrap=True,
        )
        public_intro.add_css_class("dim-label")
        public_box.append(public_intro)
        self.button(
            public_box,
            "Preview public volumes in terminal",
            lambda *_: self.open_public_library_terminal(dry_run=True),
        )
        self.button(
            public_box,
            "Synchronize all public volumes",
            self.confirm_public_library_sync,
            True,
        )
        status_box = self.group(page, "Library status")
        self._wallpaper_status_box = Gtk.Label(label="Use Refresh to inspect the actual qualifying image count.", xalign=0, wrap=True)
        status_box.append(self._wallpaper_status_box)
        self.button(status_box, "Refresh library status", self.refresh_wallpaper_status)
        self.button(status_box, "Choose next wallpaper", lambda *_: self.run_command(["fenrir-wallpaper", "next"], "A new wallpaper has been selected and its accent palette updated."))

    def open_wallpaper_studio(self, *_):
        try:
            subprocess.Popen(
                ["fenrir-wallpaper", "studio"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                close_fds=True,
            )
            self.set_status("Wallpaper Studio is opening in your browser. New accepted collection additions sync into rotation automatically.")
        except OSError as exc:
            self.set_status(str(exc), True)

    def open_public_library_terminal(self, *, dry_run: bool):
        terminal = shutil.which("kitty")
        command = ["fenrir-wallpaper", "sync-library"]
        if dry_run:
            command.append("--dry-run")
        if not terminal:
            self.set_status("Kitty terminal is unavailable; run: " + " ".join(command), True)
            return
        try:
            subprocess.Popen(
                [
                    terminal,
                    "--title", "Fenrir Public Wallpaper Library",
                    "--hold",
                    *command,
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                close_fds=True,
            )
            self.set_status(
                "Read-only public-library preview opened in a terminal."
                if dry_run else "Public multi-volume wallpaper synchronization opened in a terminal."
            )
        except OSError as exc:
            self.set_status(f"Could not open the wallpaper-library terminal: {exc}", True)

    def confirm_public_library_sync(self, *_):
        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text="Synchronize every active public wallpaper volume?",
        )
        dialog.format_secondary_text(
            "This can download a large collection into the configured wallpaper folder. "
            "Preview the volumes first. Every image is hash-verified; existing files are never overwritten or deleted. "
            "The private Catalog database is not accessed."
        )
        dialog.connect(
            "response",
            lambda window, response: (
                self.open_public_library_terminal(dry_run=False)
                if response == Gtk.ResponseType.OK else None,
                window.destroy(),
            ),
        )
        dialog.present()

    def refresh_wallpaper_status(self, *_):
        box = self._wallpaper_status_box
        try:
            data = core.wallpaper_status()
            box.set_text(f"{data['valid_count']:,} valid / {data['file_count']:,} files; {data['rejected_count']:,} rejected. Target: {data['minimum_count']:,}. Requirement {'MET' if data['requirement_met'] else 'NOT MET'}.")
            self.set_status("Wallpaper validation refreshed.")
        except Exception as exc: box.set_text(str(exc)); self.set_status(str(exc), True)

    def page_display(self, page):
        self.heading(page, "Display & Monitors", "Fenrir targets 2560×1440 at 155 Hz. The mode is applied only if the connected monitor advertises it; otherwise its existing preferred mode is left unchanged.")
        box = self.group(page, "Connected outputs")
        self.monitor_picker = Gtk.ComboBoxText()
        self.monitor_info = Gtk.Label(label="Detecting display modes…", xalign=0, wrap=True)
        self.refresh_monitors()
        self.row(box, "Monitor", self.monitor_picker)
        values = self.settings["display"]
        self.width = Gtk.SpinButton.new_with_range(640, 16384, 1); self.width.set_value(values.get("preferred_width", 2560))
        self.height = Gtk.SpinButton.new_with_range(640, 16384, 1); self.height.set_value(values.get("preferred_height", 1440))
        self.refresh = Gtk.SpinButton.new_with_range(30, 1000, 1); self.refresh.set_value(values.get("preferred_refresh", 155))
        self.scale = Gtk.SpinButton.new_with_range(0.5, 3.0, 0.05); self.scale.set_digits(2); self.scale.set_value(values.get("scale", 1.0))
        self.row(box, "Width", self.width); self.row(box, "Height", self.height); self.row(box, "Refresh target (Hz)", self.refresh); self.row(box, "Scale", self.scale)
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.append(actions)
        refresh_button = Gtk.Button(label="Detect displays"); refresh_button.connect("clicked", self.refresh_monitors); actions.append(refresh_button)
        apply_button = Gtk.Button(label="Apply supported mode"); apply_button.add_css_class("suggested-action"); apply_button.connect("clicked", self.apply_display); actions.append(apply_button)
        box.append(self.monitor_info)

    def refresh_monitors(self, *_):
        if not hasattr(self, "monitor_picker"): return
        self.monitor_picker.remove_all()
        try:
            monitors = core.get_monitors()
            for monitor in monitors:
                name = monitor.get("name")
                if name:
                    self.monitor_picker.append(name, f"{name} — {monitor.get('description', monitor.get('make',''))}")
            if monitors: self.monitor_picker.set_active(0)
            self.monitor_info.set_text("\n".join(f"{m.get('name')}: {m.get('currentMode', 'unknown')} (available: {', '.join(m.get('availableModes', []))})" for m in monitors))
            self.set_status(f"Detected {len(monitors)} connected output(s).")
        except Exception as exc: self.monitor_info.set_text(str(exc)); self.set_status(str(exc), True)

    def apply_display(self, *_):
        name = self.monitor_picker.get_active_id()
        if not name: self.set_status("No display selected.", True); return
        try:
            width, height, refresh, scale = self.width.get_value_as_int(), self.height.get_value_as_int(), self.refresh.get_value(), self.scale.get_value()
            changed, message = core.apply_monitor(name, width, height, refresh, scale)
            self.save("display", {"preferred_width": width, "preferred_height": height, "preferred_refresh": refresh, "scale": scale})
            self.monitor_info.set_text(message)
            self.set_status(message, not changed)
        except Exception as exc: self.set_status(str(exc), True)

    def page_hyprland(self, page):
        self.heading(page, "Hyprland & Workspaces", "Tune the compositor without replacing your configuration. Dwindle and Master layouts are supported; the safe session defaults prioritize frame pacing.")
        box = self.group(page, "Window layout")
        layout = Gtk.ComboBoxText(); layout.append("dwindle", "Dwindle"); layout.append("master", "Master")
        layout.set_active_id(self.settings["hyprland"].get("layout", "dwindle"))
        self.row(box, "Layout", layout)
        workspaces = Gtk.SpinButton.new_with_range(1, 20, 1); workspaces.set_value(self.settings["hyprland"].get("workspace_count", 10))
        self.row(box, "Workspace count", workspaces, "Custom workspace shortcuts are generated into a separate Fenrir Lua file.")
        animations = Gtk.CheckButton(label="Enable compositor animations", active=self.settings["hyprland"].get("animations", True)); box.append(animations)
        def save_layout(*_):
            chosen = layout.get_active_id()
            try:
                core.apply_layout(chosen)
                count = workspaces.get_value_as_int()
                if not self.save("hyprland", {"workspace_count": count, "animations": animations.get_active()}): return
                core.write_runtime_settings()
                core.write_workspace_bindings(count)
                subprocess.run(["hyprctl", "reload"], check=True, timeout=8, capture_output=True, text=True)
                self.set_status("Layout and workspace shortcuts applied to Hyprland.")
            except Exception as exc: self.set_status(str(exc), True)
        self.button(page, "Apply Hyprland settings", save_layout, True)
        self.button(page, "Reload Hyprland configuration", lambda *_: self.run_command(["hyprctl", "reload"], "Hyprland configuration reloaded."))

    def page_keybinds(self, page):
        self.heading(page, "Keybinds", "Reference the built-in shortcuts and add a custom binding using safe, predefined Fenrir actions. New bindings are written to a separate Lua file and survive theme updates.")
        ref = self.group(page, "Core shortcuts")
        shortcuts = [
            ("Super + Enter", "Kitty terminal"), ("Super + Space", "Fuzzel launcher"),
            ("Super + E", "Thunar file manager"), ("Super + B", "Firefox Nightly"),
            ("Super + A", "Fenrir Doctor"), ("Super + W", "Next wallpaper"),
            ("Super + L", "Manual lock (hyprlock)"), ("Super + Q", "Close window"),
            ("Super + F", "Fullscreen"), ("Super + Arrow", "Move focus"),
            ("Super + 1…0", "Switch workspaces"), ("Super + Shift + 1…0", "Move window to workspace"),
            ("Print", "Capture all monitors to clipboard"), ("Super + Shift + S", "Select screenshot region"),
            ("Super + V", "Clipboard history"),
            ("Super + Shift + F9", "Start/stop screen recording"),
        ]
        for key, action in shortcuts:
            label = Gtk.Label(label=f"{key}    {action}", xalign=0); ref.append(label)
        custom = self.group(page, "Add or update a custom shortcut")
        key = Gtk.Entry(placeholder_text="SUPER + CTRL + T")
        self.row(custom, "Key combination", key)
        action = Gtk.ComboBoxText()
        for ident, label in [("terminal","Open terminal"),("launcher","Open launcher"),("files","Open file manager"),("browser","Open browser"),("manual_lock","Manual lock"),("next_wallpaper","Next wallpaper"),("settings","Open Fenrir Settings"),("welcome","Open Welcome & Tutorial")]: action.append(ident,label)
        action.set_active_id("terminal"); self.row(custom, "Action", action)
        def save_binding(*_):
            try:
                target = core.save_custom_keybind(key.get_text(), action.get_active_id())
                subprocess.run(["hyprctl", "reload"], check=True, timeout=8, capture_output=True, text=True)
                self.set_status(f"Saved {key.get_text()} to {target} and reloaded Hyprland.")
            except Exception as exc: self.set_status(str(exc), True)
        self.button(page, "Save custom keybind", save_binding, True)

    def page_waybar(self, page):
        self.heading(page, "Waybar", "Choose which modules appear on the top panel. The app updates only the managed module lists and asks the running Waybar process to reload.")
        box = self.group(page, "Panel modules")
        position = Gtk.ComboBoxText(); position.append("top", "Top"); position.append("bottom", "Bottom")
        position.set_active_id(self.settings["waybar"].get("position", "top"))
        self.row(box, "Panel position", position)
        checks = {}
        labels = {"show_workspaces":"Workspaces","show_window":"Active window title","show_network":"Network","show_audio":"Audio","show_system":"CPU and memory","show_tray":"System tray"}
        for key, label in labels.items():
            checks[key] = Gtk.CheckButton(label=label, active=bool(self.settings["waybar"].get(key, True)))
            box.append(checks[key])
        def apply(*_):
            values = {key: check.get_active() for key, check in checks.items()}
            values["position"] = position.get_active_id()
            if not self.save("waybar", values): return
            try:
                core.update_waybar_modules(values)
                self.set_status("Waybar modules saved and reload signal sent.")
            except Exception as exc: self.set_status(str(exc), True)
        self.button(page, "Apply Waybar modules", apply, True)

    def page_audio(self, page):
        self.heading(page, "Audio", "PipeWire and WirePlumber provide the audio graph. QPWgraph offers detailed routing; EasyEffects handles processing chains.")
        box = self.group(page, "Audio graph and devices")
        output = Gtk.TextView(editable=False, monospace=True, cursor_visible=False, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        output.set_size_request(-1, 250)
        scroll = Gtk.ScrolledWindow(min_content_height=250, child=output)
        box.append(scroll)
        def refresh(*_):
            output.get_buffer().set_text(core.audio_status())
        refresh()
        self.button(box, "Refresh PipeWire status", refresh)
        sinks_box = self.group(page, "Default audio endpoints")
        self.sink_picker = Gtk.ComboBoxText(); self.source_picker = Gtk.ComboBoxText()
        self.row(sinks_box, "Output sink", self.sink_picker)
        self.row(sinks_box, "Input source", self.source_picker)
        self.button(sinks_box, "Refresh devices", self.refresh_audio_nodes)
        self.button(sinks_box, "Set output default", lambda *_: self.set_audio_default(self.sink_picker))
        self.button(sinks_box, "Set input default", lambda *_: self.set_audio_default(self.source_picker))
        self.refresh_audio_nodes()
        for label, command in [("Open QPWgraph", "qpwgraph"),("Open EasyEffects", "easyeffects"),("Open volume controls", "pavucontrol")]:
            self.button(page, label, lambda _b, cmd=command: self.launch(cmd))

    def refresh_audio_nodes(self, *_):
        self.sink_picker.remove_all(); self.source_picker.remove_all()
        try:
            sinks, sources = core.audio_nodes()
            for node_id, label in sinks: self.sink_picker.append(node_id, f"{node_id}: {label}")
            for node_id, label in sources: self.source_picker.append(node_id, f"{node_id}: {label}")
            if sinks: self.sink_picker.set_active(0)
            if sources: self.source_picker.set_active(0)
            self.set_status(f"Detected {len(sinks)} output sink(s) and {len(sources)} input source(s).")
        except Exception as exc: self.set_status(str(exc), True)

    def set_audio_default(self, picker):
        node_id = picker.get_active_id()
        if not node_id: self.set_status("No audio endpoint selected.", True); return
        try:
            core.set_default_audio_node(node_id)
            self.set_status(f"PipeWire default device set to node {node_id}.")
        except Exception as exc: self.set_status(str(exc), True)

    def launch(self, command: str):
        try: subprocess.Popen([command], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError as exc: self.set_status(str(exc), True)

    def page_startup(self, page):
        self.heading(page, "Startup applications", "Toggle selected desktop applications in your user autostart folder. Existing application launchers are copied; disabling an item removes only its Fenrir-created autostart entry.")
        box = self.group(page, "Autostart")
        apps = [("Discord","discord.desktop"),("Spotify","com.spotify.Client.desktop"),("Fenrir Doctor","fenrir-doctor.desktop"),("EasyEffects","com.github.wwmm.easyeffects.desktop")]
        for name, desktop_id in apps:
            target = core.CONFIG_HOME / "autostart" / desktop_id
            check = Gtk.CheckButton(label=name, active=target.exists())
            box.append(check)
            check.connect("toggled", lambda widget, n=name, d=desktop_id: self.startup_toggle(n,d,widget.get_active()))

    def startup_toggle(self, name: str, desktop_id: str, enabled: bool):
        try:
            core.set_startup_app(name, desktop_id, enabled)
            self.set_status(f"{name} {'added to' if enabled else 'removed from'} user autostart.")
        except Exception as exc: self.set_status(str(exc), True)

    def page_gaming(self, page):
        self.heading(page, "Gaming & Performance", "Control overlays and performance settings without downloading games, console firmware or large AI models. GameMode is invoked by game launch options; no background boost daemon is forced on.")
        box = self.group(page, "Game launch profile")
        gamemode = Gtk.CheckButton(label="Use gamemoderun for games", active=self.settings["gaming"].get("gamemode", True)); box.append(gamemode)
        mangohud = Gtk.CheckButton(label="Enable MangoHud overlay by default", active=self.settings["gaming"].get("mangohud", False)); box.append(mangohud)
        gamescope = Gtk.CheckButton(label="Launch through Gamescope fullscreen", active=self.settings["gaming"].get("gamescope", False)); box.append(gamescope)
        fps = Gtk.SpinButton.new_with_range(0, 1000, 5); fps.set_value(self.settings["gaming"].get("fps_limit", 0))
        self.row(box,"MangoHud FPS limit (0 = unlimited)",fps)
        def save(*_):
            try:
                core.configure_gaming(gamemode.get_active(), mangohud.get_active(), fps.get_value_as_int(), gamescope.get_active())
                self.set_status("Gaming profile and MangoHud/Gamemode configuration saved. Use gamemoderun and mangohud in Steam launch options when desired.")
            except Exception as exc: self.set_status(str(exc), True)
        self.button(page, "Save gaming profile", save, True)
        self.button(page, "Open GameMode status", lambda *_: self.run_command(["gamemoded", "-s"], "GameMode status queried."))

    def page_keyboard(self, page):
        self.heading(page, "Keyboard", "Fenrir defaults to US International with dead keys. Changes apply to the active Hyprland session and persist in Fenrir settings.")
        box = self.group(page, "Layout")
        layout = Gtk.ComboBoxText(); layout.append("us", "US"); layout.append("br", "Brazilian ABNT2"); layout.set_active_id(self.settings["keyboard"].get("layout", "us"))
        variant = Gtk.ComboBoxText(); variant.append("intl", "International (dead keys)"); variant.append("", "Default"); variant.append("abnt2", "ABNT2")
        variant.set_active_id(self.settings["keyboard"].get("variant", "intl"))
        self.row(box, "Layout", layout); self.row(box, "Variant", variant)
        def apply(*_):
            try:
                core.apply_keyboard(layout.get_active_id(), variant.get_active_id())
                self.set_status("Keyboard layout applied to Hyprland.")
            except Exception as exc: self.set_status(str(exc), True)
        self.button(page, "Apply keyboard layout", apply, True)

    def page_services(self, page):
        self.heading(page, "System services", "Inspect and control the desktop's services. NetworkManager and Bluetooth are system services and ask for authentication through PolicyKit; media and Fenrir services are user-session units.")
        self.service_rows = {}
        box = self.group(page, "Service control")
        services = [
            ("NetworkManager.service", False), ("bluetooth.service", False),
            ("pipewire.socket", True), ("wireplumber.service", True),
            ("fenrir-wallpaper.service", True), ("fenrir-stay-awake.service", True),
            ("sun-ai.service", True),
        ]
        for unit, user in services:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            label = Gtk.Label(label=unit, xalign=0); label.set_hexpand(True)
            status = Gtk.Label(label=core.service_state(unit, user), xalign=0)
            row.append(label); row.append(status)
            for action in ("start", "stop", "restart"):
                button = Gtk.Button(label=action.title())
                button.connect("clicked", lambda _b, u=unit, is_user=user, a=action, st=status: self.service_action(u, is_user, a, st))
                row.append(button)
            box.append(row)
            self.service_rows[unit] = (status, user)
        self.button(page, "Refresh service state", self.refresh_services)

    def service_action(self, unit: str, user: bool, action: str, status_label):
        try:
            core.control_service(unit, action, user)
            status_label.set_text(core.service_state(unit, user))
            self.set_status(f"{unit}: {action} requested successfully.")
        except Exception as exc: self.set_status(str(exc), True)

    def refresh_services(self, *_):
        for unit, (label, user) in self.service_rows.items():
            label.set_text(core.service_state(unit, user))
        self.set_status("Service status refreshed.")

    def page_power(self, page):
        self.heading(page, "Screen & Power", "Fenrir intentionally does not automatically blank the screen, power off displays, lock the session, suspend or hibernate. Manual locking remains available with Super+L.")
        box = self.group(page, "Keep this session awake")
        keep = Gtk.CheckButton(label="Block idle and sleep while the Fenrir session is active", active=self.settings["session"].get("keep_awake", True))
        box.append(keep)
        detail = Gtk.Label(label="Turning this off releases Fenrir's logind inhibitor. It does not add any automatic lock or DPMS timer. Configure system-wide power policy separately if you later want idle actions.", xalign=0, wrap=True)
        detail.add_css_class("dim-label"); box.append(detail)
        def toggle(*_):
            try:
                core.set_keep_awake(keep.get_active())
                self.set_status("Keep-awake inhibitor " + ("enabled." if keep.get_active() else "released; no Fenrir idle timers were added."))
            except Exception as exc: self.set_status(str(exc), True)
        self.button(page, "Apply power behavior", toggle, True)
        self.button(page, "Lock session now", lambda *_: self.run_command(["hyprlock"], "Manual lock requested."))

    def restore_defaults(self, *_):
        try:
            backup = core.restore_defaults()
            self.settings = core.load_settings()
            core.write_runtime_settings()
            core.write_workspace_bindings(self.settings["hyprland"].get("workspace_count", 10))
            self.set_status(f"Fenrir defaults restored. Backup: {backup}")
            dialog = Gtk.MessageDialog(transient_for=self.window, modal=True, message_type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK, text="Defaults restored")
            dialog.set_secondary_text("Reopen Fenrir Settings to refresh controls. Wallpaper, display, keyboard and session services retain their current runtime state until you apply the corresponding page.")
            dialog.connect("response", lambda d, _r: d.destroy()); dialog.present()
        except Exception as exc: self.set_status(str(exc), True)


def main() -> int:
    app = FenrirSettings()
    return app.run(sys.argv)

if __name__ == "__main__":
    raise SystemExit(main())
