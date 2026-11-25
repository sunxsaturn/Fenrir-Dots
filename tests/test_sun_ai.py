import importlib.util
import unittest
from pathlib import Path

SERVER = Path(__file__).resolve().parents[1] / "apps" / "sun-ai" / "server.py"
spec = importlib.util.spec_from_file_location("sun_ai_server", SERVER)
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)

class StrictJSONTests(unittest.TestCase):
    def test_duplicate_keys_rejected(self):
        with self.assertRaises(server.BadJSON):
            server.strict_json(b'{"model":"one","model":"two"}')
    def test_non_finite_constant_rejected(self):
        with self.assertRaises(server.BadJSON):
            server.strict_json(b'{"value":NaN}')
    def test_valid_object(self):
        self.assertEqual(server.strict_json(b'{"message":"hello"}'), {"message":"hello"})

class SettingsTests(unittest.TestCase):
    def test_default_settings_are_location_private(self):
        settings = server.default_settings()
        self.assertEqual(settings["default_model"], "")
        self.assertIsNone(settings["weather"]["latitude"])
        self.assertIsNone(settings["weather"]["longitude"])
        self.assertEqual(settings["weather"]["location"], "")

    def test_unconfigured_weather_does_not_make_network_request(self):
        from unittest.mock import patch
        with patch.object(server, "read_settings", return_value=server.default_settings()), \
             patch.object(server.urllib.request, "urlopen", side_effect=AssertionError("network must not be used")):
            result = server.weather_snapshot()
        self.assertFalse(result["configured"])
        self.assertIn("settings", result["message"].lower())

    def test_weather_codes_have_readable_fallback(self):
        self.assertEqual(server.WEATHER_CODES[0], "Clear sky")
        self.assertEqual(server.WEATHER_CODES[95], "Thunderstorm")

    def test_system_snapshot_has_stable_local_fields(self):
        result = server.system_snapshot()
        self.assertIn("cpu_percent", result)
        self.assertIn("memory_percent", result)
        self.assertIn("disk_percent", result)
        self.assertGreaterEqual(result["disk_total_gib"], result["disk_used_gib"])

    def test_system_snapshot_prefers_discrete_amd_gpu_over_igpu(self):
        import shutil
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            igpu = root / "card0" / "device"
            dgpu = root / "card1" / "device"
            igpu.mkdir(parents=True)
            dgpu.mkdir(parents=True)
            for path, busy, vram, device_id, name in (
                (igpu, "12", str(512 * 1024**2), "0x164e", "AMD Raphael iGPU"),
                (dgpu, "67", str(12 * 1024**3), "0x73df", "AMD Radeon RX 6750 XT"),
            ):
                (path / "vendor").write_text("0x1002", encoding="ascii")
                (path / "gpu_busy_percent").write_text(busy, encoding="ascii")
                (path / "mem_info_vram_total").write_text(vram, encoding="ascii")
                (path / "device").write_text(device_id, encoding="ascii")
                (path / "product_name").write_text(name, encoding="utf-8")

            original_glob = Path.glob
            def fake_glob(path, pattern):
                if str(path) == "/sys/class/drm" and pattern == "card*/device":
                    return iter((igpu, dgpu))
                return original_glob(path, pattern)

            usage = shutil._ntuple_diskusage(total=100 * 1024**3, used=40 * 1024**3, free=60 * 1024**3)
            with patch.object(Path, "glob", fake_glob), patch.object(server.shutil, "disk_usage", return_value=usage):
                result = server.system_snapshot()

        self.assertEqual(result["gpu_percent"], 67.0)
        self.assertEqual(result["gpu_name"], "AMD Radeon RX 6750 XT")


if __name__ == "__main__":
    unittest.main()
