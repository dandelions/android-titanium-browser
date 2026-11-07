import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("patch_titanium_visibility", ROOT / "patch_titanium_visibility.py")
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)
FIXTURES = ROOT / "tests/fixtures/chromium_157"


class TitaniumVisibilityTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for relative in PATCH.REPLACEMENTS:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(FIXTURES / relative.name, target)

    def test_chromium_157_patches_exact_surfaces_and_is_idempotent(self):
        originals = {p: (self.root / p).read_text() for p in PATCH.REPLACEMENTS}
        self.assertTrue(PATCH.patch_source_tree(self.root))
        results = {p: (self.root / p).read_text() for p in PATCH.REPLACEMENTS}
        for path, replacements in PATCH.REPLACEMENTS.items():
            expected = originals[path]
            for old, new in replacements:
                self.assertEqual(expected.count(old), 1)
                expected = expected.replace(old, new, 1)
            self.assertEqual(results[path], expected)
        generator = results[PATCH.GENERATOR]
        router = results[PATCH.ROUTER]
        self.assertEqual(generator.count(PATCH.TITANIUM_ID), 2)
        self.assertEqual(router.count(PATCH.TITANIUM_ID), 1)
        self.assertLess(router.index(PATCH.TITANIUM_ID), router.index("  auto info_generator =", router.index(PATCH.TITANIUM_ID)))
        self.assertFalse(PATCH.patch_source_tree(self.root))
        self.assertEqual(results, {p: (self.root / p).read_text() for p in PATCH.REPLACEMENTS})

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
