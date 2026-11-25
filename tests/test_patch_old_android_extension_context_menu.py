import tempfile
import unittest
from pathlib import Path

import patch_old_android_extension_context_menu as patch


SOURCE = """void ExtensionContextMenuModel::Init(const Extension* extension,
                                     bool can_show_icon_in_toolbar) {
  Init(extension, can_show_icon_in_toolbar);
}

  if (can_show_icon_in_toolbar) {
    if (IsExtensionForcePinned(*extension, profile_)) {
      AddItemWithStringId(TOGGLE_VISIBILITY, IDS_EXTENSIONS_PINNED_BY_ADMIN);
    } else {
      AddItemWithStringId(TOGGLE_VISIBILITY,
                          IDS_EXTENSIONS_CONTEXT_MENU_PIN_TO_TOOLBAR);
    }
  }
"""

OLD_FORCED_SOURCE = SOURCE.replace(
    "  Init(extension, can_show_icon_in_toolbar);",
    patch.FORCED_INIT.rstrip(),
).replace(
    patch.ANCHOR,
    patch.LEGACY_REPLACEMENT,
)


class ExtensionContextMenuPatchTest(unittest.TestCase):
    def test_preserves_pin_command_on_fresh_source(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / patch.TARGET
            path.parent.mkdir(parents=True)
            path.write_text(SOURCE, encoding="utf-8")
            self.assertFalse(patch.patch_source_tree(Path(directory)))
            self.assertEqual(SOURCE, path.read_text(encoding="utf-8"))

    def test_restores_pin_command_in_existing_source_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / patch.TARGET
            path.parent.mkdir(parents=True)
            path.write_text(OLD_FORCED_SOURCE, encoding="utf-8")

            self.assertTrue(patch.patch_source_tree(Path(directory)))

            result = path.read_text(encoding="utf-8")
            self.assertIn(patch.INIT_ANCHOR, result)
            self.assertIn("if (can_show_icon_in_toolbar) {", result)
            self.assertIn("if (IsExtensionForcePinned(*extension, profile_))", result)
            self.assertIn("IDS_EXTENSIONS_CONTEXT_MENU_PIN_TO_TOOLBAR", result)
            self.assertNotIn("Helium old-android", result)
            self.assertFalse(patch.patch_source_tree(Path(directory)))


if __name__ == "__main__":
    unittest.main()
