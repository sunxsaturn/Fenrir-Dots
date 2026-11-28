# Fenrir-Dots

**Version:** 2.0.1

Fenrir-Dots is the user-session desktop layer for Fenrir Desktop: Hyprland, an original Quickshell/Qt Quick/QML shell, themes, wallpaper rotation, desktop services, Fenrir Settings and Fenrir Doctor.

## Native shell

Fenrir launches its own Quickshell configuration from `~/.config/quickshell`. The shell includes a multi-monitor top panel, Hyprland workspace controls, app dock, and a native searchable application launcher with XDG categories and favorites, plus a system center for media, PipeWire audio, tray icons, Wi-Fi, Bluetooth, open windows and notification history. It is not based on a preconfigured third-party shell. The shell source is in `quickshell/fenrir/shell.qml`; see [Shell implementation](docs/SHELL.md) for the implemented surface and remaining work.

## Design direction

The visual system is **Fimbulwinter**: deep obsidian surfaces, adaptive blue/red/purple/violet accents derived from the active wallpaper, restrained borders, readable typography and consistent design tokens.

A single theme engine generates matching tokens for Hyprland, Waybar, Kitty, GTK, Qt, Mako compatibility styling, Fuzzel, Starship and Fenrir applications. Wallpaper changes update the accent palette while preserving contrast and readable foreground colors.

## Glass mode

Glass mode is a user-toggleable appearance profile. Its default active-surface opacity is 60%, with compositor blur where supported. Fullscreen, game, media, lock and authentication surfaces remain opaque. The profile can be controlled with `fenrir-glass enable|disable|status`.

## Wallpaper integration

The public gallery is a distinct set of image-only repositories. The system installer fetches every active manifest-listed image, verifies file size and SHA-256, decodes and validates image format/resolution/palette, resumes interrupted transfers, and refuses to overwrite conflicting local files.

The public library is not the private Catalog. Local private assets are never published automatically.

## Gaming and audio

The deployment profile includes Steam/Proton, GameMode, MangoHud, Gamescope, RPCS3 and Heroic, plus PipeWire, EasyEffects, QPWGraph, QjackCtl, Guitarix, Calf and REAPER/ReaPack where supported by the official Arch repositories.

## Native application launcher

Super+Space opens Fenrir's own searchable Quickshell launcher. It indexes visible XDG desktop entries, filters by name, description and category, and stores favorites in the user's private state directory. Launches use `gtk-launch` with the selected desktop ID; desktop-entry `Exec` text is never evaluated by the indexer. Super+Alt+Space retains Fuzzel as a fallback.

## Native shell services

Super+Space opens Fenrir's own QML application launcher. It indexes visible XDG desktop entries, launches by desktop ID through `gtk-launch`, and stores favorites in the user state directory.

Quickshell provides the system tray, MPRIS, notifications, PipeWire audio, NetworkManager Wi-Fi and BlueZ Bluetooth integrations. It also watches DWTE's validated `theme.json` tokens and updates the shell palette live, with a safe obsidian fallback. Mako is not launched alongside the native notification server.

## Command-line contracts

- `fenrir-wallpaper next` applies a validated local wallpaper.
- `fenrir-wallpaper sync-public-plan` performs read-only library preflight.
- `fenrir-wallpaper sync-public` downloads and verifies the complete published gallery.
- `fenrir-theme apply PATH` derives and propagates the wallpaper palette.
- `fenrir-glass enable|disable|status` manages the reversible glass profile; enable accepts `--opacity`.

## Release policy

Canonical versions use three single-digit decimal components; when a component reaches ten, carry into the component to its left and reset the overflowing component to zero (for example, 0.9 → 1.0 and 0.0.9 → 0.1.0). The current desktop version normalizes 0.20.0 to 2.0.0. Historical Git tags remain immutable; all current metadata, pins and future releases use normalized versions.
