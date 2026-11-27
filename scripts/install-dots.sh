#!/usr/bin/env bash
set -Eeuo pipefail

die(){ printf '[Fenrir Dots] ERROR: %s\n' "$*" >&2; exit 1; }
log(){ printf '[Fenrir Dots] %s\n' "$*"; }

[[ "$(uname -s)" == Linux ]] || die "Linux is required."
[[ -f /etc/arch-release ]] || die "Arch Linux is required."
[[ $EUID -ne 0 ]] || die "Run as the desktop user, not root."
command -v git >/dev/null || die "Git is required."
command -v python3 >/dev/null || die "Python 3 is required."

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
DOTS_COMMIT="${FENRIR_DOTS_COMMIT:-}"
[[ "$DOTS_COMMIT" =~ ^[0-9a-f]{40}$ ]] || die "FENRIR_DOTS_COMMIT must be a full 40-character SHA."
DOTS_REPO="${FENRIR_DOTS_REPO:-https://github.com/sunxsaturn/Fenrir-Dots.git}"
DOTS_DIR="${FENRIR_DOTS_DIR:-$HOME/.local/share/fenrir/dots-source}"
VENV="$HOME/.local/share/fenrir/dots-venv"

mkdir -p "$(dirname "$DOTS_DIR")" "$HOME/.local/bin" "$HOME/.config/hypr"
if [[ -e "$DOTS_DIR" ]]; then
  [[ -d "$DOTS_DIR/.git" ]] || die "$DOTS_DIR already exists and is not a Git checkout."
  [[ "$(git -C "$DOTS_DIR" remote get-url origin)" == "$DOTS_REPO" ]] || die "Unexpected Dots checkout remote."
  git -C "$DOTS_DIR" fetch --depth=1 origin "$DOTS_COMMIT"
else
  git clone --filter=blob:none "$DOTS_REPO" "$DOTS_DIR"
  git -C "$DOTS_DIR" fetch --depth=1 origin "$DOTS_COMMIT"
fi
git -C "$DOTS_DIR" checkout --detach "$DOTS_COMMIT"
actual="$(git -C "$DOTS_DIR" rev-parse HEAD)"
[[ "$actual" == "$DOTS_COMMIT" ]] || die "Pinned Dots checkout mismatch."
version="$(tr -d '\r\n' < "$DOTS_DIR/VERSION")"
[[ "$version" == "0.17.0" ]] || die "Expected Dots 0.17.0, found $version."
[[ -f "$DOTS_DIR/pyproject.toml" && -f "$DOTS_DIR/config/hypr/hyprland.lua" ]] || die "Pinned Dots source tree is incomplete."

python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --disable-pip-version-check "$DOTS_DIR"
for command_name in fenrir-wallpaper fenrir-theme fenrir-glass; do
  [[ -x "$VENV/bin/$command_name" ]] || die "Missing installed command: $command_name"
  ln -sfn "$VENV/bin/$command_name" "$HOME/.local/bin/$command_name"
done

install -Dm644 "$DOTS_DIR/config/hypr/hyprland.lua" "$HOME/.config/hypr/hyprland.lua"
install -Dm644 "$DOTS_DIR/systemd/user/fenrir-wallpaper.service" "$HOME/.config/systemd/user/fenrir-wallpaper.service"
install -Dm644 "$DOTS_DIR/systemd/user/fenrir-wallpaper.timer" "$HOME/.config/systemd/user/fenrir-wallpaper.timer"
install -Dm644 "$ROOT/config/fenrir/appearance.json" "$HOME/.config/fenrir/appearance.json"
install -Dm644 "$ROOT/applications/fenrir-wallpaper-timer.desktop" "$HOME/.config/autostart/fenrir-wallpaper-timer.desktop"
sudo install -Dm644 "$ROOT/applications/fenrir.desktop" /usr/share/wayland-sessions/fenrir.desktop

mkdir -p "$HOME/Pictures/Wallpapers" "$HOME/.local/state/fenrir"
if [[ -S "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/bus" ]]; then
  systemctl --user daemon-reload
fi
log "Installed Fenrir-Dots $version at $actual."
log "Hyprland session is available as Fenrir in SDDM."
