#!/usr/bin/env python3
"""Log a native backtrace when a Helium process aborts.

Every Helium browser process on Android aborts shortly after startup with
``FORTIFY: fcntl(F_SETFD) passed non-FD_CLOEXEC flag: 0x80000`` from a
ThreadPoolForegroundWorker thread. Neither the tombstone nor logcat carries a
stack, and the offending ``fcntl`` call is not in the Chromium tree, so the
only way to find it is to unwind from inside the process.

The handler only logs and then re-raises with the default action, so the
tombstone and the app's restart behaviour stay unchanged.
"""
import os
import sys

MAIN_FILE = "content/app/android/content_main_android.cc"

ABORT_HELPER = '''// Helium: dump a native stack before an abort kills the process.
std::atomic<bool> g_helium_abort_logged{false};

void HeliumAbortLogger(int sig, siginfo_t*, void*) {
  if (!g_helium_abort_logged.exchange(true)) {
    __android_log_print(ANDROID_LOG_FATAL, "HeliumNativeCrash",
                        "signal=%d pid=%d", sig, static_cast<int>(getpid()));
    base::debug::StackTrace trace;
    std::string text = trace.ToString();
    __android_log_print(ANDROID_LOG_FATAL, "HeliumNativeCrash", "%s",
                        text.c_str());
  }
  signal(sig, SIG_DFL);
  raise(sig);
}

void HeliumInstallAbortLogger() {
  struct sigaction action = {};
  action.sa_sigaction = &HeliumAbortLogger;
  action.sa_flags = SA_SIGINFO;
  sigaction(SIGABRT, &action, nullptr);
}

'''

ANCHOR = "ContentMainRunner* GetContentMainRunner() {"
CALL_ANCHOR = "  HeliumInstallSigSysLogger();\n"
CALL_ADDED = "  HeliumInstallSigSysLogger();\n  HeliumInstallAbortLogger();\n"


def _read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _write(path, content):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def patch_source_tree(src_dir):
    path = os.path.join(src_dir, MAIN_FILE)
    if not os.path.isfile(path):
        return False
    content = _read(path)
    if "HeliumAbortLogger" in content:
        return False
    if ANCHOR not in content or CALL_ANCHOR not in content:
        print(
            f"Warning: could not find the content entry point in {path}",
            file=sys.stderr,
        )
        return False

    new_content = content.replace(ANCHOR, ABORT_HELPER + ANCHOR, 1)
    new_content = new_content.replace(CALL_ANCHOR, CALL_ADDED, 1)
    if '#include <atomic>' not in new_content:
        new_content = new_content.replace(
            "#include <memory>\n",
            "#include <atomic>\n#include <memory>\n#include <string>\n",
            1,
        )
    if '#include "base/debug/stack_trace.h"' not in new_content:
        new_content = new_content.replace(
            '#include "base/lazy_instance.h"\n',
            '#include "base/debug/stack_trace.h"\n#include "base/lazy_instance.h"\n',
            1,
        )
    _write(path, new_content)
    print(f"Patched native abort backtrace logging: {path}")
    return True


def main():
    patch_source_tree(sys.argv[1] if len(sys.argv) > 1 else ".")


if __name__ == "__main__":
    main()
