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


class ExtensionContextMenuPatchTest(unittest.TestCase):
    def test_hides_pin_command_at_init(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / patch.TARGET
            path.parent.mkdir(parents=True)
            path.write_text(SOURCE, encoding="utf-8")
            self.assertTrue(patch.patch_source_tree(Path(directory)))
            result = path.read_text(encoding="utf-8")
            self.assertIn(patch.INIT_MARKER, result)
            self.assertIn("Init(extension, /* can_show_icon_in_toolbar= */ false);", result)
            self.assertIn(patch.MARKER, result)
            self.assertIn("if (IsExtensionForcePinned", result)
            self.assertNotIn("if (false && IsExtensionForcePinned", result)
            self.assertFalse(patch.patch_source_tree(Path(directory)))


if __name__ == "__main__":
    unittest.main()
