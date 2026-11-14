#!/usr/bin/env python3
"""Report why a child process leaves ContentMain, and tolerate missing external
storage.

On the Android 9 target the renderer disappears ~31 seconds after a navigation
starts: ``ChildProcessService`` logs ``entering child main``, then nothing, and
the browser's ``setupConnection`` call fails with ``DeadObjectException``. That
sequence means ``ChildProcessDelegate.runMain()`` returned, because the service
immediately calls ``reportCleanExit()`` and ``exitChildProcess()`` afterwards.
Without a log line for the return value there is no way to tell an intentional
shutdown from an early bail-out.

Log the value that ``runMain()`` returns, and log the point right before the
process leaves ContentMain.

The same device also fails to prepare its external storage volume
(``/storage/udisk2``: ``ServiceSpecificException`` code -30), so every process
logs ``ContextImpl: Failed to ensure .../files``. Skip those directories when the
volume is unavailable instead of retrying them on every start.
"""
import os
import sys

CHILD_SERVICE = "base/android/java/src/org/chromium/base/process_launcher/ChildProcessService.java"
PATH_UTILS = "base/android/java/src/org/chromium/base/PathUtils.java"

RUN_MAIN_ORIGINAL = """        mDelegate.runMain();
        try {
            mParentProcess.reportCleanExit();"""

RUN_MAIN_PATCHED = """        mDelegate.runMain();
        // Helium: runMain() returning means the service reports a clean exit and
        // calls exitChildProcess(); log it so an early bail-out is visible.
        Log.i(TAG, "Helium trace: child main returned pid=%d", Process.myPid());
        try {
            mParentProcess.reportCleanExit();"""

EXTERNAL_STORAGE_ORIGINAL = """    public static @JniType("std::string") String getExternalStorageDirectory() {
        return Environment.getExternalStorageDirectory().getAbsolutePath();
    }"""

EXTERNAL_STORAGE_PATCHED = """    public static @JniType("std::string") String getExternalStorageDirectory() {
        // Helium: the external volume may be unavailable (udisk2 fails to
        // prepare with ServiceSpecificException -30). Fall back to the app's
        // internal files directory instead of handing out a dead path.
        java.io.File external = Environment.getExternalStorageDirectory();
        if (external == null || !external.canRead()) {
            return ContextUtils.getApplicationContext().getFilesDir().getAbsolutePath();
        }
        return external.getAbsolutePath();
    }"""


def _read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _write(path, content):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def _replace_once(path, original, patched, label):
    if not os.path.isfile(path):
        return False
    content = _read(path)
    if patched in content:
        return False
    if original not in content:
        print(f"Warning: could not find {label} in {path}", file=sys.stderr)
        return False
    _write(path, content.replace(original, patched, 1))
    print(f"Patched {label}: {path}")
    return True


def patch_source_tree(src_dir):
    changed = False
    if _replace_once(
        os.path.join(src_dir, CHILD_SERVICE),
        RUN_MAIN_ORIGINAL,
        RUN_MAIN_PATCHED,
        "child process main return value logging",
    ):
        changed = True
    if _replace_once(
        os.path.join(src_dir, PATH_UTILS),
        EXTERNAL_STORAGE_ORIGINAL,
        EXTERNAL_STORAGE_PATCHED,
        "external storage fallback",
    ):
        changed = True
    return changed


def main():
    patch_source_tree(sys.argv[1] if len(sys.argv) > 1 else ".")


if __name__ == "__main__":
    main()
