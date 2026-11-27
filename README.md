# Fenrir Dots

**Version:** 0.17.0 · **Rebuild status:** foundation in progress

Fenrir Dots is the Hyprland desktop layer for Fenrir Arch. It owns the session, keybindings, status bar, launcher, terminal, notifications, theme engine, wallpaper rotation, Control Center and Fenrir Doctor presentation.

## Fimbulwinter design system

- Obsidian surfaces with blue, red, purple, violet and black wallpaper-derived accents.
- One theme token source feeds Kitty, Waybar, Fuzzel, GTK and supported Qt/Electron integrations.
- Frosted-glass mode is user-toggleable. Its surface background target is 80% opaque (20% transparent), with compositor blur where the application exposes a transparent surface.
- Wallpaper changes update accent colors without reducing text contrast.
- Yellow, brown, orange and pink dominant wallpapers are excluded; green is allowed.
- Glass mode is enabled by default; opacity is not applied to text or whole-window content.

## Desktop features

Hyprland Wayland session, SDDM login, GPU-aware AMD Mesa/RADV setup, Waybar, Fuzzel, Kitty, Mako, file manager, screenshots, media controls, gaming helpers, audio workstation integration, Fenrir Control Center and Fenrir Doctor.

## Wallpaper integration

The desktop consumes the public library registry and validated manifests. It must reject every SHA-256 in the private Catalog's legacy exclusion set, verify each transfer, preserve existing local files and never infer redistribution rights from a manifest.

This repository is under active rebuild. It is not yet an installable desktop release.
