-- Hardware-neutral monitor defaults. Hyprland will use preferred resolution.
-- Inspect `hyprctl monitors` before adding machine-specific rules below.
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = 1 })

-- Example only; uncomment after confirming the real connector and mode:
-- hl.monitor({ output = "DP-1", mode = "2560x1440@144", position = "0x0", scale = 1 })
