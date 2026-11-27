#!/usr/bin/env bash
set -Eeuo pipefail

die(){ printf '[Fenrir Dots] ERROR: %s\n' "$*" >&2; exit 1; }
log(){ printf '[Fenrir Dots] %s\n' "$*"; }

[[ "$(uname -s)" == Linux ]] || die "Linux is required."
[[ -f /etc/arch-release ]] || die "Arch Linux is required."
[[ $EUID -ne 0 ]] || die "Run as the desktop user, not root."
command -v git >/dev/null || die "Git is required."
command -v python3 >/dev/null || die "Python 3 is required."
command -v quickshell >/dev/null || die "The official Arch quickshell package is required."

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
[[ "$version" == "0.19.1" ]] || die "Expected Dots 0.19.1, found $version."
[[ -f "$DOTS_DIR/pyproject.toml" && -f "$DOTS_DIR/config/hypr/hyprland.lua" ]] || die "Pinned Dots source tree is incomplete."

python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --disable-pip-version-check "$DOTS_DIR"
for command_name in fenrir-wallpaper fenrir-theme fenrir-glass fenrir-doctor fenrir-control-center; do
  [[ -x "$VENV/bin/$command_name" ]] || die "Missing installed command: $command_name"
  ln -sfn "$VENV/bin/$command_name" "$HOME/.local/bin/$command_name"
done

copy_config(){
  local source="$1" destination="$2"
  if [[ -e "$destination" ]] && ! cmp -s "$source" "$destination"; then
    destination="${destination}.fenrir-default"
    log "Preserving existing configuration; installing Fenrir default as $destination"
  fi
  install -Dm644 "$source" "$destination"
}
copy_config "$DOTS_DIR/config/hypr/hyprland.lua" "$HOME/.config/hypr/hyprland.lua"
copy_config "$DOTS_DIR/config/hypr/hyprpaper.conf" "$HOME/.config/hypr/hyprpaper.conf"
copy_config "$DOTS_DIR/config/kitty/kitty.conf" "$HOME/.config/kitty/kitty.conf"
copy_config "$DOTS_DIR/config/gtk-3.0/gtk.css" "$HOME/.config/gtk-3.0/gtk.css"
copy_config "$DOTS_DIR/config/gtk-4.0/gtk.css" "$HOME/.config/gtk-4.0/gtk.css"
copy_config "$DOTS_DIR/config/waybar/config.jsonc" "$HOME/.config/waybar/config.jsonc"
copy_config "$DOTS_DIR/config/waybar/style.css" "$HOME/.config/waybar/style.css"
copy_config "$DOTS_DIR/config/mako/config" "$HOME/.config/mako/config"
copy_config "$DOTS_DIR/config/fuzzel/fuzzel.ini" "$HOME/.config/fuzzel/fuzzel.ini"
copy_config "$DOTS_DIR/config/fenrir/appearance.json" "$HOME/.config/fenrir/appearance.json"

QS_CONFIG_NAME=""
for candidate in fenrir-system fenrir-system-default fenrir-system-v0-18 fenrir-system-v0-19 fenrir-system-v0-19-1; do
  candidate_dir="$HOME/.config/quickshell/$candidate"
  if [[ ! -e "$candidate_dir/shell.qml" ]] || cmp -s "$DOTS_DIR/quickshell/fenrir/shell.qml" "$candidate_dir/shell.qml"; then
    QS_CONFIG_NAME="$candidate"
    QS_CONFIG_DIR="$candidate_dir"
    break
  fi
done
[[ -n "$QS_CONFIG_NAME" ]] || die "All managed Quickshell config paths already contain different user files; preserve them and choose a new config name."
install -Dm644 "$DOTS_DIR/quickshell/fenrir/shell.qml" "$QS_CONFIG_DIR/shell.qml"
install -d -m 0755 "$HOME/.config/fenrir"
printf '%s\n' "$QS_CONFIG_NAME" > "$HOME/.config/fenrir/quickshell-config"
for unit in fenrir-wallpaper.service fenrir-wallpaper.timer; do
  install -Dm644 "$DOTS_DIR/systemd/user/$unit" "$HOME/.config/systemd/user/$unit"
done
# Quickshell now owns the desktop notification D-Bus name. Remove only
# Fenrir's old Mako launch line from the managed Hyprland start block.
migrate_legacy_mako(){
  local config="$HOME/.config/hypr/hyprland.lua"
  if [[ -f "$config" ]]; then
    python3 - "$config" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
lines = text.splitlines(keepends=True)
inside_start = False
matches = []
for index, line in enumerate(lines):
    if 'hl.on("hyprland.start", function()' in line:
        inside_start = True
    elif inside_start and line.strip() == "end)":
        inside_start = False
    elif inside_start and line.strip() in {
        'hl.exec_cmd("mako")',
        "hl.exec_cmd('mako')",
    }:
        matches.append(index)

if len(matches) == 1:
    del lines[matches[0]]
    path.write_text("".join(lines), encoding="utf-8")
    print("[Fenrir Dots] Migrated the managed notification launcher from Mako to Quickshell.")
elif len(matches) > 1:
    raise SystemExit("[Fenrir Dots] Multiple Mako launch lines detected; refusing automatic migration.")
PY
  fi
  rm -f "$HOME/.config/autostart/fenrir-mako.desktop"
}
migrate_legacy_mako

for desktop in fenrir-wallpaper-timer.desktop fenrir-hyprpaper.desktop fenrir-initial-wallpaper.desktop; do
  install -Dm644 "$DOTS_DIR/applications/$desktop" "$HOME/.config/autostart/$desktop"
done
sudo install -Dm644 "$DOTS_DIR/applications/fenrir.desktop" /usr/share/wayland-sessions/fenrir.desktop
install -Dm644 "$DOTS_DIR/applications/fenrir-doctor.desktop" "$HOME/.local/share/applications/fenrir-doctor.desktop"
install -Dm644 "$DOTS_DIR/applications/fenrir-control-center.desktop" "$HOME/.local/share/applications/fenrir-control-center.desktop"

mkdir -p "$HOME/Pictures/Wallpapers" "$HOME/.local/state/fenrir"
for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
  if [[ -f "$rc" ]] && ! grep -q 'starship init' "$rc"; then
    shell_name=bash; [[ "$rc" == *.zshrc ]] && shell_name=zsh
    printf '\n# Fenrir adaptive Fimbulwinter prompt\neval "$(starship init %s)"\n' "$shell_name" >> "$rc"
  fi
done
mkdir -p "$HOME/.config/fish/conf.d"
cat > "$HOME/.config/fish/conf.d/fenrir-starship.fish" <<'FISH'
if status is-interactive
    starship init fish | source
end
FISH
if [[ -S "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/bus" ]]; then
  systemctl --user daemon-reload
  systemctl --user enable --now fenrir-wallpaper.timer
fi
log "Installed Fenrir-Dots $version at $actual with Quickshell config $QS_CONFIG_NAME."
log "Hyprland session is available as Fenrir in SDDM."
