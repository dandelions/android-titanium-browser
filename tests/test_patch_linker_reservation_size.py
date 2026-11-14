import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "patch_linker_reservation_size.py"
SPEC = importlib.util.spec_from_file_location(
    "patch_linker_reservation_size", MODULE_PATH
)
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)


SOURCE = """#ifndef BASE_ANDROID_LINKER_LINKER_JNI_H_
#define BASE_ANDROID_LINKER_LINKER_JNI_H_

static const size_t kAddressSpaceReservationSize = 192 * 1024 * 1024;

#endif  // BASE_ANDROID_LINKER_LINKER_JNI_H_
"""


class LinkerReservationSizePatchTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.path = self.root / PATCH.HEADER_FILE
        self.path.parent.mkdir(parents=True)
        self.path.write_text(SOURCE)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_raises_the_reservation_to_320_mib(self):
        self.assertTrue(PATCH.patch_source_tree(self.root))
        result = self.path.read_text()
        self.assertIn("kAddressSpaceReservationSize = 320 * 1024 * 1024;", result)
        self.assertNotIn("192 * 1024 * 1024", result)
        # 320 MiB must stay above the ~223.6 MiB load size of libchrome.so.
        self.assertGreater(320 * 1024 * 1024, 234479616)

    def test_repeated_runs_are_no_ops(self):
        self.assertTrue(PATCH.patch_source_tree(self.root))
        once = self.path.read_text()
        self.assertFalse(PATCH.patch_source_tree(self.root))
        self.assertEqual(once, self.path.read_text())

    def test_unknown_layout_is_left_alone(self):
        self.path.write_text(SOURCE.replace("192 * 1024 * 1024", "64 * 1024 * 1024"))
        self.assertFalse(PATCH.patch_source_tree(self.root))
        self.assertIn("64 * 1024 * 1024", self.path.read_text())

    def test_missing_file_is_ignored(self):
        self.path.unlink()
        self.assertFalse(PATCH.patch_source_tree(self.root))


class LinkerReservationSizeWiringTest(unittest.TestCase):
    def test_scripts_apply_the_patch_only_on_old_android(self):
        for name, target in (("patch.sh", "."), ("hotfix_existing_src.sh", '"$SRC_DIR"')):
            with self.subTest(script=name):
                text = (Path(__file__).resolve().parents[1] / name).read_text()
                block_start = text.index("if is_old_version_branch; then")
                block_end = text.index("verify_old_android_features.py", block_start)
                block = text[block_start:block_end]
                self.assertIn(
                    f'python3 "$SCRIPT_DIR/patch_linker_reservation_size.py" {target}',
                    block,
                )

    def test_verifier_checks_the_reservation(self):
        verifier = (
            Path(__file__).resolve().parents[1] / "verify_old_android_features.py"
        ).read_text()
        self.assertIn("def verify_linker_reservation_size(", verifier)
        self.assertIn("verify_linker_reservation_size(root)", verifier)


if __name__ == "__main__":
    unittest.main()
