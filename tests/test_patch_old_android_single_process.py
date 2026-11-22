import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "patch_old_android_single_process.py"
SPEC = importlib.util.spec_from_file_location("patch_old_android_single_process", MODULE_PATH)
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)


SOURCE = """static void JNI_BrowserStartupControllerImpl_SetCommandLineFlags(
    JNIEnv* env,
    bool single_process) {
  SetContentCommandLineFlags(single_process);
}
"""

PROCESS_MAP_SOURCE = """bool ProcessMap::CanProcessHostContextType(
    const Extension* extension,
    const content::RenderProcessHost& process,
    mojom::ContextType context_type) {
  const content::ChildProcessId process_id = process.GetID();
  switch (context_type) {
    case mojom::ContextType::kUnspecified:
      return false;
    case mojom::ContextType::kPrivilegedExtension:
      return extension && IsPrivilegedExtensionProcess(*extension, process_id);
  }
}
"""


class OldAndroidSingleProcessPatchTest(unittest.TestCase):
    def _write_sources(self, root):
        startup = Path(root) / PATCH.TARGET
        startup.parent.mkdir(parents=True, exist_ok=True)
        startup.write_text(SOURCE)

        process_map = Path(root) / PATCH.PROCESS_MAP_TARGET
        process_map.parent.mkdir(parents=True, exist_ok=True)
        process_map.write_text(PROCESS_MAP_SOURCE)
        return startup, process_map

    def test_forces_single_process(self):
        with tempfile.TemporaryDirectory() as root:
            startup, _ = self._write_sources(root)

            self.assertTrue(PATCH.patch_source_tree(root))
            result = startup.read_text()
            self.assertIn("SetContentCommandLineFlags(/*single_process=*/true);", result)
            self.assertNotIn("SetContentCommandLineFlags(single_process);", result)
            self.assertIn(PATCH.MARKER, result)

    def test_relaxes_extension_context_check(self):
        with tempfile.TemporaryDirectory() as root:
            _, process_map = self._write_sources(root)

            self.assertTrue(PATCH.patch_source_tree(root))
            result = process_map.read_text()
            self.assertIn(PATCH.PROCESS_MAP_MARKER, result)
            self.assertIn("content::RenderProcessHost::run_renderer_in_process()", result)
            self.assertIn("mojom::ContextType::kPrivilegedExtension", result)
            self.assertIn("mojom::ContextType::kOffscreenExtension", result)
            # The unspecified context must stay invalid.
            self.assertIn("case mojom::ContextType::kUnspecified:", result)

    def test_is_idempotent(self):
        with tempfile.TemporaryDirectory() as root:
            startup, process_map = self._write_sources(root)

            self.assertTrue(PATCH.patch_source_tree(root))
            startup_patched = startup.read_text()
            process_map_patched = process_map.read_text()
            self.assertFalse(PATCH.patch_source_tree(root))
            self.assertEqual(startup_patched, startup.read_text())
            self.assertEqual(process_map_patched, process_map.read_text())

    def test_fails_if_hook_is_missing(self):
        with tempfile.TemporaryDirectory() as root:
            startup, _ = self._write_sources(root)
            startup.write_text("static void unrelated() {}\n")
            with self.assertRaises(RuntimeError):
                PATCH.patch_source_tree(root)

    def test_fails_if_process_map_anchor_is_missing(self):
        with tempfile.TemporaryDirectory() as root:
            _, process_map = self._write_sources(root)
            process_map.write_text("bool Unrelated() { return false; }\n")
            with self.assertRaises(RuntimeError):
                PATCH.patch_source_tree(root)


if __name__ == "__main__":
    unittest.main()
