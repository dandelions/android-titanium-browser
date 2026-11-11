#!/usr/bin/env python3
"""Enable bounded early-start logcat capture in the Android app files directory."""

import sys
from pathlib import Path

MARKER = "Helium startup logcat capture"
HOOK = "public static void postAttachBaseContext() {"
NEXT_HOOK = "public static void onCreate() {"
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
            java.io.File warningLogFile = new java.io.File(logDirectory, "warning-error-logcat.txt");
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


if __name__ == "__main__":
    try:
        changed = patch_source_tree(Path(sys.argv[1] if len(sys.argv) > 1 else "."))
    except (OSError, RuntimeError) as error:
        print(f"[patch_startup_logcat] {error}", file=sys.stderr)
        raise SystemExit(1)
    print("[patch_startup_logcat] startup logcat capture installed" if changed else
          "[patch_startup_logcat] startup logcat capture already installed")
