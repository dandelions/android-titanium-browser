#!/usr/bin/env python3
"""Avoid an Android 9 desktop-mode layout-parameter cast during toolbar startup."""

from pathlib import Path
import sys


LOCATION_BAR_TABLET = Path(
    "chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/LocationBarTablet.java"
)
TOOLBAR_MANAGER = Path(
    "chrome/android/java/src/org/chromium/chrome/browser/toolbar/ToolbarManager.java"
)
TOOLBAR_PHONE = Path(
    "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/top/"
    "ToolbarPhone.java"
)
# An earlier build forced the toolbar omnibox onto the native NTP. The home page is supposed to
# keep it hidden and spread the buttons instead, so restore the original delegate lookup.
NTP_FORCED_OMNIBOX = """    @VisibleForTesting
    boolean isLocationBarShownInNtp() {
        // Helium: keep the toolbar omnibox visible on the native NTP. The default home page
        // used the page's fake search box instead, which left the toolbar without an address
        // bar, while extension-provided home pages showed one.
        return false;
    }
"""
NTP_ORIGINAL_OMNIBOX = """    @VisibleForTesting
    boolean isLocationBarShownInNtp() {
        return getToolbarDataProvider().getNewTabPageDelegate().isLocationBarShown();
    }
"""
METHOD_ANCHOR = "    private void adjustBackgroundForSuggestions() {\n"
GUARD = """        // Helium: desktop-mode activity recreation can briefly leave this view attached
        // with LinearLayout.LayoutParams before it returns to its FrameLayout holder.
        if (!(getLayoutParams() instanceof FrameLayout.LayoutParams)) {
            return;
        }

"""
MARKER = "Helium: desktop-mode activity recreation can briefly leave this view attached"
TOOLBAR_MARKER = "Helium: skip transient desktop-mode toolbar layout parameters"
TOOLBAR_PROGRESS_ANCHOR = """            CoordinatorLayout.LayoutParams progressBarParams =
                    (CoordinatorLayout.LayoutParams) progressBarStub.getLayoutParams();
            progressBarParams.gravity = Gravity.BOTTOM;
            progressBarStub.setLayoutParams(progressBarParams);
"""
TOOLBAR_PROGRESS_OLD_GUARD = """            if (!(progressBarStub.getLayoutParams() instanceof CoordinatorLayout.LayoutParams)) {
                return;
            }
            // Helium: skip transient desktop-mode toolbar layout parameters.
            CoordinatorLayout.LayoutParams progressBarParams =
                    (CoordinatorLayout.LayoutParams) progressBarStub.getLayoutParams();
            progressBarParams.gravity = Gravity.BOTTOM;
            progressBarStub.setLayoutParams(progressBarParams);
"""
TOOLBAR_PROGRESS_GUARD = """            // Helium: skip transient desktop-mode toolbar layout parameters.
            if (progressBarStub.getLayoutParams() instanceof CoordinatorLayout.LayoutParams) {
                CoordinatorLayout.LayoutParams progressBarParams =
                        (CoordinatorLayout.LayoutParams) progressBarStub.getLayoutParams();
                progressBarParams.gravity = Gravity.BOTTOM;
                progressBarStub.setLayoutParams(progressBarParams);
            }
"""
TOOLBAR_MARGIN_ANCHOR = """        final ViewGroup.MarginLayoutParams layoutParams =
                ((ViewGroup.MarginLayoutParams) mControlContainer.getLayoutParams());
"""
TOOLBAR_MARGIN_GUARD = """        if (!(mControlContainer.getLayoutParams() instanceof ViewGroup.MarginLayoutParams)) {
            return;
        }
        final ViewGroup.MarginLayoutParams layoutParams =
                ((ViewGroup.MarginLayoutParams) mControlContainer.getLayoutParams());
"""
TOOLBAR_TABLET_MARGIN_MARKER = "Helium: skip transient desktop-mode toolbar-tablet layout parameters"
TOOLBAR_TABLET_MARGIN_ANCHOR = """        var lp = (ViewGroup.MarginLayoutParams) toolbarTabletLayout.getLayoutParams();
"""
TOOLBAR_TABLET_MARGIN_GUARD = """        // Helium: skip transient desktop-mode toolbar-tablet layout parameters.
        if (!(toolbarTabletLayout.getLayoutParams() instanceof ViewGroup.MarginLayoutParams)) {
            return;
        }
        var lp = (ViewGroup.MarginLayoutParams) toolbarTabletLayout.getLayoutParams();
"""
def patch_source(root: Path) -> bool:
    path = root / LOCATION_BAR_TABLET
    toolbar_path = root / TOOLBAR_MANAGER
    toolbar_phone_path = root / TOOLBAR_PHONE
    for expected in (path, toolbar_path, toolbar_phone_path):
        if not expected.is_file():
            raise SystemExit(f"Expected Chromium file not found: {expected}")

    text = path.read_text(encoding="utf-8")
    changed = False
    if MARKER not in text:
        if text.count(METHOD_ANCHOR) != 1:
            raise SystemExit(f"Expected one LocationBarTablet anchor in {path}")
        text = text.replace(METHOD_ANCHOR, METHOD_ANCHOR + GUARD, 1)
        path.write_text(text, encoding="utf-8")
        changed = True

    toolbar_text = toolbar_path.read_text(encoding="utf-8")
    unguarded_toolbar_text = toolbar_text.replace(TOOLBAR_TABLET_MARGIN_GUARD, "")
    toolbar_tablet_margin_count = unguarded_toolbar_text.count(TOOLBAR_TABLET_MARGIN_ANCHOR)
    if toolbar_tablet_margin_count:
        if toolbar_tablet_margin_count != 2:
            raise SystemExit(
                f"Expected two ToolbarManager toolbar-tablet margin anchors in {toolbar_path}, "
                f"found {toolbar_tablet_margin_count}"
            )
        toolbar_text = toolbar_text.replace(
            TOOLBAR_TABLET_MARGIN_ANCHOR, TOOLBAR_TABLET_MARGIN_GUARD
        )
        changed = True

    if toolbar_text.count(TOOLBAR_PROGRESS_OLD_GUARD) == 1:
        toolbar_text = toolbar_text.replace(
            TOOLBAR_PROGRESS_OLD_GUARD, TOOLBAR_PROGRESS_GUARD, 1
        )
        if toolbar_text.count(TOOLBAR_MARGIN_ANCHOR) != 1:
            raise SystemExit(f"Expected one ToolbarManager margin anchor in {toolbar_path}")
        toolbar_text = toolbar_text.replace(TOOLBAR_MARGIN_ANCHOR, TOOLBAR_MARGIN_GUARD, 1)
        toolbar_path.write_text(toolbar_text, encoding="utf-8")
        changed = True
    elif TOOLBAR_MARKER not in toolbar_text:
        if toolbar_text.count(TOOLBAR_PROGRESS_ANCHOR) != 1:
            raise SystemExit(f"Expected one ToolbarManager progress-bar anchor in {toolbar_path}")
        if toolbar_text.count(TOOLBAR_MARGIN_ANCHOR) != 1:
            raise SystemExit(f"Expected one ToolbarManager margin anchor in {toolbar_path}")
        toolbar_text = toolbar_text.replace(
            TOOLBAR_PROGRESS_ANCHOR, TOOLBAR_PROGRESS_GUARD, 1
        )
        toolbar_text = toolbar_text.replace(TOOLBAR_MARGIN_ANCHOR, TOOLBAR_MARGIN_GUARD, 1)
        changed = True

    if changed:
        toolbar_path.write_text(toolbar_text, encoding="utf-8")

    phone_text = toolbar_phone_path.read_text(encoding="utf-8")
    if NTP_FORCED_OMNIBOX in phone_text:
        phone_text = phone_text.replace(NTP_FORCED_OMNIBOX, NTP_ORIGINAL_OMNIBOX, 1)
        toolbar_phone_path.write_text(phone_text, encoding="utf-8")
        changed = True

    return changed


if __name__ == "__main__":
    source_root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    changed = patch_source(source_root)
    print(
        "Patched old-android LocationBarTablet layout guard"
        if changed
        else "Old-android LocationBarTablet layout guard already patched"
    )
