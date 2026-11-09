#!/usr/bin/env python3
"""Prevent bottom toolbar location bar from expanding over buttons on NTP."""

from pathlib import Path
import sys


TOOLBAR_PHONE_PATH = Path(
    "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/top/ToolbarPhone.java"
)

COMPUTE_VISUAL_STATE_OLD = """    private @VisualState int computeVisualState() {
        if (isLocationBarShownInNtp()) return VisualState.NEW_TAB_NORMAL;
        if (isLocationBarShownInGeneralNtp()) {
            return VisualState.NEW_TAB_SEARCH_ENGINE_NO_LOGO;
        }
        if (isIncognitoBranded()) return VisualState.INCOGNITO;
        if (getToolbarDataProvider().isUsingBrandColor()) return VisualState.BRAND_COLOR;
        return VisualState.NORMAL;
    }"""

COMPUTE_VISUAL_STATE_NEW = """    private boolean isBottomToolbar() {
        if (mBrowserControlsStateProvider != null) {
            return mBrowserControlsStateProvider.getControlsPosition() == ControlsPosition.BOTTOM;
        }
        return !org.chromium.chrome.browser.toolbar.settings.AddressBarPreference.isToolbarConfiguredToShowOnTop();
    }

    private @VisualState int computeVisualState() {
        if (isBottomToolbar()) {
            if (isIncognitoBranded()) return VisualState.INCOGNITO;
            if (getToolbarDataProvider().isUsingBrandColor()) return VisualState.BRAND_COLOR;
            return VisualState.NORMAL;
        }
        if (isLocationBarShownInNtp()) return VisualState.NEW_TAB_NORMAL;
        if (isLocationBarShownInGeneralNtp()) {
            return VisualState.NEW_TAB_SEARCH_ENGINE_NO_LOGO;
        }
        if (isIncognitoBranded()) return VisualState.INCOGNITO;
        if (getToolbarDataProvider().isUsingBrandColor()) return VisualState.BRAND_COLOR;
        return VisualState.NORMAL;
    }"""

LEFT_BOUNDS_OLD = """        if (visualState == VisualState.NEW_TAB_NORMAL && mTabSwitcherState == STATIC_TAB) {
            return mToolbarSidePaddingForNtp;"""

LEFT_BOUNDS_NEW = """        if (!isBottomToolbar() && visualState == VisualState.NEW_TAB_NORMAL && mTabSwitcherState == STATIC_TAB) {
            return mToolbarSidePaddingForNtp;"""

RIGHT_BOUNDS_OLD = """        if (visualState == VisualState.NEW_TAB_NORMAL && mTabSwitcherState == STATIC_TAB) {
            return getMeasuredWidth() - mToolbarSidePaddingForNtp;"""

RIGHT_BOUNDS_NEW = """        if (!isBottomToolbar() && visualState == VisualState.NEW_TAB_NORMAL && mTabSwitcherState == STATIC_TAB) {
            return getMeasuredWidth() - mToolbarSidePaddingForNtp;"""

LAYOUT_WITHOUT_ANIM_OLD = """        if (mLayoutLocationBarInFocusedMode
                || (mVisualState == VisualState.NEW_TAB_NORMAL
                        && mTabSwitcherState == STATIC_TAB)) {"""

LAYOUT_WITHOUT_ANIM_NEW = """        if (mLayoutLocationBarInFocusedMode
                || (!isBottomToolbar()
                        && mVisualState == VisualState.NEW_TAB_NORMAL
                        && mTabSwitcherState == STATIC_TAB)) {"""


def patch_toolbar_phone(path: Path) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    original = text

    if "private boolean isBottomToolbar()" not in text:
        if COMPUTE_VISUAL_STATE_OLD not in text:
            raise SystemExit(f"computeVisualState anchor not found in {path}")
        text = text.replace(COMPUTE_VISUAL_STATE_OLD, COMPUTE_VISUAL_STATE_NEW, 1)

    if LEFT_BOUNDS_OLD in text:
        text = text.replace(LEFT_BOUNDS_OLD, LEFT_BOUNDS_NEW, 1)

    if RIGHT_BOUNDS_OLD in text:
        text = text.replace(RIGHT_BOUNDS_OLD, RIGHT_BOUNDS_NEW, 1)

    if LAYOUT_WITHOUT_ANIM_OLD in text:
        text = text.replace(LAYOUT_WITHOUT_ANIM_OLD, LAYOUT_WITHOUT_ANIM_NEW, 1)

    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


if __name__ == "__main__":
    source_root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    changed = patch_toolbar_phone(source_root / TOOLBAR_PHONE_PATH)
    print("Patched ToolbarPhone to prevent bottom toolbar overlap on NTP" if changed else
          "ToolbarPhone bottom toolbar bounds already active")
