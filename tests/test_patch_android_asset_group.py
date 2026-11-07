import pathlib
import subprocess
import sys
import tempfile
import unittest


REPO = pathlib.Path(__file__).resolve().parents[1]
PATCH_SCRIPT = REPO / "extensions" / "patch_android_asset_group.py"


class AndroidAssetGroupPatchTest(unittest.TestCase):
    def test_inserts_without_privacy_sandbox_anchor_and_is_idempotent(self):
        source = """\
  java_group("other_assets") {
    deps = [
      "//helium/dist:extension_assets",
    ]
  }
  java_group("chrome_public_non_pak_assets") {
    deps = [
      "//chrome/android/webapk_assets",
      "//components/privacy_sandbox/privacy_sandbox_attestations/preload:privacy_sandbox_attestations_assets",
    ]
  }
"""
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / "BUILD.gn"
            path.write_text(source)

            subprocess.run([sys.executable, str(PATCH_SCRIPT), str(path)], check=True)
            first_result = path.read_text()
            subprocess.run([sys.executable, str(PATCH_SCRIPT), str(path)], check=True)

            self.assertEqual(path.read_text(), first_result)

        self.assertEqual(first_result.count('"//helium/dist:extension_assets",'), 2)
        target_group = first_result.split(
            'java_group("chrome_public_non_pak_assets")', 1
        )[1]
        self.assertIn(
            'deps = [\n'
            '      "//helium/dist:extension_assets",\n'
            '      "//chrome/android/webapk_assets",',
            target_group,
        )
    def test_final_reapply_follows_modern_baseline_restore(self):
        hotfix = (REPO / "hotfix_existing_src.sh").read_text()
        restore = hotfix.index("restore_modern_android_sdk_baseline \"$SRC_DIR\"")
        final_reapply = hotfix.index(
            'patch_android_asset_group.py" \\\n    "$SRC_DIR/chrome/android/BUILD.gn"',
            restore,
        )
        self.assertGreater(final_reapply, restore)
        self.assertIn("Titanium Android asset target is missing after final hotfixes.", hotfix[final_reapply:])
        self.assertNotIn('patch_store_compatibility.py" "$SRC_DIR"', hotfix)
        self.assertIn('patch_titanium_store.py" "$SRC_DIR"', hotfix)
        build = (REPO / "build.sh").read_text()
        self.assertIn("Obsolete Chrome Web Store injection remains", build)


if __name__ == "__main__":
    unittest.main()
