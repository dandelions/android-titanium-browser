import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATCH_PATH = ROOT / "patch_old_android_bottom_toolbar.py"
SPEC = importlib.util.spec_from_file_location("patch_old_android_bottom_toolbar", PATCH_PATH)
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)


FEATURE_SOURCE = "BASE_FEATURE(kAndroidBottomBar, base::FEATURE_DISABLED_BY_DEFAULT);\n"
JAVA_FEATURE_SOURCE = """    public static final CachedFlag sAndroidBottomBar =
            newCachedFlag(ANDROID_BOTTOM_BAR, false, /* defaultValueInTests= */ true);
"""
DEFAULT_USER_ENABLED_SOURCE = '''    public static final BooleanCachedFeatureParam sAndroidBottomBarDefaultUserEnabled =
            newBooleanCachedFeatureParam(ANDROID_BOTTOM_BAR, "default_user_enabled", true);
'''

ACTIVITY_SOURCE = '''            if (BottomBarConfigUtils.shouldShowSettingsToggle(this)) {
                new BottomBarEnabledChangeObserver(
                        this,
                        getLifecycleDispatcher(),
                        mBottomBarHostManager != null,
                        this::doRecreateActivity);
            }
'''
ACTIVITY_MIGRATED_SOURCE = '''            // Helium: the address-bar position is the sole bottom-toolbar setting.
            new BottomBarEnabledChangeObserver(
                    this,
                    getLifecycleDispatcher(),
                    mBottomBarHostManager != null,
                    this::doRecreateActivity);
'''
ACTIVITY_V158_SOURCE = '''            // Observe BOTTOM_BAR_ENABLED when the Settings toggle or the education flow (where
            // tapping "Try it now" in the opt-in dialog enables the bottom bar) can change it, so
            // the activity recreates to inflate or remove the bottom bar. The observer registers
            // itself with ActivityLifecycleDispatcher and unregisters on destroy.
            if (BottomBarConfigUtils.shouldObserveBottomBarEnabledChanges(this)) {
                new BottomBarEnabledChangeObserver(
                        this,
                        getLifecycleDispatcher(),
                        mBottomBarHostManager != null,
                        this::doRecreateActivity);
            }
'''
HOST_METHOD_SOURCE = '''    private @Nullable BottomBarHostManager getBottomBarHostManager() {
        if (mBottomBarHostManager == null && BottomBarConfigUtils.isBottomBarEnabled(this)) {
            mBottomBarHostManager = new BottomBarHostManager();
        }
        return mBottomBarHostManager;
    }
'''

CONFIG_SOURCE = """import org.chromium.base.DeviceInfo;
import org.chromium.build.annotations.NullMarked;
import org.chromium.components.embedder_support.util.UrlUtilities;
import org.chromium.ui.base.DeviceFormFactor;

class BottomBarConfigUtils {
    private static boolean isBottomBarEligible(Context context) {
        return !DeviceFormFactor.isNonMultiDisplayContextOnTablet(context)
                && !DeviceInfo.isAutomotive()
                && ChromeFeatureList.sAndroidBottomBar.isEnabled();
    }

    public static boolean shouldShowSettingsToggle(Context context) {
        return isBottomBarEligible(context)
                && ChromeFeatureList.sAndroidBottomBarShowSettingsToggle.getValue();
    }

    
}
"""


