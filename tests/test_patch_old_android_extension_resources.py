import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "patch_old_android_extension_resources.py"
)
SPEC = importlib.util.spec_from_file_location(
    "patch_old_android_extension_resources", MODULE_PATH
)
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)


SOURCE = '''#include "extensions/browser/extension_protocols.h"

  if (process_map.Contains(request.url.GetHost(), child_id)) {
    return true;
  }
'''


class OldAndroidExtensionResourcesPatchTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / PATCH.TARGET
        self.path.parent.mkdir(parents=True)
        self.path.write_text(SOURCE)

    def test_adds_same_origin_single_process_exception(self):
        self.assertTrue(PATCH.patch_source_tree(str(self.root)))
        result = self.path.read_text()
        self.assertIn("RenderProcessHost::run_renderer_in_process()", result)
        self.assertIn("!extension->is_hosted_app()", result)
        self.assertIn("request.request_initiator.value() == extension->origin()", result)
        self.assertIn("url::Origin::Create(request.url) == extension->origin()", result)
        self.assertEqual(1, result.count(PATCH.MARKER))

    def test_is_idempotent(self):
        self.assertTrue(PATCH.patch_source_tree(str(self.root)))
        patched = self.path.read_text()
        self.assertFalse(PATCH.patch_source_tree(str(self.root)))
        self.assertEqual(patched, self.path.read_text())

    def test_fails_closed_when_source_shape_changes(self):
        self.path.write_text('#include "url/gurl.h"\n')
        with self.assertRaises(RuntimeError):
            PATCH.patch_source_tree(str(self.root))


if __name__ == "__main__":
    unittest.main()
