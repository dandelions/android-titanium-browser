#!/usr/bin/env python3
"""Guard AccessibilityManager.getRecommendedTimeoutMillis against Android 9 (API 28).

``AccessibilityManager.getRecommendedTimeoutMillis(int, int)`` was introduced in
Android 10 (API 29 / Android Q). On Android 9 targets this invocation throws
``java.lang.NoSuchMethodError`` and aborts the browser process whenever a
Snackbar, Toast, or autofill duration is calculated (e.g. BadFlagsSnackbarManager
or SnackbarManager).

Guard the call with a ``Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q`` check
and fall back to ``nonA11yTimeout`` on earlier API levels.
"""
import os
import sys

TARGET_FILE = (
    "ui/accessibility/android/java/src/org/chromium/ui/accessibility/"
    "AccessibilityStateDelegateImpl.java"
)

ORIGINAL_TIMEOUT = """    @Override
    public int getRecommendedTimeoutMillis(int minimumTimeout, int nonA11yTimeout) {
        if (mState == null) updateAccessibilityServices();

        int recommendedTimeout =
                fetchAccessibilityManager()
                        .getRecommendedTimeoutMillis(
                                nonA11yTimeout,
                                FLAG_CONTENT_ICONS | FLAG_CONTENT_TEXT | FLAG_CONTENT_CONTROLS);

        return Math.max(minimumTimeout, recommendedTimeout);
    }"""

PATCHED_TIMEOUT = """    @Override
    public int getRecommendedTimeoutMillis(int minimumTimeout, int nonA11yTimeout) {
        if (mState == null) updateAccessibilityServices();

        int recommendedTimeout = nonA11yTimeout;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            recommendedTimeout =
                    fetchAccessibilityManager()
                            .getRecommendedTimeoutMillis(
                                    nonA11yTimeout,
                                    FLAG_CONTENT_ICONS | FLAG_CONTENT_TEXT | FLAG_CONTENT_CONTROLS);
        }

        return Math.max(minimumTimeout, recommendedTimeout);
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
    path = os.path.join(src_dir, TARGET_FILE)
    return _replace_once(
        path,
        ORIGINAL_TIMEOUT,
        PATCHED_TIMEOUT,
        "accessibility recommended timeout API level guard",
    )


def main():
    patch_source_tree(sys.argv[1] if len(sys.argv) > 1 else ".")


if __name__ == "__main__":
    main()