class OldAndroidBottomToolbarPatchTest(unittest.TestCase):
    def _write_sources(self, root: Path) -> dict[str, Path]:
        paths = {
            PATCH.FEATURE_LIST: root / PATCH.FEATURE_LIST,
            PATCH.JAVA_FEATURE_LIST: root / PATCH.JAVA_FEATURE_LIST,
            PATCH.CONFIG_UTILS: root / PATCH.CONFIG_UTILS,
            PATCH.CHROME_TABBED_ACTIVITY: root / PATCH.CHROME_TABBED_ACTIVITY,
        }
        for path in paths.values():
            path.parent.mkdir(parents=True, exist_ok=True)
        paths[PATCH.FEATURE_LIST].write_text(FEATURE_SOURCE)
        paths[PATCH.JAVA_FEATURE_LIST].write_text(
            JAVA_FEATURE_SOURCE + DEFAULT_USER_ENABLED_SOURCE
        )
        paths[PATCH.CONFIG_UTILS].write_text(CONFIG_SOURCE)
        paths[PATCH.CHROME_TABBED_ACTIVITY].write_text(ACTIVITY_SOURCE + HOST_METHOD_SOURCE)
        return paths

    def test_enables_bottom_bar_for_car_desktop_and_mobile(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = self._write_sources(Path(temp))

            self.assertTrue(PATCH.patch_source_tree(temp))

            self.assertIn(
                "BASE_FEATURE(kAndroidBottomBar, base::FEATURE_DISABLED_BY_DEFAULT);",
                paths[PATCH.FEATURE_LIST].read_text(),
            )
            java_features = paths[PATCH.JAVA_FEATURE_LIST].read_text()
            self.assertIn(PATCH.JAVA_FLAG_MARKER, java_features)
            self.assertIn(
                "newCachedFlag(ANDROID_BOTTOM_BAR, false, /* defaultValueInTests= */ true);",
                java_features,
            )
            config = paths[PATCH.CONFIG_UTILS].read_text()
            self.assertIn("Helium: the address bar preference owns the only toolbar row.", config)
            self.assertNotIn("Helium: expose and allow the bottom toolbar", config)
            self.assertIn("return false;", config)
            self.assertNotIn("DeviceInfo", config)
            self.assertNotIn("DeviceFormFactor", config)
            default_setting = paths[PATCH.JAVA_FEATURE_LIST].read_text()
            self.assertIn(PATCH.DEFAULT_USER_ENABLED_MARKER, default_setting)
            self.assertIn('"default_user_enabled", false', default_setting)
            activity = paths[PATCH.CHROME_TABBED_ACTIVITY].read_text()
            self.assertIn(PATCH.ACTIVITY_OBSERVER_MARKER, activity)
            self.assertNotIn("BottomBarEnabledChangeObserver", activity)
            self.assertNotIn("shouldShowSettingsToggle(this)", activity)
            self.assertIn(PATCH.BOTTOM_BAR_HOST_METHOD_MARKER, activity)
            self.assertIn("private @Nullable BottomBarHostManager getBottomBarHostManager() {\n"
                          "        // Helium: old-android uses the address bar as the only bottom toolbar.\n"
                          "        return null;", activity)
            self.assertNotIn("mBottomBarHostManager = new BottomBarHostManager();", activity)

    def test_migrates_legacy_enabled_feature_flags(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = {
                PATCH.FEATURE_LIST: root / PATCH.FEATURE_LIST,
                PATCH.JAVA_FEATURE_LIST: root / PATCH.JAVA_FEATURE_LIST,
                PATCH.CONFIG_UTILS: root / PATCH.CONFIG_UTILS,
                PATCH.CHROME_TABBED_ACTIVITY: root / PATCH.CHROME_TABBED_ACTIVITY,
            }
            for path in paths.values():
                path.parent.mkdir(parents=True, exist_ok=True)
            paths[PATCH.FEATURE_LIST].write_text(
                "// Helium: the bottom toolbar must be available on car head units as well.\n"
                "BASE_FEATURE(kAndroidBottomBar, base::FEATURE_ENABLED_BY_DEFAULT);\n"
            )
            paths[PATCH.JAVA_FEATURE_LIST].write_text(
                "    public static final CachedFlag sAndroidBottomBar =\n"
                "            newCachedFlag(ANDROID_BOTTOM_BAR, true, /* defaultValueInTests= */ true);\n"
                + DEFAULT_USER_ENABLED_SOURCE
            )
            paths[PATCH.CONFIG_UTILS].write_text(
                CONFIG_SOURCE.replace(
                    "return !DeviceFormFactor.isNonMultiDisplayContextOnTablet(context)\n"
                    "                && !DeviceInfo.isAutomotive()\n"
                    "                && ChromeFeatureList.sAndroidBottomBar.isEnabled();",
                    "// Helium: expose and allow the bottom toolbar on every old-android form factor.\n"
                    "        // The matching native feature is enabled by the old-android build patch.\n"
                    "        return true;",
                ).replace(
                    "return isBottomBarEligible(context)\n"
                    "                && ChromeFeatureList.sAndroidBottomBarShowSettingsToggle.getValue();",
                    "// Helium: keep the bottom toolbar option visible on every old-android device.\n"
                    "        return true;",
                )
            )
            paths[PATCH.CHROME_TABBED_ACTIVITY].write_text(ACTIVITY_SOURCE + HOST_METHOD_SOURCE)

            self.assertTrue(PATCH.patch_source_tree(temp))
            self.assertIn(PATCH.FEATURE_MARKER, paths[PATCH.FEATURE_LIST].read_text())
            self.assertIn(PATCH.JAVA_FLAG_MARKER, paths[PATCH.JAVA_FEATURE_LIST].read_text())
            migrated_config = paths[PATCH.CONFIG_UTILS].read_text()
            self.assertIn(PATCH.CONFIG_MARKER, migrated_config)
            self.assertIn("return false;", migrated_config)
            self.assertFalse(PATCH.patch_source_tree(temp))

    def test_migrates_existing_observer_block(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = self._write_sources(Path(temp))
            paths[PATCH.CHROME_TABBED_ACTIVITY].write_text(
                ACTIVITY_MIGRATED_SOURCE + HOST_METHOD_SOURCE
            )

            self.assertTrue(PATCH.patch_source_tree(temp))
            activity = paths[PATCH.CHROME_TABBED_ACTIVITY].read_text()
            self.assertIn(PATCH.ACTIVITY_OBSERVER_MARKER, activity)
            self.assertNotIn("BottomBarEnabledChangeObserver", activity)
            self.assertNotIn("bottom-toolbar setting.", activity)

    def test_migrates_v158_bottom_bar_observer_and_disables_host(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = self._write_sources(Path(temp))
            paths[PATCH.CHROME_TABBED_ACTIVITY].write_text(
                ACTIVITY_V158_SOURCE + HOST_METHOD_SOURCE
            )

            self.assertTrue(PATCH.patch_source_tree(temp))
            activity = paths[PATCH.CHROME_TABBED_ACTIVITY].read_text()
            self.assertNotIn("BottomBarEnabledChangeObserver", activity)
            self.assertNotIn("shouldObserveBottomBarEnabledChanges(this)", activity)
            self.assertIn(PATCH.BOTTOM_BAR_HOST_METHOD_MARKER, activity)
            self.assertIn("return null;", activity)
            self.assertNotIn("mBottomBarHostManager = new BottomBarHostManager();", activity)

    def test_preserves_explicit_default_user_setting_patch(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = self._write_sources(Path(temp))
            user_setting = paths[PATCH.JAVA_FEATURE_LIST]
            user_setting.write_text(
                user_setting.read_text().replace(
                    PATCH.DEFAULT_USER_ENABLED_OLD,
                    PATCH.DEFAULT_USER_ENABLED_NEW,
                )
            )

            self.assertTrue(PATCH.patch_source_tree(temp))
            self.assertIn(PATCH.DEFAULT_USER_ENABLED_MARKER, user_setting.read_text())

    def test_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = self._write_sources(Path(temp))
            self.assertTrue(PATCH.patch_source_tree(temp))
            patched = {key: path.read_text() for key, path in paths.items()}

            self.assertFalse(PATCH.patch_source_tree(temp))
            self.assertEqual(patched, {key: path.read_text() for key, path in paths.items()})


if __name__ == "__main__":
    unittest.main()
