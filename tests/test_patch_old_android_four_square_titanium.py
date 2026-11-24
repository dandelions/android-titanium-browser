import json
import tempfile
import unittest
from pathlib import Path

import patch_old_android_four_square_titanium as patch


class OldAndroidFourSquareTitaniumTest(unittest.TestCase):
    def test_filters_only_bundled_titanium_from_pinned_and_all_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            index = root / "helium/dist/bundled.json"
            index.parent.mkdir(parents=True)
            index.write_text(json.dumps({
                "jlbggdgofbcndkkdimpeccablefilpkm": {
                    "external_crx": "titanium.crx"
                }
            }))

            source = root / patch.COORDINATOR
            source.parent.mkdir(parents=True)
            source.write_text("""    public String[] getAllExtensionActionIds() {
        java.util.LinkedHashSet<String> ordered = new java.util.LinkedHashSet<>();
        if (pinned != null) {
            for (String id : pinned) {
                if (id != null && !id.isEmpty()) {
                    ordered.add(id);
                }
            }
        }
        for (String id : all) {
            if (id != null && !id.isEmpty()) {
                ordered.add(id);
            }
        }
        return ordered.toArray(new String[0]);
    }
""")

            self.assertTrue(patch.patch_source_tree(root))
            result = source.read_text()
            self.assertEqual(result.count('!"jlbggdgofbcndkkdimpeccablefilpkm".equals(id)'), 2)
            self.assertIn("Helium: hide bundled Titanium from the four-square extensions sheet.", result)
            self.assertFalse(patch.patch_source_tree(root))

    def test_requires_exactly_one_bundled_titanium_id(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            index = root / "helium/dist/bundled.json"
            index.parent.mkdir(parents=True)
            index.write_text("{}")
            with self.assertRaises(RuntimeError):
                patch.bundled_titanium_id(root)


if __name__ == "__main__":
    unittest.main()
