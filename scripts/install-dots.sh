#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
HOME_DIR="${HOME:?HOME is not set}"
die() { printf '[Fenrir Dots] ERROR: %s\n' "$*" >&2; exit 1; }

[[ -d "$ROOT/config" ]] || die "Missing configuration tree."
[[ -f "$ROOT/VERSION" ]] || die "Missing Dots version."
[[ -d "$HOME_DIR" && "$HOME_DIR" != "/" ]] || die "Invalid user home directory."

mkdir -p "$HOME_DIR/.config" "$HOME_DIR/.local/bin" "$HOME_DIR/.local/share/applications" "$HOME_DIR/.config/systemd/user"

# Preserve user-owned configuration files. This deployment adds only absent
# files; a genuinely clean Arch user account receives the complete defaults.
rsync -a --ignore-existing "$ROOT/config/" "$HOME_DIR/.config/"
rsync -a "$ROOT/systemd/user/" "$HOME_DIR/.config/systemd/user/"

for command_name in fenrir-glass fenrir-theme fenrir-wallpaper fenrir-wallpaper-rotate; do
  [[ -x "$HOME_DIR/.local/bin/$command_name" ]] ||
    ln -s "$HOME_DIR/.local/share/fenrir/dots-venv/bin/$command_name" "$HOME_DIR/.local/bin/$command_name"
done

# GTK/Kitty/Waybar glass adapters and default accent are generated from the
# single appearance file; text remains fully opaque.
"$HOME_DIR/.local/bin/fenrir-glass" on

if command -v gsettings >/dev/null 2>&1; then
  gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark' >/dev/null 2>&1 || true
  gsettings set org.gnome.desktop.interface gtk-theme 'adw-gtk3-dark' >/dev/null 2>&1 || true
fi

systemctl --user daemon-reload
systemctl --user enable --now fenrir-wallpaper-rotate.timer

printf '[Fenrir Dots] Deployed version %s. Existing user files were preserved.\n' "$(cat "$ROOT/VERSION")"
printf '[Fenrir Dots] Glass is enabled at 80%% surface opacity; toggle with: fenrir-glass toggle\n'
printf '[Fenrir Dots] Wallpaper rotation runs every 15 minutes when eligible local images are available.\n'
