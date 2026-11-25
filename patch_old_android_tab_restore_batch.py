#!/usr/bin/env python3
"""Serialize old-android tab-state restoration for the single-process renderer."""

from pathlib import Path
import sys

TARGET = Path(
    "chrome/android/java/src/org/chromium/chrome/browser/tabmodel/TabPersistentStoreImpl.java"
)
MARKER = "Helium: old-android restores one tab-state batch at a time."
ANCHOR = "    private static final int BATCH_RESTORE_SIZE = 5;\n"
REPLACEMENT = """    // Helium: old-android restores one tab-state batch at a time.
    // Multiple WebContents restored concurrently can crash the in-process renderer on VMOS.
    private static final int BATCH_RESTORE_SIZE = 1;
"""


def patch_source_tree(src_dir: Path) -> bool:
    path = src_dir / TARGET
    if not path.is_file():
        raise SystemExit(f"TabPersistentStoreImpl not found: {path}")
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return False
    if text.count(ANCHOR) != 1:
        raise SystemExit(f"Restore batch anchor not found exactly once: {path}")
    path.write_text(text.replace(ANCHOR, REPLACEMENT, 1), encoding="utf-8")
    return True


if __name__ == "__main__":
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    changed = patch_source_tree(root)
    print("Serialized old-android tab restore" if changed else "Old-android tab restore already serialized")
