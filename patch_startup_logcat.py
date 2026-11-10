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
            java.io.File errorLog = new java.io.File(logDirectory, "logcat-error.txt");

            // -T keeps a capture from replaying what the system buffers already
            // hold, but it needs a stamp logcat understands. This device interprets
            // the wall clock as UTC, so a local-time string made the filter start
            // hours in the future and every capture stayed empty. Always format UTC.
            java.text.SimpleDateFormat sinceFormat =
                    new java.text.SimpleDateFormat(
                            "MM-dd HH:mm:ss.SSS", java.util.Locale.US);
            sinceFormat.setTimeZone(java.util.TimeZone.getTimeZone("UTC"));
            String sinceStamp = sinceFormat.format(new java.util.Date());
            boolean timeFilterSupported = false;
            try {
                java.util.List<String> probeCommand = new java.util.ArrayList<String>();
                probeCommand.add("/system/bin/logcat");
                probeCommand.add("-b");
                probeCommand.add("crash");
                probeCommand.add("-T");
                probeCommand.add(sinceStamp);
                probeCommand.add("-d");
                probeCommand.add("-t");
                probeCommand.add("1");
                java.lang.Process probe = new ProcessBuilder(probeCommand).start();
                timeFilterSupported =
                        probe.waitFor(500, java.util.concurrent.TimeUnit.MILLISECONDS)
                                && probe.exitValue() == 0;
                if (!timeFilterSupported) {
                    probe.destroy();
                }
            } catch (Throwable ignored) {
                // Treated as unsupported; the captures below stay usable.
            }

            java.io.FileWriter bootWriter = new java.io.FileWriter(bootLog, true);
            bootWriter.write(
                    "Helium process started at "
                            + new java.util.Date()
                            + " PID="
                            + android.os.Process.myPid()
                            + " process="
                            + android.app.Application.getProcessName()
                            + " timeFilter="
                            + timeFilterSupported
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

            // Android kills a crashed app's process group, which used to take the
            // logcat children down before they could flush the tombstone. setsid
            // moves them into their own session so they outlive the app.
            String detach =
                    new java.io.File("/system/bin/setsid").canExecute()
                            ? "/system/bin/setsid "
                            : "";

            java.io.File logFile = new java.io.File(logDirectory, "startup-logcat.txt");
            StringBuilder logcatLine = new StringBuilder(detach);
            logcatLine.append("/system/bin/logcat -b all -v threadtime");
            if (timeFilterSupported) {
                logcatLine.append(" -T '").append(sinceStamp).append("'");
            }
            logcatLine.append(" --pid=").append(android.os.Process.myPid());
            logcatLine.append(" -f '").append(logFile.getAbsolutePath()).append("'");
            logcatLine.append(" -r 4096 -n 3");
            logcatLine
                    .append(" >/dev/null 2>>'")
                    .append(errorLog.getAbsolutePath())
                    .append("'");
            new ProcessBuilder("/system/bin/sh", "-c", logcatLine + " &").start();

            // debuggerd dumps native crashes (SIGTRAP/SIGSEGV) from its own process, so the
            // --pid filter above never records the tombstone. Keep the whole crash buffer.
            java.io.File nativeCrashFile =
                    new java.io.File(logDirectory, "native-crash.txt");
            StringBuilder crashLine = new StringBuilder(detach);
            crashLine.append("/system/bin/logcat -b crash -v threadtime");
            if (timeFilterSupported) {
                crashLine.append(" -T '").append(sinceStamp).append("'");
            }
            crashLine.append(" -f '").append(nativeCrashFile.getAbsolutePath()).append("'");
            crashLine.append(" -r 2048 -n 2");
            crashLine
                    .append(" >/dev/null 2>>'")
                    .append(errorLog.getAbsolutePath())
                    .append("'");
            new ProcessBuilder("/system/bin/sh", "-c", crashLine + " &").start();

            if (timeFilterSupported) {
                // A time filter the platform reads differently than intended leaves
                // the capture silently empty. Add an unfiltered writer rather than
                // lose the tombstone; it only doubles up in that broken case.
                new java.lang.Thread(
                                new java.lang.Runnable() {
                                    @Override
                                    public void run() {
                                        try {
                                            java.lang.Thread.sleep(1500);
                                        } catch (InterruptedException ignored) {
                                            return;
                                        }
                                        if (nativeCrashFile.length() > 0) {
                                            return;
                                        }
                                        try {
                                            StringBuilder fallback =
                                                    new StringBuilder(detach);
                                            fallback.append(
                                                    "/system/bin/logcat -b crash -v threadtime");
                                            fallback
                                                    .append(" -f '")
                                                    .append(nativeCrashFile.getAbsolutePath())
                                                    .append("'");
                                            fallback.append(" -r 2048 -n 2");
                                            fallback
                                                    .append(" >/dev/null 2>>'")
                                                    .append(errorLog.getAbsolutePath())
                                                    .append("'");
                                            new ProcessBuilder(
                                                            "/system/bin/sh", "-c", fallback + " &")
                                                    .start();
                                        } catch (Throwable ignored) {
                                            // Nothing left to fall back to.
                                        }
                                    }
                                },
                                "helium-logcat-guard")
                        .start();
            }
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
