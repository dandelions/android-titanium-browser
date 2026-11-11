import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "patch_startup_logcat.py"
SPEC = importlib.util.spec_from_file_location("patch_startup_logcat", MODULE_PATH)
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)


class StartupLogcatPatchTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.hook_path = (
            self.root
            / "helium/chromium_src/chrome/android/java/src/org/chromium/chrome/browser/ChromeApplicationImplHooks.java"
        )
        self.hook_path.parent.mkdir(parents=True)
        self.hook_path.write_text(
            """final class ChromeApplicationImplHooks {
    private static final String TAG = "ChromeApplicationImplHooks";
    public static void postAttachBaseContext() {
    }

    public static void onCreate() {
    }
}
"""
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_installs_early_bounded_logcat_capture(self):
        self.assertTrue(PATCH.patch_source_tree(self.root))
        result = self.hook_path.read_text()
        self.assertIn('getExternalFilesDir("logs")', result)
        self.assertIn('"startup-logcat.txt"', result)
        self.assertIn('"warning-error-logcat.txt"', result)
        self.assertIn('"/system/bin/logcat"', result)
        self.assertIn('"-v", "threadtime"', result)
        self.assertIn('"--pid=" + android.os.Process.myPid()', result)
        self.assertIn('"--uid=" + android.os.Process.myUid()', result)
        self.assertIn('"*:W"', result)
        self.assertEqual(2, result.count('"-r", "4096"'))
        self.assertEqual(2, result.count('"-n", "3"'))
        self.assertLess(result.index("Helium startup logcat capture"), result.index("public static void onCreate()") if "public static void onCreate()" in result else len(result))

    def test_is_idempotent(self):
        PATCH.patch_source_tree(self.root)
        first_result = self.hook_path.read_text()
        self.assertFalse(PATCH.patch_source_tree(self.root))
        self.assertEqual(first_result, self.hook_path.read_text())
        self.assertEqual(1, first_result.count(PATCH.MARKER))

    def test_repairs_legacy_extra_method_closing_brace(self):
        legacy = """final class ChromeApplicationImplHooks {
    private static final String TAG = "ChromeApplicationImplHooks";
    public static void postAttachBaseContext() {
        // Helium startup logcat capture
        try {
            startCapture();
        } catch (Exception e) {
            reportError(e);
        }
    }
}
    public static void onCreate() {
    }
}
"""
        self.hook_path.write_text(legacy)

        self.assertTrue(PATCH.patch_hook(self.hook_path))
        result = self.hook_path.read_text()
        self.assertEqual(result.count("{"), result.count("}"))
        self.assertEqual(1, result.count(PATCH.MARKER))
        self.assertIn("\n    public static void onCreate() {", result)

    def test_missing_hook_fails_explicitly(self):
        self.hook_path.write_text("final class ChromeApplicationImplHooks {}\n")
        with self.assertRaisesRegex(RuntimeError, "postAttachBaseContext hook not found"):
            PATCH.patch_source_tree(self.root)

    def test_missing_hook_file_fails_explicitly(self):
        self.hook_path.unlink()
        with self.assertRaisesRegex(RuntimeError, "ChromeApplicationImplHooks.java not found"):
            PATCH.patch_source_tree(self.root)


if __name__ == "__main__":
    unittest.main()
