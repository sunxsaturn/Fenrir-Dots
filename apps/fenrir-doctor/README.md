# Fenrir Doctor

Fenrir Doctor is the local desktop companion for Fenrir Desktop. It combines the former Sun AI local assistant with read-only system diagnostics, GitHub release tracking, safe backup restoration and rights-aware wallpaper library synchronization.

## Features

- Local Ollama chat, weather and private conversation history.
- Diagnostics for Arch Linux, Hyprland, Vulkan, PipeWire, NetworkManager, wallpaper services, local catalog readiness and home-disk capacity.
- GitHub latest-release checks for Fenrir-Arch, Fenrir-Dots and Fenrir-Wallpaper-Catalog.
- Reads the local installed-versions.json manifest written by Fenrir-Arch, with safe fallback for older installations.
- Interactive upgrade handoff to a terminal. The user reviews and confirms pacman -Syu; no silent privileged update occurs.
- Launches the Catalog's loopback-only Rights & Acquisition Studio with the configured private quarantine root, enabling identity-verified transient quarantine previews without changing files or decisions.
- Recovery from Fenrir-managed configuration backups. Existing files are snapshotted before restore.
- Local wallpaper synchronization through fenrir-catalog after a bounded read-only sync-plan preflight, with a recommended default target of 20,000 images (5,000 and 10,000 remain selectable). Doctor blocks sync unless the Catalog preflight confirms an adequate, conflict-free plan; Catalog repeats per-file integrity and palette checks before each copy.
- Full-profile resumable Openverse, Wikimedia Commons, SFW Wallhaven and Cleveland Museum of Art CC0 metadata campaigns (up to 100 queries and two pages per query per user-started run), with saved per-query cursors. Discovery never downloads or accepts images.
- Automatic discovery modes controlled in Wallpaper Intelligence: continuous mode runs bounded, provider-budgeted slices back-to-back until the selected queue is exhausted; scheduled mode runs one slice every 1, 3, 6, 12 or 24 hours. Both modes persist cursors across restarts and stop safely on errors.
- A persisted round-robin queue across up to 32 unique source/profile combinations (four providers × eight profiles). Each unfinished combination has its own saved Catalog campaign ID and cursor, so the scheduler rotates after every slice and resumes that exact campaign on its next turn. Catalog budgets cap each turn at four provider API requests. Commons contact identifiers and campaign IDs remain private in local scheduler state.
- A read-only provider/profile portfolio dashboard with estimated API usage, campaign yield, quality-eligible accepted counts, a local-collection projection and a human-acceptance trend. ETA is withheld without enough history; missing attribution metadata switches the projection to a conservative local-only floor.
- A read-only campaign acquisition runway in Wallpaper Intelligence showing blocked candidates, assets ready for separate explicit authorization, currently authorized batch-ready assets, stale authorizations, unresolved transfers and quarantined assets awaiting duplicate review and human acceptance. The panel omits provider download URLs and cannot authorize or download assets.
- A sanitized rights-review queue overview and one-click launcher for the Catalog's loopback-only Rights & Acquisition Studio. The Studio provides evidence packets, independent reviewer assignments, immutable assignment events, explicit human rights decisions, disagreement reporting, per-asset acquisition-readiness assessments, separately confirmed append-only acquisition authorizations, read-only provider-specific batch preflight, verified quarantine previews, explicit pair-by-pair duplicate adjudication and separate human acceptance/rejection/deferral controls. Doctor itself remains read-only; the Studio's session-token and same-origin protections remain in force.
- Completed campaigns automatically pause with a human-review status. Rights decisions, acquisition authorization, quarantine/downloads, explicit acceptance and desktop sync remain independent, user-controlled workflows. Pausing scheduling does not interrupt a provider slice already in progress.
- Dominant-pixel palette policy: yellow, orange and brown are excluded; red, purple, blue, white and black are preferred; green and neutral grey are allowed. A shared cached local index applies the same rules to counting, diagnostics and desktop sync.

