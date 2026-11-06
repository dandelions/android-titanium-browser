import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "patch_store_compatibility.py"
SPEC = importlib.util.spec_from_file_location("patch_store_compatibility", MODULE_PATH)
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)


class StoreCompatibilityPatchTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.activity_path = self.root / PATCH.CHROME_ACTIVITY
        self.download_path = self.root / PATCH.DOWNLOAD_CRX_UTIL
        self.activity_path.parent.mkdir(parents=True)
        self.download_path.parent.mkdir(parents=True)
        self.activity_path.write_text(
            """class ChromeActivity {
    void onUrlUpdated(Tab tab) {
        PersonalizeResults.Execute(tab);
    }
}
""",
            encoding="utf-8",
        )
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
""",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_injects_desktop_store_install_and_download_support(self):
        self.assertTrue(PATCH.patch_source_tree(self.root))
        activity = self.activity_path.read_text(encoding="utf-8")
        download = self.download_path.read_text(encoding="utf-8")

        self.assertIn("HELIUM_CWS_SCRIPT", activity)
        self.assertIn("Chrome Web Store installation available", activity)
        self.assertIn("injectStoreInlineInstallSupport(tab);", activity)
        self.assertIn("os=win&arch=x64&prod=chromecrx", activity)
        self.assertIn("clients2.google.com", download)
        self.assertIn("ends_with(\".crx\")", download)
        self.assertIn("MatchesExtension(FILE_PATH_LITERAL(\".crx\"))", download)

        first_activity = activity
        first_download = download
        self.assertFalse(PATCH.patch_source_tree(self.root))
        self.assertEqual(first_activity, self.activity_path.read_text(encoding="utf-8"))
        self.assertEqual(first_download, self.download_path.read_text(encoding="utf-8"))

    def test_page_load_finished_hook_matches_chromium_156(self):
        source = '''class ChromeActivity {
    void initialize() {
        new TabModelSelectorTabObserver(tabModelSelector) {
            @Override
            public void onPageLoadFinished(Tab tab, GURL url) {
                postDeferredStartupIfNeeded();
                OfflinePageUtils.showOfflineSnackbarIfNecessary(tab);
            }
        };
    }
}
'''
        self.activity_path.write_text(source, encoding="utf-8")
        self.assertTrue(PATCH.patch_source_tree(self.root))
        result = self.activity_path.read_text(encoding="utf-8")
        self.assertIn(
            "public void onPageLoadFinished(Tab tab, GURL url) {\n"
            "                injectStoreInlineInstallSupport(tab);",
            result,
        )
        self.assertEqual(result.count("injectStoreInlineInstallSupport(tab);"), 1)
        self.assertFalse(PATCH.patch_source_tree(self.root))
        self.assertEqual(self.activity_path.read_text(encoding="utf-8"), result)

    def test_ambiguous_page_load_hooks_fail_without_writing(self):
        source = '''class ChromeActivity {
    public void onPageLoadFinished(Tab tab, GURL url) {}
    public void onPageLoadFinished(Tab tab, GURL url) {}
}
'''
        self.activity_path.write_text(source, encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "Ambiguous page load hooks"):
            PATCH.patch_chrome_activity(self.root)
        self.assertEqual(self.activity_path.read_text(encoding="utf-8"), source)

    def test_chromium_156_extension_download_detection(self):
        self.download_path.write_text(
            '''bool OffStoreInstallAllowedByPrefs(Profile* profile, const DownloadItem& item) {
  return false;
}
bool IsTrustedExtensionDownload(Profile* profile, const DownloadItem& item) {
  return extensions::util::IsExtensionDownload(item);
}
''', encoding="utf-8"
        )
        extension_path = self.root / PATCH.EXTENSION_UTIL
        extension_path.parent.mkdir(parents=True)
        extension_path.write_text(
            '''#include "base/command_line.h"
bool IsExtensionDownload(const download::DownloadItem& download_item) {
  if (download_item.GetTargetDisposition() ==
      download::DownloadItem::TARGET_DISPOSITION_PROMPT) {
    return false;
  }

  if (download_item.GetMimeType() == Extension::kMimeType) {
    return true;
  }
  return false;
}
''', encoding="utf-8"
        )
        self.assertTrue(PATCH.patch_source_tree(self.root))
        result = extension_path.read_text(encoding="utf-8")
        self.assertIn('#include "base/files/file_path.h"', result)
        self.assertIn('download_item.GetURL().path().ends_with(".crx")', result)
        self.assertIn('download_item.GetTargetFilePath().MatchesExtension(FILE_PATH_LITERAL(".crx"))', result)
        self.assertLess(result.index('TARGET_DISPOSITION_PROMPT'), result.index('ends_with(".crx")'))
        self.assertIn('clients2.google.com', self.download_path.read_text(encoding="utf-8"))
        self.assertFalse(PATCH.patch_source_tree(self.root))
        self.assertEqual(result, extension_path.read_text(encoding="utf-8"))

    def test_missing_extension_download_detection_fails(self):
        self.download_path.write_text(
            'bool OffStoreInstallAllowedByPrefs(Profile* profile, const DownloadItem& item) {\n'
            '  return false;\n}\n', encoding="utf-8"
        )
        before = self.download_path.read_text(encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "Could not find extension download detection"):
            PATCH.patch_download_crx_util(self.root)
        self.assertEqual(before, self.download_path.read_text(encoding="utf-8"))

    def test_missing_sources_are_a_noop(self):
        empty_root = Path(self.temporary_directory.name) / "empty"
        empty_root.mkdir()
        self.assertFalse(PATCH.patch_source_tree(empty_root))


if __name__ == "__main__":
    unittest.main()
