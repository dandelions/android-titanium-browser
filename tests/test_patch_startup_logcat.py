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
        self.assertIn('"/system/bin/logcat"', result)
        self.assertIn('"-v", "threadtime"', result)
        self.assertIn('"--pid=" + android.os.Process.myPid()', result)
        self.assertIn('"-r", "4096"', result)
        self.assertIn('"-n", "3"', result)
        self.assertLess(result.index("Helium startup logcat capture"), result.index("public static void onCreate()") if "public static void onCreate()" in result else len(result))

    def test_both_captures_start_after_process_start(self):
        # Without -T logcat replays whatever the system buffers still hold, which
        # is why a fresh crash log used to contain entries from hours before.
        PATCH.patch_source_tree(self.root)
        result = self.hook_path.read_text()
        self.assertIn('"MM-dd HH:mm:ss.SSS", java.util.Locale.US', result)
        self.assertEqual(2, result.count('"-T", sinceStamp'))
        for buffer_name in ('"-b", "all"', '"-b", "crash"'):
            start = result.index(buffer_name)
            block = result[start : result.index(".start()", start)]
            self.assertIn('"-T", sinceStamp', block)

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

    def test_installs_boot_crash_and_native_crash_capture(self):
        PATCH.patch_source_tree(self.root)
        result = self.hook_path.read_text()
        self.assertIn('"helium_boot.log"', result)
        self.assertIn('"Helium process started at "', result)
        self.assertIn('"crash_log.txt"', result)
        self.assertIn("Thread.setDefaultUncaughtExceptionHandler", result)
        self.assertIn("error.printStackTrace(crashWriter);", result)
        self.assertIn("previousHandler.uncaughtException(thread, error);", result)
        # debuggerd reports from another process, so the tombstone needs an
        # unfiltered crash buffer capture in addition to the --pid capture.
        self.assertIn('"native-crash.txt"', result)
        self.assertIn('"-b", "crash"', result)

    def test_upgrades_previous_logcat_only_hook(self):
        self.hook_path.write_text(
            """final class ChromeApplicationImplHooks {
    private static final String TAG = "ChromeApplicationImplHooks";
    public static void postAttachBaseContext() {
        // Helium startup logcat capture
        startCapture();
    }

    public static void onCreate() {
    }
}
"""
        )
        self.assertTrue(PATCH.patch_source_tree(self.root))
        result = self.hook_path.read_text()
        self.assertIn('"crash_log.txt"', result)
        self.assertIn('"native-crash.txt"', result)

    def test_strips_legacy_car_logger(self):
        target = self.root / PATCH.LEGACY_CALLERS[0]
        target.parent.mkdir(parents=True)
        target.write_text(
            """final class SplitChromeApplication {
    protected void attachBaseContext(Context context) {
        super.attachBaseContext(context);
        initCarSdcardLogging(context);
    }

    // [CAR_SDCARD_LOGGER_START]
    private static void initCarSdcardLogging(android.content.Context context) {
        new java.io.FileWriter(new java.io.File("helium_boot.log"), true);
    }
    // [CAR_SDCARD_LOGGER_END]

}
"""
        )
        self.assertTrue(PATCH.strip_legacy_car_logger(self.root))
        result = target.read_text()
        self.assertNotIn(PATCH.LEGACY_START, result)
        self.assertNotIn("initCarSdcardLogging", result)
        self.assertIn("super.attachBaseContext(context);", result)
        self.assertEqual(result.count("{"), result.count("}"))
        # Idempotent: nothing left to strip.
        self.assertFalse(PATCH.strip_legacy_car_logger(self.root))

    def test_strip_runs_only_on_standard_branches(self):
        for name, root in (("patch.sh", "."), ("hotfix_existing_src.sh", '"$SRC_DIR"')):
            with self.subTest(script=name):
                text = (Path(__file__).resolve().parents[1] / name).read_text()
                start = text.index('if [[ "$CURRENT_BRANCH" == old-* ]]')
                else_start = text.index("\nelse\n", start)
                end = text.index("\nfi", else_start)
                self.assertNotIn("--strip-legacy-car-logger", text[start:else_start])
                self.assertIn("--strip-legacy-car-logger", text[else_start:end])


if __name__ == "__main__":
    unittest.main()
