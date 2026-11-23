import tempfile
import unittest
from pathlib import Path

import patch_old_android_desktop_tabs as patch


class OldAndroidDesktopTabsPatchTest(unittest.TestCase):
    def _write_sources(self, root: Path) -> None:
        sources = {
            patch.MAIN_SETTINGS: """        return !DeviceInfo.isAutomotive()
                && (DeviceInfo.isFoldable()
                        || !DeviceFormFactor.isNonMultiDisplayContextOnTablet(context));
""",
            patch.ADDRESS_BAR_FRAGMENT: """import androidx.annotation.VisibleForTesting;

import org.chromium.base.DeviceInfo;

        overrideDescriptionIfFoldable();
    }

    @Override
    public void onConfigurationChanged(Configuration newConfig) {
        super.onConfigurationChanged(newConfig);
        overrideDescriptionIfFoldable();
    }

    private void overrideDescriptionIfFoldable() {
""",
            patch.ADDRESS_BAR_XML: patch.XML_ANCHOR,
            patch.ADDRESS_BAR_PREFERENCE: patch.ADDRESS_BAR_SET_OLD,
            patch.POSITION_CONTROLLER: patch.POSITION_OLD,
            patch.TOOLBAR_MANAGER: """import android.content.SharedPreferences;

public class ToolbarManager
        implements UrlFocusChangeListener,
                FuseboxControls {
        mActivity = activity;
        mWindowAndroid = windowAndroid;
        int initialTabStripHeight =
                suppressTabStripAtStart ? 0 : mToolbarLayout.getTabStripHeightFromResource();
        if (!BrowserControlsUtils.isForceTopChromeHeightAdjustmentOnStartupEnabled(mActivity)) {
            mTabStripTopControlLayer.set(mToolbar.getTabStripHeight());
        }
        mTabStripTopControlLayer.destroy();
    /** Call to tear down all of the toolbar dependencies. */
""",
            patch.STRINGS: patch.STRING_ANCHOR,
        }
        for relative, text in sources.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def test_v158_main_settings_keeps_address_bar_option_available(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_sources(root)
            main_settings = root / patch.MAIN_SETTINGS
            main_settings.write_text(patch.MAIN_V158_OLD)

            self.assertTrue(patch.patch_main_settings(root))
            result = main_settings.read_text()
            self.assertIn(patch.MAIN_MARKER, result)
            self.assertIn("        return true;", result)
            self.assertNotIn("shouldMoveToolbarSettingsToAppearance", result)
            self.assertFalse(patch.patch_main_settings(root))

    def test_patches_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_sources(root)

            self.assertTrue(patch.patch_source(root))
            first = {
                relative: (root / relative).read_text(encoding="utf-8")
                for relative in (
                    patch.MAIN_SETTINGS,
                    patch.ADDRESS_BAR_FRAGMENT,
                    patch.ADDRESS_BAR_XML,
                    patch.ADDRESS_BAR_PREFERENCE,
                    patch.POSITION_CONTROLLER,
                    patch.TOOLBAR_MANAGER,
                    patch.STRINGS,
                )
            }
            self.assertIn(patch.MAIN_MARKER, first[patch.MAIN_SETTINGS])
            self.assertIn(patch.XML_MARKER, first[patch.ADDRESS_BAR_XML])
            self.assertIn(patch.MANAGER_MARKER, first[patch.TOOLBAR_MANAGER])
            self.assertIn(patch.POSITION_MARKER, first[patch.POSITION_CONTROLLER])
            self.assertIn(patch.ADDRESS_BAR_SET_MARKER, first[patch.ADDRESS_BAR_PREFERENCE])
            self.assertIn(patch.STRING_MARKER, first[patch.STRINGS])

            self.assertFalse(patch.patch_source(root))
            self.assertEqual(
                first,
                {
                    relative: (root / relative).read_text(encoding="utf-8")
                    for relative in first
                },
            )


if __name__ == "__main__":
    unittest.main()
