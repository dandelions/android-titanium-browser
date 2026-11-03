#!/usr/bin/env python3
import os
from pathlib import Path
import re
import sys


DEVICE_FORM_FACTOR_REL = "ui/android/java/src/org/chromium/ui/base/DeviceFormFactor.java"
IDS_REL = "chrome/android/java/res/values/ids.xml"
ACTIVITY_REL = "chrome/android/java/src/org/chromium/chrome/browser/app/ChromeActivity.java"
TABBED_DELEGATE_REL = (
    "chrome/android/java/src/org/chromium/chrome/browser/tabbed_mode/"
    "TabbedAppMenuPropertiesDelegate.java"
)
EXT_TOOLBAR_COORD_IMPL_REL = (
    "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/"
    "ExtensionsToolbarCoordinatorImpl.java"
)
APP_MENU_DELEGATE_IMPL_REL = (
    "chrome/android/java/src/org/chromium/chrome/browser/app/appmenu/"
    "AppMenuPropertiesDelegateImpl.java"
)


def patch_device_form_factor(src_dir: Path) -> None:
    path = src_dir / DEVICE_FORM_FACTOR_REL
    if not path.exists():
        print(f"[patch_ui_mode] Notice: {path} not found, skipping DeviceFormFactor patch.")
        return

    text = path.read_text(encoding="utf-8")
    if "UI_MODE_AUTO" in text:
        return

    constants = """    public static final int UI_MODE_AUTO = 0;
    public static final int UI_MODE_MOBILE = 1;
    public static final int UI_MODE_DESKTOP = 2;
    public static final String PREF_UI_MODE = "helium_browser_ui_mode";

    public static int getUiMode() {
        try {
            return ContextUtils.getAppSharedPreferences().getInt(PREF_UI_MODE, UI_MODE_AUTO);
        } catch (Throwable ignored) {
            return UI_MODE_AUTO;
        }
    }

    public static void setUiMode(int mode) {
        try {
            ContextUtils.getAppSharedPreferences().edit().putInt(PREF_UI_MODE, mode).apply();
        } catch (Throwable ignored) {}
    }
"""

    class_anchor = "public class DeviceFormFactor {\n"
    if class_anchor not in text:
        raise SystemExit(f"DeviceFormFactor class anchor not found in {path}")
    text = text.replace(class_anchor, class_anchor + constants + "\n", 1)

    old_is_tablet = """    public static boolean isTablet() {
        if (sIsTabletForTesting != null) {
            return sIsTabletForTesting;
        }
        return detectScreenWidthBucket(ContextUtils.getApplicationContext())
                >= SCREEN_BUCKET_TABLET;
    }"""
    new_is_tablet = """    public static boolean isTablet() {
        if (sIsTabletForTesting != null) {
            return sIsTabletForTesting;
        }
        int mode = getUiMode();
        if (mode == UI_MODE_MOBILE) return false;
        if (mode == UI_MODE_DESKTOP) return true;
        return detectScreenWidthBucket(ContextUtils.getApplicationContext())
                >= SCREEN_BUCKET_TABLET;
    }"""
    if old_is_tablet in text:
        text = text.replace(old_is_tablet, new_is_tablet, 1)

    old_is_nmd = """    public static boolean isNonMultiDisplayContextOnTablet(Context context) {
        return detectScreenWidthBucket(context) >= SCREEN_BUCKET_TABLET;
    }"""
    new_is_nmd = """    public static boolean isNonMultiDisplayContextOnTablet(Context context) {
        int mode = getUiMode();
        if (mode == UI_MODE_MOBILE) return false;
        if (mode == UI_MODE_DESKTOP) return true;
        return detectScreenWidthBucket(context) >= SCREEN_BUCKET_TABLET;
    }"""
    if old_is_nmd in text:
        text = text.replace(old_is_nmd, new_is_nmd, 1)

    old_is_window = """    public static boolean isWindowOnTablet(WindowAndroid windowAndroid) {
        return detectScreenWidthBucket(windowAndroid) >= SCREEN_BUCKET_TABLET;
    }"""
    new_is_window = """    public static boolean isWindowOnTablet(WindowAndroid windowAndroid) {
        int mode = getUiMode();
        if (mode == UI_MODE_MOBILE) return false;
        if (mode == UI_MODE_DESKTOP) return true;
        return detectScreenWidthBucket(windowAndroid) >= SCREEN_BUCKET_TABLET;
    }"""
    if old_is_window in text:
        text = text.replace(old_is_window, new_is_window, 1)

    old_is_large = """    public static boolean isNonMultiDisplayContextOnLargeTablet(Context context) {
        return detectScreenWidthBucket(context) == SCREEN_BUCKET_LARGE_TABLET;
    }"""
    new_is_large = """    public static boolean isNonMultiDisplayContextOnLargeTablet(Context context) {
        int mode = getUiMode();
        if (mode == UI_MODE_MOBILE) return false;
        if (mode == UI_MODE_DESKTOP) return true;
        return detectScreenWidthBucket(context) == SCREEN_BUCKET_LARGE_TABLET;
    }"""
    if old_is_large in text:
        text = text.replace(old_is_large, new_is_large, 1)

    path.write_text(text, encoding="utf-8")
    print(f"[patch_ui_mode] Patched {path}")


