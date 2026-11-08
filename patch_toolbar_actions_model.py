#!/usr/bin/env python3
"""Avoid default-pinning locally installed extensions."""

from pathlib import Path
import sys


MODEL_PATH = Path("chrome/browser/ui/toolbar/toolbar_actions_model.cc")
OLD = """  const bool is_pinned_by_feature =
      pin_mode == extensions::ManagedToolbarPinMode::kNotSet &&
      !is_enterprise_extension && !is_installed_from_sync &&
      is_feature_enabled && is_toggle_on;
"""
NEW = """  const bool is_pinned_by_feature =
      extension->from_webstore() &&
      pin_mode == extensions::ManagedToolbarPinMode::kNotSet &&
      !is_enterprise_extension && !is_installed_from_sync &&
      is_feature_enabled && is_toggle_on;
"""


def patch_model(path: Path) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    if NEW in text:
        return False
    if OLD not in text:
        raise SystemExit(f"Toolbar default-pinning anchor not found in {path}")
    path.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    return True


if __name__ == "__main__":
    source_root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    changed = patch_model(source_root / MODEL_PATH)
    print("Applied local extension pinning patch" if changed else "Local extension pinning patch already active")
