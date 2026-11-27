# Fenrir-Dots

Fenrir-Dots is the user-session desktop layer for Fenrir Desktop: Hyprland, Waybar, launcher, terminal, notifications, file manager, themes, wallpaper rotation, desktop services, Fenrir Settings and Fenrir Doctor.

## Design direction

The visual system is **Fimbulwinter**: deep obsidian surfaces, adaptive blue/red/purple/violet accents derived from the active wallpaper, restrained borders, readable typography and consistent design tokens.

A single theme engine must generate matching tokens for Hyprland, Waybar, Kitty, GTK, Qt, supported Electron apps and Fenrir applications. Wallpaper changes update the accent palette while preserving contrast and readable foreground colors.

## Glass mode

Glass mode is a user-toggleable appearance profile. Its target surface opacity is 80%, with compositor blur where supported. The default profile must remain readable and performant.

A compositor can blur/translucently composite compatible surfaces, but cannot force every third-party application to implement native frosted-glass controls. Unsupported apps must retain readable opaque surfaces instead of receiving destructive whole-window transparency.

## Wallpaper integration

The public gallery is a distinct set of image-only repositories. The system installer must fetch every active manifest-listed image, verify file size and SHA-256, decode and validate image format/resolution/palette, resume interrupted transfers, and refuse to overwrite conflicting local files.

The public library is not the private Catalog. Local private assets must never be published automatically.

## Gaming and audio

The target profile includes Steam/Proton, GameMode, MangoHud, Gamescope, RPCS3 and Heroic, plus PipeWire, EasyEffects, QPWGraph, Guitarix, Calf and REAPER/ReaPack where package trust and licensing permit.

## Release policy

Canonical versions use three numeric components. Historical tags are never renumbered. The next implementation release must advance beyond v0.16.0.
