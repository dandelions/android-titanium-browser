import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "patch_tab_restore_diagnostics.py"
SPEC = importlib.util.spec_from_file_location(
    "patch_tab_restore_diagnostics", MODULE_PATH
)
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)


SOURCE = """public class TabStateFileManager {
    public static @Nullable TabState restoreTabState(
            File stateFolder, int id, CipherFactory cipherFactory) {
        File flatBufferRegular = getTabStateFile(stateFolder, id, false, true);
        File flatBufferEncrypted = getTabStateFile(stateFolder, id, true, true);
        File legacyRegular = getTabStateFile(stateFolder, id, false, false);
        File legacyEncrypted = getTabStateFile(stateFolder, id, true, false);

        boolean flatBufferRegularExists = flatBufferRegular.exists();
        boolean flatBufferEncryptedExists = flatBufferEncrypted.exists();
        boolean legacyRegularExists = legacyRegular.exists();
        boolean legacyEncryptedExists = legacyEncrypted.exists();

        recordTabStateMigrationStatus(
                flatBufferRegularExists,
                flatBufferEncryptedExists,
                legacyRegularExists,
                legacyEncryptedExists);

        TabState tabState = null;
        if (flatBufferRegularExists || flatBufferEncryptedExists) {
            try {
                boolean isEncrypted = flatBufferEncryptedExists;
                tabState = restoreTabStateInternal(targetFile, isEncrypted, cipherFactory);
            } catch (Exception e) {
                Log.d(TAG, "Error restoring TabState using FlatBuffer", e);
            }
        }
        return tabState;
    }
}
"""


class TabRestoreDiagnosticsPatchTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.path = self.root / PATCH.TAB_STATE_FILE
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(SOURCE)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_logs_which_tab_state_files_exist(self):
        self.assertTrue(PATCH.patch_source_tree(self.root))
        result = self.path.read_text()
        self.assertIn('"Helium restore: id=" + id', result)
        self.assertIn('" flatRegular=" + flatBufferRegularExists', result)
        self.assertIn('" legacyEncrypted=" + legacyEncryptedExists', result)
        self.assertLess(
            result.index('"Helium restore: id="'),
            result.index("TabState tabState = null;"),
        )

    def test_raises_restore_failure_to_warning(self):
        self.assertTrue(PATCH.patch_source_tree(self.root))
        result = self.path.read_text()
        self.assertNotIn('Log.d(TAG, "Error restoring TabState using FlatBuffer", e);', result)
        self.assertIn('"Helium restore failed: id=" + id', result)

    def test_repeated_runs_are_no_ops(self):
        self.assertTrue(PATCH.patch_source_tree(self.root))
        once = self.path.read_text()
        self.assertFalse(PATCH.patch_source_tree(self.root))
        self.assertEqual(once, self.path.read_text())

    def test_missing_file_is_ignored(self):
        self.path.unlink()
        self.assertFalse(PATCH.patch_source_tree(self.root))


class TabRestoreDiagnosticsWiringTest(unittest.TestCase):
    def test_scripts_apply_the_patch_only_on_old_android(self):
        for name, target in (("patch.sh", "."), ("hotfix_existing_src.sh", '"$SRC_DIR"')):
            with self.subTest(script=name):
                text = (Path(__file__).resolve().parents[1] / name).read_text()
                block_start = text.index("if is_old_version_branch; then")
                block_end = text.index("verify_old_android_features.py", block_start)
                block = text[block_start:block_end]
                self.assertIn(
                    f'python3 "$SCRIPT_DIR/patch_tab_restore_diagnostics.py" {target}',
                    block,
                )


if __name__ == "__main__":
    unittest.main()
