#!/usr/bin/env python3
"""Log a native backtrace when a Helium process dies from a fatal signal.

Helium processes die silently on Android: the renderer disappears while it is
foreground (``primaryMainFrameRenderProcessGone() ... termination status: 6``)
and neither the tombstone nor logcat carries a stack, because tombstoned is not
reachable from the app and Chromium installs no in-process handler on Android.
V8 does not install its own handler either (``use_v8_handler`` is false on
Linux/Android), so the process gets no diagnostic at all.

Install one handler for the fatal signals that logs a native stack and then
restores the previous action and re-raises, so crash reporting and the app's
restart behaviour stay unchanged.
"""
import os
import sys

MAIN_FILE = "content/app/android/content_main_android.cc"

FATAL_HELPER = '''// Helium: dump a native stack before a fatal signal kills the process.
std::atomic<bool> g_helium_fatal_logged{false};

struct HeliumPrevSignalAction {
  int signal_number;
  struct sigaction action;
};

HeliumPrevSignalAction g_helium_prev_abrt;
HeliumPrevSignalAction g_helium_prev_segv;
HeliumPrevSignalAction g_helium_prev_bus;
HeliumPrevSignalAction g_helium_prev_ill;
HeliumPrevSignalAction g_helium_prev_fpe;

void HeliumFatalSignalLogger(int sig, siginfo_t* info, void*) {
  if (!g_helium_fatal_logged.exchange(true)) {
    __android_log_print(ANDROID_LOG_FATAL, "HeliumNativeCrash",
                        "signal=%d code=%d addr=%p pid=%d", sig,
                        info ? info->si_code : 0,
                        info ? info->si_addr : nullptr,
                        static_cast<int>(getpid()));
    base::debug::StackTrace trace;
    std::string text = trace.ToString();
    __android_log_print(ANDROID_LOG_FATAL, "HeliumNativeCrash", "%s",
                        text.c_str());
  }
  HeliumPrevSignalAction* previous = &g_helium_prev_abrt;
  if (previous->signal_number != sig) {
    previous = &g_helium_prev_segv;
  }
  if (previous->signal_number != sig) {
    previous = &g_helium_prev_bus;
  }
  if (previous->signal_number != sig) {
    previous = &g_helium_prev_ill;
  }
  if (previous->signal_number != sig) {
    previous = &g_helium_prev_fpe;
  }
  if (previous->signal_number == sig) {
    sigaction(sig, &previous->action, nullptr);
  }
  raise(sig);
}

void HeliumInstallOneFatalSignalLogger(int sig,
                                       HeliumPrevSignalAction* previous) {
  previous->signal_number = sig;
  struct sigaction action = {};
  action.sa_sigaction = &HeliumFatalSignalLogger;
  action.sa_flags = SA_SIGINFO;
  sigaction(sig, &action, &previous->action);
}

void HeliumInstallFatalSignalLogger() {
  HeliumInstallOneFatalSignalLogger(SIGABRT, &g_helium_prev_abrt);
  HeliumInstallOneFatalSignalLogger(SIGSEGV, &g_helium_prev_segv);
  HeliumInstallOneFatalSignalLogger(SIGBUS, &g_helium_prev_bus);
  HeliumInstallOneFatalSignalLogger(SIGILL, &g_helium_prev_ill);
  HeliumInstallOneFatalSignalLogger(SIGFPE, &g_helium_prev_fpe);
}

'''

ANCHOR = "ContentMainRunner* GetContentMainRunner() {"
CALL_ANCHOR = "  HeliumInstallSigSysLogger();\n"
CALL_ADDED = "  HeliumInstallSigSysLogger();\n  HeliumInstallFatalSignalLogger();\n"

# The first revision of this patch only handled SIGABRT.
OLD_ABORT_HELPER_START = "// Helium: dump a native stack before an abort kills the process.\n"
OLD_ABORT_HELPER_END = "void HeliumInstallAbortLogger() {\n"
OLD_CALL = "  HeliumInstallAbortLogger();\n"


def _read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _write(path, content):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def _upgrade_abort_only(path, content):
    """Replace the SIGABRT-only handler written by the first revision."""
    start = content.find(OLD_ABORT_HELPER_START)
    end = content.find(OLD_ABORT_HELPER_END, start)
    if start < 0 or end < 0:
        return False
    block_end = content.index("\n}\n\n", end) + len("\n}\n\n")
    new_content = content[:start] + FATAL_HELPER + content[block_end:]
    new_content = new_content.replace(OLD_CALL, CALL_ADDED, 1)
    _write(path, new_content)
    print(f"Upgraded native crash backtrace logging: {path}")
    return True


HELPER_START = "// Helium: dump a native stack before a fatal signal kills the process.\n"
ARRAY_MARKER = "HeliumPrevSignalAction g_helium_prev_actions[5];"


def _upgrade_array_revision(path, content):
    """Replace the array-indexed revision rejected by -Wunsafe-buffer-usage."""
    start = content.find(HELPER_START)
    end = content.find(ANCHOR, start)
    if start < 0 or end < 0:
        return False
    new_content = content[:start] + FATAL_HELPER + content[end:]
    _write(path, new_content)
    print(f"Upgraded native crash backtrace logging: {path}")
    return True


def patch_source_tree(src_dir):
    path = os.path.join(src_dir, MAIN_FILE)
    if not os.path.isfile(path):
        return False
    content = _read(path)
    if ARRAY_MARKER in content:
        return _upgrade_array_revision(path, content)
    if "HeliumFatalSignalLogger" in content:
        return False
    if "HeliumAbortLogger" in content:
        return _upgrade_abort_only(path, content)
    if ANCHOR not in content or CALL_ANCHOR not in content:
        print(
            f"Warning: could not find the content entry point in {path}",
            file=sys.stderr,
        )
        return False

    new_content = content.replace(ANCHOR, FATAL_HELPER + ANCHOR, 1)
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
    print(f"Patched native crash backtrace logging: {path}")
    return True


def main():
    patch_source_tree(sys.argv[1] if len(sys.argv) > 1 else ".")


if __name__ == "__main__":
    main()
