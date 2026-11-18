import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "patch_old_android_single_process.py"
SPEC = importlib.util.spec_from_file_location("patch_old_android_single_process", MODULE_PATH)
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)


SOURCE = """static void JNI_BrowserStartupControllerImpl_SetCommandLineFlags(
    JNIEnv* env,
    bool single_process) {
  SetContentCommandLineFlags(single_process);
}
"""


class OldAndroidSingleProcessPatchTest(unittest.TestCase):
    def test_forces_single_process(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / PATCH.TARGET
            path.parent.mkdir(parents=True)
            path.write_text(SOURCE)
            self.assertTrue(PATCH.patch_source_tree(root))
            result = path.read_text()
            self.assertIn("SetContentCommandLineFlags(/*single_process=*/true);", result)
            self.assertNotIn("SetContentCommandLineFlags(single_process);", result)
            self.assertIn(PATCH.MARKER, result)

    def test_is_idempotent(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / PATCH.TARGET
            path.parent.mkdir(parents=True)
            path.write_text(SOURCE)
            self.assertTrue(PATCH.patch_source_tree(root))
            patched = path.read_text()
            self.assertFalse(PATCH.patch_source_tree(root))
            self.assertEqual(patched, path.read_text())

    def test_fails_if_hook_is_missing(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / PATCH.TARGET
            path.parent.mkdir(parents=True)
            path.write_text("static void unrelated() {}\n")
            with self.assertRaises(RuntimeError):
                PATCH.patch_source_tree(root)


if __name__ == "__main__":
    unittest.main()
