#!/usr/bin/env python3
"""Expose address-bar settings and optional tab-strip hiding on old-android."""

from pathlib import Path
import sys


MAIN_SETTINGS = Path("chrome/android/java/src/org/chromium/chrome/browser/settings/MainSettings.java")
ADDRESS_BAR_FRAGMENT = Path(
    "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/settings/"
    "AddressBarSettingsFragment.java"
)
ADDRESS_BAR_XML = Path("chrome/browser/ui/android/toolbar/java/res/xml/address_bar_settings.xml")
ADDRESS_BAR_PREFERENCE = Path(
    "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/settings/"
    "AddressBarPreference.java"
)
TOOLBAR_MANAGER = Path("chrome/android/java/src/org/chromium/chrome/browser/toolbar/ToolbarManager.java")
STRINGS = Path("chrome/browser/ui/android/strings/android_chrome_strings.grd")

MAIN_OLD = """        return !DeviceInfo.isAutomotive()
                && (DeviceInfo.isFoldable()
                        || !DeviceFormFactor.isNonMultiDisplayContextOnTablet(context));"""
MAIN_NEW = """        // Helium: address bar position remains configurable in desktop and automotive modes.
        return true;"""
MAIN_MARKER = "Helium: address bar position remains configurable in desktop and automotive modes."

FRAGMENT_IMPORT_OLD = "import androidx.annotation.VisibleForTesting;\n\nimport org.chromium.base.DeviceInfo;\n"
FRAGMENT_IMPORT_NEW = """import androidx.annotation.VisibleForTesting;

import androidx.preference.Preference;

import org.chromium.base.DeviceInfo;
"""
FRAGMENT_METHOD_OLD = """        overrideDescriptionIfFoldable();
    }

    @Override
    public void onConfigurationChanged(Configuration newConfig) {
        super.onConfigurationChanged(newConfig);
        overrideDescriptionIfFoldable();
"""
FRAGMENT_METHOD_NEW = """        overrideDescriptionIfFoldable();
        updateHideDesktopTabsPreference();
    }

    @Override
    public void onConfigurationChanged(Configuration newConfig) {
        super.onConfigurationChanged(newConfig);
        overrideDescriptionIfFoldable();
        updateHideDesktopTabsPreference();
"""
FRAGMENT_UPDATE_ANCHOR = """    private void overrideDescriptionIfFoldable() {
"""
FRAGMENT_UPDATE_METHOD = """    private void updateHideDesktopTabsPreference() {
        Preference preference = findPreference("hide_desktop_tab_strip");
        if (preference != null) {
            preference.setVisible(DeviceFormFactor.getUiMode() == DeviceFormFactor.UI_MODE_DESKTOP);
        }
    }

"""
FRAGMENT_MARKER = "private void updateHideDesktopTabsPreference()"

ADDRESS_BAR_SET_OLD = """        sharedPreferencesManager.writeInt(ChromePreferenceKeys.TOOLBAR_TOP_ANCHORED, sharedPref);
"""
ADDRESS_BAR_SET_NEW = """        sharedPreferencesManager.writeInt(ChromePreferenceKeys.TOOLBAR_TOP_ANCHORED, sharedPref);
        // Helium: the address-bar choice also controls whether bottom controls are inflated.
        ChromeSharedPreferences.getInstance()
                .writeBoolean(
                        ChromePreferenceKeys.BOTTOM_BAR_ENABLED,
                        isToolbarAtBottom(sharedPref));
"""
ADDRESS_BAR_SET_MARKER = "Helium: the address-bar choice also controls whether bottom controls are inflated."

XML_ANCHOR = """    <org.chromium.chrome.browser.toolbar.settings.AddressBarPreference
        android:key="address_bar_preference"
        android:selectable="false"
        app:allowDividerAbove="false"
        app:allowDividerBelow="false" />
"""
XML_NEW = XML_ANCHOR + """
    <org.chromium.components.browser_ui.settings.ChromeSwitchPreference
        android:key="hide_desktop_tab_strip"
        android:title="@string/hide_desktop_tab_strip_title" />
"""
XML_MARKER = 'android:key="hide_desktop_tab_strip"'

