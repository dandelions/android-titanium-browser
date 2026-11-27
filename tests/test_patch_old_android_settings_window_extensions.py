import tempfile
import unittest
from pathlib import Path

import patch_old_android_settings_window_extensions as patch


class SettingsWindowExtensionsPatchTest(unittest.TestCase):
    def test_forces_single_column_on_old_android(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / patch.TARGET
            path.parent.mkdir(parents=True)
            path.write_text(patch.ANCHOR, encoding="utf-8")
            self.assertTrue(patch.patch_source_tree(root))
            result = path.read_text(encoding="utf-8")
            self.assertIn(patch.MARKER, result)
            self.assertIn("Build.VERSION.SDK_INT < 30", result)
            self.assertFalse(patch.patch_source_tree(root))


if __name__ == "__main__":
    unittest.main()
