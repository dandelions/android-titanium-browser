import tempfile
import unittest
from pathlib import Path

import patch_old_android_mini_origin as patch


class OldAndroidMiniOriginPatchTest(unittest.TestCase):
    def _write_source(self, root: Path) -> Path:
        path = root / patch.TARGET
        path.parent.mkdir(parents=True)
        path.write_text(
            "package org.chromium.chrome.browser.toolbar;\n"
            + patch.ORIGINAL_FIELD
            + "    void init() {\n"
            + patch.ORIGINAL_INIT
            + "    }\n"
            + patch.ORIGINAL_STATE
            + "        return;\n"
            + "    }\n"
            + patch.ORIGINAL_TRANSITION
            + "        return;\n"
            + "    }\n",
            encoding="utf-8",
        )
        return path

    def test_guards_non_frame_layout_params_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self._write_source(root)

            self.assertTrue(patch.patch_source_tree(root))
            result = path.read_text(encoding="utf-8")
            self.assertIn(patch.FIELD_MARKER, result)
            self.assertIn(patch.INIT_MARKER, result)
            self.assertIn(patch.STATE_MARKER, result)
            self.assertIn("locationBarLayoutParams instanceof FrameLayout.LayoutParams", result)
            self.assertIn("instanceof FrameLayout.LayoutParams", result)
            self.assertIn("if (mDefaultLocationBarLayoutParams == null) return;", result)
            self.assertIn(patch.TRANSITION_MARKER, result)
            self.assertFalse(patch.patch_source_tree(root))
            self.assertEqual(result, path.read_text(encoding="utf-8"))

    def test_upgrades_partially_applied_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / patch.TARGET
            path.parent.mkdir(parents=True)
            path.write_text(
                "package org.chromium.chrome.browser.toolbar;\n"
                + patch.PATCHED_FIELD
                + "    void init() {\n"
                + patch.ORIGINAL_INIT
                + "    }\n"
                + patch.ORIGINAL_STATE
                + "        return;\n"
                + "    }\n"
                + patch.ORIGINAL_TRANSITION
                + "        return;\n"
                + "    }\n",
                encoding="utf-8",
            )

            self.assertTrue(patch.patch_source_tree(root))
            result = path.read_text(encoding="utf-8")
            self.assertIn(patch.INIT_MARKER, result)
            self.assertIn(patch.STATE_MARKER, result)
            self.assertIn(patch.TRANSITION_MARKER, result)


if __name__ == "__main__":
    unittest.main()
