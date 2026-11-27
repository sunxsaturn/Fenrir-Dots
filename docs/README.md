# Fenrir Dots documentation

Fenrir Dots owns the desktop configuration, user-facing tools and session services. Fenrir-Arch owns system installation and privileged integration; the private Wallpaper Catalog owns source discovery, rights evidence, acquisition and acceptance.

## Start by task

| I want to… | Read |
|---|---|
| Understand the desktop and its components | [Project overview](../README.md) |
| Install or update Fenrir Desktop | [Fenrir-Arch installer](https://github.com/sunxsaturn/Fenrir-Arch#readme) |
| Configure monitors, appearance, shortcuts or startup apps | Open Fenrir Settings; see the [Settings source](../apps/fenrir-settings/) |
| Learn the desktop and keybindings | Open Fenrir Welcome & Tutorial; see the [Welcome source](../apps/fenrir-welcome/) |
| Diagnose the system or manage wallpaper intelligence | [Fenrir Doctor guide](../apps/fenrir-doctor/README.md) |
| Install and synchronize the complete public wallpaper library | [Public library guide](WALLPAPER-LIBRARY.md) — called automatically by the one-command Fenrir-Arch installer |
| Understand private Catalog collection sync | See [Catalog integration](https://github.com/sunxsaturn/Fenrir-Wallpaper-Catalog/blob/main/docs/INTEGRATION.md) and the [desktop sync command](../README.md#private-catalog-collections) |
| Understand version pins and releases | [Fenrir version policy](https://github.com/sunxsaturn/Fenrir-Arch/blob/main/docs/VERSIONING.md) |

## Source map

| Path | Responsibility |
|---|---|
| `bin/` | User commands for settings, welcome, Doctor, wallpaper, capture, theme and upgrades |
| `apps/fenrir-settings/` | GTK4 control center and validated settings logic |
| `apps/fenrir-welcome/` | First-login guide and tutorials |
| `apps/fenrir-doctor/` | Local diagnostics, release tracking and wallpaper intelligence |
| `config/` | Hyprland, Waybar, GTK, terminal, launcher, notification and icon configuration |
| `applications/` | Desktop launchers |
| `systemd/user/` | User-session services |
| `scripts/` | Configuration and migration helpers |
| `tests/` | Unit, integration-contract and regression tests |

## Boundaries

- Keep system packages, privileged operations and installer safety in Fenrir-Arch.
- Keep desktop presentation and user-session behavior here.
- Keep provider policies, rights records, acquisition and Catalog lifecycle decisions in Fenrir-Wallpaper-Catalog.
- Treat public-library sync and private Catalog sync as distinct workflows.
- Do not put private databases, quarantine assets, credentials or unapproved artwork in this repository.

## Development

Run the compile, unit-test, shell-syntax and Doctor JavaScript checks listed in the [project README](../README.md#development-checks). Changes to settings, recovery, sync or scheduler behavior should include focused regression tests.
