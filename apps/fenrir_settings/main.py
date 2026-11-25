#!/usr/bin/env python3
"""Fenrir Settings — a practical GTK4 control center for the Hyprland desktop."""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gio, GLib, Gtk
except (ImportError, ValueError) as exc:  # pragma: no cover - host desktop dependency
    raise SystemExit(
        "Fenrir Settings requires GTK 4 and PyGObject. Install the Arch packages gtk4 and python-gobject."
    ) from exc

from settings_core import (
    apply_monitor,
    config_home,
    load_settings,
    mode_for_target,
    query_monitors,
    save_settings,
    settings_path,
    validate_settings,
    write_runtime_files,
)

APP_ID = "org.fenrir.Settings"
ACCENT = "#9b87f5"

KEYBINDS = [
    ("Super + Return", "Open Kitty terminal"),
    ("Super + Space", "Open Fuzzel application launcher"),
    ("Super + E", "Open Thunar file manager"),
    ("Super + B", "Open Firefox Nightly"),
    ("Super + A", "Open Sun AI"),
    ("Super + W", "Choose the next random wallpaper"),
    ("Super + L", "Lock the screen manually with Hyprlock"),
    ("Super + Shift + R", "Reload Hyprland configuration"),
    ("Super + Q", "Close the focused window"),
    ("Super + Shift + Q", "Exit Hyprland session"),
    ("Super + F", "Toggle fullscreen"),
    ("Super + P", "Toggle pseudotiling"),
    ("Super + J", "Toggle split orientation"),
    ("Super + Arrow keys", "Move focus between windows"),
    ("Super + 1…0", "Switch to workspaces 1…10"),
    ("Super + Shift + 1…0", "Move the focused window to workspaces 1…10"),
    ("Super + Shift + S", "Select an area screenshot and copy it"),
    ("Print", "Capture the full screen and copy it"),
    ("Super + V", "Open clipboard history"),
    ("XF86Audio…", "Hardware media and volume keys"),
]

TUTORIAL = [
    ("Getting started", "Use Super + Space to open Fuzzel. Search for an app and press Enter. Fenrir Settings is always available from the application launcher."),
    ("Workspaces", "Super + 1…0 switches workspaces. Super + Shift + 1…0 moves the focused window. Workspaces are managed by Hyprland."),
    ("Window management", "Super + arrow keys changes focus. Super + Q closes the focused window. Super + F toggles fullscreen. Super + mouse drag moves or resizes windows."),
    ("Application launcher", "Super + Space opens Fuzzel. Type an application name, use the arrow keys to select a result, and press Enter."),
    ("Screenshots and recording", "Print captures the full screen to the clipboard. Super + Shift + S selects a region and copies it. Install OBS Studio separately for screen recording."),
    ("Wallpaper and colors", "Fenrir Wallpaper validates images before rotation. The rotation target is 5,000 landscape images at 2560×1440 minimum; rotation stays paused until the target is genuinely met. Wallpaper colors feed the Fimbulwinter palettes."),
    ("Themes and Fimbulwinter Glass", "Fenrir uses an obsidian base, moderate compositor blur, and 60% surface opacity by default. Change opacity and blur in Appearance; keep enough contrast for readable controls."),
    ("Audio", "PipeWire and WirePlumber provide audio. Use QPWgraph for routing, EasyEffects for processing, and pavucontrol for device and level selection."),
    ("Gaming", "Steam and Flatpak launchers are installed separately. GameMode can be used with `gamemoderun %command%`. MangoHud is configurable through Fenrir Settings and the per-user MangoHud configuration."),
    ("Settings application", "Changes are validated and saved atomically. Existing settings are backed up before every save. Runtime controls are applied to the current Hyprland session where supported."),
    ("Troubleshooting", "If a setting does not take effect, use Apply again, then check `journalctl --user -b` and `hyprctl reload`. Recovery backups are stored beside settings.toml and under ~/.local/state/fenrir/backups."),
]


def run_command(args: list[str], *, check: bool = True, timeout: int = 8) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=check, capture_output=True, text=True, timeout=timeout)


def notify(message: str) -> None:
    print(f"[Fenrir Settings] {message}", file=sys.stderr)


