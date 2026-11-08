import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("patch_omnibox_dropdown", ROOT / "patch_omnibox_dropdown.py")
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)


class OmniboxDropdownPatchTest(unittest.TestCase):
    def test_guards_all_scroll_resets_in_bottom_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "OmniboxSuggestionsDropdown.java"
            fixture = (ROOT / "tests/fixtures/chromium_157/OmniboxSuggestionsDropdown.java").read_text()
            path.write_text(fixture)
            PATCH.patch_layout_scroll_listener(path)
            result = path.read_text()

            self.assertIn("private boolean mAlignToBottom;", result)
            self.assertIn("if (!mAlignToBottom && OmniboxFeatures.sResetSuggestionsScroll.isEnabled())", result)
            self.assertIn("if (!mAlignToBottom) {\n                postOnAnimation", result)
            self.assertIn("if (!mLayoutScrollListener.mAlignToBottom)", result)
            self.assertNotIn("if (isParked) {\n                mLayoutScrollListener", result)

            first = result
            PATCH.patch_layout_scroll_listener(path)
            self.assertEqual(first, path.read_text())

    def test_adds_dropdown_alignment_wrapper_idempotently(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "OmniboxSuggestionsDropdown.java"
            path.write_text("class OmniboxSuggestionsDropdown {\n}\n", encoding="utf-8")
            PATCH.patch_dropdown_wrapper(path)
            first = path.read_text()
            PATCH.patch_dropdown_wrapper(path)
            self.assertEqual(first, path.read_text())
            self.assertEqual(first.count("void heliumSetAlignToBottom"), 1)


if __name__ == "__main__":
    unittest.main()
