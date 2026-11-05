import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
CPP_GUARD = "sed -i 's/  CHECK(tab);/  if (!tab) return;/'"
JAVA_GUARD = "sed -i 's/        assert tab.isInitialized();/"
CPP_RESTORE = "sed -i 's/  if (!tab) return;/  CHECK(tab);/'"
JAVA_RESTORE = "assert tab.isInitialized();"


class TabModelCrashGuardIsolationTest(unittest.TestCase):
    def test_crash_guard_is_old_android_only(self):
        for name in ("patch.sh", "hotfix_existing_src.sh"):
            with self.subTest(script=name):
                text = (ROOT / name).read_text()
                start = text.index('if [[ "$CURRENT_BRANCH" == old-* ]]')
                else_start = text.index("\nelse\n", start)
                end = text.index("\nfi", else_start)
                old_android_block = text[start:else_start]
                standard_block = text[else_start:end]
                self.assertIn(CPP_GUARD, old_android_block)
                self.assertIn(JAVA_GUARD, old_android_block)
                self.assertNotIn(CPP_GUARD, standard_block)
                self.assertNotIn(JAVA_GUARD, standard_block)
                self.assertIn(CPP_RESTORE, standard_block)
                self.assertIn(JAVA_RESTORE, standard_block)


if __name__ == "__main__":
    unittest.main()
