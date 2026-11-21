import tempfile
import unittest
from pathlib import Path

import patch_old_android_location_bar_layout as patch


class OldAndroidLocationBarLayoutPatchTest(unittest.TestCase):
    def _create_fixtures(self, root):
        location_bar = root / patch.LOCATION_BAR_TABLET
        toolbar_manager = root / patch.TOOLBAR_MANAGER
        mini_origin_bar = root / patch.MINI_ORIGIN_BAR
        location_bar.parent.mkdir(parents=True, exist_ok=True)
        toolbar_manager.parent.mkdir(parents=True, exist_ok=True)
        mini_origin_bar.parent.mkdir(parents=True, exist_ok=True)
        location_bar.write_text(
            "class LocationBarTablet {\n"
            "    private void adjustBackgroundForSuggestions() {\n"
            "        FrameLayout.LayoutParams layoutParams = (FrameLayout.LayoutParams) getLayoutParams();\n"
            "    }\n"
            "}\n",
            encoding="utf-8",
        )
        toolbar_manager.write_text(
            "class ToolbarManager {\n"
            "    void progress() {\n"
            "            CoordinatorLayout.LayoutParams progressBarParams =\n"
            "                    (CoordinatorLayout.LayoutParams) progressBarStub.getLayoutParams();\n"
            "            progressBarParams.gravity = Gravity.BOTTOM;\n"
            "            progressBarStub.setLayoutParams(progressBarParams);\n"
            "    }\n"
            "    void margin() {\n"
            "        final ViewGroup.MarginLayoutParams layoutParams =\n"
            "                ((ViewGroup.MarginLayoutParams) mControlContainer.getLayoutParams());\n"
            "    }\n"
            "}\n",
            encoding="utf-8",
        )
        mini_origin_bar.write_text(
            "class MiniOriginBarController {\n"
            "    void constructorPath() {\n"
            "        mDefaultLocationBarLayoutParams =\n"
            "                (FrameLayout.LayoutParams) mLocationBar.getContainerView().getLayoutParams();\n"
            "    }\n"
            "    void statePath() {\n"
            "            mDefaultLocationBarLayoutParams =\n"
            "                    (FrameLayout.LayoutParams) mLocationBar.getContainerView().getLayoutParams();\n"
            "    }\n"
            "}\n",
            encoding="utf-8",
        )
        return location_bar, toolbar_manager, mini_origin_bar

    def test_migrates_constructor_return_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            location_bar, toolbar_manager, _ = self._create_fixtures(root)
            toolbar_manager.write_text(
                "class ToolbarManager {\n"
                + patch.TOOLBAR_PROGRESS_OLD_GUARD
                + patch.TOOLBAR_MARGIN_ANCHOR
                + "}\n",
                encoding="utf-8",
            )
            self.assertTrue(patch.patch_source(root))
            result = toolbar_manager.read_text(encoding="utf-8")
            self.assertNotIn("                return;", result)
            self.assertIn(patch.TOOLBAR_MARKER, result)
            self.assertFalse(patch.patch_source(root))

    def test_patches_location_bar_toolbar_and_mini_origin_idempotently(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            location_bar, toolbar_manager, mini_origin_bar = self._create_fixtures(root)

            self.assertTrue(patch.patch_source(root))
            first_location_bar = location_bar.read_text(encoding="utf-8")
            first_toolbar_manager = toolbar_manager.read_text(encoding="utf-8")
            first_mini_origin_bar = mini_origin_bar.read_text(encoding="utf-8")
            self.assertIn(patch.MARKER, first_location_bar)
            self.assertIn(patch.TOOLBAR_MARKER, first_toolbar_manager)
            self.assertIn("instanceof CoordinatorLayout.LayoutParams", first_toolbar_manager)
            self.assertIn("instanceof ViewGroup.MarginLayoutParams", first_toolbar_manager)
            self.assertIn(patch.MINI_ORIGIN_MARKER, first_mini_origin_bar)
            self.assertIn("instanceof FrameLayout.LayoutParams", first_mini_origin_bar)

            self.assertFalse(patch.patch_source(root))
            self.assertEqual(first_location_bar, location_bar.read_text(encoding="utf-8"))
            self.assertEqual(first_toolbar_manager, toolbar_manager.read_text(encoding="utf-8"))
            self.assertEqual(first_mini_origin_bar, mini_origin_bar.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
