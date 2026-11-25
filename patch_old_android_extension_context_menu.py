#!/usr/bin/env python3
"""Hide the extension pin-to-toolbar command on old-android."""

from pathlib import Path
import sys

TARGET = Path("chrome/browser/extensions/extension_context_menu_model.cc")
MARKER = "Helium old-android hides the extension pin-to-toolbar menu command"
ANCHOR = """  if (can_show_icon_in_toolbar) {
    if (IsExtensionForcePinned(*extension, profile_)) {
"""
REPLACEMENT = """  if (can_show_icon_in_toolbar) {
    // Helium old-android hides the extension pin-to-toolbar menu command.
    // Extensions are arranged by the browser toolbar layout instead.
    if (false && IsExtensionForcePinned(*extension, profile_)) {
"""


def patch_source_tree(src_dir: Path) -> bool:
    path = src_dir / TARGET
    if not path.is_file():
        raise SystemExit(f"Extension context menu source not found: {path}")
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return False
    if text.count(ANCHOR) != 1:
        raise SystemExit(f"Extension context menu anchor not found exactly once: {path}")
    path.write_text(text.replace(ANCHOR, REPLACEMENT, 1), encoding="utf-8")
    return True


if __name__ == "__main__":
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    changed = patch_source_tree(root)
    print("Hidden old-android extension pin menu" if changed else "Old-android extension pin menu already hidden")
