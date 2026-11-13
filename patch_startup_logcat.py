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
        // Car head units mount storage in several ways, and getExternalFilesDir()
        // can come back null or unwritable, which used to drop every log silently.
        // Probe each candidate with a real write and keep the first working one.
        java.io.File logDirectory = null;
        StringBuilder attemptedDirectories = new StringBuilder();
        try {
            android.content.Context context =
                    org.chromium.base.ContextUtils.getApplicationContext();
            java.util.List<java.io.File> candidates = new java.util.ArrayList<java.io.File>();
            candidates.add(context.getExternalFilesDir("logs"));
            java.io.File externalRoot = context.getExternalFilesDir(null);
            if (externalRoot != null) {
                candidates.add(new java.io.File(externalRoot, "helium-logs"));
            }
            candidates.add(
                    new java.io.File(
                            android.os.Environment.getExternalStorageDirectory(),
                            "Download/HeliumLogs"));
            candidates.add(context.getDir("helium-logs", android.content.Context.MODE_PRIVATE));
            for (java.io.File candidate : candidates) {
                if (candidate == null) {
                    continue;
                }
                attemptedDirectories.append(' ').append(candidate.getAbsolutePath());
                if (!candidate.isDirectory() && !candidate.mkdirs()) {
                    continue;
                }
                java.io.File probe = new java.io.File(candidate, ".helium-write-probe");
                try {
                    java.io.FileOutputStream probeStream =
                            new java.io.FileOutputStream(probe, false);
                    probeStream.write(0x48);
                    probeStream.close();
                    logDirectory = candidate;
                    probe.delete();
                    break;
                } catch (Throwable ignored) {
                    // Not writable; fall through to the next candidate.
                }
            }
            if (logDirectory == null) {
                android.util.Log.e(
                        TAG, "No writable Helium log directory, tried:" + attemptedDirectories);
            } else {
                android.util.Log.i(TAG, "Helium logs at " + logDirectory.getAbsolutePath());
            }
        } catch (Throwable caught) {
            android.util.Log.e(TAG, "Cannot resolve Helium log directory", caught);
        }
        if (logDirectory == null) {
            return;
        }
        try {
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

            // Every renderer, GPU and utility process runs this hook too. Only the
            // browser process may own the shared log files: the extra logcat readers
            // flooded logd with "unexpected EOF", and each child truncated
            // native-crash.txt while the browser was still appending to it.
            String processName = android.app.Application.getProcessName();
            if (processName != null
                    && !processName.equals(
                            org.chromium.base.ContextUtils.getApplicationContext()
                                    .getPackageName())) {
                return;
            }

            // Chromium switches for on-device diagnosis, one per line in
            // <external files>/helium-switches.txt. Only the browser process reads the
            // file; child processes inherit the resulting command line.
            try {
                java.io.File externalDir =
                        org.chromium.base.ContextUtils.getApplicationContext()
                                .getExternalFilesDir(null);
                java.io.File switchFile =
                        externalDir == null
                                ? null
                                : new java.io.File(externalDir, "helium-switches.txt");
                if (switchFile != null
                        && switchFile.isFile()
                        && org.chromium.base.CommandLine.isInitialized()) {
                    java.io.BufferedReader switchReader =
                            new java.io.BufferedReader(new java.io.FileReader(switchFile));
                    String switchLine;
                    java.util.List<String> loadedSwitches = new java.util.ArrayList<String>();
                    while ((switchLine = switchReader.readLine()) != null) {
                        switchLine = switchLine.trim();
                        while (switchLine.startsWith("-")) {
                            switchLine = switchLine.substring(1);
                        }
                        if (switchLine.isEmpty() || switchLine.startsWith("#")) {
                            continue;
                        }
                        org.chromium.base.CommandLine.getInstance().appendSwitch(switchLine);
                        loadedSwitches.add(switchLine);
                    }
                    switchReader.close();
                    if (!loadedSwitches.isEmpty()) {
                        android.util.Log.i(
                                TAG,
                                "Applied diagnostic switches from "
                                        + switchFile.getName()
                                        + ": "
                                        + loadedSwitches);
                    }
                }
            } catch (Throwable ignored) {
                // Diagnostics must never block startup.
            }

            // A previous run's EOF notices are stale once the readers are back to one.
            new java.io.FileOutputStream(errorLog, false).close();

            // Android kills a crashed app's process group, which used to take the
            // logcat children down before they could flush the tombstone. setsid
            // moves them into their own session so they outlive the app.
            String detach =
                    new java.io.File("/system/bin/setsid").canExecute()
                            ? "/system/bin/setsid "
                            : "";

            java.io.File logFile = new java.io.File(logDirectory, "startup-logcat.txt");
            java.io.File warningLogFile =
                    new java.io.File(logDirectory, "warning-error-logcat.txt");
            new ProcessBuilder(
                            "/system/bin/logcat",
                            "-b", "all",
                            "-v", "threadtime",
                            "--uid=" + android.os.Process.myUid(),
                            "*:W",
                            "-f", warningLogFile.getAbsolutePath(),
                            "-r", "4096",
                            "-n", "3")
                    .start();

            java.util.List<String> appLogCommand = new java.util.ArrayList<String>();
            appLogCommand.add("/system/bin/logcat");
            appLogCommand.add("-b");
            appLogCommand.add("main,system,crash");
            appLogCommand.add("-v");
            appLogCommand.add("threadtime");
            if (timeFilterSupported) {
                appLogCommand.add("-T");
                appLogCommand.add(sinceStamp);
            }
            appLogCommand.add("--uid=" + android.os.Process.myUid());
            appLogCommand.add("-f");
            appLogCommand.add(new java.io.File(logDirectory, "application-logcat.txt").getAbsolutePath());
            appLogCommand.add("-r");
            appLogCommand.add("4096");
            appLogCommand.add("-n");
            appLogCommand.add("3");
            new ProcessBuilder(appLogCommand).start();

            java.io.File mainErrorTemp = new java.io.File(logDirectory, "logcat-main-stderr.tmp");
            java.io.File crashErrorTemp = new java.io.File(logDirectory, "logcat-crash-stderr.tmp");
            StringBuilder logcatLine = new StringBuilder(detach);
            // Skip the events buffer: it is high volume and made logcat fall behind
            // logd enough to die with "Unexpected EOF" before writing anything.
            logcatLine.append("/system/bin/logcat -b main,system,crash -v threadtime");
            if (timeFilterSupported) {
                logcatLine.append(" -T '").append(sinceStamp).append("'");
            }
            logcatLine.append(" --pid=").append(android.os.Process.myPid());
            logcatLine.append(" -f '").append(logFile.getAbsolutePath()).append("'");
            logcatLine.append(" -r 4096 -n 3");
            logcatLine
                    .append(" >/dev/null 2>'")
                    .append(mainErrorTemp.getAbsolutePath())
                    .append("'; if [ -s '")
                    .append(mainErrorTemp.getAbsolutePath())
                    .append("' ]; then sed '/[Uu]nexpected EOF!/d' '")
                    .append(mainErrorTemp.getAbsolutePath())
                    .append("' >> '")
                    .append(errorLog.getAbsolutePath())
                    .append("'; : > '")
                    .append(mainErrorTemp.getAbsolutePath())
                    .append("'; fi");
            // logd drops slow readers; reconnect while suppressing its repeated EOF notice.
            new ProcessBuilder(
                            "/system/bin/sh",
                            "-c",
                            "while :; do " + logcatLine + "; sleep 1; done &")
                    .start();

            // debuggerd writes tombstones to the shared crash buffer under its own
            // PID, so --pid would miss them. Filter complete tombstone context by
            // the embedded app Cmdline instead of saving every app's crashes.
            java.io.File nativeCrashFile =
                    new java.io.File(logDirectory, "native-crash.txt");
            new java.io.FileOutputStream(nativeCrashFile, false).close();
            StringBuilder crashLine = new StringBuilder(detach);
            crashLine.append("/system/bin/logcat -b crash -v threadtime");
            if (timeFilterSupported) {
                crashLine.append(" -T '").append(sinceStamp).append("'");
            }
            crashLine.append(" 2>'").append(crashErrorTemp.getAbsolutePath()).append("'");
            crashLine.append(
                    " | /system/bin/grep -F -B 20 -A 120 "
                            + "'Cmdline: io.github.jqssun.helium' 2>/dev/null");
            crashLine.append(" >>'").append(nativeCrashFile.getAbsolutePath()).append("'");
            crashLine.append("; if [ -s '").append(crashErrorTemp.getAbsolutePath());
            crashLine.append("' ]; then sed '/[Uu]nexpected EOF!/d' '");
            crashLine.append(crashErrorTemp.getAbsolutePath());
            crashLine.append("' >> '").append(errorLog.getAbsolutePath()).append("'");
            crashLine.append("; : > '").append(crashErrorTemp.getAbsolutePath()).append("'; fi");
            new ProcessBuilder(
                            "/system/bin/sh",
                            "-c",
                            "while :; do " + crashLine + "; sleep 1; done &")
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


CHILD_SERVICE = "base/android/java/src/org/chromium/base/process_launcher/ChildProcessService.java"

def _insert_after_line(lines, anchor, statement, after_marker=None):
    """Insert |statement| after the first |anchor| line at or following |after_marker|."""
    start = 0
    if after_marker is not None:
        for index, line in enumerate(lines):
            if line.strip() == after_marker:
                start = index
                break
    for index in range(start, len(lines)):
        if lines[index].strip() == anchor:
            indent = lines[index][: len(lines[index]) - len(lines[index].lstrip())]
            lines.insert(index + 1, indent + statement + "\n")
            return True
    return False


def _insert_before_line(lines, anchor, statement, after_marker=None):
    """Insert |statement| before the first |anchor| line at or following |after_marker|."""
    start = 0
    if after_marker is not None:
        for index, line in enumerate(lines):
            if line.strip() == after_marker:
                start = index
                break
    for index in range(start, len(lines)):
        if lines[index].strip() == anchor:
            indent = lines[index][: len(lines[index]) - len(lines[index].lstrip())]
            lines.insert(index, indent + statement + "\n")
            return True
    return False


def patch_child_process_service_trace(source_root: Path) -> bool:
    """Trace how far a child process gets before it dies.

    Renderers and utility processes disappear on the Android 9 target without any
    Java stack trace, so the launcher only reports TERMINATION_STATUS_LAUNCH_FAILED.
    These log lines land in the UID-filtered capture and pin down the failing step.
    """
    path = source_root / CHILD_SERVICE
    if not path.is_file():
        return False
    text = path.read_text()
    if "Helium trace:" in text:
        return False
    lines = text.splitlines(keepends=True)

    _insert_after_line(
        lines,
        "assert mServiceBound;",
        'Log.i(TAG, "Helium trace: setupConnection pid=%d", Process.myPid());',
        after_marker="public void setupConnection(",
    )
    _insert_before_line(
        lines,
        "CommandLine.init(mChildProcessArgs.commandLine);",
        'Log.i(TAG, "Helium trace: main thread has args pid=%d", Process.myPid());',
    )
    _insert_before_line(
        lines,
        "mDelegate.loadNativeLibrary(getApplicationContext());",
        'Log.i(TAG, "Helium trace: loading native library pid=%d", Process.myPid());',
    )
    _insert_after_line(
        lines,
        "mDelegate.loadNativeLibrary(getApplicationContext());",
        'Log.i(TAG, "Helium trace: native library loaded pid=%d", Process.myPid());',
    )
    _insert_before_line(
        lines,
        "mDelegate.onBeforeMain();",
        'Log.i(TAG, "Helium trace: child process ready pid=%d", Process.myPid());',
    )
    _insert_after_line(
        lines,
        "} catch (Throwable e) {",
        'Log.e(TAG, "Helium trace: child process init failed", e);',
        after_marker="mDelegate.onBeforeMain();",
    )
    _insert_before_line(
        lines,
        "mDelegate.runMain();",
        'Log.i(TAG, "Helium trace: entering child main pid=%d", Process.myPid());',
    )

    patched = "".join(lines)
    if patched == text or "Helium trace:" not in patched:
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
    changed = patch_hook(hook_path)
    if patch_child_process_service_trace(source_root):
        changed = True
    return changed


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
