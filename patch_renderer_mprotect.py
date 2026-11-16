#!/usr/bin/env python3
"""Allow the VMOS renderer's required executable-memory transition.

The VMOS Android 9 target reports the memory restriction API as unavailable.
Chromium still starts the renderer with its Android renderer policy, and the
policy must allow the normal mprotect(PROT_EXEC) transition used during V8
startup. Keep Chromium's renderer-policy selection intact; replacing the
Android baseline path wholesale changes unrelated syscall rules and can leave
navigation without a usable renderer.
"""
import os
import re
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
    // VMOS still performs the executable-memory transition while jitless is
    // selected. Keep the renderer alive without changing other syscall rules.
    switch (sysno) {
      case __NR_mprotect:
      case __NR_pkey_mprotect:
        return RestrictMprotectFlags();
    }
  }
"""

LEGACY_MPROTECT = """ResultExpr RendererProcessPolicy::EvaluateSyscall(int sysno) const {
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

LEGACY_POLICY_PATTERN = re.compile(
    r"  // Always use the renderer policy\..*?"
    r"  starter\.set_policy\(\n"
    r"      std::make_unique<sandbox::policy::RendererProcessPolicy>\(options,\n"
    r"        dynamic_code_can_be_disabled\)\);\n",
    re.DOTALL,
)


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
    if "VMOS still performs the executable-memory transition" in content:
        return False
    if LEGACY_MPROTECT in content:
        _write(path, content.replace(LEGACY_MPROTECT, PATCHED_MPROTECT, 1))
        print(f"Upgraded renderer mprotect rule: {path}")
        return True
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
        new_content, count = LEGACY_POLICY_PATTERN.subn(
            ORIGINAL_POLICY_CHOICE, content, count=1
        )
        if count != 1:
            print(f"Warning: renderer policy patch needs manual upgrade: {path}", file=sys.stderr)
            return False
        for include in (
            '#include "base/command_line.h"\n',
            '#include "base/logging.h"\n',
            '#include "third_party/blink/public/common/switches.h"\n',
        ):
            new_content = new_content.replace(include, "", 1)
        _write(path, new_content)
        print(f"Restored Chromium renderer policy selection: {path}")
        return True

    if "Helium renderer policy upgrade" in content:
        return False
    return False


def patch_source_tree(src_dir):
    changed = patch_renderer_mprotect(src_dir)
    changed = patch_sandbox_policy(src_dir) or changed
    return changed


def main():
    patch_source_tree(sys.argv[1] if len(sys.argv) > 1 else ".")


if __name__ == "__main__":
    main()
