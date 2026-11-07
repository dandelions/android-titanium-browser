import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Upstream157PatchTest(unittest.TestCase):
    def test_version_specific_changes_preserve_helium_paths(self):
        patch = (ROOT / "patch.sh").read_text(encoding="utf-8")
        hotfix = (ROOT / "hotfix_existing_src.sh").read_text(encoding="utf-8")
        for script in (patch, hotfix):
            self.assertIn("static void maybeModifyCustomTabIntents(Intent intent)", script)
            self.assertIn("download::features::kEnableDownloadSaveAsContextMenu", script)
        self.assertIn("helium/chromium_src/chrome/android/java", patch)
        self.assertNotIn("feature_overrides.EnableFeature(media::kContextMenuPictureInPictureAndroid);\\\n", patch)
        self.assertIn("[*.]chromewebstore.google.com", patch)

    def test_dex_change_is_scoped(self):
        patch = (ROOT / "patch.sh").read_text(encoding="utf-8")
        line = next(line for line in patch.splitlines() if "android_apk_or_module_srcjar_deps_common" in line)
        sed = line.split(" build/config/android/rules.gni", 1)[0].replace("sed -i ", "sed ", 1)
        source = ("if (!_omit_dex) {\n"
                  "android_apk_or_module_srcjar_deps_common\n"
                  "if (!_omit_dex) {\n"
                  "if (!_omit_dex) {\n")
        result = subprocess.run(["bash", "-c", sed], input=source, text=True,
                                capture_output=True, check=True).stdout
        self.assertEqual(result.count("if (_is_base_module && !_omit_dex) {"), 1)
        self.assertEqual(result.count("if (!_omit_dex) {"), 2)


if __name__ == "__main__":
    unittest.main()
