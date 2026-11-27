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

## System center increment (0.19.0)

The native system center now integrates Quickshell's own service APIs:

- System tray item discovery, icon display and primary/secondary activation.
- MPRIS player discovery with previous, play/pause and next transport controls.
- PipeWire default output volume and mute, plus default input mute, using bound audio nodes.
- NetworkManager Wi-Fi power toggle and connection-state summary.
- BlueZ adapter power toggle and adapter state summary.
- Open-window switcher that focuses the selected Hyprland toplevel through the native dispatcher API.
- A tracked notification center with reload retention, dismiss and clear-all actions. Quickshell owns the desktop notification service; the installer removes only Fenrir's old Mako autostart entry to prevent competing notification servers.

The settings window groups these controls under Fimbulwinter styling. Network credential entry remains in NetworkManager's own connection editor; the shell does not handle or store Wi-Fi passwords.

## Live DWTE palette bridge (0.19.1)

The shell reads the wallpaper engine's semantic token document at
`~/.config/fenrir/theme/theme.json` using Quickshell's `FileView`. The file watcher reloads
the document when DWTE publishes a new palette; the root palette property then updates
panel, dock, workspace indicators, control center, media rows and notification surfaces
without restarting Quickshell.

Only the validated six-digit semantic colors are accepted. A malformed, missing or
unreadable token file leaves the previous palette in place; a clean start without a
generated theme uses the bundled obsidian/violet fallback. Glass opacity remains a
separate profile setting and the base background always stays dark.

## Native application launcher (0.20.0)

Super+Space invokes the shell's Quickshell IPC handler to toggle a Fenrir-owned QML launcher. It indexes visible XDG `.desktop` entries through `fenrir-applications`, supports name/description search, XDG category filters and persistent favorites, and launches selected entries using a fixed `gtk-launch` argument plus the desktop ID. The indexer never executes or evaluates a desktop entry's `Exec` string. A Fuzzel shortcut remains available as a fallback with Super+Alt+Space.

## Native application launcher (0.20.0)

Super+Space invokes the `fenrir` Quickshell IPC handler to toggle a Fenrir-owned QML launcher. It indexes visible XDG `.desktop` entries through `fenrir-applications`, supports name/description search, XDG category filters and persistent favorites, and launches selected entries through a fixed `gtk-launch` argument plus the desktop ID. The indexer never executes or evaluates the desktop entry's `Exec` string. A Fuzzel fallback remains available with Super+Alt+Space.

## Remaining acceptance boundary

This increment does not yet include a PAM-backed lockscreen/greeter, a full power profile/device inventory surface, an advanced Bluetooth pairing workflow, tray DBus submenu rendering, notification action buttons/inline replies, or per-application audio routing. These are explicitly not represented as complete features.

Source-level contracts run in CI. The desktop still requires runtime testing on a clean Arch/Hyprland 0.57+ session, especially PipeWire device hot-plug, Bluetooth adapter changes, tray menus, notification ownership, multi-monitor changes and Quickshell reload behavior.
