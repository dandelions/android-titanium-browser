import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TitaniumVisibilityPatchTest(unittest.TestCase):
    def test_titanium_is_filtered_from_custom_extension_action_list(self):
        source = (ROOT / "patch_lemur_app_menu.py").read_text(encoding="utf-8")
        self.assertIn(
            '!"jlbggdgofbcndkkdimpeccablefilpkm".equals(id)',
            source,
        )
        self.assertGreaterEqual(source.count('!"jlbggdgofbcndkkdimpeccablefilpkm".equals(id)'), 2)


if __name__ == "__main__":
    unittest.main()
