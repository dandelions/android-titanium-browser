#!/usr/bin/env python3
"""Use a clean NTP when the active old-android TabState is unreadable."""

from pathlib import Path
import sys

TARGET = Path(
    "chrome/android/java/src/org/chromium/chrome/browser/tabmodel/TabPersistentStoreImpl.java"
)
MARKER = "Helium: old-android uses a clean NTP after active TabState restore failure."
ANCHOR = """            Log.w(
                    TAG,
                    "Failed to restore TabState and not reparenting; creating Tab with last known"
                            + " URL.");
"""
REPLACEMENT = """            // Helium: old-android uses a clean NTP after active TabState restore failure.
            // A stale last-known URL can enter the single-process renderer before its tab is ready
            // and leave the browser on a blank surface.
            Log.w(TAG, "Failed to restore active TabState; creating a clean NTP.");
"""
URL_ANCHOR = """            LoadUrlParams params = new LoadUrlParams(tabToRestore.url);
"""
URL_REPLACEMENT = """            LoadUrlParams params =
                    new LoadUrlParams(
                            setAsActive ? UrlConstants.NTP_URL : tabToRestore.url);
"""


def patch_source_tree(src_dir: Path) -> bool:
    path = src_dir / TARGET
    if not path.is_file():
        raise SystemExit(f"TabPersistentStoreImpl not found: {path}")
    text = path.read_text(encoding="utf-8")
    changed = False
    if MARKER not in text:
        if text.count(ANCHOR) != 1:
            raise SystemExit(f"Active restore failure anchor not found exactly once: {path}")
        text = text.replace(ANCHOR, REPLACEMENT, 1)
        changed = True
    if text.count(URL_ANCHOR) > 1:
        raise SystemExit(f"Active restore URL anchor found more than once: {path}")
    if URL_REPLACEMENT not in text and URL_ANCHOR in text:
        text = text.replace(URL_ANCHOR, URL_REPLACEMENT, 1)
        changed = True
    if changed:
        path.write_text(text, encoding="utf-8")
    return changed


if __name__ == "__main__":
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    changed = patch_source_tree(root)
    print("Added clean active-tab restore fallback" if changed else "Clean active-tab restore fallback already active")
