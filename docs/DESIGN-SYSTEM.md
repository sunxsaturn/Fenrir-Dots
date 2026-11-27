# Fimbulwinter Design System

## Foundation

The desktop uses a dark Obsidian base (#090b12), soft elevated surfaces, thin neutral borders and restrained wallpaper-derived accents. The accent engine prioritizes blue, red, purple, violet and black. Green remains eligible. Yellow, brown, orange and pink are excluded from wallpaper accent selection.

One token document is the source of truth. Runtime adapters generate the formats needed by each supported application; hand-maintained duplicate palettes are not authoritative.

## Frosted glass

The user preference is stored in `~/.config/fenrir/appearance.json`:

- `glass.enabled`: false by default; users can turn it on from Fenrir Control Center or `fenrir-glass on|off|toggle|status`.
- `glass.surface_opacity`: 0.80 (80% opaque / 20% transparent).
- `glass.blur_px`: 24, applied by the compositor to eligible transparent surfaces.

Opacity applies to window and panel background surfaces, never text, icons, controls or whole-window rendering. The target is a readable frosted surface, not a faded application.

## Compatibility boundary

There is no universal Linux switch that can make every application window translucent. Hyprland can blur eligible transparent windows and layer surfaces; GTK and Qt themes can style supported widgets; terminals, browsers and Electron apps need their own transparency support. Applications that do not expose transparent surfaces retain an opaque but color-consistent theme. The Control Center must show the effective support state instead of claiming every app is glass.

## Accessibility and performance

Keep foreground contrast at WCAG-friendly levels, provide a high-contrast fallback, and never enable expensive blur passes on the whole screen by default. Glass is optional and independently switchable. Text readability and stable gaming frame times take priority over visual effects.

## Terminal

Kitty is the default terminal. It uses the same Obsidian base, wallpaper accent, foreground and selection tokens as the rest of the desktop. Terminal background alpha follows the glass preference; text remains fully opaque.
