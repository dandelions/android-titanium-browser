#!/usr/bin/env python3
"""Hide the extension pin-to-toolbar command on old-android."""

from pathlib import Path
import sys

TARGET = Path("chrome/browser/extensions/extension_context_menu_model.cc")
MARKER = "Helium old-android hides the extension pin-to-toolbar menu command"
INIT_MARKER = "Helium old-android passes false for context-menu toolbar pinning"
INIT_ANCHOR = "  Init(extension, can_show_icon_in_toolbar);\n"
INIT_REPLACEMENT = """  // Helium old-android passes false for context-menu toolbar pinning.
  Init(extension, /* can_show_icon_in_toolbar= */ false);
"""
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
    changed = False
    if INIT_MARKER not in text:
        if text.count(INIT_ANCHOR) != 1:
            raise SystemExit(f"Extension context menu init anchor not found exactly once: {path}")
        text = text.replace(INIT_ANCHOR, INIT_REPLACEMENT, 1)
        changed = True
    if MARKER not in text:
        if text.count(ANCHOR) != 1:
            raise SystemExit(f"Extension context menu anchor not found exactly once: {path}")
        text = text.replace(ANCHOR, REPLACEMENT, 1)
        changed = True
    if changed:
        path.write_text(text, encoding="utf-8")
    return changed


if __name__ == "__main__":
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    changed = patch_source_tree(root)
    print("Hidden old-android extension pin menu" if changed else "Old-android extension pin menu already hidden")