def patch_ids(src_dir: Path) -> None:
    path = src_dir / IDS_REL
    if not path.exists():
        print(f"[patch_ui_mode] Notice: {path} not found, skipping IDs patch.")
        return

    text = path.read_text(encoding="utf-8")
    anchor = '    <item type="id" name="preferences_id" />'
    if anchor not in text:
        anchor = '<item type="id" name="preferences_id" />'
    if anchor not in text:
        # Fallback to any menu item anchor
        anchor = '<item type="id" name="all_bookmarks_menu_id" />'
    if anchor not in text:
        raise SystemExit(f"Menu ID anchor not found in {path}")

    for name in (
        "ui_mode_auto_menu_id",
        "ui_mode_mobile_menu_id",
        "ui_mode_desktop_menu_id",
        "ui_mode_menu_id",
    ):
        if f'name="{name}"' not in text:
            text = text.replace(anchor, f'    <item type="id" name="{name}" />\n' + anchor, 1)

    path.write_text(text, encoding="utf-8")
    print(f"[patch_ui_mode] Patched {path}")


def patch_chrome_activity(src_dir: Path) -> None:
    path = src_dir / ACTIVITY_REL
    if not path.exists():
        print(f"[patch_ui_mode] Notice: {path} not found, skipping ChromeActivity patch.")
        return

    text = path.read_text(encoding="utf-8")

    # In getTabletMode():
    old_tablet_mode = """        int smallestWidth = DisplayUtil.getCurrentSmallestScreenWidth(this);
        boolean isTablet = smallestWidth >= DeviceFormFactor.MINIMUM_TABLET_WIDTH_DP;
        boolean wasTablet =
                mConfig.smallestScreenWidthDp >= DeviceFormFactor.MINIMUM_TABLET_WIDTH_DP;"""
    new_tablet_mode = """        boolean isTablet = DeviceFormFactor.isNonMultiDisplayContextOnTablet(this);
        boolean wasTablet = isTablet;"""
    if old_tablet_mode in text:
        text = text.replace(old_tablet_mode, new_tablet_mode, 1)

    # In onMenuOrKeyboardAction:
    ui_handler = """        if (id == R.id.ui_mode_auto_menu_id
                || id == R.id.ui_mode_mobile_menu_id
                || id == R.id.ui_mode_desktop_menu_id
                || id == R.id.ui_mode_menu_id) {
            int targetMode;
            if (id == R.id.ui_mode_mobile_menu_id) {
                targetMode = DeviceFormFactor.UI_MODE_MOBILE;
            } else if (id == R.id.ui_mode_desktop_menu_id) {
                targetMode = DeviceFormFactor.UI_MODE_DESKTOP;
            } else if (id == R.id.ui_mode_auto_menu_id) {
                targetMode = DeviceFormFactor.UI_MODE_AUTO;
            } else {
                int cur = DeviceFormFactor.getUiMode();
                targetMode = (cur == DeviceFormFactor.UI_MODE_AUTO)
                        ? (DeviceFormFactor.isNonMultiDisplayContextOnTablet(this)
                                ? DeviceFormFactor.UI_MODE_MOBILE
                                : DeviceFormFactor.UI_MODE_DESKTOP)
                        : (cur == DeviceFormFactor.UI_MODE_MOBILE
                                ? DeviceFormFactor.UI_MODE_DESKTOP
                                : DeviceFormFactor.UI_MODE_MOBILE);
            }
            if (targetMode != DeviceFormFactor.getUiMode()) {
                DeviceFormFactor.setUiMode(targetMode);
                try {
                    if (mTabReparentingControllerSupplier != null
                            && mTabReparentingControllerSupplier.get() != null) {
                        mTabReparentingControllerSupplier.get().prepareTabsForReparenting();
                    }
                } catch (Throwable ignored) {}
                recreate();
            }
            RecordUserAction.record("MobileMenuUiModeChange");
            return true;
        }

"""
    if "R.id.ui_mode_auto_menu_id" not in text:
        handler_anchor = "        if (id == R.id.preferences_id) {\n"
        if handler_anchor in text:
            text = text.replace(handler_anchor, ui_handler + handler_anchor, 1)

    path.write_text(text, encoding="utf-8")
    print(f"[patch_ui_mode] Patched {path}")


