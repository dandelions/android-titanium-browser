import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch as mock_patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("patch_titanium_visibility", ROOT / "patch_titanium_visibility.py")
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)
FIXTURES = ROOT / "tests/fixtures/chromium_157"
OLD_ID = "jlbggdgofbcndkkdimpeccablefilpkm"
NEW_ID = "a" * 32


class TitaniumVisibilityTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.index = self.root / "helium/dist/bundled.json"
        self.index.parent.mkdir(parents=True)
        self.set_id(NEW_ID)
        for relative in (PATCH.GENERATOR, PATCH.ROUTER):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(FIXTURES / relative.name, target)

    def set_id(self, extension_id):
        self.index.write_text(json.dumps({extension_id: {"external_crx": "titanium.crx"},
                                          "b" * 32: {"external_crx": "other.crx"}}))

    def test_chromium_157_patches_exact_surfaces_and_is_idempotent(self):
        changes = PATCH.replacements(NEW_ID)
        originals = {p: (self.root / p).read_text() for p in changes}
        self.assertTrue(PATCH.patch_source_tree(self.root))
        results = {p: (self.root / p).read_text() for p in changes}
        for path, replacements in changes.items():
            expected = originals[path]
            for old, new in replacements:
                self.assertEqual(expected.count(old), 1)
                expected = expected.replace(old, new, 1)
            self.assertEqual(results[path], expected)
        self.assertEqual(results[PATCH.GENERATOR].count(NEW_ID), 2)
        self.assertEqual(results[PATCH.ROUTER].count(NEW_ID), 1)
        self.assertFalse(PATCH.patch_source_tree(self.root))
        self.assertEqual(results, {p: (self.root / p).read_text() for p in changes})

    def test_old_hardcoded_guards_are_updated(self):
        self.set_id(OLD_ID)
        PATCH.patch_source_tree(self.root)
        self.set_id(NEW_ID)
        self.assertTrue(PATCH.patch_source_tree(self.root))
        for path, expected in ((PATCH.GENERATOR, 2), (PATCH.ROUTER, 1)):
            text = (self.root / path).read_text()
            self.assertNotIn(OLD_ID, text)
            self.assertEqual(text.count(NEW_ID), expected)
        self.assertFalse(PATCH.patch_source_tree(self.root))

    def test_invalid_missing_duplicate_indexes_fail_before_writes(self):
        before = (self.root / PATCH.GENERATOR).read_text()
        for contents in ("{", "[]", "{}", json.dumps({"invalid": {"external_crx": "titanium.crx"}}),
                         json.dumps({"a" * 32: {"external_crx": "titanium.crx"},
                                     "c" * 32: {"external_crx": "titanium.crx"}})):
            with self.subTest(contents=contents):
                self.index.write_text(contents)
                with self.assertRaises(RuntimeError):
                    PATCH.patch_source_tree(self.root)
                self.assertEqual((self.root / PATCH.GENERATOR).read_text(), before)
        self.index.unlink()
        with mock_patch.object(PATCH, "__file__", str(self.root / "script.py")):
            with self.assertRaises(RuntimeError):
                PATCH.patch_source_tree(self.root)

    def test_fallback_index_and_staged_index_precedence(self):
        fallback = self.root / "extensions/dist/bundled.json"
        fallback.parent.mkdir(parents=True)
        fallback.write_text(json.dumps({"c" * 32: {"external_crx": "titanium.crx"}}))
        with mock_patch.object(PATCH, "__file__", str(self.root / "script.py")):
            self.assertEqual(PATCH.bundled_titanium_id(self.root), NEW_ID)
            self.index.unlink()
            self.assertEqual(PATCH.bundled_titanium_id(self.root), "c" * 32)

    def test_unexpected_router_source_fails_before_any_write(self):
        generator = self.root / PATCH.GENERATOR
        original = generator.read_text()
        router = self.root / PATCH.ROUTER
        router.write_text(router.read_text().replace("  auto info_generator = std::make_unique<ExtensionInfoGenerator>(profile_);", "  changed();"))
        with self.assertRaises(RuntimeError):
            PATCH.patch_source_tree(self.root)
        self.assertEqual(generator.read_text(), original)

    def test_scripts_invoke_patch(self):
        self.assertIn('patch_titanium_visibility.py" . || exit 1', (ROOT / "patch.sh").read_text())
        self.assertIn('patch_titanium_visibility.py" "$SRC_DIR"', (ROOT / "hotfix_existing_src.sh").read_text())


if __name__ == "__main__":
    unittest.main()
