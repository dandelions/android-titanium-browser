#!/usr/bin/env python3
"""Enable bounded crash and startup log capture in the Android app files directory."""

import sys
from pathlib import Path

MARKER = "Helium startup logcat capture"
HOOK = "public static void postAttachBaseContext() {"
NEXT_HOOK = "public static void onCreate() {"
LEGACY_START = "// [CAR_SDCARD_LOGGER_START]"
LEGACY_END = "// [CAR_SDCARD_LOGGER_END]"
LEGACY_CALL = "initCarSdcardLogging("
LEGACY_CALLERS = (
    "chrome/android/java/src/org/chromium/chrome/browser/base/SplitChromeApplication.java",
    "chrome/android/java/src/org/chromium/chrome/browser/ChromeTabbedActivity.java",
)

BODY = '''public static void postAttachBaseContext() {
        // Helium startup logcat capture
        try {
            java.io.File logDirectory =
                    org.chromium.base.ContextUtils.getApplicationContext()
                            .getExternalFilesDir("logs");
            if (logDirectory == null || (!logDirectory.isDirectory() && !logDirectory.mkdirs())) {
                android.util.Log.e(TAG, "Cannot create external startup log directory");
                return;
            }
            java.io.File bootLog = new java.io.File(logDirectory, "helium_boot.log");
            java.io.FileWriter bootWriter = new java.io.FileWriter(bootLog, true);
            bootWriter.write(
                    "Helium process started at "
                            + new java.util.Date()
                            + " PID="
                            + android.os.Process.myPid()
                            + " process="
                            + android.app.Application.getProcessName()
                            + "\\n");
            bootWriter.close();

            final java.io.File javaCrashLog =
                    new java.io.File(logDirectory, "crash_log.txt");
            final java.lang.Thread.UncaughtExceptionHandler previousHandler =
                    java.lang.Thread.getDefaultUncaughtExceptionHandler();
            java.lang.Thread.setDefaultUncaughtExceptionHandler(
                    new java.lang.Thread.UncaughtExceptionHandler() {
                        @Override
                        public void uncaughtException(
                                java.lang.Thread thread, java.lang.Throwable error) {
                            try {
                                java.io.PrintWriter crashWriter =
                                        new java.io.PrintWriter(
                                                new java.io.FileWriter(javaCrashLog, true));
                                crashWriter.println(
                                        "=== Helium java crash at "
                                                + new java.util.Date()
                                                + " thread="
                                                + thread.getName()
                                                + " ===");
                                error.printStackTrace(crashWriter);
                                crashWriter.flush();
                                crashWriter.close();
                            } catch (Throwable ignored) {
                                // Crash logging must never mask the original failure.
                            }
                            if (previousHandler != null) {
                                previousHandler.uncaughtException(thread, error);
                            }
                        }
                    });

            java.io.File logFile = new java.io.File(logDirectory, "startup-logcat.txt");
            new ProcessBuilder(
                            "/system/bin/logcat",
                            "-b", "all",
                            "-v", "threadtime",
                            "--pid=" + android.os.Process.myPid(),
                            "-f", logFile.getAbsolutePath(),
                            "-r", "4096",
                            "-n", "3")
                    .start();

            // debuggerd dumps native crashes (SIGTRAP/SIGSEGV) from its own process, so the
            // --pid filter above never records the tombstone. Keep the whole crash buffer.
            java.io.File nativeCrashFile =
                    new java.io.File(logDirectory, "native-crash.txt");
            new ProcessBuilder(
                            "/system/bin/logcat",
                            "-b", "crash",
                            "-v", "threadtime",
                            "-f", nativeCrashFile.getAbsolutePath(),
                            "-r", "2048",
                            "-n", "2")
                    .start();
        } catch (Exception e) {
            android.util.Log.e(TAG, "Cannot start startup logcat capture", e);
        }
    }'''


def patch_hook(path: Path) -> bool:
    text = path.read_text()
    start = text.find(HOOK)
    if start < 0:
        raise RuntimeError(f"postAttachBaseContext hook not found in {path}")
    end = text.find(NEXT_HOOK, start + len(HOOK))
    if end < 0:
        raise RuntimeError(f"onCreate hook not found after postAttachBaseContext in {path}")

    patched = text[:start] + BODY + "\n\n    " + text[end:]
    if patched == text:
        return False
    path.write_text(patched)
    return True


def patch_source_tree(source_root: Path) -> bool:
    candidates = (
        source_root / "helium/chromium_src/chrome/android/java/src/org/chromium/chrome/browser/ChromeApplicationImplHooks.java",
        source_root / "vanadium/chromium_src/chrome/android/java/src/org/chromium/chrome/browser/ChromeApplicationImplHooks.java",
    )
    hook_path = next((path for path in candidates if path.is_file()), None)
    if hook_path is None:
        raise RuntimeError(
            "ChromeApplicationImplHooks.java not found under helium/chromium_src or vanadium/chromium_src"
        )
    return patch_hook(hook_path)


def strip_legacy_car_logger(source_root: Path) -> bool:
    """Remove the old-android SD card logger left behind in a reused source tree."""
    changed = False
    for relative in LEGACY_CALLERS:
        path = source_root / relative
        if not path.is_file():
            continue
        text = path.read_text()
        start = text.find(LEGACY_START)
        while start >= 0:
            end = text.find(LEGACY_END, start)
            if end < 0:
                break
            end += len(LEGACY_END)
            if end < len(text) and text[end] == "\n":
                end += 1
            text = text[:start] + text[end:]
            start = text.find(LEGACY_START)
        kept = [
            line
            for line in text.splitlines(keepends=True)
            if LEGACY_CALL not in line
        ]
        text = "".join(kept)
        if text != path.read_text():
            path.write_text(text)
            changed = True
    return changed


if __name__ == "__main__":
    arguments = [argument for argument in sys.argv[1:] if not argument.startswith("--")]
    root = Path(arguments[0] if arguments else ".")
    try:
        if "--strip-legacy-car-logger" in sys.argv[1:]:
            stripped = strip_legacy_car_logger(root)
            print(
                "[patch_startup_logcat] removed legacy car crash logger"
                if stripped
                else "[patch_startup_logcat] no legacy car crash logger found"
            )
        else:
            changed = patch_source_tree(root)
            print(
                "[patch_startup_logcat] startup logcat capture installed"
                if changed
                else "[patch_startup_logcat] startup logcat capture already installed"
            )
    except (OSError, RuntimeError) as error:
        print(f"[patch_startup_logcat] {error}", file=sys.stderr)
        raise SystemExit(1)
