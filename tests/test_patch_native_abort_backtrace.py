import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "patch_native_abort_backtrace.py"
SPEC = importlib.util.spec_from_file_location("patch_native_abort_backtrace", MODULE_PATH)
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)


SOURCE = """#include "content/app/android/content_main_android.h"

#include <android/log.h>
#include <signal.h>
#include <unistd.h>

#include <memory>

#include "base/lazy_instance.h"

namespace {

void HeliumInstallSigSysLogger() {
  struct sigaction action = {};
  action.sa_sigaction = &HeliumSigSysLogger;
  sigaction(SIGSYS, &action, nullptr);
}

ContentMainRunner* GetContentMainRunner() {
  return nullptr;
}

static int32_t JNI_ContentMain_Start(JNIEnv* env, bool start_minimal_browser) {
  HeliumInstallSigSysLogger();
  return StartContentMain(start_minimal_browser);
}

}  // namespace
"""


class NativeAbortBacktracePatchTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.path = self.root / PATCH.MAIN_FILE
        self.path.parent.mkdir(parents=True)
        self.path.write_text(SOURCE)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_installs_fatal_signal_handlers_that_dump_a_stack(self):
        self.assertTrue(PATCH.patch_source_tree(self.root))
        result = self.path.read_text()
        self.assertIn(
            "void HeliumFatalSignalLogger(int sig, siginfo_t* info, void*) {", result
        )
        self.assertIn("base::debug::StackTrace trace;", result)
        self.assertIn('"HeliumNativeCrash"', result)
        for signal_name in ("SIGABRT", "SIGSEGV", "SIGBUS", "SIGILL", "SIGFPE"):
            self.assertIn(signal_name, result)
        self.assertIn("  HeliumInstallFatalSignalLogger();", result)
        # The previous handler must be restored before re-raising, otherwise the
        # process would spin on the same fault.
        self.assertIn("sigaction(sig, &previous.action, nullptr);", result)
        self.assertIn("raise(sig);", result)
        self.assertIn('#include "base/debug/stack_trace.h"', result)
        self.assertIn("#include <atomic>", result)
        self.assertIn("#include <string>", result)
        self.assertLess(
            result.index("void HeliumFatalSignalLogger"),
            result.index("ContentMainRunner* GetContentMainRunner()"),
        )
        self.assertLess(
            result.index("HeliumInstallSigSysLogger();"),
            result.index("HeliumInstallFatalSignalLogger();"),
        )

    def test_repeated_runs_are_no_ops(self):
        self.assertTrue(PATCH.patch_source_tree(self.root))
        once = self.path.read_text()
        self.assertFalse(PATCH.patch_source_tree(self.root))
        self.assertEqual(once, self.path.read_text())

    def test_upgrades_the_abort_only_revision(self):
        self.path.write_text(
            SOURCE.replace(
                "ContentMainRunner* GetContentMainRunner() {",
                '// Helium: dump a native stack before an abort kills the process.\n'
                "std::atomic<bool> g_helium_abort_logged{false};\n\n"
                "void HeliumAbortLogger(int sig, siginfo_t*, void*) {\n"
                "  signal(sig, SIG_DFL);\n"
                "  raise(sig);\n"
                "}\n\n"
                "void HeliumInstallAbortLogger() {\n"
                "  sigaction(SIGABRT, nullptr, nullptr);\n"
                "}\n\n"
                "ContentMainRunner* GetContentMainRunner() {",
            ).replace(
                "  HeliumInstallSigSysLogger();",
                "  HeliumInstallSigSysLogger();\n  HeliumInstallAbortLogger();",
            )
        )
        self.assertTrue(PATCH.patch_source_tree(self.root))
        result = self.path.read_text()
        self.assertIn("HeliumFatalSignalLogger", result)
        self.assertNotIn("HeliumAbortLogger", result)
        self.assertNotIn("HeliumInstallAbortLogger();", result)

    def test_missing_file_is_ignored(self):
        self.path.unlink()
        self.assertFalse(PATCH.patch_source_tree(self.root))


class NativeAbortBacktraceWiringTest(unittest.TestCase):
    def test_scripts_apply_the_patch_only_on_old_android(self):
        for name, target in (("patch.sh", "."), ("hotfix_existing_src.sh", '"$SRC_DIR"')):
            with self.subTest(script=name):
                text = (Path(__file__).resolve().parents[1] / name).read_text()
                block_start = text.index("if is_old_version_branch; then")
                block_end = text.index("verify_old_android_features.py", block_start)
                block = text[block_start:block_end]
                self.assertIn(
                    f'python3 "$SCRIPT_DIR/patch_native_abort_backtrace.py" {target}',
                    block,
                )


if __name__ == "__main__":
    unittest.main()
