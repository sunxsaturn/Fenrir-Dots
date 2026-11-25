-- Fimbulwinter Glass: deep obsidian, moderate blur, live wallpaper-derived accent.
-- Surface opacity is generated into Waybar/GTK palette CSS by fenrir-theme.

hl.config({
    general = {
        col = {
            active_border = { colors = { "rgba(9b87f5ff)", "rgba(51447fff)" }, angle = 45 },
            inactive_border = "rgba(3a4050cc)",
        },
    },
    decoration = {
        rounding = 14,
        rounding_power = 2,
        active_opacity = 0.96,
        inactive_opacity = 0.90,
        shadow = {
            enabled = true,
            range = 18,
            render_power = 3,
            color = "rgba(00000055)",
        },
        blur = {
            enabled = true,
            size = 6,
            passes = 2,
            new_optimizations = true,
            ignore_opacity = false,
            vibrancy = 0.12,
            xray = false,
        },
    },
})
