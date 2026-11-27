#!/usr/bin/env python3
"""Keep old-android settings in single-column mode without Window Extensions."""

from pathlib import Path
import sys

TARGET = Path("chrome/android/java/src/org/chromium/chrome/browser/settings/MultiColumnSettings.java")
MARKER = "Helium: old-android has no Window Extensions implementation."
ANCHOR = """        if (getContext() == null) return false;

        SlidingPaneLayout slidingPane = getSlidingPaneLayoutOrNull();
"""
REPLACEMENT = """        if (getContext() == null) return false;
        // Helium: old-android has no Window Extensions implementation. Keep settings in
        // single-column mode so AndroidX does not load missing XR split-engine classes.
        if (android.os.Build.VERSION.SDK_INT < 30) return false;

        SlidingPaneLayout slidingPane = getSlidingPaneLayoutOrNull();
"""


def patch_source_tree(src_dir: Path) -> bool:
    path = src_dir / TARGET
    if not path.is_file():
        raise SystemExit(f"MultiColumnSettings not found: {path}")
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return False
    if text.count(ANCHOR) != 1:
        raise SystemExit(f"MultiColumnSettings anchor not found exactly once: {path}")
    path.write_text(text.replace(ANCHOR, REPLACEMENT, 1), encoding="utf-8")
    return True


if __name__ == "__main__":
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    changed = patch_source_tree(root)
    print("Disabled old-android multi-column Window Extensions path" if changed else "Old-android settings Window Extensions guard already active")
