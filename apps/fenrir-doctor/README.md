# Fenrir Doctor

Fenrir Doctor is the local desktop companion for Fenrir Desktop. It combines the former Sun AI local assistant with read-only system diagnostics, GitHub release tracking, safe backup restoration and rights-aware wallpaper library synchronization.

## Features

- Local Ollama chat, weather and private conversation history.
- Diagnostics for Arch Linux, Hyprland, Vulkan, PipeWire, NetworkManager, wallpaper services, local catalog readiness and home-disk capacity.
- GitHub latest-release checks for Fenrir-Arch, Fenrir-Dots and Fenrir-Wallpaper-Catalog.
- Reads the local installed-versions.json manifest written by Fenrir-Arch, with safe fallback for older installations.
- Interactive upgrade handoff to a terminal. The user reviews and confirms pacman -Syu; no silent privileged update occurs.
- Recovery from Fenrir-managed configuration backups. Existing files are snapshotted before restore.
- Local wallpaper synchronization through fenrir-catalog catalog library sync, with 5,000, 10,000 and 20,000 image targets.
- Full-profile resumable Openverse, Wikimedia Commons and SFW Wallhaven metadata campaigns (up to 100 queries and two pages per query per user-started run), with saved per-query cursors. Discovery never downloads or accepts images.
- Optional automatic discovery scheduler controlled in Wallpaper Intelligence: one sequential bounded slice per selected interval (1, 3, 6, 12 or 24 hours; six hours by default), persisted across restarts, with a 30-second scheduler poll and stop-on-error behavior.
- Completed campaigns automatically pause with a human-review status. Rights decisions, acquisition authorization, quarantine/downloads, explicit acceptance and desktop sync remain independent, user-controlled workflows. Pausing scheduling does not interrupt a provider slice already in progress.
- Dominant-pixel palette policy: yellow, orange and brown are excluded; red, purple, blue, white and black are preferred; green and neutral grey are allowed.
- A cached local wallpaper index reports qualifying files, excluded palettes and invalid images using the same quality/color rules as desktop sync.
- A shared cached palette index: yellow, orange and brown are excluded; red, purple, blue, white and black are preferred; green and neutral grey are allowed.

## Automatic discovery policy

The scheduler is disabled by default and must be explicitly enabled in Wallpaper Intelligence. Each slice is bounded to two queries and two pages per query, runs sequentially, and uses the Catalog's persisted cursor state. The default interval is six hours; one hour is the minimum supported interval. Commons scheduling requires a contact identifier. Scheduler state is stored with restrictive local file permissions and malformed or symlinked state fails closed. A campaign completion stops scheduling and requests human review; provider/catalog errors also stop scheduling rather than retrying aggressively.

## Privacy and safety

The HTTP service binds only to 127.0.0.1:8765. Ollama is restricted to the local API. Conversation history and settings remain under the current user's state/config directories. Legacy data from ~/.local/state/sun-ai and ~/.config/sun-ai is copied into the Fenrir Doctor locations on first launch; original files are retained.

Diagnostics are read-only. Upgrade is launched in a terminal and requires interactive confirmation. Recovery accepts only a Fenrir backup identifier and restores a fixed allowlist of user configuration paths, creating a rollback snapshot first.

Wallpaper sync copies only locally quarantined, SHA-256-verified, human-accepted and human-rights-approved assets with an approved license-policy decision and a dominant palette that passes Fenrir’s color policy. It does not contact providers, publish files or grant redistribution rights. Creator, source and license attribution is retained in fenrir-catalog-attribution.json.

## Run

Use the installed command:

    fenrir-doctor open
    fenrir-doctor status
    fenrir-doctor logs

Ollama starts on demand so it does not compete with gaming or audio production at login.
