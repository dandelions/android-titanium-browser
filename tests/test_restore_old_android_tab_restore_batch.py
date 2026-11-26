import tempfile
import unittest
from pathlib import Path

import restore_old_android_tab_restore_batch as restore


class RestoreTabBatchTest(unittest.TestCase):
    def test_restores_original_batch_and_continuation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / restore.TARGET
            path.parent.mkdir(parents=True)
            path.write_text(restore.PATCHED_BATCH + "\n" + restore.PATCHED_COMPLETE)

            self.assertTrue(restore.restore_source_tree(root))
            result = path.read_text()
            self.assertIn(restore.ORIGINAL_BATCH, result)
            self.assertIn(restore.ORIGINAL_COMPLETE, result)
            self.assertNotIn("Helium: old-android restores", result)
            self.assertFalse(restore.restore_source_tree(root))


if __name__ == "__main__":
    unittest.main()
