import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "patch_old_android_extension_commit.py"
SPEC = importlib.util.spec_from_file_location("patch_old_android_extension_commit", MODULE_PATH)
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)


SOURCE = """#include "content/public/common/child_process_id.h"

  ProcessMap* process_map = ProcessMap::Get(process_host->GetBrowserContext());
  if (process_map->Contains(extension->id(), process_host->GetID())) {
    return true;
  }
"""


class OldAndroidExtensionCommitPatchTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / PATCH.TARGET
        self.path.parent.mkdir(parents=True)
        self.path.write_text(SOURCE)

    def test_adds_single_process_only_exception(self):
        self.assertTrue(PATCH.patch_source_tree(str(self.root)))
        result = self.path.read_text()
        self.assertIn('#include "content/public/common/content_switches.h"', result)
        self.assertIn("HasSwitch(\n          ::switches::kSingleProcess)", result)
        self.assertIn("VMOS Android 9 uses the old-android single-process compatibility mode.", result)
        self.assertIn("if (process_map->Contains(extension->id(), process_host->GetID()))", result)
        self.assertEqual(1, result.count(MARKER := PATCH.MARKER))

    def test_is_idempotent(self):
        self.assertTrue(PATCH.patch_source_tree(str(self.root)))
        patched = self.path.read_text()
        self.assertFalse(PATCH.patch_source_tree(str(self.root)))
        self.assertEqual(patched, self.path.read_text())

    def test_upgrades_previous_switch_namespace_in_place(self):
        self.assertTrue(PATCH.patch_source_tree(str(self.root)))
        text = self.path.read_text().replace(
            "::switches::kSingleProcess", "switches::kSingleProcess"
        )
        self.path.write_text(text)
        self.assertTrue(PATCH.patch_source_tree(str(self.root)))
        self.assertIn("::switches::kSingleProcess", self.path.read_text())
        self.assertFalse(PATCH.patch_source_tree(str(self.root)))

    def test_fails_closed_when_source_shape_changes(self):
        self.path.write_text('#include "content/public/common/child_process_id.h"\n')
        with self.assertRaises(RuntimeError):
            PATCH.patch_source_tree(str(self.root))


if __name__ == "__main__":
    unittest.main()
