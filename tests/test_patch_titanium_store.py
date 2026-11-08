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

    def test_removes_crx_detection_when_allowlist_already_normalized(self):
        normalized = (
            'bool OffStoreInstallAllowedByPrefs(const DownloadItem& item) {'
            + PATCH.TITANIUM_ALLOWLIST
            + '\n  return false;\n}\n'
        )
        detection = '''void CheckDownload(const DownloadItem& download_item) {
  if (download_item.GetMimeType() == extensions::Extension::kMimeType ||
      download_item.GetURL().path().ends_with(".crx") ||
      download_item.GetTargetFilePath().MatchesExtension(FILE_PATH_LITERAL(".crx")) ||
      extensions::UserScript::IsURLUserScript(download_item.GetURL(), download_item.GetMimeType())) {
  }
}
'''
        self.download_path.write_text(normalized + detection)
        self.assertTrue(PATCH.restore_titanium_allowlist(self.download_path))
        cleaned = self.download_path.read_text()
        self.assertNotIn('ends_with(".crx")', cleaned)
        self.assertNotIn('MatchesExtension(FILE_PATH_LITERAL(".crx"))', cleaned)
        self.assertIn('download_item.GetMimeType() == extensions::Extension::kMimeType ||', cleaned)
        self.assertIn('extensions::UserScript::IsURLUserScript', cleaned)
        self.assertTrue(cleaned.startswith(normalized))
        self.assertFalse(PATCH.restore_titanium_allowlist(self.download_path))
        self.assertEqual(cleaned, self.download_path.read_text())

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

    def test_patches_desktop_site_utils_and_is_idempotent(self):
        desktop_site_path = self.root / PATCH.DESKTOP_SITE_UTILS
        desktop_site_path.parent.mkdir(parents=True, exist_ok=True)
        source = """public class DesktopSiteUtils {
    public static void maybeDefaultEnableWindowSetting(Activity activity, Profile profile) {
        WebsitePreferenceBridge.setContentSettingCustomScope(profile, ContentSettingsType.REQUEST_DESKTOP_SITE, "[*.]chromewebstore.google.com", SITE_WILDCARD, ContentSetting.ALLOW);
        int smallestScreenWidthDp = DisplayUtil.getCurrentSmallestScreenWidth(activity);
    }

    public static boolean shouldOverrideDesktopSite(
            Profile profile, @Nullable GURL url, Context context) {
        if (CommandLine.getInstance().hasSwitch(ChromeSwitches.REQUEST_DESKTOP_SITES)) {
            return true;
        }
        return false;
    }

    public static boolean isDesktopSiteEnabled(Profile profile, GURL url) {
        return WebsitePreferenceBridge.getContentSetting(
                        profile, ContentSettingsType.REQUEST_DESKTOP_SITE, url, url)
                == ContentSetting.ALLOW;
    }
}
"""
        desktop_site_path.write_text(source, encoding="utf-8")
        self.assertTrue(PATCH.patch_desktop_site_utils(desktop_site_path))
        patched = desktop_site_path.read_text(encoding="utf-8")
        self.assertNotIn("setContentSettingCustomScope", patched)
        self.assertIn("chromewebstore.google.com", patched)
        self.assertIn("chrome.google.com", patched)
        self.assertEqual(patched.count('"chromewebstore.google.com".equals(host)'), 2)
        self.assertFalse(PATCH.patch_desktop_site_utils(desktop_site_path))
        self.assertEqual(patched, desktop_site_path.read_text(encoding="utf-8"))

    def test_patches_webstore_private_and_manifest_v2_handler(self):
        ws_path = self.root / PATCH.WEBSTORE_PRIVATE_PATHS[0]
        mv2_path = self.root / PATCH.MANIFEST_V2_HANDLER
        ws_path.parent.mkdir(parents=True, exist_ok=True)
        mv2_path.parent.mkdir(parents=True, exist_ok=True)
        ws_path.write_text(
            'return RespondNow(ArgumentList(GetMV2DeprecationStatus::Results::Create(\n'
            '    api::webstore_private::MV2DeprecationStatus::kHardDisable)));\n',
            encoding="utf-8",
        )
        mv2_path.write_text('bool g_allow_mv2_for_testing = false;\n', encoding="utf-8")

        self.assertTrue(PATCH.patch_source_tree(self.root))
        self.assertIn("MV2DeprecationStatus::kNone", ws_path.read_text(encoding="utf-8"))
        self.assertIn("bool g_allow_mv2_for_testing = true;", mv2_path.read_text(encoding="utf-8"))
        self.assertFalse(PATCH.patch_source_tree(self.root))

    def test_expands_webstore_api_matches_for_legacy_path(self):
        api_path = self.root / PATCH.API_FEATURES
        api_path.parent.mkdir(parents=True, exist_ok=True)
        fixture = Path(__file__).resolve().parent / "fixtures/chromium_157/_api_features.json"
        api_path.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

        self.assertTrue(PATCH.patch_source_tree(self.root))
        patched = api_path.read_text(encoding="utf-8")
        self.assertEqual(patched.count('"https://chrome.google.com/webstore/*"'), 2)
        self.assertNotIn('"https://chrome.google.com/*"', patched)
        self.assertFalse(PATCH.patch_source_tree(self.root))
        self.assertEqual(patched, api_path.read_text(encoding="utf-8"))

    def test_normalizes_android_version_info_and_webstore_version(self):
        version_info_path = self.root / PATCH.VERSION_INFO
        version_info_path.parent.mkdir(parents=True, exist_ok=True)
        version_info_path.write_text(
            'namespace version_info {\n'
            '#if BUILDFLAG(IS_ANDROID)\n'
            'std::string_view GetVersionNumber() {\n'
            '  return base::android::apk_info::package_version_name();\n'
            '}\n'
            '#endif\n'
            '}\n',
            encoding="utf-8",
        )
        ws_path = self.root / PATCH.WEBSTORE_PRIVATE_PATHS[0]
        ws_path.parent.mkdir(parents=True, exist_ok=True)
        ws_path.write_text(
            'WebstorePrivateGetFullChromeVersionFunction::Run() {\n'
            '  std::string_view version = version_info::GetVersionNumber();\n'
            '  GetFullChromeVersion::Results::Info info;\n'
            '  info.version_number = std::string(version);\n'
            '  return RespondNow(ArgumentList(GetFullChromeVersion::Results::Create(info)));\n'
            '}\n',
            encoding="utf-8",
        )

        self.assertTrue(PATCH.patch_source_tree(self.root))
        patched_vi = version_info_path.read_text(encoding="utf-8")
        self.assertIn("dot_count == 4", patched_vi)
        self.assertIn("base::NoDestructor<std::string>", patched_vi)

        patched_ws = ws_path.read_text(encoding="utf-8")
        self.assertIn("trim_pos", patched_ws)
        self.assertIn("dot_count == 4", patched_ws)

        self.assertFalse(PATCH.patch_source_tree(self.root))
        self.assertEqual(patched_vi, version_info_path.read_text(encoding="utf-8"))
        self.assertEqual(patched_ws, ws_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
