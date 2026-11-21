#!/usr/bin/env python3
"""Show ZeroOmega's PAC status action in the old-android toolbar."""

from pathlib import Path
import sys


MODEL_PATH = Path("chrome/browser/ui/toolbar/toolbar_actions_model.cc")
EXTENSION_ID = "hajncedpjcplegoofakinfikikjngdop"
OLD_PIN_DEFAULT = "  const bool is_pinned_by_feature = false;\n"
NEW_PIN_DEFAULT = f"""  const bool is_pinned_by_feature =
      extension->id() == \"{EXTENSION_ID}\" &&
      pin_mode == extensions::ManagedToolbarPinMode::kNotSet &&
      !is_enterprise_extension && !is_installed_from_sync;
"""
OLD_INITIALIZE = """  // Set |pinned_action_ids_| directly to avoid notifying observers that they
  // have changed even though they haven't.
  pinned_action_ids_ = GetFilteredPinnedActionIds();
"""
NEW_INITIALIZE = f"""  // Helium: migrate an existing ZeroOmega install to the toolbar once so its
  // PAC profile status remains visible. A later explicit user unpin is preserved.
  constexpr char kZeroOmegaExtensionId[] = \"{EXTENSION_ID}\";
  if (action_ids_.contains(kZeroOmegaExtensionId) &&
      extension_prefs_->WasPinnedByDefault(kZeroOmegaExtensionId) != true) {{
    auto stored_pinned_actions = extension_prefs_->GetPinnedExtensions();
    if (!std::ranges::contains(stored_pinned_actions, kZeroOmegaExtensionId)) {{
      stored_pinned_actions.push_back(kZeroOmegaExtensionId);
      extension_prefs_->SetPinnedExtensions(stored_pinned_actions);
    }}
    extension_prefs_->SetWasPinnedByDefault(kZeroOmegaExtensionId, true);
  }}

  // Set |pinned_action_ids_| directly to avoid notifying observers that they
  // have changed even though they haven't.
  pinned_action_ids_ = GetFilteredPinnedActionIds();
"""


def patch_model(path: Path) -> bool:
    if not path.is_file():
        raise SystemExit(f"Toolbar actions model not found: {path}")

    text = path.read_text(encoding="utf-8")
    original = text

    if "Helium: migrate an existing ZeroOmega install" not in text:
        if OLD_INITIALIZE not in text:
            raise SystemExit(f"Toolbar initialization anchor not found in {path}")
        text = text.replace(OLD_INITIALIZE, NEW_INITIALIZE, 1)

    if f'extension->id() == "{EXTENSION_ID}"' not in text:
        if OLD_PIN_DEFAULT in text:
            text = text.replace(OLD_PIN_DEFAULT, NEW_PIN_DEFAULT, 1)
        else:
            raise SystemExit(f"Toolbar pin-default anchor not found in {path}")

    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def patch_source_tree(src_dir: Path) -> bool:
    return patch_model(src_dir / MODEL_PATH)


if __name__ == "__main__":
    source_root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    changed = patch_source_tree(source_root)
    print("Enabled ZeroOmega toolbar status" if changed else "ZeroOmega toolbar status already enabled")