def patch_tabbed_app_menu_delegate(src_dir: Path) -> None:
    path = src_dir / TABBED_DELEGATE_REL
    if not path.exists():
        print(f"[patch_ui_mode] Notice: {path} not found, skipping TabbedAppMenuPropertiesDelegate patch.")
        return

    text = path.read_text(encoding="utf-8")

    ui_methods = """    private ListItem buildUiModeChoiceItem(int id, String title) {
        return AppMenuItemUtils.createStandardListItem(
                AppMenuItemUtils.buildBaseModelForTextItem(
                                getAppMenuItemTheme(), id, isMenuIconAtStart())
                        .with(AppMenuItemProperties.TITLE, title)
                        .build(),
                /* showIcon= */ false);
    }

    private ListItem buildUiModeItem() {
        int currentMode = DeviceFormFactor.getUiMode();
        boolean isTabletUi = DeviceFormFactor.isNonMultiDisplayContextOnTablet(mContext);
        String currentModeDesc;
        if (currentMode == DeviceFormFactor.UI_MODE_MOBILE) {
            currentModeDesc = " (移动版)";
        } else if (currentMode == DeviceFormFactor.UI_MODE_DESKTOP) {
            currentModeDesc = " (桌面版)";
        } else {
            currentModeDesc = " (自动: " + (isTabletUi ? "桌面版" : "移动版") + ")";
        }

        List<ListItem> submenuItems = new ArrayList<>();
        submenuItems.add(
                buildUiModeChoiceItem(
                        R.id.ui_mode_auto_menu_id,
                        (currentMode == DeviceFormFactor.UI_MODE_AUTO ? "✓ " : "   ")
                                + "跟随系统（自动识别）"));
        submenuItems.add(
                buildUiModeChoiceItem(
                        R.id.ui_mode_mobile_menu_id,
                        (currentMode == DeviceFormFactor.UI_MODE_MOBILE ? "✓ " : "   ")
                                + "移动版（手机界面：底部工具栏）"));
        submenuItems.add(
                buildUiModeChoiceItem(
                        R.id.ui_mode_desktop_menu_id,
                        (currentMode == DeviceFormFactor.UI_MODE_DESKTOP ? "✓ " : "   ")
                                + "桌面版（平板/电脑：顶部标签栏）"));

        return new ListItem(
                AppMenuHandler.AppMenuItemType.MENU_ITEM_WITH_SUBMENU,
                AppMenuItemUtils.buildModelForMenuItemWithSubmenu(
                        mContext,
                        getAppMenuItemTheme(),
                        R.id.ui_mode_menu_id,
                        "界面模式" + currentModeDesc,
                        Resources.ID_NULL,
                        () -> submenuItems,
                        isMenuIconAtStart()));
    }

"""
    if "private ListItem buildUiModeItem()" not in text:
        settings_anchor = "    private ListItem buildSettingsItem() {\n"
        if settings_anchor in text:
            text = text.replace(settings_anchor, ui_methods + settings_anchor, 1)

    if "modelList.add(buildUiModeItem());" not in text:
        if "modelList.add(buildAppearanceItem());" in text:
            text = text.replace(
                "        modelList.add(buildAppearanceItem());\n        modelList.add(buildSettingsItem());",
                "        modelList.add(buildAppearanceItem());\n        modelList.add(buildUiModeItem());\n        modelList.add(buildSettingsItem());",
            )
        else:
            text = text.replace(
                "        modelList.add(buildSettingsItem());",
                "        modelList.add(buildUiModeItem());\n        modelList.add(buildSettingsItem());",
            )

    path.write_text(text, encoding="utf-8")
    print(f"[patch_ui_mode] Patched {path}")


