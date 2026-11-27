# Changelog

## 0.15.0 — 2026-11-27

- Removed fixed wallpaper-count goals from rotation, Settings, Doctor, Catalog synchronization and portfolio reporting.
- Local Catalog sync now inspects all accepted metadata pages during bounded read-only preflight and syncs every eligible accepted asset without a quota.
- Added a read-only public-library audit covering manifest uniqueness, category distribution, dimensions, source/attribution/license metadata, palette declarations and GitHub repository storage headroom.
- Closed public wallpaper population while keeping all existing volumes active for desktop synchronization.
- Updated Doctor UI, Settings, CLI and task documentation to report observed inventory rather than target progress or ETA.


Notable changes for this repository. See the [project map](https://github.com/sunxsaturn/Fenrir-Arch/blob/main/docs/PROJECT-MAP.md) for ecosystem responsibilities and compatibility pins.

## 0.14.2 — 2026-11-27

- Reorganized the project README and documentation index into task-oriented topics.
- Clarified the 32-combination discovery queue and four-request per-turn provider budget.
- Described public-library sync, private Catalog sync and public redistribution as separate workflows.
- Replaced the legacy “Sun AI” product description with Fenrir Doctor and documented on-demand Ollama behavior.
