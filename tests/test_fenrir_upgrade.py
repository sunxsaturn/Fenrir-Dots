import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPGRADE = ROOT / "bin" / "fenrir-upgrade"
PREVIOUS_SHA = "1111111111111111111111111111111111111111"
TARGET_SHA = "2222222222222222222222222222222222222222"


class FenrirUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.data_home = self.root / "data"
        self.state_home = self.root / "state"
        self.arch = self.data_home / "fenrir" / "arch-source"
        self.arch.mkdir(parents=True)
        (self.arch / ".git").mkdir()
        (self.arch / ".current").write_text(PREVIOUS_SHA, encoding="ascii")
        (self.arch / "install.sh").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        git = self.bin / "git"
        git.write_text(
            """#!/usr/bin/env bash
set -Eeuo pipefail
if [[ "${1:-}" == "-C" ]]; then repo="$2"; shift 2; else repo="${FAKE_REPO:?}"; fi
case "${1:-}" in
  remote)
    printf 'https://github.com/sunxsaturn/Fenrir-Arch.git\n'
    ;;
  fetch)
    exit 0
    ;;
  status)
    if [[ -e "$FAKE_DATA_DIR/dirty" ]]; then printf ' M tracked-file\n'; fi
    ;;
  tag)
    printf 'v0.7.6\n'
    ;;
  rev-parse)
    case "${2:-}" in
      HEAD) cat "$repo/.current" ;;
      'v0.7.6^{commit}'|'origin/main^{commit}') printf '%s\n' "$FAKE_TARGET_SHA" ;;
      *) echo "unsupported fake rev-parse: ${2:-}" >&2; exit 2 ;;
    esac
    ;;
  checkout)
    [[ "${2:-}" == "--detach" ]]
    printf '%s\n' "$3" > "$repo/.current"
    ;;
  *)
    echo "unsupported fake git command: $*" >&2
    exit 2
    ;;
esac
""",
            encoding="utf-8",
        )
        git.chmod(0o755)
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "XDG_DATA_HOME": str(self.data_home),
            "XDG_STATE_HOME": str(self.state_home),
            "PATH": str(self.bin) + os.pathsep + os.environ.get("PATH", ""),
            "FAKE_DATA_DIR": str(self.data_home),
            "FAKE_REPO": str(self.arch),
            "FAKE_TARGET_SHA": TARGET_SHA,
        }

    def tearDown(self):
        self.temporary.cleanup()

    def run_upgrade(self, action):
        return subprocess.run(
            ["bash", str(UPGRADE), action],
            capture_output=True,
            text=True,
            env=self.env,
        )

    def test_preflight_validates_release_and_clean_installer(self):
        result = self.run_upgrade("preflight")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Preflight passed", result.stdout)
        self.assertIn("v0.7.6", result.stdout)
        self.assertIn("Working tree: clean", result.stdout)

    def test_preflight_refuses_dirty_source_without_overwriting_it(self):
        (self.data_home / "dirty").touch()
        result = self.run_upgrade("preflight")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("local changes", result.stderr)
        self.assertEqual((self.arch / ".current").read_text(encoding="ascii"), PREVIOUS_SHA)

    def test_failed_install_restores_source_and_records_failure(self):
        (self.arch / "install.sh").write_text("#!/usr/bin/env bash\nexit 23\n", encoding="utf-8")
        result = self.run_upgrade("apply")
        self.assertEqual(result.returncode, 23, result.stderr)
        self.assertIn("source checkout was returned", result.stdout)
        self.assertEqual((self.arch / ".current").read_text(encoding="ascii").strip(), PREVIOUS_SHA)
        state = (self.state_home / "fenrir" / "upgrade-state").read_text(encoding="utf-8")
        self.assertIn(f"previous_sha={PREVIOUS_SHA}", state)
        self.assertIn(f"target_sha={TARGET_SHA}", state)
        self.assertIn("status=failed", state)

    def test_successful_install_records_recoverable_previous_source(self):
        result = self.run_upgrade("apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.arch / ".current").read_text(encoding="ascii").strip(), TARGET_SHA)
        state = (self.state_home / "fenrir" / "upgrade-state").read_text(encoding="utf-8")
        self.assertIn("status=completed", state)

    def test_explicit_rollback_restores_saved_source_revision(self):
        state_dir = self.state_home / "fenrir"
        state_dir.mkdir(parents=True)
        (state_dir / "upgrade-state").write_text(
            f"previous_sha={PREVIOUS_SHA}\ntarget_sha={TARGET_SHA}\ntarget_ref=v0.7.6\nstatus=completed\n",
            encoding="ascii",
        )
        (self.arch / ".current").write_text(TARGET_SHA, encoding="ascii")
        result = self.run_upgrade("rollback")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.arch / ".current").read_text(encoding="ascii").strip(), PREVIOUS_SHA)
        self.assertIn("status=rolled_back", (state_dir / "upgrade-state").read_text(encoding="utf-8"))
        self.assertIn("source checkout only", result.stdout)

    def test_updater_refuses_paths_under_protected_storage(self):
        self.env["XDG_DATA_HOME"] = "/mnt/storage/fenrir-data"
        result = self.run_upgrade("preflight")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("protected /mnt/storage", result.stderr)


if __name__ == "__main__":
    unittest.main()
