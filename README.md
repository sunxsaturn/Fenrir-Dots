# Fenrir Dots

Original **Fenrir Desktop** Hyprland configuration, visual identity, wallpaper engine, dynamic color system, user services and Sun AI application. This repository is deployed by [Fenrir-Arch](https://github.com/sunxsaturn/Fenrir-Arch).

## Design

- Hyprland Lua configuration with monitor and Fimbulwinter Glass modules
- Obsidian-black base, moderate blur and 60% frosted-surface opacity
- Wallpaper-derived accent colors shared by Waybar, Kitty, Fuzzel, Mako, GTK and live Hyprland borders
- Original Fenrir-Obsidian icon theme
- Random wallpaper rotation every 15 minutes
- Rotation stays paused until at least 5,000 valid landscape wallpapers (minimum 2560×1440; 3840×2160 preferred) are available
- Sun AI local dashboard and on-demand Ollama integration

## Installation

Use the full system installer; it clones this repository automatically:

```bash
git clone --depth=1 https://github.com/sunxsaturn/Fenrir-Arch.git ~/Fenrir && cd ~/Fenrir && ./install.sh
```

This repository alone is not a complete Arch installer. It expects the package and system integration layer from Fenrir-Arch.

## Manual wallpaper commands

```bash
fenrir-wallpaper status
fenrir-wallpaper next
```

Wallpapers are user-owned files under `~/Pictures/Wallpapers`; no copyrighted or unlicensed image corpus is committed here. Read Fenrir-Arch's [wallpaper-pack contract](https://github.com/sunxsaturn/Fenrir-Arch/blob/main/docs/WALLPAPER-PACK.md) and the separate Fenrir Wallpaper Catalog source policy before preparing a production pack.

## Tests

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q bin apps/sun-ai scripts tests
```

The software license has not yet been selected.
