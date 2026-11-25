# Fenrir Dots

Fenrir Dots is the visual and user-session layer of **Fenrir Desktop**, an original Arch Linux + Hyprland environment. The system installer lives in [Fenrir-Arch](https://github.com/sunxsaturn/Fenrir-Arch); this repository supplies the desktop configuration, applications and services.

## Installation

Use the single-command Arch installer, which clones Fenrir Dots automatically:

```bash
git clone --depth=1 https://github.com/sunxsaturn/Fenrir-Arch.git ~/Fenrir && cd ~/Fenrir && ./install.sh
```

Do not install this repository as a complete system installer. It expects Arch package and system integration from Fenrir-Arch.

## Components

- Hyprland 0.57+ Lua configuration, monitor detection and generated workspace/keybind modules
- Fenrir Settings GTK4 application with persistent, validated controls, atomic writes and backups
- Searchable, persistent Fenrir Welcome & Tutorial
- Fimbulwinter Glass: obsidian foundation, moderate blur, 60% frosted-surface opacity and wallpaper-derived dynamic accents
- Waybar, Kitty, Fuzzel, Mako, GTK and Fenrir-Obsidian icon theme
- Validated random wallpaper engine and palette synchronization
- Manual screen recording toggle (`Super+Shift+F9`), screenshots and clipboard workflow
- Fenrir Doctor local assistant, system diagnostics, GitHub release tracking, configuration recovery and rights-aware wallpaper intelligence; Ollama models remain opt-in
  - Supervised wallpaper metadata scheduler: sequential, resumable discovery slices (up to two queries and two pages per scheduled slice), conservative 1–24 hour cooldowns, safe pause on errors, and automatic stop at the human-review boundary; no automated downloads, rights decisions, acceptance or sync.
  - `fenrir-doctor` provides the integrated local UI; `fenrir-upgrade` fetches the latest tagged Fenrir-Arch release and starts the interactive installer.
  - Complete source map: [apps/fenrir-doctor/README.md](apps/fenrir-doctor/README.md) (server, web assets, CLI, user service, desktop entry, icon and tests are all versioned in this repository)
- Keep-awake session inhibitor; no automatic lock, display-off or idle-suspend timers. Manual lock remains `Super+L`.

## Wallpaper policy

Wallpapers are user-owned files under `~/Pictures/Wallpapers` by default. Qualifying images must be readable landscape images at least 2560×1440; 3840×2160 or higher is preferred. Rotation uses the currently acquired qualifying images every 15 minutes. The **5,000-image target is a real collection goal, not a rotation prerequisite**; status does not report it as met until 5,000 actual files pass validation.

No bulk image collection is bundled or fabricated. Do not download copyrighted images without permission. The separate Fenrir Wallpaper Catalog owns source discovery, rights review, acquisition authorization, deduplication and acceptance provenance. See [Fenrir-Arch's wallpaper-pack contract](https://github.com/sunxsaturn/Fenrir-Arch/blob/main/docs/WALLPAPER-PACK.md).

## Settings and tutorial

Open **Fenrir Settings** from the launcher to change appearance, wallpapers, display mode/scaling, Hyprland layout/workspaces, keybinds, Waybar, audio devices, startup applications, gaming tools, keyboard and session power policy. Unsupported display modes are left unchanged. Configuration writes are validated and backed up.

Open **Fenrir Welcome & Tutorial** to search first-login guidance, shortcuts, workspaces, captures, wallpapers, visual customization, audio, gaming, recovery and troubleshooting.

## Development checks

```bash
python3 -m compileall -q bin apps scripts tests
python3 -m unittest discover -s tests -v
bash -n bin/fenrir-settings bin/fenrir-welcome bin/fenrir-monitor bin/fenrir-record bin/fenrir-doctor
```

The software license has not yet been selected. Publication does not grant redistribution rights to third-party artwork, applications or assets.
