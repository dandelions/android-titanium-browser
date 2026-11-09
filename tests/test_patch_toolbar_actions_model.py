import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("patch_toolbar_actions_model", ROOT / "patch_toolbar_actions_model.py")
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)
FIXTURE = ROOT / "tests/fixtures/chromium_157/toolbar_actions_model.cc"


class ToolbarActionsModelPatchTest(unittest.TestCase):
    def test_disables_automatic_toolbar_pinning_for_all_extensions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "toolbar_actions_model.cc"
            path.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")

            self.assertTrue(PATCH.patch_model(path))
            result = path.read_text(encoding="utf-8")
            self.assertIn("const bool is_pinned_by_feature = false;", result)
            self.assertIn("is_pinned_by_policy || is_pinned_by_feature", result)
            self.assertFalse(PATCH.patch_model(path))
            self.assertEqual(result, path.read_text(encoding="utf-8"))

    def test_replaces_previous_webstore_filter_with_full_disable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "toolbar_actions_model.cc"
            content = FIXTURE.read_text(encoding="utf-8").replace(
                PATCH.OLD_VANILLA, PATCH.OLD_WEBSTORE
            )
            path.write_text(content, encoding="utf-8")

            self.assertTrue(PATCH.patch_model(path))
            result = path.read_text(encoding="utf-8")
            self.assertIn("const bool is_pinned_by_feature = false;", result)
            self.assertNotIn("extension->from_webstore()", result)
            self.assertFalse(PATCH.patch_model(path))


if __name__ == "__main__":
    unittest.main()
