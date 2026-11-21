import tempfile
import unittest
from pathlib import Path

import patch_old_android_location_bar_layout as patch


class OldAndroidLocationBarLayoutPatchTest(unittest.TestCase):
    def test_migrates_constructor_return_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            location_bar = root / patch.LOCATION_BAR_TABLET
            toolbar_manager = root / patch.TOOLBAR_MANAGER
            location_bar.parent.mkdir(parents=True)
            toolbar_manager.parent.mkdir(parents=True)
            location_bar.write_text(
                patch.METHOD_ANCHOR + "    }\n", encoding="utf-8"
            )
            toolbar_manager.write_text(
                "class ToolbarManager {\n"
                + patch.TOOLBAR_PROGRESS_OLD_GUARD
                + patch.TOOLBAR_MARGIN_ANCHOR
                + patch.TOOLBAR_TABLET_MARGIN_ANCHOR
                + patch.TOOLBAR_TABLET_MARGIN_ANCHOR
                + "}\n",
                encoding="utf-8",
            )

            self.assertTrue(patch.patch_source(root))
            result = toolbar_manager.read_text(encoding="utf-8")
            self.assertNotIn("                return;", result)
            self.assertIn(patch.TOOLBAR_MARKER, result)
            self.assertFalse(patch.patch_source(root))

    def test_upgrades_existing_toolbar_patch_with_tablet_layout_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            location_bar = root / patch.LOCATION_BAR_TABLET
            toolbar_manager = root / patch.TOOLBAR_MANAGER
            location_bar.parent.mkdir(parents=True)
            toolbar_manager.parent.mkdir(parents=True)
            location_bar.write_text(patch.MARKER + "\n", encoding="utf-8")
            toolbar_manager.write_text(
                "class ToolbarManager {\n"
                + patch.TOOLBAR_MARKER
                + "\n"
                + patch.TOOLBAR_TABLET_MARGIN_ANCHOR
                + patch.TOOLBAR_TABLET_MARGIN_ANCHOR
                + "}\n",
                encoding="utf-8",
            )

            self.assertTrue(patch.patch_source(root))
            result = toolbar_manager.read_text(encoding="utf-8")
            self.assertEqual(2, result.count(patch.TOOLBAR_TABLET_MARGIN_MARKER))
            self.assertEqual(2, result.count("instanceof ViewGroup.MarginLayoutParams"))
            self.assertFalse(patch.patch_source(root))

    def test_patches_location_bar_and_toolbar_layouts_idempotently(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            location_bar = root / patch.LOCATION_BAR_TABLET
            toolbar_manager = root / patch.TOOLBAR_MANAGER
            location_bar.parent.mkdir(parents=True)
            toolbar_manager.parent.mkdir(parents=True)
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
                "    void toolbarTabletMargins() {\n"
                + patch.TOOLBAR_TABLET_MARGIN_ANCHOR
                + "    }\n"
                "    void toolbarTabletMarginChanged() {\n"
                + patch.TOOLBAR_TABLET_MARGIN_ANCHOR
                + "    }\n"
                "}\n",
                encoding="utf-8",
            )

            self.assertTrue(patch.patch_source(root))
            first_location_bar = location_bar.read_text(encoding="utf-8")
            first_toolbar_manager = toolbar_manager.read_text(encoding="utf-8")
            self.assertIn(patch.MARKER, first_location_bar)
            self.assertIn(patch.TOOLBAR_MARKER, first_toolbar_manager)
            self.assertIn("instanceof CoordinatorLayout.LayoutParams", first_toolbar_manager)
            self.assertIn("instanceof ViewGroup.MarginLayoutParams", first_toolbar_manager)

            self.assertFalse(patch.patch_source(root))
            self.assertEqual(first_location_bar, location_bar.read_text(encoding="utf-8"))
            self.assertEqual(first_toolbar_manager, toolbar_manager.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
