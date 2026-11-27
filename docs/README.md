# Fenrir Dots documentation

Start here when navigating this repository.

## Architecture

- [Fenrir Dots README](../README.md) — product overview, installation relationship and user-facing features.
- [Fenrir Doctor guide](../apps/fenrir-doctor/README.md) — diagnostics, wallpaper intelligence, rights workflow, and the local service.
- [Wallpaper library integration](WALLPAPER-LIBRARY.md) — public multi-volume sync, private Catalog sync, directory layout, attribution, and troubleshooting.

## Source map

| Path | Responsibility |
|---|---|
| `bin/` | User-facing command-line entry points, including wallpaper rotation and library sync |
| `apps/fenrir-settings/` | GTK4 Control Center |
| `apps/fenrir-welcome/` | First-login guide and tutorials |
| `apps/fenrir-doctor/` | Local diagnostics and wallpaper intelligence dashboard |
| `config/` | Hyprland, Waybar, GTK, terminal, launcher, notifications and icon configuration |
| `applications/` | Desktop launchers |
| `systemd/user/` | User-session services |
| `tests/` | Unit and integration-contract tests |

## Where changes belong

- Desktop behavior, commands, UI, dotfiles, and user services belong here in **Fenrir-Dots**.
- System packages, system services, installation safety and deployment pins belong in **Fenrir-Arch**.
- Discovery, image intake, rights evidence, acceptance, curation and private Catalog synchronization belong in **Fenrir-Wallpaper-Catalog**.
- Publicly cleared image bytes and volume manifests belong in **Fenrir-Wallpapers** and its registered numbered volumes.

See the [Fenrir ecosystem project map](https://github.com/sunxsaturn/Fenrir-Arch/blob/main/docs/PROJECT-MAP.md) for the complete repository map and end-to-end data flow.
