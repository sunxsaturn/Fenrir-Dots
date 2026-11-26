#!/usr/bin/env python3
"""Searchable first-login overview and persistent Fenrir tutorial."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk

STATE = Path.home() / ".local/state/fenrir/welcome-seen"

SECTIONS = [
    ("Getting started", "setup login hyprland sddm", "## Welcome to Fenrir\n\nFenrir is an original Arch Linux + Hyprland desktop. It uses the Fimbulwinter Glass visual system: an obsidian foundation, moderate blur, 60% frosted-surface opacity and accents derived from the active wallpaper.\n\n1. Choose **Hyprland** in SDDM at login.\n2. Open **Fenrir Settings** from Fuzzel or the application menu.\n3. Use `Super + Space` to open Fuzzel and search installed applications.\n4. Keep a TTY recovery path available with `Ctrl + Alt + F3`.\n\nFenrir does not repartition, format or reboot the computer during desktop installation."),
    ("Keybind reference", "shortcut super terminal launcher browser files lock", "## Core shortcuts\n\n| Shortcut | Action |\n|---|---|\n| `Super + Enter` | Kitty terminal |\n| `Super + Space` | Fuzzel application launcher |\n| `Super + E` | Thunar file manager |\n| `Super + B` | Firefox Nightly |\n| `Super + A` | Fenrir Doctor |\n| `Super + W` | Next wallpaper |\n| `Super + L` | Manual lock with hyprlock |\n| `Super + Q` | Close focused window |\n| `Super + F` | Toggle fullscreen |\n| `Super + P` | Toggle pseudotile |\n| `Super + J` | Toggle split |\n| `Super + Arrow` | Move focus |\n| `Super + 1…0` | Switch workspace |\n| `Super + Shift + 1…0` | Move window to workspace |\n| `Super + Shift + R` | Reload Hyprland |\n| `Super + Shift + Q` | Exit Hyprland |\n| `Super + Shift + S` | Select screenshot region and copy |\n| `Print` | Capture displays to clipboard |\n| `Super + V` | Clipboard history |\n\nAudio/media keys control volume and playback. Open Fenrir Settings → Keybinds to view or add custom bindings."),
    ("Workspaces and windows", "workspace navigation window tiling floating master dwindle", "## Workspaces and windows\n\nFenrir uses Hyprland with Dwindle as the default tiling layout. Switch workspaces with `Super + 1` through `Super + 0`; move a focused window with `Super + Shift + number`.\n\nUse `Super + Arrow` to change focus, `Super + Q` to close a window, `Super + F` for fullscreen and `Super + mouse drag` to move floating windows. Fenrir Settings → Hyprland lets you switch between Dwindle and Master layouts."),
    ("Application launcher", "fuzzel applications search launch", "## Launch applications\n\nPress `Super + Space` to open Fuzzel. Start typing an application name, use the arrow keys to select it and press Enter. Desktop entries are used for installed applications. Use the application menu to open Fenrir Settings or this tutorial again."),
    ("Screenshots and recording", "screenshot print screen record video grim slurp wf-recorder", "## Capture the screen\n\n- `Print`: capture all displays and copy the image to the clipboard.\n- `Super + Shift + S`: select a region with Slurp, capture it with Grim and copy it.\n\nFor video capture, press `Super + Shift + F9` to start or stop a recording. Fenrir saves recordings under `~/Videos/Fenrir` and records nothing automatically."),
    ("Wallpapers", "wallpaper change rotation interval folder 5000 10000 20000 4k resolution", "## Wallpaper library\n\nWallpapers live under `~/Pictures/Wallpapers` by default. Fenrir validates files and counts only readable landscape images at least 2560×1440. It prefers 3840×2160 or higher.\n\nRotation is configured for every 15 minutes and uses all currently qualifying images. The default collection goal is 20,000 qualifying images. In Fenrir Doctor → Wallpaper Intelligence, you can choose a 5,000, 10,000 or 20,000-image goal. Rotation uses the qualifying images already present; it never waits for the goal, and the status is not marked complete until the selected count is reached. Use `fenrir-wallpaper status` to inspect the real count and `fenrir-wallpaper next` to select an image.\n\nUse Fenrir Settings → Wallpapers to change the folder and interval."),
    ("Themes and colors", "theme appearance color accent transparency blur Fimbulwinter Glass", "## Fimbulwinter Glass\n\nThe desktop uses a deep obsidian base, moderate compositor blur and frosted surfaces at 0.60 opacity (40% transparent) by default. Wallpaper-derived accent colors can synchronize Waybar, Kitty, Fuzzel, Mako, GTK and Hyprland borders.\n\nUse Fenrir Settings → Appearance to adjust opacity, blur and dynamic colors. Contrast and readable text take priority over decorative transparency."),
    ("Audio configuration", "audio pipewire qpwgraph easyeffects guitarix routing microphone", "## Audio\n\nPipeWire and WirePlumber provide the audio graph. Open **QPWgraph** to inspect connections and route interfaces, applications and plugins. Open **EasyEffects** to configure input/output processing. `wpctl status` lists devices and streams; `wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%+` raises the default output.\n\nBefore recording, verify your interface, sample rate, routing and latency in a real test session. Fenrir does not apply aggressive latency tuning automatically."),
    ("Gaming and performance", "gaming steam proton gamemode mangohud gamescope vulkan amd", "## Gaming\n\nSteam, Proton support, GameMode, MangoHud, Gamescope, 32-bit AMD Mesa/Vulkan libraries, Heroic, RPCS3 and Prism Launcher are included in the full profile.\n\nUse `gamemoderun %command%` or `mangohud %command%` in Steam launch options when useful. Verify the Vulkan stack with `vulkaninfo --summary`. Avoid running optional AI inference while gaming or recording when GPU/CPU headroom matters. Fenrir does not download game ROMs, console firmware or proprietary assets."),
    ("Fenrir Settings walkthrough", "settings customization display refresh rate keyboard startup gaming services power", "## Fenrir Settings\n\nThe Settings app groups controls into Appearance, Wallpapers, Display, Hyprland & Workspaces, Keybinds, Waybar, Audio, Startup applications, Gaming & Performance, Keyboard and Screen & Power.\n\nSettings are validated before writes, existing values are backed up under `~/.local/state/fenrir/settings-backups/`, and managed configuration files are updated atomically. Unsupported monitor modes are not forced. Use **Restore defaults** to reset Fenrir's managed settings."),
    ("Screen and power behavior", "idle screen blanking display power off lock suspend hibernate stay awake", "## Screen and power\n\nFenrir does not automatically blank the screen, power off displays, lock the session, suspend or hibernate due to inactivity. The keep-awake service blocks logind idle/sleep while enabled. Turning that inhibitor off does not add timers.\n\nManual locking is always available with `Super + L`. Use Fenrir Settings → Screen & Power to control the inhibitor; automatic idle lock and DPMS timers remain disabled by default."),
    ("Troubleshooting and recovery", "troubleshooting recovery black screen tty rollback logs backup config", "## Troubleshooting\n\n**Black screen or broken panel:** switch to a TTY with `Ctrl + Alt + F3`, log in and inspect `journalctl --user -b` and `journalctl -b`. You can disable user units with `systemctl --user disable --now fenrir-wallpaper.service fenrir-stay-awake.service`.\n\n**Hyprland config issue:** inspect `~/.config/hypr/hyprland.lua`, run `hyprctl reload` from a working session and use the TTY to restore a known-good backup.\n\n**Audio issue:** run `wpctl status`, restart `pipewire`/`wireplumber` user services and inspect QPWgraph connections.\n\n**Wallpaper issue:** run `fenrir-wallpaper status`, check file permissions and supported image dimensions.\n\nFenrir user-configuration backups are stored in `~/.local/state/fenrir/backups/` and Settings backups in `~/.local/state/fenrir/settings-backups/`. Restore only the files you intend to replace. The installer never formats or repartitions disks."),
]


class Welcome(Gtk.Application):
    def __init__(self, once: bool = False):
        super().__init__(application_id="org.fenrir.Welcome", flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.once = once

    def do_activate(self):
        if self.once and STATE.exists():
            self.quit(); return
        win = Gtk.ApplicationWindow(application=self)
        win.set_title("Welcome to Fenrir")
        win.set_default_size(1100, 760)
        win.connect("close-request", self.mark_seen)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        header = Gtk.HeaderBar()
        title = Gtk.Label(label="Welcome to Fenrir")
        title.add_css_class("title-2"); header.set_title_widget(title)
        root.append(header)
        layout = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        nav = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        nav.set_size_request(280, -1)
        nav.set_margin_top(18); nav.set_margin_start(16); nav.set_margin_end(16)
        search = Gtk.SearchEntry(placeholder_text="Search the tutorial…")
        nav.append(search)
        listing = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        listing.add_css_class("navigation-sidebar")
        nav.append(listing)
        layout.append(nav)
        layout.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        detail = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        detail.set_hexpand(True); detail.set_vexpand(True)
        detail.set_margin_top(22); detail.set_margin_start(26); detail.set_margin_end(26); detail.set_margin_bottom(24)
        text = Gtk.TextView(editable=False, cursor_visible=False, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        text.set_monospace(False)
        scroller = Gtk.ScrolledWindow(hexpand=True, vexpand=True, child=text)
        detail.append(scroller)
        layout.append(detail)
        root.append(layout)
        win.set_child(root)
        self.rows = []
        for title_text, keywords, body in SECTIONS:
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=title_text, xalign=0)
            label.set_margin_top(10); label.set_margin_bottom(10); label.set_margin_start(10)
            row.set_child(label)
            listing.append(row)
            self.rows.append((row, title_text, keywords.lower(), body))
        def choose(_list, row):
            if row is None: return
            selected = next(item for item in self.rows if item[0] is row)
            text.get_buffer().set_text(selected[3])
        listing.connect("row-selected", choose)
        listing.select_row(listing.get_row_at_index(0))
        def filter_rows(entry):
            query = entry.get_text().strip().lower()
            visible = []
            for row, title_text, keywords, body in self.rows:
                match = not query or query in title_text.lower() or query in keywords or query in body.lower()
                row.set_visible(match)
                if match: visible.append(row)
            if visible and listing.get_selected_row() not in visible:
                listing.select_row(visible[0])
        search.connect("search-changed", filter_rows)
        win.present()

    def mark_seen(self, *_):
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text("Fenrir first-login welcome completed\n", encoding="utf-8")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="show only until first completed welcome")
    args = parser.parse_args()
    return Welcome(args.once).run([sys.argv[0]])

if __name__ == "__main__":
    raise SystemExit(main())
