import tempfile
import unittest
from pathlib import Path

import patch_old_android_location_bar_layout as patch


class OldAndroidLocationBarLayoutPatchTest(unittest.TestCase):
    def test_patches_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / patch.LOCATION_BAR_TABLET
            path.parent.mkdir(parents=True)
            path.write_text(
                "class LocationBarTablet {\n"
                "    private void adjustBackgroundForSuggestions() {\n"
                "        FrameLayout.LayoutParams layoutParams = (FrameLayout.LayoutParams) getLayoutParams();\n"
                "    }\n"
                "}\n",
                encoding="utf-8",
            )

            self.assertTrue(patch.patch_source(root))
            first = path.read_text(encoding="utf-8")
            self.assertIn(patch.MARKER, first)
            self.assertFalse(patch.patch_source(root))
            self.assertEqual(first, path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
