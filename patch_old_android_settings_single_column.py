#!/usr/bin/env python3
"""Use the regular single-column settings host on old Android."""

from pathlib import Path
import sys

TARGET = Path("chrome/android/java/src/org/chromium/chrome/browser/settings/SettingsActivity.java")
MARKER = "Helium: old-android uses the single-column settings host."
ANCHOR = "        mStandalone = getIntent().getBooleanExtra(EXTRA_SHOW_FRAGMENT_STANDALONE, false);\n"
REPLACEMENT = """        mStandalone = getIntent().getBooleanExtra(EXTRA_SHOW_FRAGMENT_STANDALONE, false);
        // Helium: old-android uses the single-column settings host. The multi-column host
        // probes unavailable AndroidX Window Extensions classes during onCreateView().
        if (android.os.Build.VERSION.SDK_INT < 30) {
            mStandalone = true;
        }
"""


def patch_source_tree(src_dir: Path) -> bool:
    path = src_dir / TARGET
    if not path.is_file():
        raise SystemExit(f"SettingsActivity not found: {path}")
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return False
    if text.count(ANCHOR) != 1:
        raise SystemExit(f"SettingsActivity standalone anchor not found exactly once: {path}")
    path.write_text(text.replace(ANCHOR, REPLACEMENT, 1), encoding="utf-8")
    return True


if __name__ == "__main__":
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    changed = patch_source_tree(root)
    print("Enabled old-android single-column settings" if changed else "Old-android single-column settings already enabled")