## Public multi-volume wallpaper library

Fenrir Doctor exposes the separately published GitHub wallpaper mirror under **Wallpapers → Public multi-volume library**. Run a read-only preview to inspect the active registry volumes, globally unique image count, already-present files, missing images and estimated transfer size. Starting a download is a separate explicit confirmation. Doctor keeps independent process status and a log for this operation.

This public mirror is not the private Catalog workflow. It does not read the Catalog database or quarantine, create rights decisions, authorize acquisition, approve publication or change Catalog acceptance. It only synchronizes already-committed public manifest assets through `fenrir-wallpaper sync-library`, preserving attribution in its own sidecar.

Fenrir Settings exposes the same preview and confirmation-gated command in its Wallpapers page. See the [complete public library guide](../../docs/WALLPAPER-LIBRARY.md).

## Automatic discovery policy

The scheduler is disabled by default and must be explicitly enabled in Wallpaper Intelligence. Select one or more of the four metadata sources (Openverse, Wikimedia Commons, SFW Wallhaven or Cleveland Museum of Art Open Access) and one or more of the eight visual profiles to build a finite queue of up to 32 unique combinations. Continuous mode immediately starts the next bounded turn after the previous provider slice finishes; scheduled mode preserves the interval-based cadence. Each unfinished source/profile combination receives one bounded provider-balanced turn before the queue rotates. Every entry has its own saved Catalog campaign ID and query cursor, so it resumes at that exact position on its next round. The Catalog defines the provider budgets (at most four API requests per turn): Openverse and SFW Wallhaven use two queries by two pages, while Commons uses one query by two pages because each result page expands into two API requests. The default mode is continuous, avoiding multi-hour waits between turns. Scheduled mode remains available with a one-hour minimum interval. Wikimedia Commons queue items require a contact identifier. Queue state is stored with restrictive local file permissions; legacy schema v1/v2/v3 state migrates safely and malformed or symlinked state fails closed. Pausing preserves all cursors. Exhausting the queue stops with a human-review status; provider/catalog errors stop scheduling rather than retrying aggressively.

## Privacy and safety

The HTTP service binds only to 127.0.0.1:8765. Ollama is restricted to the local API. Conversation history and settings remain under the current user's state/config directories. The portfolio endpoint reads only the local Catalog database and a non-symlinked attribution sidecar; its estimates never authorize acquisition, rights decisions or synchronization. Legacy data from ~/.local/state/sun-ai and ~/.config/sun-ai is copied into the Fenrir Doctor locations on first launch; original files are retained.

Diagnostics and the Doctor rights-review overview are read-only. The Rights & Acquisition Studio runs as a separate loopback-only Catalog service with a per-session secret token; write operations require same-origin requests and that token. Explicit per-asset acquisition authorization additionally requires a separate confirmation and rechecks all current evidence transactionally. The batch preflight only revalidates current authorizations and provider consistency; it creates no batch and starts no transfer. Duplicate reviews append only human pair decisions from current fingerprint candidates; they do not merge or modify assets. Human acceptance remains a separate explicit step. Authorization never starts a download. Doctor reuses an already-running board and stops its child process during orderly shutdown. Upgrade is launched in a terminal and requires interactive confirmation. Recovery accepts only a Fenrir backup identifier and restores a fixed allowlist of user configuration paths, creating a rollback snapshot first.

Wallpaper sync copies only locally quarantined, SHA-256-verified, human-accepted and human-rights-approved assets with an approved license-policy decision and a dominant palette that passes Fenrir’s color policy. It does not contact providers, publish files or grant redistribution rights. Creator, source and license attribution is retained in fenrir-catalog-attribution.json.

## Run

Use the installed command:

    fenrir-doctor open
    fenrir-doctor status
    fenrir-doctor logs

Ollama starts on demand so it does not compete with gaming or audio production at login.
