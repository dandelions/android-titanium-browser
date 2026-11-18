#!/usr/bin/env python3
"""Use Chromium single-process mode for the old Android compatibility build.

VMOS Android 9 starts the renderer and reaches its message loop, but the
browser's CommitNavigation Mojo message never arrives in that renderer. The
same build commits pages with --single-process, which keeps the renderer in the
browser process and avoids the broken cross-process handoff.
"""
import os
import sys

TARGET = "content/browser/android/browser_startup_controller.cc"
ORIGINAL = """static void JNI_BrowserStartupControllerImpl_SetCommandLineFlags(
    JNIEnv* env,
    bool single_process) {
  SetContentCommandLineFlags(single_process);
}
"""
PATCHED = """static void JNI_BrowserStartupControllerImpl_SetCommandLineFlags(
    JNIEnv* env,
    bool single_process) {
  // VMOS Android 9 loses CommitNavigation between the browser and renderer
  // processes. Keep the renderer in-process for the old compatibility build.
  SetContentCommandLineFlags(/*single_process=*/true);
}
"""
MARKER = "VMOS Android 9 loses CommitNavigation"


def patch_source_tree(src_dir: str) -> bool:
    path = os.path.join(src_dir, TARGET)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read()
    if MARKER in content:
        return False
    if ORIGINAL not in content:
        raise RuntimeError(f"single-process startup hook not found in {path}")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content.replace(ORIGINAL, PATCHED, 1))
    print(f"Patched old-android single-process startup: {path}")
    return True


if __name__ == "__main__":
    try:
        patch_source_tree(sys.argv[1] if len(sys.argv) > 1 else ".")
    except (FileNotFoundError, RuntimeError) as error:
        print(f"[patch_old_android_single_process] {error}", file=sys.stderr)
        raise SystemExit(1)