MANAGER_IMPORT_OLD = "import android.content.SharedPreferences;\n"
MANAGER_IMPORT_NEW = """import android.content.SharedPreferences;
import android.content.SharedPreferences.OnSharedPreferenceChangeListener;
"""
MANAGER_CLASS_OLD = """                FuseboxControls {
"""
MANAGER_CLASS_NEW = """                FuseboxControls,
                OnSharedPreferenceChangeListener {
"""
MANAGER_PREF_KEY = "helium_hide_desktop_tab_strip"
MANAGER_INITIAL_HEIGHT_OLD = """        int initialTabStripHeight =
                suppressTabStripAtStart ? 0 : mToolbarLayout.getTabStripHeightFromResource();
"""
MANAGER_INITIAL_HEIGHT_NEW = f"""        int initialTabStripHeight =
                suppressTabStripAtStart || shouldHideDesktopTabStrip()
                        ? 0
                        : mToolbarLayout.getTabStripHeightFromResource();
"""
MANAGER_INIT_ANCHOR = """        mActivity = activity;
        mWindowAndroid = windowAndroid;
"""
MANAGER_INIT_NEW = f"""        mActivity = activity;
        ContextUtils.getAppSharedPreferences().registerOnSharedPreferenceChangeListener(this);
        mWindowAndroid = windowAndroid;
"""
MANAGER_NATIVE_ANCHOR = """        if (!BrowserControlsUtils.isForceTopChromeHeightAdjustmentOnStartupEnabled(mActivity)) {
            mTabStripTopControlLayer.set(mToolbar.getTabStripHeight());
        }
"""
MANAGER_NATIVE_NEW = """        if (!BrowserControlsUtils.isForceTopChromeHeightAdjustmentOnStartupEnabled(mActivity)) {
            mTabStripTopControlLayer.set(
                    shouldHideDesktopTabStrip() ? 0 : mToolbar.getTabStripHeight());
        }
"""
MANAGER_DESTROY_ANCHOR = """        mTabStripTopControlLayer.destroy();
"""
MANAGER_DESTROY_NEW = """        ContextUtils.getAppSharedPreferences().unregisterOnSharedPreferenceChangeListener(this);
        mTabStripTopControlLayer.destroy();
"""
MANAGER_METHOD_ANCHOR = """    /** Call to tear down all of the toolbar dependencies. */
"""
MANAGER_METHODS = f"""    private boolean shouldHideDesktopTabStrip() {{
        return org.chromium.ui.base.DeviceFormFactor.getUiMode()
                        == org.chromium.ui.base.DeviceFormFactor.UI_MODE_DESKTOP
                && ContextUtils.getAppSharedPreferences()
                        .getBoolean("{MANAGER_PREF_KEY}", false);
    }}

    @Override
    public void onSharedPreferenceChanged(SharedPreferences preferences, @Nullable String key) {{
        if ("{MANAGER_PREF_KEY}".equals(key)) {{
            mTabStripTopControlLayer.set(
                    shouldHideDesktopTabStrip() ? 0 : mToolbar.getTabStripHeight());
        }}
    }}

"""
MANAGER_MARKER = "private boolean shouldHideDesktopTabStrip()"

POSITION_CONTROLLER = Path(
    "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/"
    "ToolbarPositionController.java"
)
POSITION_OLD = """        return !isCustomTab
                && !DeviceInfo.isAutomotive()
                && !DeviceFormFactor.isNonMultiDisplayContextOnTablet(context);"""
POSITION_NEW = """        // Helium: desktop mode can use the bottom address bar on old-android.
        return !isCustomTab;"""
POSITION_MARKER = "Helium: desktop mode can use the bottom address bar on old-android."

