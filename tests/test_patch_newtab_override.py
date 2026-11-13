import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "patch_newtab_override.py"
SPEC = importlib.util.spec_from_file_location("patch_newtab_override", MODULE_PATH)
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)


OVERRIDES_SOURCE = """#include "base/functional/bind.h"
#include "chrome/common/url_constants.h"

namespace {

std::vector<GURL> GetOverridesForChromeURL(
    const GURL& url,
    content::BrowserContext* browser_context,
    bool get_all) {
  // Only chrome: URLs can be overridden like this.
  CHECK(url.SchemeIs(content::kChromeUIScheme), base::NotFatalUntil::M161);

  Profile* profile = Profile::FromBrowserContext(browser_context);
  const base::DictValue& overrides = profile->GetPrefs()->GetDict(
      ExtensionUrlOverrides::kExtensionURLOverrides);

  const base::ListValue* url_list = overrides.FindListByDottedPath(url.host());
  if (!url_list) {
    return {};  // No overrides present for this host.
  }

  extensions::ExtensionRegistry* registry =
      extensions::ExtensionRegistry::Get(browser_context);
  const extensions::ExtensionSet& extensions = registry->enabled_extensions();

  return {};
}

}  // namespace
"""

RESOLVER_SOURCE = """package org.chromium.chrome.browser.url_constants;

import org.chromium.build.annotations.NullMarked;

public class UrlConstantResolver {
    public String getNtpUrl() {
        return getUrlOverrideIfPresent(getOriginalNativeNtpUrl());
    }
}
"""


class NewTabOverridePatchTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.overrides_path = self.root / PATCH.OVERRIDES_FILE
        self.overrides_path.parent.mkdir(parents=True)
        self.overrides_path.write_text(OVERRIDES_SOURCE)
        self.resolver_path = self.root / PATCH.RESOLVER_FILE
        self.resolver_path.parent.mkdir(parents=True)
        self.resolver_path.write_text(RESOLVER_SOURCE)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_falls_back_to_enabled_extensions_when_pref_is_empty(self):
        self.assertTrue(PATCH.patch_source_tree(self.root))
        result = self.overrides_path.read_text()
        self.assertIn("HeliumNtp: pref list missing", result)
        self.assertIn("URLOverrides::GetChromeURLOverrides(extension.get())", result)
        self.assertIn("if (!profile->IsOffTheRecord()) {", result)
        self.assertIn("fallback.push_back(override_iter->second);", result)
        self.assertIn('#include "base/logging.h"', result)
        self.assertLess(
            result.index("const extensions::ExtensionSet& extensions"),
            result.index("const base::ListValue* url_list"),
        )

    def test_logs_the_ntp_override_state_in_logcat(self):
        PATCH.patch_source_tree(self.root)
        self.assertIn('"HeliumNtp: pref list entries="', self.overrides_path.read_text())
        resolver = self.resolver_path.read_text()
        self.assertIn("import android.util.Log;", resolver)
        self.assertIn('"HeliumNtp"', resolver)
        self.assertIn(
            "ExtensionsUrlOverrideRegistry.getNtpOverrideEnabled()", resolver
        )

    def test_repeated_runs_are_no_ops(self):
        self.assertTrue(PATCH.patch_source_tree(self.root))
        overrides_once = self.overrides_path.read_text()
        resolver_once = self.resolver_path.read_text()
        self.assertFalse(PATCH.patch_source_tree(self.root))
        self.assertEqual(overrides_once, self.overrides_path.read_text())
        self.assertEqual(resolver_once, self.resolver_path.read_text())

    def test_missing_files_are_ignored(self):
        self.overrides_path.unlink()
        self.resolver_path.unlink()
        self.assertFalse(PATCH.patch_source_tree(self.root))


class NewTabOverrideWiringTest(unittest.TestCase):
    def test_scripts_apply_the_patch_only_on_old_android(self):
        for name, target in (("patch.sh", "."), ("hotfix_existing_src.sh", '"$SRC_DIR"')):
            with self.subTest(script=name):
                text = (Path(__file__).resolve().parents[1] / name).read_text()
                block_start = text.index("if is_old_version_branch; then")
                block_end = text.index("verify_old_android_features.py", block_start)
                block = text[block_start:block_end]
                self.assertIn(
                    f'python3 "$SCRIPT_DIR/patch_newtab_override.py" {target}', block
                )


if __name__ == "__main__":
    unittest.main()
