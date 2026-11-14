#!/usr/bin/env python3
"""Keep the renderer usable when Chromium forces V8 into jitless mode.

On devices where the OS reports restricted memory (``isMemoryDclRestricted()``)
Helium appends ``--js-flags=--jitless`` to every sandboxed child process. The
renderer sandbox then selects the "no W^X" mprotect rule, which rejects
``mprotect(PROT_EXEC)`` with SIGSYS. V8 still calls mprotect for its code pages
during startup, so the renderer is killed before the first frame is committed
and every web page fails to load.

Allow PROT_EXEC in the renderer's mprotect rule regardless of the jitless flag:
a jitless V8 does not create executable code pages, so the rule change does not
widen the reachable attack surface, and it keeps the process alive.
"""
import os
import sys

POLICY_FILE = "sandbox/policy/linux/bpf_renderer_policy_linux.cc"
DELEGATE_FILE = "content/renderer/renderer_main_platform_delegate_android.cc"

ORIGINAL_MPROTECT = """ResultExpr RendererProcessPolicy::EvaluateSyscall(int sysno) const {
  if (!is_jit_disabled_) {
    switch (sysno) {
#if defined(__i386__) || defined(__x86_64__) || defined(__mips__) || \\
    defined(__aarch64__)
      case __NR_mmap:
#endif
#if defined(__i386__) || defined(__arm__) || \\
    (defined(ARCH_CPU_MIPS_FAMILY) && defined(ARCH_CPU_32_BITS))
      case __NR_mmap2:
#endif
        return RestrictMmapFlags(sysno);
      case __NR_mprotect:
      case __NR_pkey_mprotect:
        return RestrictMprotectFlags();
    }
  }
"""

PATCHED_MPROTECT = """ResultExpr RendererProcessPolicy::EvaluateSyscall(int sysno) const {
  if (!is_jit_disabled_) {
    switch (sysno) {
#if defined(__i386__) || defined(__x86_64__) || defined(__mips__) || \\
    defined(__aarch64__)
      case __NR_mmap:
#endif
#if defined(__i386__) || defined(__arm__) || \\
    (defined(ARCH_CPU_MIPS_FAMILY) && defined(ARCH_CPU_32_BITS))
      case __NR_mmap2:
#endif
        return RestrictMmapFlags(sysno);
      case __NR_mprotect:
      case __NR_pkey_mprotect:
        return RestrictMprotectFlags();
    }
  } else {
    // V8 keeps its code pages writable until they are marked executable, and it
    // still calls mprotect() for them when jitless mode is forced on. Denying
    // PROT_EXEC here kills the renderer before it can commit a navigation.
    switch (sysno) {
      case __NR_mprotect:
      case __NR_pkey_mprotect:
        return RestrictMprotectFlags();
    }
  }
"""

ORIGINAL_POLICY_CHOICE = """  if (sandbox::policy::SandboxTypeFromCommandLine(
          *base::CommandLine::ForCurrentProcess()) ==
          sandbox::mojom::Sandbox::kRenderer &&
    base::FeatureList::IsEnabled(
        sandbox::policy::features::kUseRendererProcessPolicy)) {
    bool dynamic_code_can_be_disabled = sandbox::policy::CanDynamicCodeBeDisabled();
    starter.set_policy(
        std::make_unique<sandbox::policy::RendererProcessPolicy>(options,
          dynamic_code_can_be_disabled));
  } else {
    starter.set_policy(
        std::make_unique<sandbox::BaselinePolicyAndroid>(options));
  }
"""

PATCHED_POLICY_CHOICE = """  // Always use the renderer policy. The baseline policy rejects
  // mprotect(PROT_EXEC), which kills the renderer while V8 sets up its code
  // pages, so every page load failed on this device.
  bool dynamic_code_can_be_disabled = sandbox::policy::CanDynamicCodeBeDisabled();
  LOG(INFO) << "Helium sandbox: renderer policy=1 jit_disabled="
            << dynamic_code_can_be_disabled << " js_flags="
            << base::CommandLine::ForCurrentProcess()->GetSwitchValueASCII(
                   blink::switches::kJavaScriptFlags);
  starter.set_policy(
      std::make_unique<sandbox::policy::RendererProcessPolicy>(options,
        dynamic_code_can_be_disabled));
"""


def _read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _write(path, content):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def patch_renderer_mprotect(src_dir):
    path = os.path.join(src_dir, POLICY_FILE)
    if not os.path.isfile(path):
        return False
    content = _read(path)
    if "jitless mode is forced on" in content:
        return False
    if ORIGINAL_MPROTECT not in content:
        print(f"Warning: could not find RendererProcessPolicy in {path}", file=sys.stderr)
        return False
    _write(path, content.replace(ORIGINAL_MPROTECT, PATCHED_MPROTECT, 1))
    print(f"Patched renderer mprotect rule: {path}")
    return True


def patch_sandbox_policy(src_dir):
    path = os.path.join(src_dir, DELEGATE_FILE)
    if not os.path.isfile(path):
        return False
    content = _read(path)
    if "Helium sandbox: renderer policy=" in content:
        return False
    if ORIGINAL_POLICY_CHOICE not in content:
        print(f"Warning: could not find the sandbox policy choice in {path}", file=sys.stderr)
        return False
    new_content = content.replace(ORIGINAL_POLICY_CHOICE, PATCHED_POLICY_CHOICE, 1)
    if '#include "base/command_line.h"' not in new_content:
        new_content = new_content.replace(
            '#include "base/android/android_info.h"\n',
            '#include "base/android/android_info.h"\n'
            '#include "base/command_line.h"\n'
            '#include "base/logging.h"\n',
            1,
        )
    if 'third_party/blink/public/common/switches.h' not in new_content:
        new_content = new_content.replace(
            '#include "sandbox/sandbox_buildflags.h"\n',
            '#include "sandbox/sandbox_buildflags.h"\n'
            '#include "third_party/blink/public/common/switches.h"\n',
            1,
        )
    _write(path, new_content)
    print(f"Patched renderer sandbox policy: {path}")
    return True


def patch_source_tree(src_dir):
    changed = patch_renderer_mprotect(src_dir)
    changed = patch_sandbox_policy(src_dir) or changed
    return changed


def main():
    patch_source_tree(sys.argv[1] if len(sys.argv) > 1 else ".")


if __name__ == "__main__":
    main()
