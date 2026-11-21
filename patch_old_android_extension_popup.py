#!/usr/bin/env python3
"""Give extension action popups usable initial bounds on old-android."""

from pathlib import Path
import sys


POPUP_PATH = Path(
    "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/"
    "ExtensionActionPopup.java"
)

OLD = """        int initialWidthPx =
                resources.getDimensionPixelSize(R.dimen.extension_action_popup_min_width);
        int initialHeightPx =
                resources.getDimensionPixelSize(R.dimen.extension_action_popup_min_height);
"""
NEW = """        // Helium: ZeroOmega and similar popups may report their auto-size after first paint.
        // A 25dp initial window clips all profile text until that callback arrives.
        int initialWidthPx = Math.min(
                maxContentWidthPx,
                ViewUtils.dpToPx(mActivity, 320));
        int initialHeightPx = Math.min(
                maxContentHeightPx,
                ViewUtils.dpToPx(mActivity, 480));
"""
MARKER = "Helium: ZeroOmega and similar popups may report their auto-size after first paint."


def patch_source(source_root: Path) -> bool:
    path = source_root / POPUP_PATH
    if not path.is_file():
        raise SystemExit(f"Expected Chromium file not found: {path}")
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return False
    if text.count(OLD) != 1:
        raise SystemExit(f"Extension popup initial-size anchor not found in {path}")
    path.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    return True


if __name__ == "__main__":
    source_root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    changed = patch_source(source_root)
    print("Patched old-android extension popup initial size" if changed else
          "Old-android extension popup initial size already patched")
