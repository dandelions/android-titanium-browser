import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "patch_content_main_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location(
    "patch_content_main_diagnostics", MODULE_PATH
)
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)

CONTENT_MAIN = PATCH.CONTENT_MAIN
CONTENT_MAIN_RUNNER = PATCH.CONTENT_MAIN_RUNNER

CONTENT_MAIN_SOURCE = """NO_STACK_PROTECTOR int RunContentProcess(
    ContentMainParams params,
    ContentMainRunner* content_main_runner) {
  base::FeatureList::FailOnFeatureAccessWithoutFeatureList();
  int exit_code = -1;

    exit_code = content_main_runner->Initialize(std::move(params));

    if (exit_code >= 0) {
      return exit_code;
    }
  }

  if (IsSubprocess())
    CommonSubprocessInit();
  exit_code = content_main_runner->Run();

  return exit_code;
}
"""

CONTENT_MAIN_RUNNER_SOURCE = """NO_STACK_PROTECTOR int RunOtherNamedProcessTypeMain(
    const std::string& process_type,
    MainFunctionParams main_function_params,
    ContentMainDelegate* delegate) {
  static const auto kMainFunctions = std::to_array<MainFunction>({
      {switches::kRendererProcess, RendererMain},
  });

  for (const MainFunction& main_function : kMainFunctions) {
    if (process_type == main_function.name) {
      auto exit_code =
          delegate->RunProcess(process_type, std::move(main_function_params));
      return std::get<int>(exit_code);
    }
  }

  // If it's a process we don't know about, the embedder should know.
  auto exit_code =
      delegate->RunProcess(process_type, std::move(main_function_params));
  return std::get<int>(exit_code);
}
"""


class TestPatchContentMainDiagnostics(unittest.TestCase):
    def _apply(self, tmp, content_main=CONTENT_MAIN_SOURCE, runner=CONTENT_MAIN_RUNNER_SOURCE):
        root = Path(tmp)
        main_path = root / CONTENT_MAIN
        main_path.parent.mkdir(parents=True, exist_ok=True)
        main_path.write_text(content_main, encoding="utf-8")
        runner_path = root / CONTENT_MAIN_RUNNER
        runner_path.parent.mkdir(parents=True, exist_ok=True)
        runner_path.write_text(runner, encoding="utf-8")
        return main_path, runner_path, PATCH.patch_source_tree(tmp)

    def test_reports_process_type_and_both_return_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            main_path, _, changed = self._apply(tmp)
            self.assertTrue(changed)
            out = main_path.read_text(encoding="utf-8")
            self.assertIn("Helium content main trace revision: 1", out)
            self.assertIn("Helium content main: type=", out)
            self.assertIn("Helium content main: initialize returned ", out)
            self.assertIn("Helium content main: run returned ", out)

    def test_reports_child_main_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, runner_path, changed = self._apply(tmp)
            self.assertTrue(changed)
            out = runner_path.read_text(encoding="utf-8")
            self.assertIn("Helium child main: type=", out)
            self.assertIn("Helium child main: matched ", out)
            self.assertIn("Helium child main: no main function for type=", out)

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            main_path, runner_path, _ = self._apply(tmp)
            main_first = main_path.read_text(encoding="utf-8")
            runner_first = runner_path.read_text(encoding="utf-8")
            self.assertFalse(PATCH.patch_source_tree(tmp))
            self.assertEqual(main_first, main_path.read_text(encoding="utf-8"))
            self.assertEqual(runner_first, runner_path.read_text(encoding="utf-8"))

    def test_missing_files_are_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(PATCH.patch_source_tree(tmp))

    def test_unknown_anchor_does_not_rewrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            main_path, _, _ = self._apply(
                tmp, content_main="int RunContentProcess() { return 0; }\n"
            )
            self.assertNotIn(
                "Helium content main: type=", main_path.read_text(encoding="utf-8")
            )


if __name__ == "__main__":
    unittest.main()
