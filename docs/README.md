# Fenrir Dots documentation

Fenrir Dots is the desktop and user-session layer of Fenrir Desktop. Use this page to find the right guide by task.

## Start here

- [Project overview](../README.md) — components, installation relationship and main desktop features.
- [Fenrir Doctor](../apps/fenrir-doctor/README.md) — diagnostics, wallpaper intelligence, campaign scheduler, rights-review hand-off and the local service.
- [Complete Fenrir ecosystem map](https://github.com/sunxsaturn/Fenrir-Arch/blob/main/docs/PROJECT-MAP.md) — repository responsibilities, data flow and compatibility pins.

## Wallpapers

- [Public wallpaper library](WALLPAPER-LIBRARY.md) — registry-driven multi-volume sync, dry-run, confirmation, integrity checks and attribution.
- [Private Catalog collections](../README.md#sync-a-curated-catalog-collection-into-wallpaper-rotation) — accepted, curated collections copied from the private Catalog.
- [Fenrir Wallpaper Catalog discovery and rights policy](https://github.com/sunxsaturn/Fenrir-Wallpaper-Catalog/blob/main/docs/README.md) — discovery, licensing, acquisition, duplicate review and acceptance.

These are separate workflows: the public mirror contains separately approved public assets; the private Catalog holds the user's metadata, rights evidence, quarantine and accepted collections.

## Source map

| Path | Responsibility |
|---|---|
| `bin/` | User-facing CLI entry points, wallpaper rotation and sync commands |
| `apps/fenrir-settings/` | GTK4 Control Center |
| `apps/fenrir-welcome/` | First-login guide and tutorials |
| `apps/fenrir-doctor/` | Diagnostics, release tracking and wallpaper intelligence |
| `config/` | Hyprland, Waybar, GTK, terminal, launcher, notifications and icon configuration |
| `applications/` | Desktop launchers |
| `systemd/user/` | User-session services |
| `tests/` | Unit and integration-contract tests |

## Where changes belong

- Desktop behavior, commands, UI, dotfiles and user services belong in **Fenrir-Dots**.
- System packages, system services, installation safety and exact deployment pins belong in **Fenrir-Arch**.
- Provider discovery, metadata, rights evidence, acquisition, quarantine, duplicate review and acceptance belong in the private **Fenrir-Wallpaper-Catalog**.
- Publicly cleared image bytes, attribution manifests, volume registry and publication tooling belong in **Fenrir-Wallpapers** and its numbered volumes.

See the [versioning policy](https://github.com/sunxsaturn/Fenrir-Arch/blob/main/docs/VERSIONING.md) for independent monotonic component versions and exact-SHA release pinning.
