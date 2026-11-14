import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "patch_linker_relro_sharing.py"
SPEC = importlib.util.spec_from_file_location("patch_linker_relro_sharing", MODULE_PATH)
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)


SOURCE = """public class Linker {
    final void loadLibrary(String library) {
        synchronized (mLock) {
            try {
                attemptLoadLibraryLocked(
                        library,
                        mRelroProducer ? RelroSharingMode.PRODUCE : RelroSharingMode.CONSUME);
            } catch (UnsatisfiedLinkError e) {
                attemptLoadLibraryLocked(library, RelroSharingMode.NO_SHARING);
            }
        }
    }
}
"""


class LinkerRelroSharingPatchTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.path = self.root / PATCH.LINKER_FILE
        self.path.parent.mkdir(parents=True)
        self.path.write_text(SOURCE)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_loads_without_shared_relro(self):
        self.assertTrue(PATCH.patch_source_tree(self.root))
        result = self.path.read_text()
        self.assertIn(
            "attemptLoadLibraryLocked(library, RelroSharingMode.NO_SHARING);", result
        )
        self.assertNotIn("mRelroProducer ? RelroSharingMode.PRODUCE", result)

    def test_repeated_runs_are_no_ops(self):
        self.assertTrue(PATCH.patch_source_tree(self.root))
        once = self.path.read_text()
        self.assertFalse(PATCH.patch_source_tree(self.root))
        self.assertEqual(once, self.path.read_text())

    def test_unknown_layout_is_left_alone(self):
        self.path.write_text("public class Linker {}\n")
        self.assertFalse(PATCH.patch_source_tree(self.root))
        self.assertEqual("public class Linker {}\n", self.path.read_text())

    def test_missing_file_is_ignored(self):
        self.path.unlink()
        self.assertFalse(PATCH.patch_source_tree(self.root))


class LinkerRelroSharingWiringTest(unittest.TestCase):
    def test_scripts_apply_the_patch_only_on_old_android(self):
        for name, target in (("patch.sh", "."), ("hotfix_existing_src.sh", '"$SRC_DIR"')):
            with self.subTest(script=name):
                text = (Path(__file__).resolve().parents[1] / name).read_text()
                block_start = text.index("if is_old_version_branch; then")
                block_end = text.index("verify_old_android_features.py", block_start)
                block = text[block_start:block_end]
                self.assertIn(
                    f'python3 "$SCRIPT_DIR/patch_linker_relro_sharing.py" {target}',
                    block,
                )

    def test_verifier_checks_the_sharing_mode(self):
        verifier = (
            Path(__file__).resolve().parents[1] / "verify_old_android_features.py"
        ).read_text()
        self.assertIn("def verify_linker_relro_sharing(", verifier)
        self.assertIn("verify_linker_relro_sharing(root)", verifier)


if __name__ == "__main__":
    unittest.main()