STRING_ANCHOR = """      <message name="IDS_ADDRESS_BAR_SETTINGS_BOTTOM" desc="Title for the toggle that will show the address bar on the bottom. [CHAR_LIMIT=32]">
        Bottom
      </message>
"""
STRING_NEW = STRING_ANCHOR + """
      <message name="IDS_HIDE_DESKTOP_TAB_STRIP_TITLE" desc="Title for the setting that hides the desktop tab strip.">
        Hide desktop tab bar
      </message>
"""
STRING_MARKER = "IDS_HIDE_DESKTOP_TAB_STRIP_TITLE"


def replace_once(text: str, old: str, new: str, path: Path, marker: str) -> tuple[str, bool]:
    if marker in text:
        return text, False
    if text.count(old) != 1:
        raise SystemExit(f"Expected one patch anchor in {path}: {marker}")
    return text.replace(old, new, 1), True


def patch_file(root: Path, relative: Path, changes: tuple[tuple[str, str, str], ...]) -> bool:
    path = root / relative
    if not path.is_file():
        raise SystemExit(f"Expected Chromium file not found: {path}")
    text = path.read_text(encoding="utf-8")
    original = text
    for old, new, marker in changes:
        text, _ = replace_once(text, old, new, path, marker)
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def patch_source(root: Path) -> bool:
    changed = False
    changed |= patch_file(
        root, MAIN_SETTINGS, ((MAIN_OLD, MAIN_NEW, MAIN_MARKER),)
    )
    changed |= patch_file(
        root,
        ADDRESS_BAR_FRAGMENT,
        (
            (FRAGMENT_IMPORT_OLD, FRAGMENT_IMPORT_NEW, "import androidx.preference.Preference;"),
            (FRAGMENT_METHOD_OLD, FRAGMENT_METHOD_NEW, "updateHideDesktopTabsPreference();"),
            (FRAGMENT_UPDATE_ANCHOR, FRAGMENT_UPDATE_METHOD + FRAGMENT_UPDATE_ANCHOR, FRAGMENT_MARKER),
        ),
    )
    changed |= patch_file(root, ADDRESS_BAR_XML, ((XML_ANCHOR, XML_NEW, XML_MARKER),))
    changed |= patch_file(
        root,
        ADDRESS_BAR_PREFERENCE,
        ((ADDRESS_BAR_SET_OLD, ADDRESS_BAR_SET_NEW, ADDRESS_BAR_SET_MARKER),),
    )
    changed |= patch_file(
        root,
        TOOLBAR_MANAGER,
        (
            (MANAGER_IMPORT_OLD, MANAGER_IMPORT_NEW, "import android.content.SharedPreferences.OnSharedPreferenceChangeListener;"),
            (MANAGER_CLASS_OLD, MANAGER_CLASS_NEW, "OnSharedPreferenceChangeListener {"),
            (MANAGER_INITIAL_HEIGHT_OLD, MANAGER_INITIAL_HEIGHT_NEW, "shouldHideDesktopTabStrip()"),
            (MANAGER_INIT_ANCHOR, MANAGER_INIT_NEW, f'registerOnSharedPreferenceChangeListener(this);'),
            (MANAGER_NATIVE_ANCHOR, MANAGER_NATIVE_NEW, "shouldHideDesktopTabStrip() ? 0 : mToolbar.getTabStripHeight()"),
            (MANAGER_DESTROY_ANCHOR, MANAGER_DESTROY_NEW, "unregisterOnSharedPreferenceChangeListener(this)"),
            (MANAGER_METHOD_ANCHOR, MANAGER_METHODS + MANAGER_METHOD_ANCHOR, MANAGER_MARKER),
        ),
    )
    changed |= patch_file(root, STRINGS, ((STRING_ANCHOR, STRING_NEW, STRING_MARKER),))
    changed |= patch_file(root, POSITION_CONTROLLER, ((POSITION_OLD, POSITION_NEW, POSITION_MARKER),))
    return changed


if __name__ == "__main__":
    source_root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    changed = patch_source(source_root)
    print("Patched desktop tab-strip settings" if changed else "Desktop tab-strip settings already patched")
