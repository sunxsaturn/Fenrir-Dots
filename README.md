# Fenrir Dots

**Version:** 0.16.0

**Documentation:** [Documentation index](docs/README.md) · [Changelog](CHANGELOG.md) · [Wallpaper library sync](docs/WALLPAPER-LIBRARY.md) · [Fenrir Doctor](apps/fenrir-doctor/README.md) · [Project map](https://github.com/sunxsaturn/Fenrir-Arch/blob/main/docs/PROJECT-MAP.md) · [Version policy](https://github.com/sunxsaturn/Fenrir-Arch/blob/main/docs/VERSIONING.md)

Fenrir Dots is the desktop and user-session layer of **Fenrir Desktop**, an original Arch Linux + Hyprland environment. [Fenrir-Arch](https://github.com/sunxsaturn/Fenrir-Arch) owns the system installer, package integration and privileged setup. This repository owns the desktop configuration, user applications and session services.

## Install

Use the Fenrir-Arch installer. It checks out a pinned Fenrir-Dots commit and validates the complete required source set:

```bash
git clone --depth=1 https://github.com/sunxsaturn/Fenrir-Arch.git ~/Fenrir
cd ~/Fenrir
./install.sh
```

Do not use Fenrir-Dots as a standalone system installer. It expects the Arch packages and system integration provided by Fenrir-Arch.

Fenrir-Arch 1.0.0 pins this release by exact commit SHA and deploys it as part of the full system installation.

## What is included

### Desktop and appearance

- Hyprland 0.57+ with Lua configuration, monitor detection, generated workspace and keybinding modules.
- Waybar, Fuzzel, Kitty, Mako, GTK styling and the Fenrir-Obsidian icon theme.
- Fimbulwinter Glass: an obsidian foundation, moderate blur, frosted surfaces and wallpaper-derived dynamic accents.
- Wallpaper validation and rotation every 15 minutes, with palette synchronization.

### Settings and onboarding

- **Fenrir Settings:** GTK4 control center for appearance, display/scaling, wallpapers, Hyprland layout/workspaces, keybindings, Waybar, audio devices, startup applications, gaming tools, keyboard and session power behavior. Writes are validated, atomic and backed up.
- **Fenrir Welcome & Tutorial:** searchable first-login help for shortcuts, workspaces, screenshots, wallpapers, visual customization, audio, gaming, recovery and troubleshooting.

### Fenrir Doctor

Fenrir Doctor combines read-only system diagnostics, release tracking, configuration recovery and wallpaper intelligence. An optional local Ollama assistant provides chat and weather; the service starts on demand and does not download model weights automatically.

Wallpaper Library includes:

- Opt-in, resumable metadata discovery across Openverse, Wikimedia Commons, SFW Wallhaven and Cleveland Museum of Art Open Access.
- Eight visual profiles and a persisted round-robin queue of up to **32 source/profile combinations**.
- Provider-defined scheduling slices capped at **four API requests per turn**; pause on errors or when a campaign queue reaches the human-review boundary.
- A read-only provider/profile portfolio showing observed local inventory and recorded human-acceptance activity. It does not set a collection-size goal or infer a completion ETA.
- A read-only acquisition runway and launchers for the Catalog's loopback-only Rights & Acquisition Studio. Rights decisions, acquisition authorization, downloads, duplicate review, acceptance and sync remain separate operations.

Doctor is the desktop control surface; rights and acquisition policy remains in the private Catalog.

## Wallpaper library

Fenrir keeps two wallpaper ingestion paths separate.

### Public multi-volume library

The public library is hosted by [Fenrir-Wallpapers](https://github.com/sunxsaturn/Fenrir-Wallpapers). Population is closed at the existing 1,871 published images; all three registered volumes remain active for desktop synchronization.

**New installations download the complete public library as part of the single Fenrir-Arch command** (`git clone … && ./install.sh`). After deploying the pinned Dots source, the installer runs the registry-driven `fenrir-wallpaper sync-library` operation without a batch limit, checks that enough space exists, verifies every downloaded image and confirms that no manifest-listed image remains missing. There is no separate wallpaper download step.

For an already installed system or to resume/reconcile a later transfer, use the same command supplied by Fenrir Dots:

```bash
fenrir-wallpaper audit-library --json
fenrir-wallpaper sync-library --dry-run --json
fenrir-wallpaper sync-library
```

The sync validates all active manifests, deduplicates content by SHA-256, resumes interrupted transfers, checks image quality/palette, preserves public attribution and never overwrites or deletes existing wallpaper files. Use `--limit` only for an intentionally staged maintenance transfer; the system installer never uses it. See the [public library guide](docs/WALLPAPER-LIBRARY.md).

### Private Catalog collections

Sync one explicitly curated Catalog collection into the configured rotation directory:

```bash
fenrir-wallpaper sync-catalog --collection-id COLLECTION_ID
```

Sync copies only assets that have passed the Catalog's current rights, license, authorization, human-acceptance, integrity, resolution and palette checks. Collection membership alone does not grant permission. The private database and quarantine remain local and are never published by this command.

### Wallpaper Studio

Open **Wallpaper Studio** from Fenrir Settings → Wallpapers or run:

```bash
fenrir-wallpaper studio
```

The loopback-only workbench browses accepted Catalog assets, inspects rights and provenance, curates ordered collections, reviews duplicate candidates, and previews 16:9, 16:10, 21:9 and 32:9 display fits without modifying originals. Adding accepted assets can trigger the existing guarded Catalog-to-rotation sync; sync is additive and never deletes a previously staged wallpaper.

## Wallpaper quality policy

There is no image-count goal. Rotation uses all qualifying images already present in the selected directory. Qualifying images must be readable landscape files at least 2560×1440; 3840×2160 or higher is preferred.

The enforced dominant-palette policy excludes yellow, orange and brown; red, purple, blue, white and black are preferred; green and neutral grey are allowed. The desktop validates decoded image pixels rather than trusting titles or provider tags.

## Development checks

Run from the repository root:

```bash
python3 -m compileall -q bin apps scripts tests
python3 -m unittest discover -s tests -v
bash -n bin/fenrir-settings bin/fenrir-welcome bin/fenrir-monitor bin/fenrir-record bin/fenrir-doctor
node --check apps/fenrir-doctor/assets/app.js
```

No software license has been selected yet. Publishing the source does not grant redistribution rights to third-party applications, artwork or assets.