class FenrirSettings(Gtk.Application):
    def __init__(self, welcome: bool = False):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.open_welcome = welcome
        self.settings = load_settings()
        self.window: Gtk.ApplicationWindow | None = None
        self.status: Gtk.Label | None = None
        self.stack: Gtk.Stack | None = None
        self.page_buttons: dict[str, Gtk.Button] = {}
        self.monitor_items: list[dict] = []
        self.monitor_output: Gtk.DropDown | None = None
        self.monitor_mode: Gtk.DropDown | None = None
        self.monitor_scale: Gtk.SpinButton | None = None
        self.help_list: Gtk.ListBox | None = None
        self.help_search: Gtk.SearchEntry | None = None
        self.help_detail: Gtk.Label | None = None
        self.help_items: list[tuple[str, str]] = []

    def do_activate(self) -> None:
        if self.window is not None:
            self.window.present()
            return
        self.window = Gtk.ApplicationWindow(application=self, title="Fenrir Settings")
        self.window.set_default_size(1100, 760)
        self.window.set_size_request(900, 620)
        self._install_css()

        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        root.add_css_class("fenrir-root")
        self.window.set_child(root)

        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        sidebar.set_size_request(235, -1)
        sidebar.add_css_class("sidebar")
        root.append(sidebar)
        brand = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        brand.set_margin_top(26)
        brand.set_margin_start(20)
        brand.set_margin_end(20)
        brand.set_margin_bottom(18)
        title = Gtk.Label(label="FENRIR")
        title.set_xalign(0)
        title.add_css_class("brand")
        subtitle = Gtk.Label(label="Desktop Control Center")
        subtitle.set_xalign(0)
        subtitle.add_css_class("muted")
        brand.append(title)
        brand.append(subtitle)
        sidebar.append(brand)

        scroll_nav = Gtk.ScrolledWindow()
        scroll_nav.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll_nav.set_vexpand(True)
        sidebar.append(scroll_nav)
        nav = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        nav.set_margin_start(12)
        nav.set_margin_end(12)
        scroll_nav.set_child(nav)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content.set_hexpand(True)
        root.append(content)
        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        top.set_margin_start(28)
        top.set_margin_end(28)
        top.set_margin_top(22)
        top.set_margin_bottom(14)
        heading = Gtk.Label(label="System preferences")
        heading.set_xalign(0)
        heading.set_hexpand(True)
        heading.add_css_class("page-heading")
        top.append(heading)
        reset = Gtk.Button(label="Restore defaults")
        reset.add_css_class("quiet-button")
        reset.connect("clicked", self._restore_defaults)
        top.append(reset)
        content.append(top)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(120)
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)
        content.append(self.stack)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        footer.set_margin_start(28)
        footer.set_margin_end(28)
        footer.set_margin_top(12)
        footer.set_margin_bottom(16)
        self.status = Gtk.Label(label="Settings are stored locally and backed up before changes.")
        self.status.set_xalign(0)
        self.status.set_hexpand(True)
        self.status.add_css_class("muted")
        footer.append(self.status)
        save = Gtk.Button(label="Apply changes")
        save.add_css_class("suggested-action")
        save.connect("clicked", self._apply_all)
        footer.append(save)
        content.append(footer)

        pages: list[tuple[str, str, Callable[[], Gtk.Widget]]] = [
            ("welcome", "Welcome", self._page_welcome),
            ("appearance", "Appearance", self._page_appearance),
            ("wallpaper", "Wallpaper", self._page_wallpaper),
            ("display", "Display", self._page_display),
            ("windows", "Window behavior", self._page_windows),
            ("waybar", "Waybar", self._page_waybar),
            ("audio", "Audio", self._page_audio),
            ("keyboard", "Keyboard", self._page_keyboard),
            ("startup", "Startup applications", self._page_startup),
            ("gaming", "Gaming & performance", self._page_gaming),
            ("session", "Screen & power", self._page_session),
            ("services", "System services", self._page_services),
            ("help", "Help & keybinds", self._page_help),
        ]
        for name, label, factory in pages:
            page = self._scroll_page(factory())
            self.stack.add_named(page, name)
            button = Gtk.Button(label=label)
            button.set_halign(Gtk.Align.FILL)
            button.add_css_class("nav-button")
            button.connect("clicked", lambda _button, page_name=name: self._show_page(page_name))
            nav.append(button)
            self.page_buttons[name] = button

        initial = "welcome" if self.open_welcome or not self.settings["welcome"]["completed"] else "appearance"
        self._show_page(initial)
        self.window.present()

    def _install_css(self) -> None:
        css = b"""
        .fenrir-root { background: #090b12; color: #e8e9f2; }
        .sidebar { background: #0d1019; border-right: 1px solid #293044; }
        .brand { color: #c7bbff; font-size: 22px; font-weight: 800; letter-spacing: 3px; }
        .page-heading { color: #f1f0f7; font-size: 21px; font-weight: 700; }
        .section-title { color: #ded9f7; font-size: 17px; font-weight: 700; margin-top: 16px; }
        .muted { color: #a2a6b6; }
        .nav-button { padding: 10px 14px; border-radius: 10px; background: transparent; color: #c4c7d2; text-align: left; }
        .nav-button:hover { background: #1b2030; color: #ffffff; }
        .nav-active { background: #25213a; color: #e4ddff; }
        .setting-row { background: #111622; border: 1px solid #252c3e; border-radius: 14px; padding: 14px 16px; margin: 4px 0; }
        .setting-title { font-weight: 650; color: #eeeef5; }
        .card { background: #101521; border: 1px solid #2a3042; border-radius: 18px; padding: 22px; }
        .welcome-title { font-size: 30px; font-weight: 800; color: #e8e1ff; }
        .suggested-action { background: #6250a6; color: white; }
        .quiet-button { background: #1a2030; color: #d8daea; }
        entry, spinbutton, dropdown, textview { background: #0c111b; color: #eef0f7; border: 1px solid #343b51; border-radius: 8px; }
        scale trough { background: #282b3c; border-radius: 6px; }
        scale highlight { background: #9b87f5; }
        switch:checked { background: #7665bd; }
        button { min-height: 34px; }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_display(
            self.window.get_display(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _scroll_page(self, child: Gtk.Widget) -> Gtk.ScrolledWindow:
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)
        scroll.set_child(child)
        return scroll

    def _page_box(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(28)
        box.set_margin_end(28)
        box.set_margin_top(14)
        box.set_margin_bottom(24)
        return box

    def _heading(self, parent: Gtk.Box, title: str, description: str | None = None) -> None:
        label = Gtk.Label(label=title)
        label.set_xalign(0)
        label.add_css_class("section-title")
        parent.append(label)
        if description:
            desc = Gtk.Label(label=description)
            desc.set_xalign(0)
            desc.set_wrap(True)
            desc.add_css_class("muted")
            parent.append(desc)

    def _row(self, parent: Gtk.Box, title: str, description: str, control: Gtk.Widget) -> None:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        row.add_css_class("setting-row")
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        left.set_hexpand(True)
        name = Gtk.Label(label=title)
        name.set_xalign(0)
        name.add_css_class("setting-title")
        detail = Gtk.Label(label=description)
        detail.set_xalign(0)
        detail.set_wrap(True)
        detail.add_css_class("muted")
        left.append(name)
        left.append(detail)
        row.append(left)
        control.set_valign(Gtk.Align.CENTER)
        row.append(control)
        parent.append(row)

    def _button(self, label: str, callback: Callable[[Gtk.Button], None]) -> Gtk.Button:
        button = Gtk.Button(label=label)
        button.connect("clicked", callback)
        return button

    def _switch(self, value: bool, callback: Callable[[Gtk.Switch, bool], None] | None = None) -> Gtk.Switch:
        widget = Gtk.Switch(active=value)
        if callback:
            widget.connect("state-set", callback)
        return widget

    def _scale(self, low: float, high: float, step: float, value: float, width: int = 230) -> Gtk.Scale:
        widget = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, low, high, step)
        widget.set_value(value)
        widget.set_size_request(width, -1)
        widget.set_draw_value(True)
        return widget

    def _show_page(self, name: str) -> None:
        if self.stack is None:
            return
        self.stack.set_visible_child_name(name)
        for key, button in self.page_buttons.items():
            if key == name:
                button.add_css_class("nav-active")
            else:
                button.remove_css_class("nav-active")
        if self.status:
            self.status.set_text(f"{name.replace('-', ' ').title()} · {settings_path()}")

    def _set_status(self, message: str) -> None:
        if self.status:
            self.status.set_text(message)

    def _persist(self, *, apply_runtime: bool = True) -> None:
        self.settings = validate_settings(self.settings)
        target = save_settings(self.settings)
        if apply_runtime:
            write_runtime_files(self.settings)
        self._set_status(f"Saved with a reversible backup: {target}")

    def _page_welcome(self) -> Gtk.Widget:
        box = self._page_box()
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        card.add_css_class("card")
        title = Gtk.Label(label="Welcome to Fenrir")
        title.set_xalign(0)
        title.add_css_class("welcome-title")
        card.append(title)
        text = Gtk.Label(label="A cohesive Arch Linux desktop built around Hyprland, Fimbulwinter Glass, thoughtful customization, and a quiet system that stays awake until you choose otherwise.")
        text.set_xalign(0)
        text.set_wrap(True)
        text.add_css_class("muted")
        card.append(text)
        for line in (
            "Appearance, wallpaper and dynamic colors are configured together.",
            "Display settings detect advertised modes before attempting 2560×1440 at 155 Hz.",
            "Automatic screen blanking, idle locking and idle suspension are off by default.",
            "Your existing settings are backed up before each change.",
            "The wallpaper engine pauses until 5,000 genuinely validated images are available.",
        ):
            label = Gtk.Label(label="•  " + line)
            label.set_xalign(0)
            label.set_wrap(True)
            card.append(label)
        finish = Gtk.Button(label="Finish welcome setup")
        finish.add_css_class("suggested-action")
        finish.set_halign(Gtk.Align.START)
        finish.connect("clicked", self._complete_welcome)
        card.append(finish)
        box.append(card)
        self._heading(box, "Quick start", "Use Super + Space to launch applications. Open Help & keybinds at any time for the searchable guide.")
        return box

    def _complete_welcome(self, _button: Gtk.Button) -> None:
        self.settings["welcome"]["completed"] = True
        try:
            self._persist()
            self._set_status("Welcome completed. You can reopen this page at any time.")
            self._show_page("appearance")
        except Exception as exc:
            self._set_status(f"Could not save welcome status: {exc}")

    def _page_appearance(self) -> Gtk.Widget:
        box = self._page_box()
        self._heading(box, "Fimbulwinter Glass", "Obsidian foundations, restrained blur and wallpaper-derived accents. The default surface opacity is 60% (40% transparency).")
        opacity = self._scale(0.45, 0.85, 0.01, self.settings["theme"]["surface_opacity"])
        opacity.connect("value-changed", lambda scale: self.settings["theme"].update(surface_opacity=round(scale.get_value(), 2)))
        self._row(box, "Frosted surface opacity", "Higher opacity improves readability; 0.60 is the Fenrir default.", opacity)
        dynamic = self._switch(self.settings["theme"]["dynamic_colors"], lambda _w, state: self._set_theme_flag("dynamic_colors", state))
        self._row(box, "Wallpaper-derived colors", "Synchronize accents across Waybar, Kitty, Fuzzel, Mako and GTK.", dynamic)
        blur = self._switch(self.settings["theme"]["blur_enabled"], lambda _w, state: self._set_theme_flag("blur_enabled", state))
        self._row(box, "Compositor blur", "Moderate blur for translucent desktop surfaces.", blur)
        blur_size = self._scale(0, 20, 1, self.settings["theme"]["blur_size"])
        blur_size.connect("value-changed", lambda scale: self.settings["theme"].update(blur_size=int(scale.get_value())))
        self._row(box, "Blur radius", "Applied to the Hyprland decoration configuration.", blur_size)
        apply = self._button("Apply appearance", self._apply_appearance)
        apply.set_halign(Gtk.Align.START)
        box.append(apply)
        return box

    def _set_theme_flag(self, key: str, state: bool) -> bool:
        self.settings["theme"][key] = state
        return False

    def _apply_appearance(self, _button: Gtk.Button) -> None:
        try:
            self._persist()
            current = Path.home() / ".local" / "state" / "fenrir" / "wallpaper.json"
            wallpaper = None
            try:
                wallpaper = json.loads(current.read_text(encoding="utf-8")).get("path")
            except (OSError, ValueError, TypeError):
                pass
            command = ["fenrir-theme"]
            if wallpaper and self.settings["theme"]["dynamic_colors"]:
                command += ["--wallpaper", wallpaper]
            run_command(command, check=False, timeout=20)
            run_command(["hyprctl", "reload"], check=False)
            self._set_status("Appearance saved and applied. New application windows read the updated palette.")
        except Exception as exc:
            self._set_status(f"Appearance could not be applied: {exc}")

    def _page_wallpaper(self) -> Gtk.Widget:
        box = self._page_box()
        self._heading(box, "Wallpaper library", "Only valid landscape images at 2560×1440 or higher count toward the 5,000-image target.")
        directory = Gtk.Entry()
        directory.set_text(self.settings["wallpaper"]["directory"])
        directory.set_hexpand(True)
        directory.connect("changed", lambda entry: self.settings["wallpaper"].update(directory=entry.get_text()))
        self._row(box, "Wallpaper folder", "The folder scanned by the validated wallpaper engine.", directory)
        interval = Gtk.SpinButton.new_with_range(1, 1440, 1)
        interval.set_value(self.settings["wallpaper"]["interval_minutes"])
        interval.connect("value-changed", lambda spin: self.settings["wallpaper"].update(interval_minutes=spin.get_value_as_int()))
        self._row(box, "Rotation interval", "15 minutes by default. Valid range: 1 minute to 24 hours.", interval)
        folder = self._button("Choose wallpaper folder…", lambda _b: self._choose_folder(directory))
        choose_image = self._button("Choose image…", self._choose_wallpaper_file)
        next_wallpaper = self._button("Next wallpaper", self._next_wallpaper)
        status = self._button("Check library status", self._wallpaper_status)
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        actions.append(folder)
        actions.append(choose_image)
        actions.append(next_wallpaper)
        actions.append(status)
        box.append(actions)
        return box

    def _choose_folder(self, entry: Gtk.Entry) -> None:
        dialog = Gtk.FileChooserNative.new("Choose wallpaper folder", self.window, Gtk.FileChooserAction.SELECT_FOLDER, "Select", "Cancel")
        dialog.connect("response", lambda chooser, response: self._folder_selected(chooser, response, entry))
        dialog.show()

    def _folder_selected(self, chooser: Gtk.FileChooserNative, response: int, entry: Gtk.Entry) -> None:
        if response == Gtk.ResponseType.ACCEPT:
            file = chooser.get_file()
            if file and file.get_path():
                entry.set_text(file.get_path())
        chooser.destroy()

    def _choose_wallpaper_file(self, _button: Gtk.Button) -> None:
        dialog = Gtk.FileChooserNative.new("Choose a wallpaper", self.window, Gtk.FileChooserAction.OPEN, "Apply", "Cancel")
        image_filter = Gtk.FileFilter()
        image_filter.set_name("Supported image files")
        for pattern in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
            image_filter.add_pattern(pattern)
        dialog.add_filter(image_filter)
        dialog.connect("response", self._wallpaper_file_selected)
        dialog.show()

    def _wallpaper_file_selected(self, chooser: Gtk.FileChooserNative, response: int) -> None:
        if response == Gtk.ResponseType.ACCEPT:
            selected = chooser.get_file()
            path = selected.get_path() if selected else None
            if path:
                try:
                    result = run_command(["fenrir-wallpaper", "set", "--file", path], check=False, timeout=35)
                    self._set_status(result.stdout.strip() or result.stderr.strip() or "Wallpaper selection requested.")
                except Exception as exc:
                    self._set_status(f"Wallpaper could not be applied: {exc}")
        chooser.destroy()

    def _next_wallpaper(self, _button: Gtk.Button) -> None:
        try:
            self._persist()
            result = run_command(["fenrir-wallpaper", "next"], check=False, timeout=30)
            self._set_status(result.stdout.strip() or result.stderr.strip() or "Wallpaper selection requested.")
        except Exception as exc:
            self._set_status(f"Wallpaper did not change: {exc}")

    def _wallpaper_status(self, _button: Gtk.Button) -> None:
        try:
            result = run_command(["fenrir-wallpaper", "status"], check=False, timeout=30)
            self._set_status(result.stdout.strip() or result.stderr.strip())
        except Exception as exc:
            self._set_status(f"Wallpaper status unavailable: {exc}")

    def _page_display(self) -> Gtk.Widget:
        box = self._page_box()
        self._heading(box, "Monitor and refresh rate", "Fenrir requests 2560×1440 at 155 Hz only when that exact mode is advertised by the monitor. Otherwise it keeps a supported current/preferred mode.")
        self.monitor_items = query_monitors()
        names = [item["name"] for item in self.monitor_items]
        self.monitor_output = Gtk.DropDown.new_from_strings(names or ["No Hyprland monitor detected"])
        self.monitor_output.connect("notify::selected", self._monitor_changed)
        self._row(box, "Output", "Detected live outputs reported by Hyprland.", self.monitor_output)
        modes = self._modes_for_selected_monitor()
        self.monitor_mode = Gtk.DropDown.new_from_strings(modes or ["preferred"])
        if self.monitor_items:
            mode, _exact = mode_for_target(modes, current=self.monitor_items[0]["current"])
            if mode in modes:
                self.monitor_mode.set_selected(modes.index(mode))
        self._row(box, "Available mode", "155 Hz is preselected only when the monitor advertises it; otherwise a supported fallback is chosen.", self.monitor_mode)
        self.monitor_scale = Gtk.SpinButton.new_with_range(0.5, 3.0, 0.05)
        self.monitor_scale.set_digits(2)
        self.monitor_scale.set_value(self.settings["monitor"]["scale"])
        self._row(box, "Display scale", "Hyprland output scale factor.", self.monitor_scale)
        target = self._button("Detect and apply best supported mode", self._apply_monitor)
        target.set_halign(Gtk.Align.START)
        box.append(target)
        refresh = self._button("Refresh detected outputs", self._refresh_monitors)
        refresh.set_halign(Gtk.Align.START)
        box.append(refresh)
        if not names:
            warning = Gtk.Label(label="A Hyprland session is required to inspect and apply monitor modes.")
            warning.set_xalign(0)
            warning.add_css_class("muted")
            box.append(warning)
        return box

    def _modes_for_selected_monitor(self) -> list[str]:
        if not self.monitor_items:
            return ["preferred"]
        index = self.monitor_output.get_selected() if self.monitor_output else 0
        item = self.monitor_items[min(index, len(self.monitor_items)-1)]
        modes = item.get("modes") or []
        if item.get("current") and item["current"] not in modes:
            modes = [item["current"], *modes]
        return modes or ["preferred"]

    def _monitor_changed(self, *_args) -> None:
        if self.monitor_mode is not None:
            modes = self._modes_for_selected_monitor()
            self.monitor_mode.set_model(Gtk.StringList.new(modes))
            self.monitor_mode.set_selected(0)

    def _refresh_monitors(self, _button: Gtk.Button) -> None:
        self.monitor_items = query_monitors()
        if self.monitor_output is not None:
            names = [item["name"] for item in self.monitor_items] or ["No Hyprland monitor detected"]
            self.monitor_output.set_model(Gtk.StringList.new(names))
            self.monitor_output.set_selected(0)
        self._monitor_changed()
        self._set_status(f"Detected {len(self.monitor_items)} monitor(s).")

    def _apply_monitor(self, _button: Gtk.Button) -> None:
        if not self.monitor_items or self.monitor_output is None or self.monitor_mode is None or self.monitor_scale is None:
            self._set_status("No monitor was detected. Run this control inside Hyprland.")
            return
        index = min(self.monitor_output.get_selected(), len(self.monitor_items)-1)
        item = self.monitor_items[index]
        selected = self.monitor_mode.get_selected_item()
        mode = selected.get_string() if selected else "preferred"
        if mode == "No Hyprland monitor detected":
            return
        try:
            apply_monitor(item["name"], mode, self.monitor_scale.get_value())
            self.settings["monitor"]["scale"] = self.monitor_scale.get_value()
            parsed = re.match(r"(\d+)x(\d+)@([0-9.]+)", mode)
            if parsed:
                self.settings["monitor"].update(target_width=int(parsed.group(1)), target_height=int(parsed.group(2)), target_refresh=float(parsed.group(3)))
            self._persist(apply_runtime=False)
            self._set_status(f"Applied {item['name']}: {mode} at scale {self.monitor_scale.get_value():.2f}.")
        except Exception as exc:
            self._set_status(f"Monitor mode was not applied: {exc}")

    def _page_windows(self) -> Gtk.Widget:
        box = self._page_box()
        self._heading(box, "Hyprland behavior", "Values are persisted in a generated Lua module and reloaded into the current session.")
        for key, title, desc, low, high in (
            ("gaps_inner", "Inner gaps", "Space between tiled windows.", 0, 40),
            ("gaps_outer", "Outer gaps", "Space between windows and screen edges.", 0, 80),
            ("border_size", "Window border size", "Thickness of the active and inactive window borders.", 0, 10),
        ):
            scale = self._scale(low, high, 1, self.settings["hyprland"][key])
            scale.connect("value-changed", lambda widget, field=key: self.settings["hyprland"].update({field: int(widget.get_value())}))
            self._row(box, title, desc, scale)
        layout = Gtk.DropDown.new_from_strings(["dwindle", "master"])
        layout.set_selected(0 if self.settings["hyprland"]["layout"] == "dwindle" else 1)
        layout.connect("notify::selected", lambda widget: self.settings["hyprland"].update(layout=widget.get_selected_item().get_string()))
        self._row(box, "Tiling layout", "Choose the Hyprland dwindle or master layout.", layout)
        return box

    def _page_waybar(self) -> Gtk.Widget:
        box = self._page_box()
        self._heading(box, "Panel layout", "Switch Waybar on or off and choose the standard or compact Fimbulwinter layout.")
        enabled = self._switch(self.settings["waybar"]["enabled"], lambda _w, state: self.settings["waybar"].update(enabled=state))
        self._row(box, "Show Waybar", "Starts or stops the panel in the current session.", enabled)
        layout = Gtk.DropDown.new_from_strings(["default", "compact"])
        layout.set_selected(0 if self.settings["waybar"]["layout"] == "default" else 1)
        layout.connect("notify::selected", lambda widget: self.settings["waybar"].update(layout=widget.get_selected_item().get_string()))
        self._row(box, "Panel spacing", "Compact reduces the vertical padding and panel margin.", layout)
        return box

    def _page_audio(self) -> Gtk.Widget:
        box = self._page_box()
        self._heading(box, "Audio devices and routing", "PipeWire and WirePlumber provide the audio server. Open the appropriate tool for detailed routing and processing.")
        for label, command, detail in (
            ("Open QPWgraph", "qpwgraph", "Connect audio applications, interfaces and hardware endpoints."),
            ("Open EasyEffects", "easyeffects", "Apply equalization, compression and effects to input/output streams."),
            ("Open volume control", "pavucontrol", "Choose devices and adjust playback and recording levels."),
        ):
            self._row(box, label, detail, self._button("Launch", lambda _b, cmd=command: self._launch(cmd)))
        self._heading(box, "Audio service status")
        status = Gtk.Label(label=self._audio_status())
        status.set_xalign(0)
        status.set_selectable(True)
        status.set_wrap(True)
        status.add_css_class("muted")
        box.append(status)
        return box

    def _audio_status(self) -> str:
        try:
            result = run_command(["wpctl", "status"], check=False, timeout=5)
            return result.stdout[-1800:] if result.stdout else result.stderr or "No PipeWire status was returned."
        except Exception as exc:
            return f"Audio status unavailable: {exc}"

    def _launch(self, command: str) -> None:
        try:
            subprocess.Popen([command], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError as exc:
            self._set_status(f"Could not launch {command}: {exc}")

    def _page_keyboard(self) -> Gtk.Widget:
        box = self._page_box()
        self._heading(box, "Keyboard layout", "The default is US International with dead keys (XKB: us / intl).")
        layouts = Gtk.DropDown.new_from_strings(["US International (dead keys)", "US International (AltGr)", "Brazilian ABNT2", "British"])
        current = (self.settings["keyboard"]["layout"], self.settings["keyboard"]["variant"])
        index = {("us", "intl"): 0, ("us", "altgr-intl"): 1, ("br", "abnt2"): 2, ("gb", ""): 3}.get(current, 0)
        layouts.set_selected(index)
        layouts.connect("notify::selected", self._keyboard_selected)
        self._row(box, "Keyboard layout", "Select a supported XKB layout and variant.", layouts)
        return box

    def _keyboard_selected(self, widget: Gtk.DropDown, *_args) -> None:
        options = [("us", "intl"), ("us", "altgr-intl"), ("br", "abnt2"), ("gb", "")]
        self.settings["keyboard"]["layout"], self.settings["keyboard"]["variant"] = options[widget.get_selected()]
        layout, variant = options[widget.get_selected()]
        try:
            run_command(["hyprctl", "keyword", "input:kb_layout", layout], check=True)
            run_command(["hyprctl", "keyword", "input:kb_variant", variant], check=True)
            self._persist(apply_runtime=False)
            self._set_status("Keyboard layout applied to the current Hyprland session.")
        except Exception as exc:
            self._set_status(f"Keyboard layout could not be applied: {exc}")

    def _page_startup(self) -> Gtk.Widget:
        box = self._page_box()
        self._heading(box, "Startup applications", "Add user-session applications without changing system services. Commands are stored as desktop entries, not shell scripts.")
        name = Gtk.Entry()
        name.set_placeholder_text("Application name")
        command = Gtk.Entry()
        command.set_placeholder_text("Executable and arguments, e.g. discord --start-minimized")
        self._row(box, "Application name", "Visible name in the startup list.", name)
        self._row(box, "Launch command", "Must be a valid executable command.", command)
        add = Gtk.Button(label="Add to startup")
        add.set_halign(Gtk.Align.START)
        add.connect("clicked", lambda _b: self._add_startup(name.get_text(), command.get_text()))
        box.append(add)
        self._heading(box, "Configured startup applications")
        for entry in sorted((config_home() / "autostart").glob("fenrir-*.desktop")):
            label = Gtk.Label(label=entry.name)
            label.set_xalign(0)
            self._row(box, entry.stem, "Fenrir-managed user autostart entry.", self._button("Remove", lambda _b, path=entry: self._remove_startup(path)))
        return box

    def _add_startup(self, name: str, command: str) -> None:
        clean_name = name.strip()
        if not clean_name or "\n" in clean_name or "\n" in command:
            self._set_status("Enter a valid application name and single-line command.")
            return
        try:
            parts = shlex.split(command)
            if not parts:
                raise ValueError("Launch command is empty")
            if not (Path(parts[0]).is_absolute() and Path(parts[0]).exists()) and shutil.which(parts[0]) is None:
                raise ValueError(f"Executable not found: {parts[0]}")
            slug = re.sub(r"[^a-z0-9-]+", "-", clean_name.lower()).strip("-")[:48] or "application"
            target = config_home() / "autostart" / f"fenrir-{slug}.desktop"
            def desktop_arg(part: str) -> str:
                escaped = part.replace("\\", "\\\\").replace('"', '\\"')
                return f'"{escaped}"' if any(char.isspace() for char in part) or "\\" in part or '"' in part else escaped
            exec_line = " ".join(desktop_arg(part) for part in parts).replace("%", "%%")
            content = f"[Desktop Entry]\nType=Application\nName={clean_name}\nExec={exec_line}\nX-GNOME-Autostart-enabled=true\n"
            target.parent.mkdir(parents=True, exist_ok=True)
            from settings_core import atomic_write
            atomic_write(target, content, 0o600)
            self._set_status(f"Added {clean_name} to {target}.")
            self._show_page("startup")
        except Exception as exc:
            self._set_status(f"Startup entry was not added: {exc}")

    def _remove_startup(self, path: Path) -> None:
        try:
            if path.is_file() and path.name.startswith("fenrir-"):
                path.unlink()
                self._set_status(f"Removed {path.name}.")
                self._show_page("startup")
        except OSError as exc:
            self._set_status(f"Could not remove startup entry: {exc}")

    def _page_gaming(self) -> Gtk.Widget:
        box = self._page_box()
        self._heading(box, "Gaming performance", "Fenrir installs GameMode, MangoHud, Gamescope and AMD 32-bit Vulkan/Mesa support in the Arch profile.")
        hud = self._switch(self.settings["gaming"]["mangohud"], lambda _w, state: self.settings["gaming"].update(mangohud=state))
        self._row(box, "Enable MangoHud environment", "Writes a per-user environment.d setting; sign out and back in for all game launchers to inherit it.", hud)
        gamemode = Gtk.Label(label="GameMode launch option: gamemoderun %command%")
        gamemode.set_xalign(0)
        gamemode.set_selectable(True)
        gamemode.set_wrap(True)
        box.append(gamemode)
        test = self._button("Test GameMode", self._test_gamemode)
        test.set_halign(Gtk.Align.START)
        box.append(test)
        return box

    def _test_gamemode(self, _button: Gtk.Button) -> None:
        try:
            result = run_command(["gamemoded", "-t"], check=False, timeout=20)
            self._set_status((result.stdout or result.stderr)[-900:])
        except Exception as exc:
            self._set_status(f"GameMode test unavailable: {exc}")

    def _page_session(self) -> Gtk.Widget:
        box = self._page_box()
        self._heading(box, "Screen and power behavior", "Default behavior keeps the screen on, leaves the session unlocked and ignores idle suspension. Manual locking remains available with Super + L.")
        screen = self._switch(self.settings["session"]["allow_screen_off"], lambda _w, state: self.settings["session"].update(allow_screen_off=state))
        self._row(box, "Allow display power-off after inactivity", "Off by default. Enabling this adds a 15-minute Hypridle DPMS timeout.", screen)
        lock = self._switch(self.settings["session"]["auto_lock"], lambda _w, state: self.settings["session"].update(auto_lock=state))
        self._row(box, "Automatically lock after inactivity", "Off by default. Manual Hyprlock remains available regardless of this setting.", lock)
        self._heading(box, "Automatic system suspension")
        note = Gtk.Label(label="IdleAction=ignore is enforced by the Fenrir system profile. Fenrir Settings does not enable automatic suspend or hibernate; use the system power menu for deliberate power actions.")
        note.set_xalign(0)
        note.set_wrap(True)
        note.add_css_class("muted")
        box.append(note)
        return box

    def _page_services(self) -> Gtk.Widget:
        box = self._page_box()
        self._heading(box, "User services", "Manage the desktop audio and wallpaper services for the current login session.")
        for title, unit, detail in (
            ("PipeWire audio", "pipewire.socket", "User audio server socket."),
            ("WirePlumber", "wireplumber.service", "Audio session and device policy."),
            ("Fenrir wallpaper engine", "fenrir-wallpaper.service", "15-minute rotation, only after the validated image target is met."),
            ("Sun AI", "sun-ai.service", "Local Sun AI web interface on demand."),
        ):
            buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            buttons.append(self._button("Start", lambda _b, u=unit: self._service_action("start", u)))
            buttons.append(self._button("Stop", lambda _b, u=unit: self._service_action("stop", u)))
            self._row(box, title, detail, buttons)
        return box

    def _service_action(self, action: str, unit: str) -> None:
        try:
            result = run_command(["systemctl", "--user", action, unit], check=False, timeout=12)
            self._set_status(result.stderr.strip() or f"{unit}: {action} requested.")
        except Exception as exc:
            self._set_status(f"Could not {action} {unit}: {exc}")

    def _page_help(self) -> Gtk.Widget:
        box = self._page_box()
        self._heading(box, "Searchable help and keybind reference", "Search for a task, key combination, audio, wallpapers, workspaces, or recovery instructions.")
        self.help_search = Gtk.SearchEntry()
        self.help_search.set_placeholder_text("Search Fenrir help…")
        self.help_search.connect("search-changed", self._filter_help)
        box.append(self.help_search)
        split = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        split.set_vexpand(True)
        box.append(split)
        list_scroll = Gtk.ScrolledWindow()
        list_scroll.set_size_request(280, 360)
        list_scroll.set_vexpand(True)
        split.append(list_scroll)
        self.help_list = Gtk.ListBox()
        self.help_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.help_list.connect("row-selected", self._help_selected)
        list_scroll.set_child(self.help_list)
        detail_scroll = Gtk.ScrolledWindow()
        detail_scroll.set_hexpand(True)
        detail_scroll.set_vexpand(True)
        split.append(detail_scroll)
        self.help_detail = Gtk.Label(label="Select a guide topic or keybind.")
        self.help_detail.set_xalign(0)
        self.help_detail.set_yalign(0)
        self.help_detail.set_wrap(True)
        self.help_detail.set_selectable(True)
        self.help_detail.set_margin_start(16)
        self.help_detail.set_margin_end(16)
        self.help_detail.set_margin_top(12)
        detail_scroll.set_child(self.help_detail)
        self.help_items = [(f"Keybind · {key}", desc) for key, desc in KEYBINDS] + TUTORIAL
        self._populate_help(self.help_items)
        return box

    def _populate_help(self, items: list[tuple[str, str]]) -> None:
        if self.help_list is None:
            return
        child = self.help_list.get_first_child()
        while child:
            following = child.get_next_sibling()
            self.help_list.remove(child)
            child = following
        for title, body in items:
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=title)
            label.set_xalign(0)
            label.set_wrap(True)
            label.set_margin_start(10)
            label.set_margin_end(10)
            label.set_margin_top(8)
            label.set_margin_bottom(8)
            row.set_child(label)
            row.set_tooltip_text(body)
            self.help_list.append(row)

    def _filter_help(self, entry: Gtk.SearchEntry) -> None:
        query = entry.get_text().strip().casefold()
        items = [(title, body) for title, body in self.help_items if not query or query in title.casefold() or query in body.casefold()]
        self._populate_help(items)
        self._set_status(f"{len(items)} help topic(s) match '{query}'.")

    def _help_selected(self, _list: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if row is None or self.help_detail is None:
            return
        self.help_detail.set_text(row.get_tooltip_text() or "")

    def _apply_all(self, _button: Gtk.Button) -> None:
        try:
            self._persist()
            run_command(["hyprctl", "reload"], check=False)
            run_command(["pkill", "-x", "hypridle"], check=False)
            idle_actions = self.settings["session"]["auto_lock"] or self.settings["session"]["allow_screen_off"]
            if idle_actions:
                subprocess.Popen(["hypridle"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            run_command(["systemctl", "--user", "restart", "fenrir-wallpaper.service"], check=False)
            wallpaper_state = Path.home() / ".local" / "state" / "fenrir" / "wallpaper.json"
            try:
                selected_wallpaper = json.loads(wallpaper_state.read_text(encoding="utf-8")).get("path")
            except (OSError, ValueError, TypeError):
                selected_wallpaper = None
            if selected_wallpaper:
                run_command(["fenrir-theme", "--wallpaper", selected_wallpaper], check=False, timeout=20)
            run_command(["pkill", "-USR2", "waybar"], check=False)
            self._apply_mangohud_environment()
            run_command(["fenrir-waybar", "start" if self.settings["waybar"]["enabled"] else "stop"], check=False)
            self._set_status("Settings validated, backed up and applied to the current session where supported.")
        except Exception as exc:
            self._set_status(f"Settings were not applied: {exc}")

    def _apply_mangohud_environment(self) -> None:
        from settings_core import atomic_write
        env_file = config_home() / "environment.d" / "90-fenrir-gaming.conf"
        if self.settings["gaming"]["mangohud"]:
            atomic_write(env_file, "MANGOHUD=1\n", 0o600)
            mangohud = config_home() / "MangoHud" / "MangoHud.conf"
            atomic_write(mangohud, "fps\ncpu_stats\ngpu_stats\nframe_timing\nframetime\n", 0o600)
        else:
            if env_file.exists():
                env_file.unlink()

    def _restore_defaults(self, _button: Gtk.Button) -> None:
        dialog = Gtk.AlertDialog(message="Restore Fenrir Settings defaults?", detail="Your current settings will be backed up before defaults are written.")
        dialog.set_buttons(["Cancel", "Restore defaults"])
        dialog.set_cancel_button(0)
        dialog.set_default_button(0)
        dialog.choose(self.window, None, self._restore_response)

    def _restore_response(self, dialog: Gtk.AlertDialog, result: Gio.AsyncResult) -> None:
        try:
            choice = dialog.choose_finish(result)
            if choice != 1:
                return
            from settings_core import DEFAULTS
            self.settings = json.loads(json.dumps(DEFAULTS))
            self._persist()
            self._set_status("Defaults restored. Review settings pages and Apply changes to update the session.")
            self._show_page("welcome")
        except Exception as exc:
            self._set_status(f"Defaults were not restored: {exc}")


def main() -> int:
    welcome = "--welcome" in sys.argv[1:]
    app = FenrirSettings(welcome=welcome)
    return app.run([sys.argv[0]])


if __name__ == "__main__":
    raise SystemExit(main())
