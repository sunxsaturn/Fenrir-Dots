# Fenrir Doctor

Fenrir Doctor is the local desktop companion for Fenrir Desktop. It combines the former Sun AI local assistant with read-only system diagnostics, GitHub release tracking, safe backup restoration and rights-aware wallpaper library synchronization.

## Features

- Local Ollama chat, weather and private conversation history.
- Diagnostics for Arch Linux, Hyprland, Vulkan, PipeWire, NetworkManager, wallpaper services, local catalog readiness and home-disk capacity.
- GitHub latest-release checks for Fenrir-Arch, Fenrir-Dots and Fenrir-Wallpaper-Catalog.
- Interactive upgrade handoff to a terminal. The user reviews and confirms pacman -Syu; no silent privileged update occurs.
- Recovery from Fenrir-managed configuration backups. Existing files are snapshotted before restore.
- Local wallpaper synchronization through fenrir-catalog catalog library sync, with 5,000, 10,000 and 20,000 image targets.

## Privacy and safety

The HTTP service binds only to 127.0.0.1:8765. Ollama is restricted to the local API. Conversation history and settings remain under the current user's state/config directories. Legacy data from ~/.local/state/sun-ai and ~/.config/sun-ai is copied into the Fenrir Doctor locations on first launch; original files are retained.

Diagnostics are read-only. Upgrade is launched in a terminal and requires interactive confirmation. Recovery accepts only a Fenrir backup identifier and restores a fixed allowlist of user configuration paths, creating a rollback snapshot first.

Wallpaper sync copies only locally quarantined, SHA-256-verified, human-accepted and human-rights-approved assets with an approved license-policy decision. It does not contact providers, publish files or grant redistribution rights. Creator, source and license attribution is retained in fenrir-catalog-attribution.json.

## Run

Use the installed command:

    fenrir-doctor open
    fenrir-doctor status
    fenrir-doctor logs

Ollama starts on demand so it does not compete with gaming or audio production at login.
