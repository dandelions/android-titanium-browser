import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("asset_patch", ROOT / "extensions/patch_android_asset_group.py")
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)


class AndroidAssetGroupTest(unittest.TestCase):
    def test_scoped_insert_and_idempotence(self):
        source = '''java_group("other") {
  deps = [
    "//helium/dist:extension_assets",
  ]
}
java_group("chrome_public_non_pak_assets") {
  deps = [
    "//chrome/android/webapk_assets",
  ]
}
'''
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "BUILD.gn"
            path.write_text(source)
            self.assertTrue(PATCH.patch(path))
            result = path.read_text()
            self.assertEqual(result.count('"//helium/dist:extension_assets",'), 2)
            self.assertIn('java_group("chrome_public_non_pak_assets") {\n  deps = [\n    "//helium/dist:extension_assets",', result)
            self.assertFalse(PATCH.patch(path))
            self.assertEqual(path.read_text(), result)

    def test_normal_build_stages_before_patch_and_restores_asset_dependency(self):
        build = (ROOT / "build.sh").read_text()
        self.assertLess(build.index("\nensure_titanium_extension_bundle\n"),
                        build.index('source "$SCRIPT_DIR/patch.sh"'))
        source = (ROOT / "patch.sh").read_text()
        self.assertIn('extensions/dist/bundled.json', source)
        self.assertIn('cp -r "$SCRIPT_DIR/extensions/dist" helium/', source)
        self.assertLess(source.index('restore_modern_android_sdk_baseline .'),
                        source.index('patch_android_asset_group.py" chrome/android/BUILD.gn'))
        hotfix = (ROOT / "hotfix_existing_src.sh").read_text()
        self.assertLess(hotfix.index('restore_modern_android_sdk_baseline "$SRC_DIR"'),
                        hotfix.index('patch_android_asset_group.py" "$SRC_DIR/chrome/android/BUILD.gn"'))
        gn = (ROOT / "extensions/BUILD.gn").read_text()
        self.assertIn('"bundled.json"', gn)
        self.assertIn('"extensions/bundled.json"', gn)


if __name__ == "__main__":
    unittest.main()
