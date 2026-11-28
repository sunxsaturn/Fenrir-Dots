import unittest
from pathlib import Path


class ReleaseContractTests(unittest.TestCase):
    def test_release_workflow_validates_versions_builds_checksums_and_attests(self):
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn("branches: [main]", workflow)
        self.assertIn("VERSION", workflow)
        self.assertIn("pyproject.toml", workflow)
        self.assertIn("src/fenrir_dots/__init__.py", workflow)
        self.assertIn('assert package["project"]["version"] == version', workflow)
        self.assertIn('assert runtime["__version__"] == version', workflow)
        self.assertIn("python -m build --outdir dist", workflow)
        self.assertIn("sha256sum ", workflow)
        self.assertIn("actions/attest-build-provenance@v2", workflow)
        self.assertIn("attestations: write", workflow)
        self.assertIn("gh release create", workflow)
        self.assertIn('--target "${GITHUB_SHA}"', workflow)
        self.assertIn("release_needed=false", workflow)
        self.assertIn("release_needed=true", workflow)
        self.assertIn("if: steps.metadata.outputs.release_needed == 'true'", workflow)
        self.assertNotIn("publish-public", workflow)


if __name__ == "__main__":
    unittest.main()
