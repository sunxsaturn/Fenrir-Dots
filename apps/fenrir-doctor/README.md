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
- A persisted, finite round-robin queue across up to 18 unique source/profile combinations. The queue rotates selected providers within each profile; pause/resume preserves progress. Commons contact identifiers stay in the private scheduler state and are not returned by the status API.
- A read-only campaign acquisition runway in Wallpaper Intelligence showing blocked candidates, assets ready for separate explicit authorization, currently authorized batch-ready assets, stale authorizations, unresolved transfers and quarantined assets awaiting duplicate review and human acceptance. The panel omits provider download URLs and cannot authorize or download assets.
- A sanitized rights-review queue overview and one-click launcher for the Catalog's loopback-only Rights & Acquisition Studio. The Studio provides evidence packets, independent reviewer assignments, immutable assignment events, explicit human rights decisions, disagreement reporting, per-asset acquisition-readiness assessments and separately confirmed append-only acquisition authorizations. Doctor itself remains read-only; the Studio's session-token and same-origin protections remain in force.
- Completed campaigns automatically pause with a human-review status. Rights decisions, acquisition authorization, quarantine/downloads, explicit acceptance and desktop sync remain independent, user-controlled workflows. Pausing scheduling does not interrupt a provider slice already in progress.
- Dominant-pixel palette policy: yellow, orange and brown are excluded; red, purple, blue, white and black are preferred; green and neutral grey are allowed.
- A cached local wallpaper index reports qualifying files, excluded palettes and invalid images using the same quality/color rules as desktop sync.
- A shared cached palette index: yellow, orange and brown are excluded; red, purple, blue, white and black are preferred; green and neutral grey are allowed.

## Automatic discovery policy

The scheduler is disabled by default and must be explicitly enabled in Wallpaper Intelligence. Select one or more of the three metadata sources and one or more of the six visual profiles to build a finite queue of up to 18 unique combinations. The queue rotates providers for each selected profile before moving to the next profile. Each campaign advances in bounded slices of two queries and two pages per query and uses the Catalog's persisted cursor state; the next queued campaign starts only after completion. The default interval is six hours; one hour is the minimum supported interval. Wikimedia Commons queue items require a contact identifier. Queue state (including the active position) is stored with restrictive local file permissions; legacy schema v1 state migrates safely and malformed or symlinked state fails closed. Pausing preserves the queue, and resuming skips campaigns already completed while paused. Exhausting the queue stops with a human-review status; provider/catalog errors stop scheduling rather than retrying aggressively.

## Privacy and safety

The HTTP service binds only to 127.0.0.1:8765. Ollama is restricted to the local API. Conversation history and settings remain under the current user's state/config directories. Legacy data from ~/.local/state/sun-ai and ~/.config/sun-ai is copied into the Fenrir Doctor locations on first launch; original files are retained.

Diagnostics and the Doctor rights-review overview are read-only. The Rights & Acquisition Studio runs as a separate loopback-only Catalog service with a per-session secret token; write operations require same-origin requests and that token. Explicit per-asset acquisition authorization additionally requires a separate confirmation and rechecks all current evidence transactionally. Authorization never starts a download. Doctor reuses an already-running board and stops its child process during orderly shutdown. Upgrade is launched in a terminal and requires interactive confirmation. Recovery accepts only a Fenrir backup identifier and restores a fixed allowlist of user configuration paths, creating a rollback snapshot first.

Wallpaper sync copies only locally quarantined, SHA-256-verified, human-accepted and human-rights-approved assets with an approved license-policy decision and a dominant palette that passes Fenrir’s color policy. It does not contact providers, publish files or grant redistribution rights. Creator, source and license attribution is retained in fenrir-catalog-attribution.json.

## Run

Use the installed command:

    fenrir-doctor open
    fenrir-doctor status
    fenrir-doctor logs

Ollama starts on demand so it does not compete with gaming or audio production at login.
