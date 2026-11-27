# Fenrir native Quickshell interface

Fenrir owns its shell UI. Quickshell is the Qt Quick/QML runtime and Wayland integration toolkit; Fenrir supplies the QML interface and its visual identity.

## Runtime and deployment

- Runtime: official Arch Linux `quickshell` package (0.3.2 series at this release).
- Config entry: `~/.config/quickshell/<managed-config>/shell.qml`.
- Startup: Hyprland's `hyprland.start` event launches `quickshell --config <managed-config>`.
- Multi-monitor: the top panel and dock use Quickshell `Variants` over `Quickshell.screens`.
- The installer preserves pre-existing Quickshell config files and selects a separate managed config name rather than replacing user content.

## First shell increment (0.18.0)

- Fimbulwinter obsidian top panel with live clock.
- Workspace switching using fixed Hyprland dispatcher arguments.
- Bottom app dock for Fuzzel, Kitty, Thunar, Firefox, Spotify and QPWGraph.
- Quick control-center window.
- Norse Cinematic profile applies 60% glass; Norse Performance disables compositor glass.
- Quick actions for next wallpaper and Fenrir Doctor.
- The top-panel and dock layer namespaces receive the same compositor blur treatment as other Fenrir surfaces.

The QML code does not evaluate user-provided strings or pass dynamic free-form text to a shell. Application and dispatcher invocations use fixed argument arrays.

## Deliberate implementation boundary

This is the shell foundation, not the complete blueprint UI. Notifications still use Mako as a compatibility backend. The first increment does not yet include the full notification history, task switcher, media center, system tray browser, audio mixer, network/BlueZ menus, full device profile panel, lockscreen or PAM-backed greeter. Those features require their own integration and runtime acceptance tests before being called complete.

The shell has source-level contract tests. It still requires runtime testing on a clean Arch/Hyprland 0.57+ session, including hot-plugging monitors and checking that all panels exit cleanly.
