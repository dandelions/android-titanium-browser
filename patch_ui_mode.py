#!/usr/bin/env python3
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
TAB_MODEL_OBSERVER_CC_REL = (
    "chrome/browser/ui/android/tab_model/tab_model_observer_jni_bridge.cc"
)
TAB_MODEL_OBSERVER_JAVA_REL = (
    "chrome/android/java/src/org/chromium/chrome/browser/tabmodel/TabModelObserverJniBridge.java"
)


def is_old_android_branch(src_dir: Path) -> bool:
    import subprocess

    script_dir = Path(__file__).resolve().parent
    for cwd in (script_dir, src_dir):
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                cwd=cwd,
                check=False,
            )
        except OSError:
            continue
        branch = result.stdout.strip()
        if branch in ("", "HEAD"):
            continue
        if branch in ("old-android", "old-version") or branch.startswith("old-"):
            return True
        if branch in ("main", "lemur", "lemur-style-app-menu"):
            return False

    import os
    return (
        os.environ.get("OLD_VERSION") == "1"
        or os.environ.get("OLD_ANDROID") == "1"
        or os.environ.get("CAR_COMPAT") == "1"
    )


def patch_device_form_factor(src_dir: Path) -> None:
    path = src_dir / DEVICE_FORM_FACTOR_REL
    if not path.exists():
        print(f"[patch_ui_mode] Notice: {path} not found, skipping DeviceFormFactor patch.")
        return

    text = path.read_text(encoding="utf-8")

    constants = """    public static final int UI_MODE_AUTO = 0;
    public static final int UI_MODE_MOBILE = 1;
    public static final int UI_MODE_DESKTOP = 2;
    public static final String PREF_UI_MODE = "helium_browser_ui_mode";
    public static final String PREF_UI_MODE_CRASH_COUNT = "helium_ui_mode_crash_count";
    public static final String PREF_UI_MODE_PENDING_VERIFY = "helium_ui_mode_pending_verify";

    private static boolean sCrashRecoveryChecked;

    private static void checkAndRecoverFromCrashIfNeeded() {
        if (sCrashRecoveryChecked) return;
        sCrashRecoveryChecked = true;
        try {
            android.content.SharedPreferences prefs = ContextUtils.getAppSharedPreferences();
            int mode = prefs.getInt(PREF_UI_MODE, UI_MODE_AUTO);
            if (mode != UI_MODE_AUTO) {
                boolean pendingVerify = prefs.getBoolean(PREF_UI_MODE_PENDING_VERIFY, false);
                int crashCount = prefs.getInt(PREF_UI_MODE_CRASH_COUNT, 0);
                if (pendingVerify && crashCount >= 1) {
                    android.util.Log.w("HeliumUiMode", "UI mode " + mode + " failed on previous run; recovering to default UI_MODE_AUTO");
                    prefs.edit()
                            .putInt(PREF_UI_MODE, UI_MODE_AUTO)
                            .putBoolean(PREF_UI_MODE_PENDING_VERIFY, false)
                            .putInt(PREF_UI_MODE_CRASH_COUNT, 0)
                            .commit();
                    return;
                }
                prefs.edit()
                        .putBoolean(PREF_UI_MODE_PENDING_VERIFY, true)
                        .putInt(PREF_UI_MODE_CRASH_COUNT, 1)
                        .commit();
            }
        } catch (Throwable ignored) {}
    }

    public static void markUiModeStartupSuccess() {
        try {
            android.content.SharedPreferences prefs = ContextUtils.getAppSharedPreferences();
            if (prefs.getBoolean(PREF_UI_MODE_PENDING_VERIFY, false)) {
                prefs.edit()
                        .putBoolean(PREF_UI_MODE_PENDING_VERIFY, false)
                        .putInt(PREF_UI_MODE_CRASH_COUNT, 0)
                        .commit();
            }
        } catch (Throwable ignored) {}
    }

    public static int getUiMode() {
        try {
            checkAndRecoverFromCrashIfNeeded();
            return ContextUtils.getAppSharedPreferences().getInt(PREF_UI_MODE, UI_MODE_AUTO);
        } catch (Throwable ignored) {
            return UI_MODE_AUTO;
        }
    }

    public static void setUiMode(int mode) {
        try {
            sCrashRecoveryChecked = true;
            android.content.SharedPreferences.Editor editor = ContextUtils.getAppSharedPreferences().edit();
            editor.putInt(PREF_UI_MODE, mode);
            if (mode == UI_MODE_AUTO) {
                editor.putBoolean(PREF_UI_MODE_PENDING_VERIFY, false);
                editor.putInt(PREF_UI_MODE_CRASH_COUNT, 0);
            } else {
                editor.putBoolean(PREF_UI_MODE_PENDING_VERIFY, true);
                editor.putInt(PREF_UI_MODE_CRASH_COUNT, 1);
            }
            editor.commit();
        } catch (Throwable ignored) {}
    }

    static {
        try {
            Thread.UncaughtExceptionHandler defaultHandler =
                    Thread.getDefaultUncaughtExceptionHandler();
            Thread.setDefaultUncaughtExceptionHandler((thread, throwable) -> {
                try {
                    int mode = ContextUtils.getAppSharedPreferences().getInt(PREF_UI_MODE, UI_MODE_AUTO);
                    if (mode != UI_MODE_AUTO) {
                        android.util.Log.e("HeliumUiMode", "Crash detected in UI mode " + mode + "; recovering default UI_MODE_AUTO", throwable);
                        ContextUtils.getAppSharedPreferences().edit()
                                .putInt(PREF_UI_MODE, UI_MODE_AUTO)
                                .putBoolean(PREF_UI_MODE_PENDING_VERIFY, false)
                                .putInt(PREF_UI_MODE_CRASH_COUNT, 0)
                                .commit();
                    }
                } catch (Throwable ignored) {}
                if (defaultHandler != null) {
                    defaultHandler.uncaughtException(thread, throwable);
                }
            });
        } catch (Throwable ignored) {}
    }
"""

    mode_start = text.find("    public static final int UI_MODE_AUTO = 0;")
    if mode_start >= 0:
        tablet_start = text.find("    public static boolean isTablet() {", mode_start)
        if tablet_start < 0:
            raise SystemExit(f"DeviceFormFactor UI mode block end not found in {path}")
        text = text[:mode_start] + constants + "\n\n" + text[tablet_start:]
    else:
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
    print(f"[patch_ui_mode] Patched {path} with UI mode and crash recovery")


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
    new_tablet_mode = """        int smallestWidth = DisplayUtil.getCurrentSmallestScreenWidth(this);
        boolean isTablet = DeviceFormFactor.isNonMultiDisplayContextOnTablet(this);
        boolean wasTablet = isTablet;"""
    if old_tablet_mode in text:
        text = text.replace(old_tablet_mode, new_tablet_mode, 1)

    incomplete_tablet_mode = """        boolean isTablet = DeviceFormFactor.isNonMultiDisplayContextOnTablet(this);
        boolean wasTablet = isTablet;"""
    if incomplete_tablet_mode in text and "int smallestWidth" not in text:
        # Restore the width calculation if a previous patch removed it.
        text = text.replace(incomplete_tablet_mode, new_tablet_mode, 1)

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

    startup_success_statement = (
        "        try { DeviceFormFactor.markUiModeStartupSuccess(); } "
        "catch (Throwable ignored) {}\n"
    )
    text = text.replace(startup_success_statement, "")
    if "DeviceFormFactor.markUiModeStartupSuccess();" not in text:
        native_start = text.find("    public void finishNativeInitialization() {")
        completion_anchor = "        super.finishNativeInitialization();\n"
        completion_pos = text.find(completion_anchor, native_start)
        if native_start < 0 or completion_pos < 0:
            raise SystemExit(f"finishNativeInitialization completion anchor not found in {path}")
        text = (
            text[: completion_pos + len(completion_anchor)]
            + "\n"
            + startup_success_statement
            + text[completion_pos + len(completion_anchor) :]
        )

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


