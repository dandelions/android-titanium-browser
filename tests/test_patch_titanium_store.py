import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "patch_titanium_store.py"
SPEC = importlib.util.spec_from_file_location("patch_titanium_store", MODULE_PATH)
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)


class TitaniumStorePatchTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.activity_path = self.root / PATCH.CHROME_ACTIVITY
        self.download_path = self.root / PATCH.DOWNLOAD_CRX_UTIL
        self.activity_path.parent.mkdir(parents=True)
        self.download_path.parent.mkdir(parents=True)
        self.activity_path.write_text(
            '''class ChromeActivity {
    private static final String HELIUM_CWS_SCRIPT = "window.chrome = {};";
    private static final String HELIUM_EDGE_SCRIPT = "window.edge = {};";
    // Helium: Native inline installation for Chrome Web Store & Edge Addons
    private void injectStoreInlineInstallSupport(Tab tab) {
        if (tab == null || tab.getWebContents() == null) return;
        tab.getWebContents().evaluateJavaScript(HELIUM_CWS_SCRIPT, null);
    }
    void onUrlUpdated(Tab tab) {
        PersonalizeResults.Execute(tab);
        injectStoreInlineInstallSupport(tab);
    }
}
''',
            encoding="utf-8",
        )
        self.download_path.write_text(
            '''bool OffStoreInstallAllowedByPrefs(const DownloadItem& item) {
  // Helium: Whitelist store domains for inline CRX installation
  if (const auto& o = item.GetRequestInitiator(); o && o->scheme() == "chrome-extension") return true;
  for (const char* d : {"clients2.google.com", "chromewebstore.google.com", "addons.opera.com"}) {
    if (item.GetURL().DomainIs(d) || item.GetReferrerUrl().DomainIs(d)) return true;
  }
  for (const char* d : {"addons.opera.com", "operacdn.com", "microsoftedge.microsoft.com", "edge.microsoft.com", "delivery.mp.microsoft.com"}) if (item.GetURL().DomainIs(d) || item.GetReferrerUrl().DomainIs(d)) return true;
  return false;
}
void CheckDownload(const DownloadItem& download_item) {
  if (download_item.GetMimeType() == extensions::Extension::kMimeType ||
      download_item.GetURL().path().ends_with(".crx") ||
      download_item.GetTargetFilePath().MatchesExtension(FILE_PATH_LITERAL(".crx")) ||
      extensions::UserScript::IsURLUserScript(download_item.GetURL(), download_item.GetMimeType())) {
  }
}
''',
            encoding="utf-8",
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_restores_native_titanium_flow_and_is_idempotent(self):
        self.assertTrue(PATCH.patch_source_tree(self.root))
        activity = self.activity_path.read_text(encoding="utf-8")
        download = self.download_path.read_text(encoding="utf-8")

        self.assertNotIn("HELIUM_CWS_SCRIPT", activity)
        self.assertNotIn("HELIUM_EDGE_SCRIPT", activity)
        self.assertNotIn("injectStoreInlineInstallSupport", activity)
        self.assertIn("PersonalizeResults.Execute(tab);", activity)
        self.assertIn("chrome-extension", download)
        self.assertIn("addons.opera.com", download)
        self.assertIn("microsoftedge.microsoft.com", download)
        self.assertNotIn("chromewebstore.google.com", download)
        self.assertNotIn('ends_with(".crx")', download)
        self.assertNotIn('MatchesExtension(FILE_PATH_LITERAL(".crx"))', download)

        first_activity = activity
        first_download = download
        self.assertFalse(PATCH.patch_source_tree(self.root))
        self.assertEqual(first_activity, self.activity_path.read_text(encoding="utf-8"))
        self.assertEqual(first_download, self.download_path.read_text(encoding="utf-8"))

    def test_migrates_156_compatibility_output(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "compat", MODULE_PATH.parent / "patch_store_compatibility.py")
        compat = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(compat)
        extension = self.root / PATCH.EXTENSION_UTIL
        extension.parent.mkdir(parents=True)
        baseline = '''#include "base/command_line.h"
bool IsExtensionDownload(const download::DownloadItem& download_item) {
  return download_item.GetMimeType() == Extension::kMimeType;
}
'''
        extension.write_text(baseline)
        self.activity_path.write_text('''class ChromeActivity {
    public void onPageLoadFinished(Tab tab, GURL url) {
    }
}
''')
        self.download_path.write_text('''bool OffStoreInstallAllowedByPrefs(const DownloadItem& item) {
  return false;
}
''')
        compat.patch_source_tree(self.root)
        self.assertIn('googleusercontent.com', self.download_path.read_text())
        self.assertIn('MatchesExtension', extension.read_text())
        PATCH.patch_source_tree(self.root)
        activity = self.activity_path.read_text()
        download = self.download_path.read_text()
        cleaned = extension.read_text()
        self.assertNotIn('HELIUM_CWS_SCRIPT', activity)
        self.assertNotIn('injectStoreInlineInstallSupport', activity)
        self.assertNotIn('googleusercontent.com', download)
        self.assertNotIn('chromewebstore.google.com', download)
        self.assertIn('addons.opera.com', download)
        self.assertNotIn('MatchesExtension', cleaned)
        self.assertNotIn('ends_with', cleaned)
        self.assertIn('download_item.GetMimeType() == Extension::kMimeType;', cleaned)
        self.assertFalse(PATCH.patch_source_tree(self.root))
        self.assertEqual(cleaned, extension.read_text())
        self.assertEqual(download, self.download_path.read_text())
        self.assertEqual(activity, self.activity_path.read_text())

    def test_missing_sources_are_a_noop(self):
        empty_root = Path(self.temporary_directory.name) / "empty"
        empty_root.mkdir()
        self.assertFalse(PATCH.patch_source_tree(empty_root))


if __name__ == "__main__":
    unittest.main()
