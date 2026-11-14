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

The stack is walked from the frame-pointer chain recorded in the signal
context. ``base::debug::StackTrace()`` unwinds from the handler itself, so on
its own it only ever reports the handler and the signal trampoline.
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

// Helium: load bias of libchrome.so, so crash addresses stay symbolizable.
// Android randomizes the load address per process, so a raw address in the
// log cannot be mapped to a symbol without it.
uintptr_t g_helium_libchrome_base = 0;

// Helium: log an address together with its offset inside libchrome.so.
void HeliumLogFrameAddress(const char* label, int index, uintptr_t address) {
  const uintptr_t offset = address - g_helium_libchrome_base;
  if (g_helium_libchrome_base != 0 && offset < 0x20000000) {
    __android_log_print(ANDROID_LOG_FATAL, "HeliumNativeCrash", "%s%d %#lx+%#lx",
                        label, index, static_cast<unsigned long>(g_helium_libchrome_base),
                        static_cast<unsigned long>(offset));
  } else {
    __android_log_print(ANDROID_LOG_FATAL, "HeliumNativeCrash", "%s%d %#lx",
                        label, index, static_cast<unsigned long>(address));
  }
}

// Helium: walk the frame-pointer chain recorded in the signal context.
// base::debug::StackTrace() starts unwinding from the handler itself, so it
// reports the handler and the signal trampoline instead of the interrupted
// code.
void HeliumLogInterruptedStack(void* context) {
#if defined(__aarch64__)
  const auto* interrupted = static_cast<const ucontext_t*>(context);
  if (!interrupted) {
    return;
  }
  const uintptr_t stack_pointer = interrupted->uc_mcontext.sp;
  uintptr_t link_register = 0;
  uintptr_t frame = 0;
  // SAFETY: the aarch64 signal context always carries the 31 general purpose
  // registers; x29 holds the frame pointer and x30 the link register.
  UNSAFE_BUFFERS({
    frame = interrupted->uc_mcontext.regs[29];
    link_register = interrupted->uc_mcontext.regs[30];
  });
  __android_log_print(ANDROID_LOG_FATAL, "HeliumNativeCrash",
                      "pc=%#lx lr=%#lx sp=%#lx fp=%#lx",
                      static_cast<unsigned long>(interrupted->uc_mcontext.pc),
                      static_cast<unsigned long>(link_register),
                      static_cast<unsigned long>(stack_pointer),
                      static_cast<unsigned long>(frame));
  HeliumLogFrameAddress("pc", 0, interrupted->uc_mcontext.pc);
  HeliumLogFrameAddress("lr", 0, link_register);
  for (int depth = 0; depth < 32; ++depth) {
    // A frame outside the interrupted stack cannot be read without faulting.
    if ((frame & 0x7) != 0 || frame < stack_pointer ||
        frame - stack_pointer > (1u << 20)) {
      break;
    }
    uintptr_t next_frame = 0;
    uintptr_t return_address = 0;
    memcpy(&next_frame, reinterpret_cast<const void*>(frame),
           sizeof(next_frame));
    memcpy(&return_address, reinterpret_cast<const void*>(frame + 8),
           sizeof(return_address));
    if (return_address < 0x1000) {
      break;
    }
    HeliumLogFrameAddress("#", depth, return_address);
    if (next_frame <= frame) {
      break;
    }
    frame = next_frame;
  }
#else
  (void)context;
#endif
}

