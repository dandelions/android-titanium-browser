#!/usr/bin/env python3
"""Remove the retired old-android tab-restore throttling from reused source trees."""

from pathlib import Path
import sys

TARGET = Path(
    "chrome/android/java/src/org/chromium/chrome/browser/tabmodel/TabPersistentStoreImpl.java"
)
PATCHED_BATCH = """    // Helium: old-android restores one tab-state batch at a time.
    // Multiple WebContents restored concurrently can crash the in-process renderer on VMOS.
    private static final int BATCH_RESTORE_SIZE = 1;
"""
ORIGINAL_BATCH = "    private static final int BATCH_RESTORE_SIZE = 5;\n"
PATCHED_COMPLETE = """        mTabBatchLoader = null;
        // Helium: let the first restored WebContents reach an idle frame before the next tab.
        PostTask.postTask(TaskTraits.UI_DEFAULT, () ->
                PostTask.postTask(TaskTraits.UI_DEFAULT, this::loadNextTabs));
"""
ORIGINAL_COMPLETE = """        mTabBatchLoader = null;
        loadNextTabs();
"""


def restore_source_tree(src_dir: Path) -> bool:
    path = src_dir / TARGET
    if not path.is_file():
        raise SystemExit(f"TabPersistentStoreImpl not found: {path}")
    text = path.read_text(encoding="utf-8")
    original = text
    text = text.replace(PATCHED_BATCH, ORIGINAL_BATCH, 1)
    text = text.replace(PATCHED_COMPLETE, ORIGINAL_COMPLETE, 1)
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


if __name__ == "__main__":
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    print(
        "Restored native old-android tab recovery"
        if restore_source_tree(root)
        else "Native old-android tab recovery already restored"
    )
