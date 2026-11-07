import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("lemur", ROOT / "patch_lemur_app_menu.py")
lemur = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lemur)


class TitaniumVisibilityPatchTest(unittest.TestCase):
    def test_fresh_and_incremental_action_list_use_bundled_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = root / "helium/dist/bundled.json"
            index.parent.mkdir(parents=True)
            index.write_text(json.dumps({"a" * 32: {"external_crx": "titanium.crx"}}))
            path = root / lemur.EXT_TOOLBAR_COORD_IMPL_REL
            path.parent.mkdir(parents=True)
            path.write_text("""class Coordinator {
    @Override
    public ToolbarWidthConsumer getActionListWidthConsumer() {
        return mActionListWidthConsumer;
    }
}
""")
            lemur.patch_extensions_toolbar_coordinator_impl(root)
            fresh = path.read_text()
            self.assertEqual(fresh.count('!"' + 'a' * 32 + '".equals(id)'), 2)
            self.assertIn('for (String id : pinned)', fresh)
            self.assertIn('for (String id : all)', fresh)
            stale = fresh.replace('!"' + 'a' * 32 + '".equals(id)', 'true')
            path.write_text(stale)
            lemur.patch_extensions_toolbar_coordinator_impl(root)
            self.assertEqual(fresh, path.read_text())
            lemur.patch_extensions_toolbar_coordinator_impl(root)
            self.assertEqual(fresh, path.read_text())

    def test_missing_bundle_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / lemur.EXT_TOOLBAR_COORD_IMPL_REL
            path.parent.mkdir(parents=True)
            path.write_text('class Coordinator {}')
            with self.assertRaises(SystemExit):
                lemur.patch_extensions_toolbar_coordinator_impl(root)


if __name__ == '__main__':
    unittest.main()