void HeliumFatalSignalLogger(int sig, siginfo_t* info, void* context) {
  if (!g_helium_fatal_logged.exchange(true)) {
    __android_log_print(ANDROID_LOG_FATAL, "HeliumNativeCrash",
                        "signal=%d code=%d addr=%p pid=%d", sig,
                        info ? info->si_code : 0,
                        info ? info->si_addr : nullptr,
                        static_cast<int>(getpid()));
    HeliumLogInterruptedStack(context);
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
  // Resolve the load bias here rather than in the handler: dladdr takes the
  // linker lock, which is not safe to acquire from a signal handler.
  Dl_info module = {};
  if (dladdr(reinterpret_cast<void*>(&HeliumInstallFatalSignalLogger), &module) &&
      module.dli_fbase) {
    g_helium_libchrome_base = reinterpret_cast<uintptr_t>(module.dli_fbase);
    __android_log_print(ANDROID_LOG_INFO, "HeliumNativeCrash",
                        "libchrome base %#lx",
                        static_cast<unsigned long>(g_helium_libchrome_base));
  }
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

HELPER_START = "// Helium: dump a native stack before a fatal signal kills the process.\n"
# Revisions before the stack walker logged the previous-action records as an
# array, or without any way to unwind past the handler and map its addresses
# back to libchrome.so.
ARRAY_MARKER = "HeliumPrevSignalAction g_helium_prev_actions[5];"
STACK_WALKER_MARKER = "g_helium_libchrome_base"


def _read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _write(path, content):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def _ensure_includes(content):
    """Add the headers the fatal signal logger needs."""
    if '#include <atomic>' not in content:
        content = content.replace(
            "#include <memory>\n",
            "#include <atomic>\n#include <cstring>\n#include <memory>\n#include <string>\n",
            1,
        )
    if '#include <ucontext.h>' not in content:
        content = content.replace(
            "#include <signal.h>\n",
            "#include <signal.h>\n#include <stdint.h>\n#include <ucontext.h>\n",
            1,
        )
    if '#include <dlfcn.h>' not in content:
        content = content.replace(
            "#include <android/log.h>\n",
            "#include <android/log.h>\n#include <dlfcn.h>\n",
            1,
        )
    if '#include "base/compiler_specific.h"' not in content:
        content = content.replace(
            '#include "base/lazy_instance.h"\n',
            '#include "base/compiler_specific.h"\n#include "base/lazy_instance.h"\n',
            1,
        )
    if '#include "base/debug/stack_trace.h"' not in content:
        content = content.replace(
            '#include "base/lazy_instance.h"\n',
            '#include "base/debug/stack_trace.h"\n#include "base/lazy_instance.h"\n',
            1,
        )
    return content


def _upgrade_abort_only(path, content):
    """Replace the SIGABRT-only handler written by the first revision."""
    start = content.find(OLD_ABORT_HELPER_START)
    end = content.find(OLD_ABORT_HELPER_END, start)
    if start < 0 or end < 0:
        return False
    block_end = content.index("\n}\n\n", end) + len("\n}\n\n")
    new_content = content[:start] + FATAL_HELPER + content[block_end:]
    new_content = new_content.replace(OLD_CALL, CALL_ADDED, 1)
    _write(path, _ensure_includes(new_content))
    print(f"Upgraded native crash backtrace logging: {path}")
    return True


def _replace_helper_block(path, content):
    """Rewrite an older revision of the handler with the current one."""
    start = content.find(HELPER_START)
    end = content.find(ANCHOR, start)
    if start < 0 or end < 0:
        return False
    new_content = content[:start] + FATAL_HELPER + content[end:]
    _write(path, _ensure_includes(new_content))
    print(f"Upgraded native crash backtrace logging: {path}")
    return True


def patch_source_tree(src_dir):
    path = os.path.join(src_dir, MAIN_FILE)
    if not os.path.isfile(path):
        return False
    content = _read(path)
    if ARRAY_MARKER in content:
        return _replace_helper_block(path, content)
    if "HeliumFatalSignalLogger" in content:
        if STACK_WALKER_MARKER in content:
            return False
        return _replace_helper_block(path, content)
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
    _write(path, _ensure_includes(new_content))
    print(f"Patched native crash backtrace logging: {path}")
    return True


def main():
    patch_source_tree(sys.argv[1] if len(sys.argv) > 1 else ".")


if __name__ == "__main__":
    main()
