# Fimbulwinter Design System

Fimbulwinter is the common Fenrir design system: obsidian surfaces, subtle borders, readable neutral foregrounds and a wallpaper-derived accent.

## Tokens

- Base background: `#090b12`
- Surface: `#151a28`
- Foreground: `#edf0fa`
- Initial accent: `#9b87f5`
- Accent source: decoded pixels in the active wallpaper
- Glass surface opacity: 0.60 (toggleable)
- Blur: compositor-backed, with two passes by default

The theme command generates CSS/QSS/terminal tokens. The initial configuration includes conservative defaults; token propagation to each supported application is implemented by the theme installer.

## Glass behavior

Glass changes compositor opacity and blur on supported Wayland surfaces. Fullscreen content, games, lock screens and authentication dialogs are protected. Third-party application controls that do not support transparency remain native and readable.


## Cross-application tokens

Fenrir writes a shared token set for Hyprland, GTK3/GTK4, Qt6ct, Waybar, Kitty, Mako, Fuzzel and Starship. Dynamic red/purple/blue/white/black accents (with violet as a purple variant) are preferred and sampled from decoded image pixels, then contrast-adjusted against #090b12. Green is allowed; yellow, orange and brown are excluded. Other hues such as pink are not exclusion classes. Fimbulwinter Glass is a reversible 60% compositor-level mode with protected fullscreen/game/media/lock windows.
