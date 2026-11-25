import tempfile
import unittest
from pathlib import Path

import patch_old_android_tab_restore_batch as patch


class TabRestoreBatchPatchTest(unittest.TestCase):
    def test_serializes_restore_batches(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / patch.TARGET
            path.parent.mkdir(parents=True)
            path.write_text(patch.ANCHOR, encoding="utf-8")

            self.assertTrue(patch.patch_source_tree(root))
            result = path.read_text(encoding="utf-8")
            self.assertIn(patch.MARKER, result)
            self.assertIn("BATCH_RESTORE_SIZE = 1", result)
            self.assertFalse(patch.patch_source_tree(root))


if __name__ == "__main__":
    unittest.main()
