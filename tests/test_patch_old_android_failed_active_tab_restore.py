import tempfile
import unittest
from pathlib import Path

import patch_old_android_failed_active_tab_restore as patch


SOURCE = patch.ANCHOR + """            LoadUrlParams params = new LoadUrlParams(tabToRestore.url);
"""


class FailedActiveTabRestoreTest(unittest.TestCase):
    def test_uses_clean_ntp_for_active_restore_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / patch.TARGET
            path.parent.mkdir(parents=True)
            path.write_text(SOURCE, encoding="utf-8")
            self.assertTrue(patch.patch_source_tree(root))
            result = path.read_text(encoding="utf-8")
            self.assertIn(patch.MARKER, result)
            self.assertIn("setAsActive ? UrlConstants.NTP_URL : tabToRestore.url", result)
            self.assertFalse(patch.patch_source_tree(root))


if __name__ == "__main__":
    unittest.main()
