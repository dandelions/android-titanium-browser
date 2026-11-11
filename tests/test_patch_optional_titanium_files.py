import pathlib
import subprocess
import unittest


REPO = pathlib.Path(__file__).resolve().parents[1]
PATCH = REPO / "patch.sh"


class OptionalTitaniumFilesTest(unittest.TestCase):
    def test_optional_titanium_patches_check_file_presence(self):
        source = PATCH.read_text()
        self.assertIn(
            "if [ -f titanium/android_config/parser/java/src/app/titanium/config/"
            "TitaniumConfParser.java ]; then",
            source,
        )
        self.assertIn(
            "if [ -f titanium/chromium_src/services/downstream/device/"
            "geolocation/android/java/src/org/chromium/device/geolocation/"
            "CoarseLocationRequests.java ]; then",
            source,
        )

    def test_patch_script_has_valid_shell_syntax(self):
        subprocess.run(["bash", "-n", str(PATCH)], check=True)


if __name__ == "__main__":
    unittest.main()
