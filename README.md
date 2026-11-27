# Fenrir-Dots

**Version:** 0.18.0

Fenrir-Dots is the user-session desktop layer for Fenrir Desktop: Hyprland, Waybar, launcher, terminal, notifications, file manager, themes, wallpaper rotation, desktop services, Fenrir Settings and Fenrir Doctor.

## Design direction

The visual system is **Fimbulwinter**: deep obsidian surfaces, adaptive blue/red/purple/violet accents derived from the active wallpaper, restrained borders, readable typography and consistent design tokens.

A single theme engine generates matching tokens for Hyprland, Waybar, Kitty, GTK, Qt, Mako, Fuzzel, Starship and Fenrir applications. Wallpaper changes update the accent palette while preserving contrast and readable foreground colors.

## Glass mode

Glass mode is a user-toggleable appearance profile. Its default active-surface opacity is 60%, with compositor blur where supported. Fullscreen, game, media, lock and authentication surfaces remain opaque. The profile can be controlled with `fenrir-glass enable|disable|status`.

## Wallpaper integration

The public gallery is a distinct set of image-only repositories. The system installer fetches every active manifest-listed image, verifies file size and SHA-256, decodes and validates image format/resolution/palette, resumes interrupted transfers, and refuses to overwrite conflicting local files.

The public library is not the private Catalog. Local private assets are never published automatically.

## Gaming and audio

The deployment profile includes Steam/Proton, GameMode, MangoHud, Gamescope, RPCS3 and Heroic, plus PipeWire, EasyEffects, QPWGraph, QjackCtl, Guitarix, Calf and REAPER/ReaPack where supported by the official Arch repositories.

## Command-line contracts

- `fenrir-wallpaper next` applies a validated local wallpaper.
- `fenrir-wallpaper sync-public-plan` performs read-only library preflight.
- `fenrir-wallpaper sync-public` downloads and verifies the complete published gallery.
- `fenrir-theme apply PATH` derives and propagates the wallpaper palette.
- `fenrir-glass enable|disable|status` manages the reversible glass profile; enable accepts `--opacity`.

## Release policy

Canonical versions use three numeric components. Historical tags are never renumbered.