def patch_extensions_visibility(src_dir: Path) -> None:
    # 1. ExtensionsToolbarCoordinatorImpl.java: ensure extensions button is pinned and visible
    ext_path = src_dir / EXT_TOOLBAR_COORD_IMPL_REL
    if ext_path.exists():
        text = ext_path.read_text(encoding="utf-8")
        old_pinned = "return mPrefService.getBoolean(Pref.PIN_EXTENSIONS_MENU_BUTTON);"
        new_pinned = "return true; // Helium: Extensions button pinned by default"
        if old_pinned in text:
            text = text.replace(old_pinned, new_pinned, 1)

        old_should_show = """    private boolean shouldShowMenuIcon() {
        return mExtensionsMenuCoordinator.isExtensionsMenuOpen()
                || mShowExtensionsMenuPending
                || (mCanShowMenuIcon && isMenuButtonPinned());
    }"""
        new_should_show = """    private boolean shouldShowMenuIcon() {
        return !mIsWebApp && mCanShowMenuIcon;
    }"""
        if old_should_show in text:
            text = text.replace(old_should_show, new_should_show, 1)

        ext_path.write_text(text, encoding="utf-8")
        print(f"[patch_ui_mode] Patched {ext_path} to keep extensions button visible")

    # 2. AppMenuPropertiesDelegateImpl.java: ensure extensions item is shown in menu
    menu_path = src_dir / APP_MENU_DELEGATE_IMPL_REL
    if menu_path.exists():
        text = menu_path.read_text(encoding="utf-8")
        old_show_ext = """    protected boolean shouldShowExtensionsItem() {
        Profile profile = getProfileFromTabModel();
        return profile != null && ExtensionUi.isEnabled(profile);
    }"""
        new_show_ext = """    protected boolean shouldShowExtensionsItem() {
        return true;
    }"""
        if old_show_ext in text:
            text = text.replace(old_show_ext, new_show_ext, 1)

        menu_path.write_text(text, encoding="utf-8")
        print(f"[patch_ui_mode] Patched {menu_path} to make extensions menu entry always visible")


def main() -> None:
    src_dir = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    patch_device_form_factor(src_dir)
    patch_ids(src_dir)
    patch_chrome_activity(src_dir)
    patch_tabbed_app_menu_delegate(src_dir)
    patch_extensions_visibility(src_dir)
    print(f"[patch_ui_mode] Successfully applied UI mode & Extensions patches to {src_dir}")


if __name__ == "__main__":
    main()
