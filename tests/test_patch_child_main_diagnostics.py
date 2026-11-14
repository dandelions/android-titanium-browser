import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "patch_child_main_diagnostics.py"
SPEC = importlib.util.spec_from_file_location(
    "patch_child_main_diagnostics", MODULE_PATH
)
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)


CHILD_SERVICE_SOURCE = """    private void onBeforeMain() {
        Log.i(TAG, "Helium trace: entering child main pid=%d", Process.myPid());
        mDelegate.runMain();
        try {
            mParentProcess.reportCleanExit();
        } catch (RemoteException e) {
            Log.e(TAG, "Failed to call clean exit callback.", e);
        }
        ChildProcessServiceJni.get().exitChildProcess();
    }
"""

PATH_UTILS_SOURCE = """public class PathUtils {
    @SuppressWarnings("unused")
    @CalledByNative
    public static @JniType("std::string") String getExternalStorageDirectory() {
        return Environment.getExternalStorageDirectory().getAbsolutePath();
    }
}
"""


class ChildMainDiagnosticsPatchTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.child_service = self.root / PATCH.CHILD_SERVICE
        self.path_utils = self.root / PATCH.PATH_UTILS
        self.child_service.parent.mkdir(parents=True, exist_ok=True)
        self.path_utils.parent.mkdir(parents=True, exist_ok=True)
        self.child_service.write_text(CHILD_SERVICE_SOURCE)
        self.path_utils.write_text(PATH_UTILS_SOURCE)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_logs_the_child_main_return_value(self):
        self.assertTrue(PATCH.patch_source_tree(self.root))
        result = self.child_service.read_text()
        self.assertIn('"Helium trace: child main returned pid=%d"', result)
        self.assertLess(
            result.index("mDelegate.runMain();"),
            result.index("Helium trace: child main returned"),
        )
        self.assertLess(
            result.index("Helium trace: child main returned"),
            result.index("reportCleanExit()"),
        )

    def test_falls_back_when_external_storage_is_unavailable(self):
        self.assertTrue(PATCH.patch_source_tree(self.root))
        result = self.path_utils.read_text()
        self.assertIn("!external.canRead()", result)
        self.assertIn("getFilesDir().getAbsolutePath()", result)
        self.assertNotIn(
            "return Environment.getExternalStorageDirectory().getAbsolutePath();", result
        )

    def test_repeated_runs_are_no_ops(self):
        self.assertTrue(PATCH.patch_source_tree(self.root))
        child_once = self.child_service.read_text()
        path_once = self.path_utils.read_text()
        self.assertFalse(PATCH.patch_source_tree(self.root))
        self.assertEqual(child_once, self.child_service.read_text())
        self.assertEqual(path_once, self.path_utils.read_text())

    def test_missing_files_are_ignored(self):
        self.child_service.unlink()
        self.path_utils.unlink()
        self.assertFalse(PATCH.patch_source_tree(self.root))


class ChildMainDiagnosticsWiringTest(unittest.TestCase):
    def test_scripts_apply_the_patch_only_on_old_android(self):
        for name, target in (("patch.sh", "."), ("hotfix_existing_src.sh", '"$SRC_DIR"')):
            with self.subTest(script=name):
                text = (Path(__file__).resolve().parents[1] / name).read_text()
                block_start = text.index("if is_old_version_branch; then")
                block_end = text.index("verify_old_android_features.py", block_start)
                block = text[block_start:block_end]
                self.assertIn(
                    f'python3 "$SCRIPT_DIR/patch_child_main_diagnostics.py" {target}',
                    block,
                )


if __name__ == "__main__":
    unittest.main()
