import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "patch_unwindstack_cloexec.py"
SPEC = importlib.util.spec_from_file_location("patch_unwindstack_cloexec", MODULE_PATH)
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)


MEMORY_SOURCE = """bool MemoryFileAtOffset::Init(const std::string& file, uint64_t offset, uint64_t size) {
  Clear();

  android::base::unique_fd fd(TEMP_FAILURE_RETRY(open(file.c_str(), O_RDONLY | O_CLOEXEC)));
  if (fd == -1) {
    return false;
  }
  return true;
}
"""

PROCESS_MAP_SOURCE = """bool ReadProcessMaps(const std::string& map_file, char* buffer, size_t buffer_size,
                     const CallbackType& callback) {
  int fd = open(map_file, O_RDONLY | O_CLOEXEC);
  if (fd == -1) {
    return false;
  }
  return true;
}
"""


class UnwindstackCloexecPatchTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.memory = self.root / PATCH.MEMORY_FILE
        self.process_map = self.root / PATCH.PROCESS_MAP_FILE
        self.memory.parent.mkdir(parents=True, exist_ok=True)
        self.process_map.parent.mkdir(parents=True, exist_ok=True)
        self.memory.write_text(MEMORY_SOURCE)
        self.process_map.write_text(PROCESS_MAP_SOURCE)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_sets_fd_cloexec_instead_of_o_cloexec(self):
        self.assertTrue(PATCH.patch_source_tree(self.root))
        memory = self.memory.read_text()
        self.assertNotIn("O_RDONLY | O_CLOEXEC", memory)
        self.assertIn("fcntl(helium_fd, F_SETFD, FD_CLOEXEC)", memory)

        process_map = self.process_map.read_text()
        self.assertNotIn("open(map_file, O_RDONLY | O_CLOEXEC)", process_map)
        self.assertIn("fcntl(fd, F_SETFD, FD_CLOEXEC)", process_map)

    def test_repeated_runs_are_no_ops(self):
        self.assertTrue(PATCH.patch_source_tree(self.root))
        memory_once = self.memory.read_text()
        map_once = self.process_map.read_text()
        self.assertFalse(PATCH.patch_source_tree(self.root))
        self.assertEqual(memory_once, self.memory.read_text())
        self.assertEqual(map_once, self.process_map.read_text())

    def test_missing_files_are_ignored(self):
        self.memory.unlink()
        self.process_map.unlink()
        self.assertFalse(PATCH.patch_source_tree(self.root))


class UnwindstackCloexecWiringTest(unittest.TestCase):
    def test_scripts_apply_the_patch_only_on_old_android(self):
        for name, target in (("patch.sh", "."), ("hotfix_existing_src.sh", '"$SRC_DIR"')):
            with self.subTest(script=name):
                text = (Path(__file__).resolve().parents[1] / name).read_text()
                block_start = text.index("if is_old_version_branch; then")
                block_end = text.index("verify_old_android_features.py", block_start)
                block = text[block_start:block_end]
                self.assertIn(
                    f'python3 "$SCRIPT_DIR/patch_unwindstack_cloexec.py" {target}',
                    block,
                )

    def test_verifier_checks_the_open_flags(self):
        verifier = (
            Path(__file__).resolve().parents[1] / "verify_old_android_features.py"
        ).read_text()
        self.assertIn("def verify_unwindstack_cloexec(", verifier)
        self.assertIn("verify_unwindstack_cloexec(root)", verifier)


if __name__ == "__main__":
    unittest.main()
