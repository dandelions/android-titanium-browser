#!/usr/bin/env python3
"""Offer the bottom toolbar in every UI mode of the old-android build.

Chrome gates the "Show bottom toolbar" option on a phone, non-automotive form
factor and on a flag that is disabled by default, so the option never appears on
car head units and disappears after switching to the desktop UI mode. Enable the
flag and drop the form factor restrictions; the user's own switch in Settings
still decides whether the bottom toolbar is used.
"""
import os
import sys

FEATURE_LIST = "chrome/browser/flags/android/chrome_feature_list.cc"
FEATURE_OLD = "BASE_FEATURE(kAndroidBottomBar, base::FEATURE_DISABLED_BY_DEFAULT);"
FEATURE_NEW = """// Helium: the bottom toolbar must be available on car head units as well.
BASE_FEATURE(kAndroidBottomBar, base::FEATURE_ENABLED_BY_DEFAULT);"""
FEATURE_MARKER = "Helium: the bottom toolbar must be available"

JAVA_FEATURE_LIST = (
    "chrome/browser/flags/android/java/src/org/chromium/chrome/browser/flags/"
    "ChromeFeatureList.java"
)
JAVA_FLAG_OLD = """    public static final CachedFlag sAndroidBottomBar =
            newCachedFlag(ANDROID_BOTTOM_BAR, false, /* defaultValueInTests= */ true);
"""
JAVA_FLAG_NEW = """    public static final CachedFlag sAndroidBottomBar =
            newCachedFlag(ANDROID_BOTTOM_BAR, true, /* defaultValueInTests= */ true);
"""
JAVA_FLAG_MARKER = "newCachedFlag(ANDROID_BOTTOM_BAR, true, /* defaultValueInTests= */ true);"

CONFIG_UTILS = (
    "chrome/browser/ui/android/bottombar/java/src/org/chromium/chrome/browser/ui/"
    "bottombar/BottomBarConfigUtils.java"
)
ELIGIBLE_OLD = """        return !DeviceFormFactor.isNonMultiDisplayContextOnTablet(context)
                && !DeviceInfo.isAutomotive()
                && ChromeFeatureList.sAndroidBottomBar.isEnabled();
"""
ELIGIBLE_NEW = """        // Helium: expose and allow the bottom toolbar on every old-android form factor.
        // The matching native feature is enabled by the old-android build patch.
        return true;
"""
IMPORTS_OLD = """import org.chromium.base.DeviceInfo;
import org.chromium.build.annotations.NullMarked;
"""
IMPORTS_NEW = """import org.chromium.build.annotations.NullMarked;
"""
FORM_FACTOR_IMPORT_OLD = """import org.chromium.components.embedder_support.util.UrlUtilities;
import org.chromium.ui.base.DeviceFormFactor;
"""
FORM_FACTOR_IMPORT_NEW = """import org.chromium.components.embedder_support.util.UrlUtilities;
"""
CONFIG_MARKER = "Helium: expose and allow the bottom toolbar on every old-android form factor"
TOGGLE_OLD = """    public static boolean shouldShowSettingsToggle(Context context) {
        return isBottomBarEligible(context)
                && ChromeFeatureList.sAndroidBottomBarShowSettingsToggle.getValue();
    }

"""
TOGGLE_NEW = """    public static boolean shouldShowSettingsToggle(Context context) {
        // Helium: keep the bottom toolbar option visible on every old-android device.
        return true;
    }
"""
TOGGLE_MARKER = "Helium: keep the bottom toolbar option visible on every old-android device."


def patch_feature_list(src_dir: str) -> bool:
    path = os.path.join(src_dir, FEATURE_LIST)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read()

    if FEATURE_MARKER in content:
        return False
    if FEATURE_OLD not in content:
        raise RuntimeError(f"bottom bar feature definition not found in {path}")

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content.replace(FEATURE_OLD, FEATURE_NEW, 1))
    print(f"Patched old-android bottom bar feature flag: {path}")
    return True


def patch_java_feature_flag(src_dir: str) -> bool:
    path = os.path.join(src_dir, JAVA_FEATURE_LIST)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read()

    if JAVA_FLAG_MARKER in content:
        return False
    if content.count(JAVA_FLAG_OLD) != 1:
        raise RuntimeError(f"bottom bar Java feature flag not found in {path}")

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content.replace(JAVA_FLAG_OLD, JAVA_FLAG_NEW, 1))
    print(f"Patched old-android bottom bar Java feature flag: {path}")
    return True


def patch_config_utils(src_dir: str) -> bool:
    path = os.path.join(src_dir, CONFIG_UTILS)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read()

    if CONFIG_MARKER in content and TOGGLE_MARKER in content:
        return False
    for anchor in (ELIGIBLE_OLD, IMPORTS_OLD, FORM_FACTOR_IMPORT_OLD, TOGGLE_OLD):
        if content.count(anchor) != 1:
            raise RuntimeError(f"bottom bar eligibility anchor not found in {path}: {anchor!r}")

    content = content.replace(ELIGIBLE_OLD, ELIGIBLE_NEW, 1)
    content = content.replace(IMPORTS_OLD, IMPORTS_NEW, 1)
    content = content.replace(FORM_FACTOR_IMPORT_OLD, FORM_FACTOR_IMPORT_NEW, 1)
    content = content.replace(TOGGLE_OLD, TOGGLE_NEW, 1)

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    print(f"Patched old-android bottom bar eligibility: {path}")
    return True


def patch_source_tree(src_dir: str) -> bool:
    feature_changed = patch_feature_list(src_dir)
    java_flag_changed = patch_java_feature_flag(src_dir)
    config_changed = patch_config_utils(src_dir)
    return feature_changed or java_flag_changed or config_changed


if __name__ == "__main__":
    try:
        patch_source_tree(sys.argv[1] if len(sys.argv) > 1 else ".")
    except (FileNotFoundError, RuntimeError) as error:
        print(f"[patch_old_android_bottom_toolbar] {error}", file=sys.stderr)
        raise SystemExit(1)
