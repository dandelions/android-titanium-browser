#!/usr/bin/env python3
"""Restore extension pin-to-toolbar commands on old-android."""

from pathlib import Path
import sys

TARGET = Path("chrome/browser/extensions/extension_context_menu_model.cc")
MARKER = "Helium old-android hides the extension pin-to-toolbar menu command"
INIT_MARKER = "Helium old-android passes false for context-menu toolbar pinning"
INIT_ANCHOR = "  Init(extension, can_show_icon_in_toolbar);\n"
INIT_REPLACEMENT = "  Init(extension, can_show_icon_in_toolbar);\n"
FORCED_INIT = """  // Helium old-android passes false for context-menu toolbar pinning.
  Init(extension, /* can_show_icon_in_toolbar= */ false);
"""
ANCHOR = """  if (can_show_icon_in_toolbar) {
    if (IsExtensionForcePinned(*extension, profile_)) {
"""
REPLACEMENT = """  if (can_show_icon_in_toolbar) {
    // Helium old-android hides the extension pin-to-toolbar menu command.
    // Extensions are arranged by the browser toolbar layout instead.
    if (IsExtensionForcePinned(*extension, profile_)) {
"""
LEGACY_REPLACEMENT = """  if (can_show_icon_in_toolbar) {
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
    if LEGACY_REPLACEMENT in text:
        text = text.replace(LEGACY_REPLACEMENT, REPLACEMENT, 1)
        changed = True
    if FORCED_INIT in text:
        text = text.replace(FORCED_INIT, INIT_REPLACEMENT, 1)
        changed = True
    if LEGACY_REPLACEMENT in text:
        text = text.replace(LEGACY_REPLACEMENT, ANCHOR, 1)
        changed = True
    if MARKER in text:
        text = text.replace(
            "  if (can_show_icon_in_toolbar) {\n"
            "    // Helium old-android hides the extension pin-to-toolbar menu command.\n"
            "    // Extensions are arranged by the browser toolbar layout instead.\n"
            "    if (IsExtensionForcePinned(*extension, profile_)) {\n",
            ANCHOR,
            1,
        )
        text = text.replace(
            "    // Helium old-android hides the extension pin-to-toolbar menu command.\n"
            "    // Extensions are arranged by the browser toolbar layout instead.\n",
            "",
            1,
        )
        changed = True
    if INIT_MARKER in text and INIT_ANCHOR not in text:
        raise SystemExit(f"Could not restore extension context menu init in {path}")
    if INIT_ANCHOR not in text:
        raise SystemExit(f"Extension context menu init anchor not found in {path}")
    if changed:
        path.write_text(text, encoding="utf-8")
    return changed


if __name__ == "__main__":
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    changed = patch_source_tree(root)
    print("Hidden old-android extension pin menu" if changed else "Old-android extension pin menu already hidden")
