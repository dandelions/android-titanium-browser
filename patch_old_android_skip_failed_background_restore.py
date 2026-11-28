#!/usr/bin/env python3
"""Avoid creating fallback WebContents for broken background tab states on old-android."""

from pathlib import Path
import sys

TARGET = Path(
    "chrome/android/java/src/org/chromium/chrome/browser/tabmodel/TabPersistentStoreImpl.java"
)
MARKER = "Helium: skip broken background TabState instead of creating a fallback WebContents."
ANCHOR = """        TabModel model = mTabModelSelector.getModel(isIncognito);
"""
INSERT = """        if (tabState == null
                && !setAsActive
                && !tabToRestore.fromMerge
                && !isTabReparenting(tabToRestore.id, isIncognito)) {
            // Helium: skip broken background TabState instead of creating a fallback WebContents.
            // The active tab still uses the normal last-known-URL fallback above.
            Log.w(TAG, "Skipping broken background TabState: id=" + tabToRestore.id);
            return;
        }

"""


def patch_source_tree(src_dir: Path) -> bool:
    path = src_dir / TARGET
    if not path.is_file():
        raise SystemExit(f"TabPersistentStoreImpl not found: {path}")
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return False
    if text.count(ANCHOR) != 1:
        raise SystemExit(f"Tab restore model anchor not found exactly once: {path}")
    path.write_text(text.replace(ANCHOR, INSERT + ANCHOR, 1), encoding="utf-8")
    return True


if __name__ == "__main__":
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    changed = patch_source_tree(root)
    print("Added old-android safe background TabState restore" if changed else "Old-android background TabState restore already protected")
