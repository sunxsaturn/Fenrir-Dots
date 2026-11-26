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
- Explicit, collection-scoped Fenrir Catalog synchronization into the configured wallpaper directory, with integrity/rights checks retained and rotation index refresh
- Manual screen recording toggle (`Super+Shift+F9`), screenshots and clipboard workflow
- Fenrir Doctor local assistant, system diagnostics, GitHub release tracking, configuration recovery and rights-aware wallpaper intelligence; Ollama models remain opt-in
  - Cleveland Museum of Art Open Access discovery is included in the supervised scheduler; only individually marked CC0 artworks with qualifying landscape images are kept in metadata discovery.
  - Supervised provider-balanced wallpaper metadata scheduler: continuous or interval-based round-robin slices across up to 32 source/profile combinations, independent resumable campaign cursors, and Catalog-defined four-request budgets per turn; safe pause on errors and an explicit human-review boundary.
  - Read-only collection portfolio dashboard: provider/profile yield, accepted quality-eligible inventory, local collection projection and human-acceptance trend; no guessed ETA without sufficient history.
  - `fenrir-doctor` provides the integrated local UI; `fenrir-upgrade` fetches the latest tagged Fenrir-Arch release and starts the interactive installer.
  - Complete source map: [apps/fenrir-doctor/README.md](apps/fenrir-doctor/README.md) (server, web assets, CLI, user service, desktop entry, icon and tests are all versioned in this repository)
- Keep-awake session inhibitor; no automatic lock, display-off or idle-suspend timers. Manual lock remains `Super+L`.

## Wallpaper policy

Wallpapers are user-owned files under `~/Pictures/Wallpapers` by default. Qualifying images must be readable landscape images at least 2560×1440; 3840×2160 or higher is preferred. Rotation uses the currently acquired qualifying images every 15 minutes. The **20,000-image target is the recommended collection goal, not a rotation prerequisite**; status does not report it as met until 20,000 actual files pass validation.

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


## Sync a curated Catalog collection into wallpaper rotation

Fenrir Desktop can stage one explicitly curated collection from the private
Fenrir Wallpaper Catalog into the wallpaper directory configured in
`~/.config/fenrir/settings.toml`:

    fenrir-wallpaper sync-catalog --collection-id COLLECTION_ID

The command uses the installed `fenrir-catalog` companion and the default
private database/quarantine paths under
`~/.local/share/fenrir/catalog`. Optional `--database` and
`--quarantine-root` arguments support an explicitly selected local Catalog.
Use `--target-count 5000|10000|20000` to choose the destination target; the
default is 20000. The Catalog command only copies assets which are already
human-accepted, rights-approved, license-approved, sufficiently high
resolution, palette-eligible, and verified against quarantine SHA-256/size
evidence. Collection membership alone never grants rights approval or
acceptance.

The wallpaper index is refreshed after a successful sync. The normal Fenrir
rotation service picks up new qualifying files on its next cycle; the sync
command does not switch the active wallpaper immediately. The destination
must be a safe local directory outside `/mnt/storage`.


## Fenrir Wallpaper Studio

Launch the loopback-only visual workbench from the terminal with `fenrir-wallpaper studio`, or use **Open Wallpaper Studio** in Fenrir Settings → Wallpapers. The Studio browses accepted Catalog assets, inspects rights/provenance, builds ordered collections, reviews possible duplicates and previews 16:9, 16:10, 21:9 and 32:9 scaling without modifying source images.

Adding an accepted image or batch to a collection automatically stages the updated collection through the existing rights- and integrity-checked Catalog sync and refreshes the wallpaper rotation index. New qualifying images become eligible immediately for the next scheduled or manual wallpaper change; the active wallpaper is not forcibly replaced. Existing collections also have a manual sync control. Removal from a collection does not delete previously staged user-owned wallpaper files.

## GitHub wallpaper library

The public wallpaper files are hosted separately at [sunxsaturn/Fenrir-Wallpapers](https://github.com/sunxsaturn/Fenrir-Wallpapers), inside its `Fenrir Wallpapers/` directory. Clone it locally:

```bash
git clone --depth=1 https://github.com/sunxsaturn/Fenrir-Wallpapers.git ~/Pictures/Fenrir-Wallpapers
```

To use that collection for rotation, set the existing `wallpaper.directory` value in `~/.config/fenrir/settings.toml` to `~/Pictures/Fenrir-Wallpapers/Fenrir Wallpapers`. Pull the repository periodically to receive new committed images. Fenrir's normal image validation and rotation rules still apply.

The GitHub mirror contains only assets with separate public-redistribution and provider-terms clearance. The private Catalog remains the source of truth for discovery, evidence, acquisition, validation and human acceptance; local Catalog acceptance alone does not authorize publication.

