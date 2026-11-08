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
    def test_only_webstore_extensions_receive_feature_default_pin(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "toolbar_actions_model.cc"
            path.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")

            self.assertTrue(PATCH.patch_model(path))
            result = path.read_text(encoding="utf-8")
            self.assertIn("extension->from_webstore() &&", result)
            self.assertIn("is_pinned_by_policy || is_pinned_by_feature", result)
            self.assertIn("kDefaultPinned", result)
            self.assertFalse(PATCH.patch_model(path))
            self.assertEqual(result, path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
