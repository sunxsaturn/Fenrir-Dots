# Fenrir Desktop — Welcome and searchable tutorial

Fenrir is a keyboard-first Hyprland desktop. Open the application launcher with **Super + Space** and search for Fenrir Settings whenever you need to customize the session.

## Workspaces and windows

- **Super + 1…0** switches workspaces 1–10.
- **Super + Shift + 1…0** moves the focused window to a workspace.
- **Super + Arrow keys** moves focus.
- **Super + Q** closes a window; **Super + F** toggles fullscreen.
- **Super + mouse drag** moves or resizes floating windows.

## Launching applications

Press **Super + Space**, type an application name and press Enter. **Super + Return** opens Kitty. **Super + E** opens Thunar. **Super + B** opens Firefox Nightly. **Super + A** opens Sun AI when the optional Sun AI component is installed.

## Screenshots and screen recording

Press **Print** to capture the full screen. Press **Super + Shift + S** to select a region. Use OBS Studio or another Wayland screen recorder for recordings; recording shortcuts are configurable in Hyprland.

## Wallpaper and themes

Fenrir Wallpaper scans the configured directory, validates landscape orientation and minimum 2560×1440 resolution, and only enables timed random rotation when at least 5,000 qualifying files exist. It never fills the library with unverified or copyrighted downloads. The active wallpaper feeds dynamic accents for Waybar, Kitty, Fuzzel, Mako and GTK.

## Audio

PipeWire and WirePlumber are the audio foundation. Use QPWgraph to connect devices and applications, EasyEffects for signal processing and pavucontrol for volume/device selection.

## Gaming and performance

Use the installed Steam/Proton stack and official Flatpak clients. **GameMode launch option:** `gamemoderun %command%`. MangoHud configuration is available in Fenrir Settings. Gamescope can be used as a per-game wrapper when needed.

## Display and power

Fenrir inspects Hyprland's advertised monitor modes before requesting 2560×1440@155 Hz. If unavailable, it keeps a supported current or preferred mode. The default session does not blank the display, power it off or auto-lock while idle. Manual locking is available with **Super + L**.

## Recovery and troubleshooting

- Run `hyprctl reload` after hand-editing Hyprland configuration.
- Check user services with `systemctl --user --failed`.
- Inspect session logs with `journalctl --user -b`.
- Fenrir Settings creates timestamped `settings.toml.backup-*` files before each update.
- Installer-managed configuration backups live under `~/.local/state/fenrir/backups/`.
- Do not delete a backup until the corresponding configuration has been verified.
