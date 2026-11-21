import tempfile
import unittest
from pathlib import Path

import patch_old_android_extension_popup as patch


SOURCE = """        int initialWidthPx =
                resources.getDimensionPixelSize(R.dimen.extension_action_popup_min_width);
        int initialHeightPx =
                resources.getDimensionPixelSize(R.dimen.extension_action_popup_min_height);
"""


class OldAndroidExtensionPopupPatchTest(unittest.TestCase):
    def test_patches_initial_size_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / patch.POPUP_PATH
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(SOURCE, encoding="utf-8")

            self.assertTrue(patch.patch_source(root))
            result = path.read_text(encoding="utf-8")
            self.assertIn(patch.MARKER, result)
            self.assertIn("ViewUtils.dpToPx(mActivity, 320)", result)
            self.assertIn("ViewUtils.dpToPx(mActivity, 480)", result)
            self.assertFalse(patch.patch_source(root))
            self.assertEqual(result, path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
