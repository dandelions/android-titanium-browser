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
        self.assertIn('"--uid=" + android.os.Process.myUid()', result)
        self.assertIn('"*:W"', result)
        self.assertIn('"application-logcat.txt"', result)
        self.assertIn('appLogCommand.add("main,system,crash")', result)
        self.assertIn('appLogCommand.add("--uid=" + android.os.Process.myUid())', result)
        app_log_start = result.index('java.util.List<String> appLogCommand')
        app_log_end = result.index('java.io.File mainErrorTemp', app_log_start)
        app_log_block = result[app_log_start:app_log_end]
        self.assertNotIn('"*:W"', app_log_block)
        self.assertIn('appLogCommand.add("-T")', app_log_block)
        self.assertIn('appLogCommand.add("4096")', app_log_block)
        self.assertIn('appLogCommand.add("3")', app_log_block)
        self.assertIn("/system/bin/logcat -b main,system,crash -v threadtime", result)
        self.assertIn('" --pid="', result)
        self.assertIn("android.os.Process.myPid()", result)
        self.assertIn("-r 4096 -n 3", result)
        self.assertLess(result.index("Helium startup logcat capture"), result.index("public static void onCreate()") if "public static void onCreate()" in result else len(result))

    def test_captures_detach_from_the_app_process_group(self):
        # Android kills a crashed app's process group; without setsid the logcat
        # children died before flushing, which left the log files behind empty.
        PATCH.patch_source_tree(self.root)
        result = self.hook_path.read_text()
        self.assertIn('new java.io.File("/system/bin/setsid").canExecute()', result)
        self.assertIn("String detach =", result)
        self.assertEqual(2, result.count("new StringBuilder(detach)"))
        for name in ("logcatLine", "crashLine"):
            start = result.index(f"StringBuilder {name} = ")
            block = result[start : result.index(".start();", start)]
            self.assertIn('"/system/bin/sh",', block)
            self.assertIn('"while :; do "', block)

    def test_generated_java_has_no_unterminated_string_literal(self):
        # A bare "\n" inside the Python template becomes a real newline and breaks
        # the Java literal (build error: unterminated string literal).
        PATCH.patch_source_tree(self.root)
        result = self.hook_path.read_text()
        for number, line in enumerate(result.splitlines(), start=1):
            self.assertFalse(
                line.rstrip().endswith('+ "'),
                f"line {number} ends with an unterminated literal: {line!r}",
            )
            self.assertEqual(
                0,
                line.count('"') % 2,
                f"line {number} has an odd number of quotes: {line!r}",
            )
        self.assertIn('+ "\\n");', result)

    def test_only_the_browser_process_runs_the_logcat_readers(self):
        # Renderer, GPU and utility processes run this hook too. Their extra logcat
        # readers flooded logd with "unexpected EOF", and each child truncated
        # native-crash.txt while the browser was still appending to it.
        PATCH.patch_source_tree(self.root)
        result = self.hook_path.read_text()
        gate = result.index("String processName = android.app.Application.getProcessName();")
        self.assertIn(
            "org.chromium.base.ContextUtils.getApplicationContext()", result[gate:]
        )
        self.assertIn("return;", result[gate : gate + 400])
        self.assertLess(result.index("setDefaultUncaughtExceptionHandler"), gate)
        self.assertLess(gate, result.index("StringBuilder logcatLine"))
        self.assertLess(
            gate, result.index("new java.io.FileOutputStream(nativeCrashFile, false).close();")
        )
        self.assertLess(gate, result.index('new java.io.FileOutputStream(errorLog, false)'))

    def test_log_directory_falls_back_to_writable_locations(self):
        # Car head units can expose an external files dir that is missing or
        # read-only; the capture then produced nothing at all.
        PATCH.patch_source_tree(self.root)
        result = self.hook_path.read_text()
        self.assertIn('"Download/HeliumLogs"', result)
        self.assertIn('new java.io.File(externalRoot, "helium-logs")', result)
        self.assertIn('context.getDir("helium-logs", android.content.Context.MODE_PRIVATE)', result)
        self.assertIn('".helium-write-probe"', result)
        self.assertIn("No writable Helium log directory", result)
        self.assertIn('"Helium logs at "', result)
        self.assertLess(
            result.index('getExternalFilesDir("logs")'),
            result.index('"Download/HeliumLogs"'),
        )

    def test_reads_diagnostic_switches_from_the_app_files_dir(self):
        PATCH.patch_source_tree(self.root)
        result = self.hook_path.read_text()
        gate = result.index("String processName = android.app.Application.getProcessName();")
        switches = result.index('"helium-switches.txt"')
        self.assertLess(gate, switches)
        self.assertLess(switches, result.index("StringBuilder logcatLine"))
        block = result[
            result.index("java.io.File externalDir =") : result.index(
                "catch (Throwable ignored)", switches
            )
            + 40
        ]
        self.assertIn("CommandLine.isInitialized()", block)
        self.assertIn("getExternalFilesDir(null)", block)
        self.assertIn("catch (Throwable ignored)", block)
        self.assertIn("Applied diagnostic switches from", block)

    def test_native_crash_capture_filters_to_helium_tombstones(self):
        PATCH.patch_source_tree(self.root)
        result = self.hook_path.read_text()
        self.assertIn('new java.io.FileOutputStream(nativeCrashFile, false).close();', result)
        start = result.index("StringBuilder crashLine = new StringBuilder(detach);")
        end = result.index('.start();', start)
        block = result[start:end]
        self.assertIn('/system/bin/logcat -b crash -v threadtime', block)
        self.assertIn("grep -F -B 20 -A 120", block)
        self.assertIn("Cmdline: io.github.jqssun.helium", block)
        self.assertNotIn("--pid=", block)

    def test_both_captures_start_after_process_start(self):
        # Without -T logcat replays whatever the system buffers still hold, which
        # is why a fresh crash log used to contain entries from hours before.
        PATCH.patch_source_tree(self.root)
        result = self.hook_path.read_text()
        self.assertIn('"MM-dd HH:mm:ss.SSS", java.util.Locale.US', result)
        for name, buffer in (("logcatLine", "-b main,system,crash"), ("crashLine", "-b crash")):
            start = result.index(f"StringBuilder {name} = ")
            block = result[start : result.index(".start();", start)]
            self.assertIn("if (timeFilterSupported) {", block)
            self.assertIn('append(" -T \'").append(sinceStamp)', block)
            self.assertIn(buffer, block)

    def test_time_filter_stamp_is_utc(self):
        # The device reads the -T wall clock as UTC; a local-time stamp pushed the
        # filter hours into the future and left every capture empty.
        PATCH.patch_source_tree(self.root)
        result = self.hook_path.read_text()
        self.assertIn("java.text.SimpleDateFormat sinceFormat", result)
        self.assertIn(
            'sinceFormat.setTimeZone(java.util.TimeZone.getTimeZone("UTC"))', result
        )
        self.assertLess(
            result.index('getTimeZone("UTC")'), result.index("String sinceStamp")
        )

    def test_native_crash_capture_does_not_fall_back_to_unfiltered_logs(self):
        PATCH.patch_source_tree(self.root)
        result = self.hook_path.read_text()
        start = result.index("StringBuilder crashLine = new StringBuilder(detach);")
        end = result.index('new ProcessBuilder(', start)
        crash_capture = result[start:end]
        self.assertIn("Cmdline: io.github.jqssun.helium", crash_capture)
        self.assertNotIn('"helium-logcat-guard"', result)
        self.assertNotIn('"logcat-fallback-stderr.tmp"', result)

    def test_logcat_stderr_filters_repeated_unexpected_eof(self):
        PATCH.patch_source_tree(self.root)
        result = self.hook_path.read_text()
        self.assertIn('"logcat-error.txt"', result)
        self.assertGreaterEqual(result.count("sed '/[Uu]nexpected EOF!/d'"), 2)
        self.assertIn("[Uu]nexpected EOF!", result)
        self.assertIn('"logcat-main-stderr.tmp"', result)
        self.assertIn('"logcat-crash-stderr.tmp"', result)
        self.assertIn("append(errorLog.getAbsolutePath())", result)
        self.assertIn("append(mainErrorTemp.getAbsolutePath())", result)
        self.assertIn("append(crashErrorTemp.getAbsolutePath())", result)

    def test_logcat_stderr_keeps_non_eof_errors(self):
        PATCH.patch_source_tree(self.root)
        result = self.hook_path.read_text()
        self.assertIn("[Uu]nexpected EOF!", result)
        self.assertIn(" >> '", result)
        self.assertIn("; : > '", result)

    def test_time_filter_is_probed_before_use(self):
        # A logcat build that rejects -T exits before writing anything, which left
        # only helium_boot.log behind, so probe first and record the outcome.
        PATCH.patch_source_tree(self.root)
        result = self.hook_path.read_text()
        probe = result.index("timeFilterSupported =")
        first_capture = result.index("StringBuilder logcatLine")
        self.assertLess(probe, first_capture)
        self.assertIn('probeCommand.add("-T")', result)
        self.assertIn("probe.waitFor(500, java.util.concurrent.TimeUnit.MILLISECONDS)", result)
        self.assertIn('" timeFilter="', result)
        self.assertIn("+ timeFilterSupported", result)

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
        # debuggerd reports from another process, so filter the crash buffer by
        # the app command line instead of saving every app's tombstone.
        self.assertIn('"native-crash.txt"', result)
        self.assertIn("/system/bin/logcat -b crash -v threadtime", result)
        self.assertIn("Cmdline: io.github.jqssun.helium", result)
        self.assertIn('"warning-error-logcat.txt"', result)

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
