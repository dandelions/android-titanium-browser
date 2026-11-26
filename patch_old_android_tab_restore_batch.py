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
COMPLETE_MARKER = "Helium: let the first restored WebContents reach an idle frame before the next tab."
COMPLETE_ANCHOR = """        mTabBatchLoader = null;
        loadNextTabs();
"""
COMPLETE_REPLACEMENT = """        mTabBatchLoader = null;
        // Helium: let the first restored WebContents reach an idle frame before the next tab.
        PostTask.postTask(TaskTraits.UI_DEFAULT, () ->
                PostTask.postTask(TaskTraits.UI_DEFAULT, this::loadNextTabs));
"""


def patch_source_tree(src_dir: Path) -> bool:
    path = src_dir / TARGET
    if not path.is_file():
        raise SystemExit(f"TabPersistentStoreImpl not found: {path}")
    text = path.read_text(encoding="utf-8")
    changed = False
    if MARKER not in text:
        if text.count(ANCHOR) != 1:
            raise SystemExit(f"Restore batch anchor not found exactly once: {path}")
        text = text.replace(ANCHOR, REPLACEMENT, 1)
        changed = True
    if COMPLETE_MARKER not in text:
        if text.count(COMPLETE_ANCHOR) != 1:
            raise SystemExit(f"Restore completion anchor not found exactly once: {path}")
        text = text.replace(COMPLETE_ANCHOR, COMPLETE_REPLACEMENT, 1)
        changed = True
    if changed:
        path.write_text(text, encoding="utf-8")
    return changed


if __name__ == "__main__":
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    changed = patch_source_tree(root)
    print("Serialized old-android tab restore" if changed else "Old-android tab restore already serialized")
