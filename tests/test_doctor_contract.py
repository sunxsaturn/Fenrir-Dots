import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DoctorContractTests(unittest.TestCase):
    def test_openverse_review_requires_and_records_original_host_terms_url(self):
        source = (ROOT / "src" / "fenrir_dots" / "doctor.py").read_text(encoding="utf-8")
        self.assertIn("source_terms_url.startswith(\"https://\")", source)
        self.assertIn('args.extend(["--terms-evidence-url", source_terms_url])', source)
        self.assertIn("not is_openverse or source_terms_url.startswith", source)
        self.assertIn("required for Openverse", source)

    def test_provider_terms_links_cover_all_discovery_sources(self):
        source = (ROOT / "src" / "fenrir_dots" / "doctor.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        assignment = next(
            node for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "PROVIDER_TERMS_URLS"
                for target in node.targets
            )
        )
        urls = ast.literal_eval(assignment.value)
        self.assertEqual(
            set(urls),
            {"cleveland", "met", "wikimedia", "aic", "openverse", "smk"},
        )
        self.assertTrue(all(
            isinstance(url, str) and url.startswith("https://")
            for url in urls.values()
        ))


if __name__ == "__main__":
    unittest.main()
