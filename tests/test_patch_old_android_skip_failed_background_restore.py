import tempfile
import unittest
from pathlib import Path

import patch_old_android_skip_failed_background_restore as patch


class SkipFailedBackgroundRestoreTest(unittest.TestCase):
    def test_skips_broken_background_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / patch.TARGET
            path.parent.mkdir(parents=True)
            path.write_text(patch.ANCHOR, encoding="utf-8")
            self.assertTrue(patch.patch_source_tree(root))
            result = path.read_text(encoding="utf-8")
            self.assertIn(patch.MARKER, result)
            self.assertIn("!setAsActive", result)
            self.assertIn("Skipping broken background TabState", result)
            self.assertFalse(patch.patch_source_tree(root))


if __name__ == "__main__":
    unittest.main()