def clean_ui_mode_from_standard_branches(src_dir: Path) -> None:
    """Removes UI mode patches from standard branches (main, lemur) as requested."""
    # 1. TabbedAppMenuPropertiesDelegate.java
    tabbed_path = src_dir / TABBED_DELEGATE_REL
    if tabbed_path.exists():
        text = tabbed_path.read_text(encoding="utf-8")
        if "modelList.add(buildUiModeItem());\n" in text:
            text = text.replace("        modelList.add(buildUiModeItem());\n", "")
        if "private ListItem buildUiModeItem()" in text:
            text = re.sub(r"    private ListItem buildUiModeChoiceItem\([\s\S]*?    private ListItem buildSettingsItem\(\) \{\n", "    private ListItem buildSettingsItem() {\n", text)
        tabbed_path.write_text(text, encoding="utf-8")

    from patch_lemur_app_menu import clean_ui_mode_from_lemur_menu

    clean_ui_mode_from_lemur_menu(tabbed_path)

    # 2. ChromeActivity.java
    act_path = src_dir / ACTIVITY_REL
    if act_path.exists():
        text = act_path.read_text(encoding="utf-8")
        if "R.id.ui_mode_auto_menu_id" in text:
            text = re.sub(r"        if \(id == R\.id\.ui_mode_auto_menu_id[\s\S]*?        if \(id == R\.id\.preferences_id\) \{\n", "        if (id == R.id.preferences_id) {\n", text)
        if "DeviceFormFactor.markUiModeStartupSuccess();" in text:
            text = text.replace("        try { DeviceFormFactor.markUiModeStartupSuccess(); } catch (Throwable ignored) {}\n", "")
        act_path.write_text(text, encoding="utf-8")

    # 3. ids.xml
    ids_path = src_dir / IDS_REL
    if ids_path.exists():
        text = ids_path.read_text(encoding="utf-8")
        for name in ("ui_mode_auto_menu_id", "ui_mode_mobile_menu_id", "ui_mode_desktop_menu_id", "ui_mode_menu_id"):
            text = text.replace(f'    <item type="id" name="{name}" />\n', "")
        ids_path.write_text(text, encoding="utf-8")

    # 4. DeviceFormFactor.java
    dff_path = src_dir / DEVICE_FORM_FACTOR_REL
    if dff_path.exists():
        text = dff_path.read_text(encoding="utf-8")
        mode_start = text.find("    public static final int UI_MODE_AUTO = 0;")
        if mode_start >= 0:
            tablet_start = text.find("    public static boolean isTablet() {", mode_start)
            if tablet_start < 0:
                raise SystemExit(f"DeviceFormFactor UI mode block end not found in {dff_path}")
            text = text[:mode_start] + text[tablet_start:]
            text = re.sub(r"    public static boolean isTablet\(\) \{\n[\s\S]*?\n    \}",
                          """    public static boolean isTablet() {
        if (sIsTabletForTesting != null) {
            return sIsTabletForTesting;
        }
        return detectScreenWidthBucket(ContextUtils.getApplicationContext())
                >= SCREEN_BUCKET_TABLET;
    }""", text, count=1)
            # Revert isNonMultiDisplayContextOnTablet
            text = re.sub(r"    public static boolean isNonMultiDisplayContextOnTablet\(Context context\) \{\n[\s\S]*?        return detectScreenWidthBucket\(context\) >= SCREEN_BUCKET_TABLET;\n    \}",
                          """    public static boolean isNonMultiDisplayContextOnTablet(Context context) {
        return detectScreenWidthBucket(context) >= SCREEN_BUCKET_TABLET;
    }""", text)
            # Revert isWindowOnTablet
            text = re.sub(r"    public static boolean isWindowOnTablet\(WindowAndroid windowAndroid\) \{\n[\s\S]*?        return detectScreenWidthBucket\(windowAndroid\) >= SCREEN_BUCKET_TABLET;\n    \}",
                          """    public static boolean isWindowOnTablet(WindowAndroid windowAndroid) {
        return detectScreenWidthBucket(windowAndroid) >= SCREEN_BUCKET_TABLET;
    }""", text)
            # Revert isNonMultiDisplayContextOnLargeTablet
            text = re.sub(r"    public static boolean isNonMultiDisplayContextOnLargeTablet\(Context context\) \{\n[\s\S]*?        return detectScreenWidthBucket\(context\) == SCREEN_BUCKET_LARGE_TABLET;\n    \}",
                          """    public static boolean isNonMultiDisplayContextOnLargeTablet(Context context) {
        return detectScreenWidthBucket(context) == SCREEN_BUCKET_LARGE_TABLET;
    }""", text)
        dff_path.write_text(text, encoding="utf-8")


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
        return !mIsWebApp;
    }"""
        if old_should_show in text:
            text = text.replace(old_should_show, new_should_show, 1)

        old_consumer = """        @Override
        public boolean hasSpaceToShow() {
            return mCanShowMenuIcon;
        }

        @Override
        public int updateVisibility(int availableWidth) {
            int puzzleButtonWidth =
                    mContainer.getResources().getDimensionPixelSize(R.dimen.toolbar_button_width);
            mCanShowMenuIcon = puzzleButtonWidth <= availableWidth;

            updateMenuIconVisibility();

            return shouldShowMenuIcon() ? puzzleButtonWidth : 0;
        }"""
        new_consumer = """        @Override
        public boolean hasSpaceToShow() {
            return true;
        }

        @Override
        public int updateVisibility(int availableWidth) {
            int puzzleButtonWidth =
                    mContainer.getResources().getDimensionPixelSize(R.dimen.toolbar_button_width);
            mCanShowMenuIcon = true;

            updateMenuIconVisibility();

            return shouldShowMenuIcon() ? puzzleButtonWidth : 0;
        }"""
        if old_consumer in text:
            text = text.replace(old_consumer, new_consumer, 1)

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


def patch_tab_model_observer_bridge(src_dir: Path) -> None:
    # 1. CC: Replace CHECK(tab); with safe null guard if (!tab) return;
    cc_path = src_dir / TAB_MODEL_OBSERVER_CC_REL
    if cc_path.exists():
        text = cc_path.read_text(encoding="utf-8")
        if "CHECK(tab);" in text:
            text = text.replace("  CHECK(tab);", "  if (!tab) return;")
            cc_path.write_text(text, encoding="utf-8")
            print(f"[patch_ui_mode] Patched {cc_path} to guard against null tab crash")

    # 2. Java: Replace assert tab.isInitialized(); with runtime guard
    java_path = src_dir / TAB_MODEL_OBSERVER_JAVA_REL
    if java_path.exists():
        text = java_path.read_text(encoding="utf-8")
        if "assert tab.isInitialized();" in text:
            text = text.replace(
                "        assert tab.isInitialized();",
                "        if (tab == null || !tab.isInitialized()) return;",
            )
            java_path.write_text(text, encoding="utf-8")
            print(f"[patch_ui_mode] Patched {java_path} to guard against uninitialized tab JNI calls")


def main() -> None:
    remove_only = len(sys.argv) > 1 and sys.argv[1] == "--remove-ui-mode"
    extensions_only = len(sys.argv) > 1 and sys.argv[1] == "--extensions-only"
    argument_index = 2 if (remove_only or extensions_only) else 1
    src_dir = Path(sys.argv[argument_index] if len(sys.argv) > argument_index else ".").resolve()
    if remove_only:
        clean_ui_mode_from_standard_branches(src_dir)
        print(f"[patch_ui_mode] Removed UI mode patches from {src_dir}")
        return
    if extensions_only:
        patch_extensions_visibility(src_dir)
        print(f"[patch_ui_mode] Applied extension visibility only to {src_dir}")
        return

    # Core stability & extensions visibility patches apply to all branches
    patch_extensions_visibility(src_dir)
    patch_tab_model_observer_bridge(src_dir)

    # UI Mode (Desktop/Mobile) is only added to old-version / old-android branch
    if is_old_android_branch(src_dir):
        patch_device_form_factor(src_dir)
        patch_ids(src_dir)
        patch_chrome_activity(src_dir)
        patch_tabbed_app_menu_delegate(src_dir)
        print(f"[patch_ui_mode] Applied UI mode with crash recovery to old-version branch in {src_dir}")
    else:
        clean_ui_mode_from_standard_branches(src_dir)
        print(f"[patch_ui_mode] Standard branch detected (main/lemur). Skipped UI mode patches.")


if __name__ == "__main__":
    main()
