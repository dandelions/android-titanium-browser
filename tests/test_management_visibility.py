import json
import shutil
import tempfile
import unittest
from pathlib import Path

import patch_titanium_visibility as patch

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/chromium_157"


class ManagementVisibilityTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.set_id("a" * 32)
        for relative in (patch.GENERATOR, patch.ROUTER):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(FIXTURES / relative.name, target)

    def set_id(self, extension_id):
        index = self.root / "helium/dist/bundled.json"
        index.parent.mkdir(parents=True, exist_ok=True)
        index.write_text(json.dumps({extension_id: {"external_crx": "titanium.crx"}}))

    def test_exact_157_source_and_idempotency(self):
        changes = patch.replacements("a" * 32)
        originals = {p: (self.root / p).read_text() for p in changes}
        self.assertTrue(patch.patch_source_tree(self.root))
        results = {p: (self.root / p).read_text() for p in changes}
        for path, edits in changes.items():
            expected = originals[path]
            for old, new in edits:
                self.assertEqual(expected.count(old), 1)
                expected = expected.replace(old, new, 1)
            self.assertEqual(results[path], expected)
        router = results[patch.ROUTER]
        for event in ("kLoaded", "kInstalled", "kUnloaded", "kUninstalled"):
            self.assertIn("BroadcastItemStateChanged(developer::EventType::" + event, router)
        self.assertIn('if (extension_id == "' + 'a' * 32 + '")', router)
        self.assertFalse(patch.patch_source_tree(self.root))
        self.assertEqual(results, {p: (self.root / p).read_text() for p in changes})

    def test_key_change_updates_all_guards(self):
        patch.patch_source_tree(self.root)
        self.set_id("b" * 32)
        self.assertTrue(patch.patch_source_tree(self.root))
        for relative in (patch.GENERATOR, patch.ROUTER):
            text = (self.root / relative).read_text()
            self.assertNotIn('a' * 32, text)
            self.assertIn('b' * 32, text)
        self.assertFalse(patch.patch_source_tree(self.root))

    def test_unexpected_router_does_not_write_generator(self):
        generator = self.root / patch.GENERATOR
        original = generator.read_text()
        router = self.root / patch.ROUTER
        router.write_text(router.read_text().replace(
            "  auto info_generator = std::make_unique<ExtensionInfoGenerator>(profile_);",
            "  changed();"))
        with self.assertRaises(RuntimeError):
            patch.patch_source_tree(self.root)
        self.assertEqual(original, generator.read_text())

    def test_missing_id_fails_before_writes(self):
        self.set_id("not-an-extension-id")
        before = (self.root / patch.GENERATOR).read_text()
        with self.assertRaises(RuntimeError):
            patch.patch_source_tree(self.root)
        self.assertEqual(before, (self.root / patch.GENERATOR).read_text())

    def test_script_entrypoints(self):
        self.assertIn('patch_titanium_visibility.py" . || exit 1', (ROOT / "patch.sh").read_text())
        self.assertIn('patch_titanium_visibility.py" "$SRC_DIR"', (ROOT / "hotfix_existing_src.sh").read_text())


if __name__ == "__main__":
    unittest.main()
