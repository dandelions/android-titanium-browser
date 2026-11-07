import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "patch_extension_popup_width.py"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "chromium_157"


class TestPatchExtensionPopupWidth(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self.temp_dir.name)
        self.popup = self.work_dir / "ExtensionActionPopup.java"
        self.contents_java = self.work_dir / "ExtensionActionPopupContents.java"
        self.contents_cc = self.work_dir / "extension_action_popup_contents.cc"
        self.contents_h = self.work_dir / "extension_action_popup_contents.h"

        shutil.copy(FIXTURES / "ExtensionActionPopup.java", self.popup)
        shutil.copy(FIXTURES / "ExtensionActionPopupContents.java", self.contents_java)
        shutil.copy(FIXTURES / "extension_action_popup_contents.cc", self.contents_cc)
        shutil.copy(FIXTURES / "extension_action_popup_contents.h", self.contents_h)

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_patch(self):
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                str(self.popup),
                str(self.contents_java),
                str(self.contents_cc),
                str(self.contents_h),
            ],
            capture_output=True,
            text=True,
        )

    def test_patch_chromium_157_success_and_idempotent(self):
        res1 = self.run_patch()
        self.assertEqual(res1.returncode, 0, f"STDOUT: {res1.stdout}\nSTDERR: {res1.stderr}")

        contents_java_text = self.contents_java.read_text(encoding="utf-8")
        self.assertIn("public static ExtensionActionPopupContents create(long hostPtr)", contents_java_text)
        self.assertIn("long hostPtr, boolean inspectWithDevTools)", contents_java_text)
        self.assertIn("ExtensionActionPopupContents create(long hostPtr, boolean inspectWithDevTools);", contents_java_text)
        self.assertIn("void resizeDueToAutoResize(int width, int height, float scale);", contents_java_text)
        self.assertIn("setMaxSize(int maxWidth, int maxHeight)", contents_java_text)

        contents_cc_text = self.contents_cc.read_text(encoding="utf-8")
        self.assertIn("constexpr gfx::Size kMinSize = {256, 25};", contents_cc_text)
        self.assertIn("void ExtensionActionPopupContents::SetMaxSize(", contents_cc_text)
        self.assertIn("JNI_ExtensionActionPopupContents_Create", contents_cc_text)
        self.assertIn("ExtensionActionPopupContents::Create(", contents_cc_text)

        contents_h_text = self.contents_h.read_text(encoding="utf-8")
        self.assertIn("void SetMaxSize(int max_width, int max_height);", contents_h_text)
        self.assertIn("int max_height_ = 600;", contents_h_text)

        popup_text = self.popup.read_text(encoding="utf-8")
        self.assertIn("private static class ScaledContentView extends FrameLayout", popup_text)
        self.assertIn("mScaledContentView = new ScaledContentView(", popup_text)

        # Idempotence
        res2 = self.run_patch()
        self.assertEqual(res2.returncode, 0, f"Second run failed: {res2.stderr}")
        self.assertEqual(self.contents_java.read_text(encoding="utf-8"), contents_java_text)
        self.assertEqual(self.contents_cc.read_text(encoding="utf-8"), contents_cc_text)
        self.assertEqual(self.contents_h.read_text(encoding="utf-8"), contents_h_text)
        self.assertEqual(self.popup.read_text(encoding="utf-8"), popup_text)


if __name__ == "__main__":
    unittest.main()
