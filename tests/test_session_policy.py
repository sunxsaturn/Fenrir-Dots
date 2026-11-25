import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SessionPolicyTests(unittest.TestCase):
    def test_hyprland_does_not_start_hypridle_and_keeps_manual_lock(self):
        config = (ROOT / "config/hypr/hyprland.lua").read_text(encoding="utf-8")
        self.assertNotIn('hl.exec_cmd("hypridle")', config)
        self.assertIn(
            'hl.exec_cmd("systemctl --user start fenrir-stay-awake.service")',
            config,
        )
        self.assertIn('hl.bind(mainMod .. " + L", hl.dsp.exec_cmd("hyprlock"))', config)

    def test_hypridle_configuration_has_no_automatic_actions(self):
        config = (ROOT / "config/hypr/hypridle.conf").read_text(encoding="utf-8")
        active_lines = [
            line.strip()
            for line in config.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertEqual(active_lines, [])

    def test_stay_awake_unit_uses_idle_and_sleep_inhibitors(self):
        unit = (ROOT / "systemd/user/fenrir-stay-awake.service").read_text(
            encoding="utf-8"
        )
        self.assertIn("--what=idle:sleep", unit)
        self.assertIn("--mode=block", unit)
        self.assertIn("/usr/bin/sleep infinity", unit)


if __name__ == "__main__":
    unittest.main()
