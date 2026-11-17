import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "patch_renderer_lifecycle_diagnostics.py"
SPEC = importlib.util.spec_from_file_location("patch_renderer_lifecycle_diagnostics", MODULE_PATH)
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)

RENDERER = """#include \"base/feature_list.h\"
#include \"content/renderer/render_thread_impl.h\"

int RendererMain(MainFunctionParams parameters) {
    new RenderThreadImpl(run_loop.QuitClosure(),
                         std::move(main_thread_scheduler));
    if (should_run_loop) {
      run_loop.Run();
    }
    return 0;
}
"""

CHILD = """#include \"base/logging.h\"
#include \"base/process/process.h\"

void ChildThreadImpl::OnChannelError() {
  on_channel_error_called_ = true;
  if (!IsInBrowserProcess())
    quit_closure_.Run();
}
"""


class TestPatchRendererLifecycleDiagnostics(unittest.TestCase):
    def _apply(self, tmp):
        root = Path(tmp)
        renderer = root / PATCH.RENDERER_MAIN
        renderer.parent.mkdir(parents=True, exist_ok=True)
        renderer.write_text(RENDERER, encoding="utf-8")
        child = root / PATCH.CHILD_THREAD
        child.parent.mkdir(parents=True, exist_ok=True)
        child.write_text(CHILD, encoding="utf-8")
        return renderer, child, PATCH.patch_source_tree(tmp)

    def test_instruments_loop_and_channel_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            renderer, child, changed = self._apply(tmp)
            self.assertTrue(changed)
            renderer_out = renderer.read_text(encoding="utf-8")
            child_out = child.read_text(encoding="utf-8")
            self.assertIn("Helium renderer lifecycle: main entered", renderer_out)
            self.assertIn("Helium renderer lifecycle: RenderThreadImpl ready", renderer_out)
            self.assertIn("Helium renderer lifecycle: message loop entered", renderer_out)
            self.assertIn("Helium renderer lifecycle: message loop exited", renderer_out)
            self.assertIn("Helium renderer lifecycle: child channel error", child_out)

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            renderer, child, _ = self._apply(tmp)
            first = (renderer.read_text(encoding="utf-8"), child.read_text(encoding="utf-8"))
            self.assertFalse(PATCH.patch_source_tree(tmp))
            self.assertEqual(first, (renderer.read_text(encoding="utf-8"), child.read_text(encoding="utf-8")))

    def test_missing_files_are_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(PATCH.patch_source_tree(tmp))


if __name__ == "__main__":
    unittest.main()
