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
            for symbol in (
                "UI_MODE_AUTO",
                "markUiModeStartupSuccess",
                'public static final String DESKTOP = "Desktop";',
                "MINIMUM_TABLET_WIDTH_DP",
                "SCREEN_BUCKET_TABLET",
                "SCREEN_BUCKET_LARGE_TABLET",
                "sIsTabletForTesting",
                "@CalledByNative",
            ):
                self.assertIn(symbol, second)

            clean_ui_mode_from_standard_branches(root)
            cleaned = dff.read_text(encoding="utf-8")
            self.assertEqual(MOCK_DEVICE_FORM_FACTOR, cleaned)


if __name__ == "__main__":
    unittest.main()
