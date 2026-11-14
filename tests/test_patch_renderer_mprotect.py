import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "patch_renderer_mprotect.py"
SPEC = importlib.util.spec_from_file_location("patch_renderer_mprotect", MODULE_PATH)
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)


POLICY_SOURCE = """ResultExpr RendererProcessPolicy::EvaluateSyscall(int sysno) const {
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

  switch (sysno) {
    case __NR_clock_getres:
      return RestrictClockID();
  }
}
"""

DELEGATE_SOURCE = """#include "base/android/android_info.h"
#include "sandbox/sandbox_buildflags.h"

bool RendererMainPlatformDelegate::EnableSandbox() {
  sandbox::SeccompStarterAndroid starter(
      base::android::android_info::sdk_int());
#if BUILDFLAG(USE_SECCOMP_BPF)
  sandbox::BaselinePolicyAndroid::RuntimeOptions options(
      starter.GetDefaultBaselineOptions());
  if (sandbox::policy::SandboxTypeFromCommandLine(
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
#endif
  starter.StartSandbox();

  SetSeccompSandboxStatus(starter.status());

  return true;
}
"""


class RendererMprotectPatchTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.policy_path = self.root / PATCH.POLICY_FILE
        self.policy_path.parent.mkdir(parents=True)
        self.policy_path.write_text(POLICY_SOURCE)
        self.delegate_path = self.root / PATCH.DELEGATE_FILE
        self.delegate_path.parent.mkdir(parents=True)
        self.delegate_path.write_text(DELEGATE_SOURCE)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_allows_mprotect_when_jit_is_disabled(self):
        self.assertTrue(PATCH.patch_source_tree(self.root))
        result = self.policy_path.read_text()
        self.assertIn("jitless mode is forced on", result)
        jitless_branch = result[result.index("} else {") :]
        self.assertIn("case __NR_mprotect:", jitless_branch)
        self.assertIn("return RestrictMprotectFlags();", jitless_branch)

    def test_always_uses_the_renderer_policy(self):
        PATCH.patch_source_tree(self.root)
        delegate = self.delegate_path.read_text()
        self.assertIn("Helium sandbox: renderer policy=", delegate)
        self.assertIn("std::make_unique<sandbox::policy::RendererProcessPolicy>", delegate)
        self.assertNotIn("std::make_unique<sandbox::BaselinePolicyAndroid>", delegate)
        self.assertIn('#include "base/command_line.h"', delegate)
        self.assertIn('#include "base/logging.h"', delegate)
        self.assertIn('#include "third_party/blink/public/common/switches.h"', delegate)

    def test_repeated_runs_are_no_ops(self):
        self.assertTrue(PATCH.patch_source_tree(self.root))
        policy_once = self.policy_path.read_text()
        delegate_once = self.delegate_path.read_text()
        self.assertFalse(PATCH.patch_source_tree(self.root))
        self.assertEqual(policy_once, self.policy_path.read_text())
        self.assertEqual(delegate_once, self.delegate_path.read_text())

    def test_missing_files_are_ignored(self):
        self.policy_path.unlink()
        self.delegate_path.unlink()
        self.assertFalse(PATCH.patch_source_tree(self.root))


class RendererMprotectWiringTest(unittest.TestCase):
    def test_scripts_apply_the_patch_only_on_old_android(self):
        for name, target in (("patch.sh", "."), ("hotfix_existing_src.sh", '"$SRC_DIR"')):
            with self.subTest(script=name):
                text = (Path(__file__).resolve().parents[1] / name).read_text()
                block_start = text.index("if is_old_version_branch; then")
                block_end = text.index("verify_old_android_features.py", block_start)
                block = text[block_start:block_end]
                self.assertIn(
                    f'python3 "$SCRIPT_DIR/patch_renderer_mprotect.py" {target}', block
                )


if __name__ == "__main__":
    unittest.main()
