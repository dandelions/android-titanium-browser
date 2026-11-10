import tempfile
import unittest
from pathlib import Path

from patch_ui_mode import (
    DEVICE_FORM_FACTOR_REL,
    clean_ui_mode_from_standard_branches,
    patch_device_form_factor,
)


MOCK_DEVICE_FORM_FACTOR = """package org.chromium.ui.base;

@NullMarked
public class DeviceFormFactor {
    public static final String DESKTOP = "Desktop";
    public static final int MINIMUM_TABLET_WIDTH_DP =
            DeviceInfo.LARGE_DISPLAY_MIN_SCREEN_WIDTH_600_DP;
    @VisibleForTesting public static final int SCREEN_BUCKET_TABLET = 2;
    private static final int SCREEN_BUCKET_LARGE_TABLET = 3;
    private static @Nullable Boolean sIsTabletForTesting;

    @CalledByNative
    @Deprecated
    public static boolean isTablet() {
        if (sIsTabletForTesting != null) {
            return sIsTabletForTesting;
        }
        return detectScreenWidthBucket(ContextUtils.getApplicationContext())
                >= SCREEN_BUCKET_TABLET;
    }

    public static boolean isNonMultiDisplayContextOnTablet(Context context) {
        return detectScreenWidthBucket(context) >= SCREEN_BUCKET_TABLET;
    }

    @UiThread
    public static boolean isWindowOnTablet(WindowAndroid windowAndroid) {
        return detectScreenWidthBucket(windowAndroid) >= SCREEN_BUCKET_TABLET;
    }

    public static boolean isNonMultiDisplayContextOnLargeTablet(Context context) {
        return detectScreenWidthBucket(context) == SCREEN_BUCKET_LARGE_TABLET;
    }
}
"""


class PatchUiModeTest(unittest.TestCase):
    def test_patch_device_form_factor_repeated_runs_preserve_chromium_constants(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dff = root / DEVICE_FORM_FACTOR_REL
            dff.parent.mkdir(parents=True, exist_ok=True)
            dff.write_text(MOCK_DEVICE_FORM_FACTOR, encoding="utf-8")

            patch_device_form_factor(root)
            first = dff.read_text(encoding="utf-8")
            patch_device_form_factor(root)
            second = dff.read_text(encoding="utf-8")

            self.assertEqual(first, second)
            self.assertEqual(second.count("markUiModeStartupSuccess()"), 1)
            for symbol in (
                "UI_MODE_AUTO",
                "markUiModeStartupSuccess",
                'public static final String DESKTOP = "Desktop";',
                "public static final int MINIMUM_TABLET_WIDTH_DP",
                "SCREEN_BUCKET_TABLET = 2",
                "SCREEN_BUCKET_LARGE_TABLET = 3",
                "sIsTabletForTesting;",
                "@CalledByNative",
            ):
                self.assertIn(symbol, second)

            # Simulate legacy unmarked block and verify upgrade does not duplicate methods or drop constants.
            unmarked = (
                second.replace("    // BEGIN HELIUM UI MODE\n", "")
                .replace("    // END HELIUM UI MODE\n", "")
            )
            dff.write_text(unmarked, encoding="utf-8")
            patch_device_form_factor(root)
            upgraded = dff.read_text(encoding="utf-8")
            self.assertEqual(upgraded, second)
            self.assertEqual(upgraded.count("markUiModeStartupSuccess()"), 1)

            clean_ui_mode_from_standard_branches(root)
            cleaned = dff.read_text(encoding="utf-8")
            self.assertEqual(MOCK_DEVICE_FORM_FACTOR, cleaned)

    def test_clean_tabbed_delegate_removes_all_ui_mode_items(self):
        from patch_ui_mode import TABBED_DELEGATE_REL

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tabbed = root / TABBED_DELEGATE_REL
            tabbed.parent.mkdir(parents=True, exist_ok=True)
            original = """class TabbedAppMenuPropertiesDelegate {
    void populate1(ModelList modelList) {
        modelList.add(buildAppearanceItem());
        modelList.add(buildUiModeItem());
        modelList.add(buildSettingsItem());
    }
    void populate2(ModelList modelList) {
        modelList.add(buildAppearanceItem());
        modelList.add(buildUiModeItem());
        modelList.add(buildSettingsItem());
    }
    private ListItem buildUiModeChoiceItem(int id, String title) {
        return null;
    }
    private ListItem buildUiModeItem() {
        return null;
    }
    private ListItem buildSettingsItem() {
        return null;
    }
}
"""
            tabbed.write_text(original, encoding="utf-8")
            clean_ui_mode_from_standard_branches(root)
            cleaned = tabbed.read_text(encoding="utf-8")
            self.assertNotIn("buildUiModeItem", cleaned)
            self.assertNotIn("buildUiModeChoiceItem", cleaned)
            self.assertIn("buildSettingsItem", cleaned)
            self.assertIn("buildAppearanceItem", cleaned)


if __name__ == "__main__":
    unittest.main()
