import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATCH_PATH = ROOT / "patch_old_android_pac_proxy.py"
SPEC = importlib.util.spec_from_file_location("patch_old_android_pac_proxy", PATCH_PATH)
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)


UPSTREAM = """  if (!command_line.HasSwitch(switches::kWinHttpProxyResolver)) {
    if (command_line.HasSwitch(switches::kSingleProcess)) {
      LOG(ERROR) << "Cannot use V8 Proxy resolver in single process mode.";
    } else {
      network_context_params->proxy_resolver_factory =
          ChromeMojoProxyResolverFactory::CreateWithSelfOwnedReceiver();
    }
  }
"""

UNSAFE_PATCHED = """  if (!command_line.HasSwitch(switches::kWinHttpProxyResolver)) {
    // VMOS Android 9 keeps the network service inside the browser process. The
    // V8 resolver still works there, and PAC proxy rules require it.
    {
      network_context_params->proxy_resolver_factory =
          ChromeMojoProxyResolverFactory::CreateWithSelfOwnedReceiver();
    }
  }
"""


class OldAndroidPacProxyPatchTest(unittest.TestCase):
    def _write_source(self, root: str, content: str) -> Path:
        path = Path(root) / PATCH.TARGET
        path.parent.mkdir(parents=True)
        path.write_text(content)
        return path

    def test_preserves_upstream_single_process_restriction(self):
        with tempfile.TemporaryDirectory() as temp:
            path = self._write_source(temp, UPSTREAM)
            self.assertFalse(PATCH.patch_source_tree(temp))
            self.assertEqual(UPSTREAM, path.read_text())

    def test_reverts_unsafe_single_process_override(self):
        with tempfile.TemporaryDirectory() as temp:
            path = self._write_source(temp, UNSAFE_PATCHED)
            self.assertTrue(PATCH.patch_source_tree(temp))
            result = path.read_text()
            self.assertIn("Cannot use V8 Proxy resolver in single process mode.", result)
            self.assertNotIn("V8 resolver still works there", result)
            self.assertIn("ChromeMojoProxyResolverFactory::CreateWithSelfOwnedReceiver()", result)

    def test_preserves_upstream_guard_on_clean_source(self):
        with tempfile.TemporaryDirectory() as temp:
            path = self._write_source(temp, UPSTREAM)
            self.assertFalse(PATCH.patch_source_tree(temp))
            self.assertEqual(UPSTREAM, path.read_text())

    def test_accepts_dedicated_pac_resolver_process(self):
        dedicated_process = "// Helium: the PAC resolver runs in a dedicated utility process.\n"
        with tempfile.TemporaryDirectory() as temp:
            path = self._write_source(temp, dedicated_process)
            self.assertFalse(PATCH.patch_source_tree(temp))
            self.assertEqual(dedicated_process, path.read_text())

    def test_is_idempotent_after_revert(self):
        with tempfile.TemporaryDirectory() as temp:
            path = self._write_source(temp, UNSAFE_PATCHED)
            self.assertTrue(PATCH.patch_source_tree(temp))
            restored = path.read_text()
            self.assertFalse(PATCH.patch_source_tree(temp))
            self.assertEqual(restored, path.read_text())


if __name__ == "__main__":
    unittest.main()
