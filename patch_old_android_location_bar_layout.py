#!/usr/bin/env python3
"""Avoid an Android 9 desktop-mode layout-parameter cast during toolbar startup."""

from pathlib import Path
import sys


LOCATION_BAR_TABLET = Path(
    "chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/LocationBarTablet.java"
)
METHOD_ANCHOR = "    private void adjustBackgroundForSuggestions() {\n"
GUARD = """        // Helium: desktop-mode activity recreation can briefly leave this view attached
        // with LinearLayout.LayoutParams before it returns to its FrameLayout holder.
        if (!(getLayoutParams() instanceof FrameLayout.LayoutParams)) {
            return;
        }

"""
MARKER = "Helium: desktop-mode activity recreation can briefly leave this view attached"


def patch_source(root: Path) -> bool:
    path = root / LOCATION_BAR_TABLET
    if not path.is_file():
        raise SystemExit(f"Expected Chromium file not found: {path}")

    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return False
    if text.count(METHOD_ANCHOR) != 1:
        raise SystemExit(f"Expected one LocationBarTablet anchor in {path}")

    path.write_text(text.replace(METHOD_ANCHOR, METHOD_ANCHOR + GUARD, 1), encoding="utf-8")
    return True


if __name__ == "__main__":
    source_root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    changed = patch_source(source_root)
    print(
        "Patched old-android LocationBarTablet layout guard"
        if changed
        else "Old-android LocationBarTablet layout guard already patched"
    )
