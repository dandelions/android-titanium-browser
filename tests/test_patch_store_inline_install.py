import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "patch_store_inline_install.py"
SPEC = importlib.util.spec_from_file_location("patch_store_inline_install", MODULE_PATH)
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)


class StoreInlineInstallPatchTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.download_path = self.root / "chrome/browser/download/download_crx_util.cc"
        self.activity_path = (
            self.root
            / "chrome/android/java/src/org/chromium/chrome/browser/app/ChromeActivity.java"
        )
        self.download_path.parent.mkdir(parents=True)
        self.activity_path.parent.mkdir(parents=True)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_download_patch_is_complete_and_idempotent(self):
        self.download_path.write_text(
            """bool OffStoreInstallAllowedByPrefs(const DownloadItem& item) {
  return false;
}
void CheckDownload(const DownloadItem& download_item) {
  if (download_item.GetMimeType() == extensions::Extension::kMimeType ||
      extensions::UserScript::IsURLUserScript(download_item.GetURL(),
                                              download_item.GetMimeType())) {
  }
}
"""
        )

        PATCH.patch_download_crx_util(self.root)
        first_result = self.download_path.read_text()
        self.assertIn("Helium: Whitelist store domains for inline CRX installation", first_result)
        self.assertIn('MatchesExtension(FILE_PATH_LITERAL(".crx"))', first_result)

        PATCH.patch_download_crx_util(self.root)
        self.assertEqual(first_result, self.download_path.read_text())

    def test_download_patch_fails_when_crx_anchor_changes(self):
        self.download_path.write_text(
            """bool OffStoreInstallAllowedByPrefs(const DownloadItem& item) {
  return false;
}
void CheckDownload(const DownloadItem& download_item) {
  return;
}
"""
        )

        with self.assertRaisesRegex(RuntimeError, "CRX download check"):
            PATCH.patch_download_crx_util(self.root)

    def test_existing_activity_scripts_are_refreshed_idempotently(self):
        self.activity_path.write_text(
            """class ChromeActivity {
  private static final String HELIUM_CWS_SCRIPT = "old-cws";
  private static final String HELIUM_EDGE_SCRIPT = "old-edge";
  private void injectStoreInlineInstallSupport(Tab tab) {}
  void onUrlUpdated(Tab tab) {
    PersonalizeResults.Execute(tab);
  }
}
"""
        )

        PATCH.patch_chrome_activity(self.root)
        first_result = self.activity_path.read_text()
        self.assertIn("window.location.assign(crxUrl)", first_result)
        self.assertNotIn("old-cws", first_result)
        self.assertNotIn("old-edge", first_result)
        self.assertEqual(
            1,
            first_result.count(
                "PersonalizeResults.Execute(tab);\n              injectStoreInlineInstallSupport(tab);"
            ),
        )

        PATCH.patch_chrome_activity(self.root)
        second_result = self.activity_path.read_text()
        self.assertEqual(first_result, second_result)


if __name__ == "__main__":
    unittest.main()
