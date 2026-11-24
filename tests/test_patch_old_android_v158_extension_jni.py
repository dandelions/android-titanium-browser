import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "patch_old_android_v158_extension_jni", ROOT / "patch_old_android_v158_extension_jni.py"
)
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)


class OldAndroidV158ExtensionJniPatchTest(unittest.TestCase):
    def test_migrates_legacy_bridge_fields_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            menu = root / PATCH.BRIDGES[0]
            toolbar = root / PATCH.BRIDGES[1]
            for path in (menu, toolbar):
                path.parent.mkdir(parents=True, exist_ok=True)
            menu.write_text(
                "mNativeExtensionsMenuDelegateAndroid\n"
                "mNativeExtensionsToolbarAndroid\n"
                "long nativeExtensionsMenuDelegateAndroid\n"
                "long nativeExtensionsToolbarAndroid\n"
                "        assert mNative != 0;\n"
                "    private void openExtensionOptionsFromMenu(String extensionId) {\n"
                "        String optionsUrl = mMenuBridge.getOptionsPageUrl(extensionId);\n"
                "        if (optionsUrl != null && !optionsUrl.isEmpty()) {\n"
                "            openUrlFromMenu(optionsUrl);\n"
                "            return;\n"
                "        }\n"
                "    }\n"
                "    public List<ExtensionsMenuTypes.MenuEntryState> getMenuEntries() {\n"
                "    }\n"
                "    interface Natives {\n"
                "    }\n"
            )
            toolbar.write_text(
                "mNativeExtensionsMenuDelegateAndroid\n"
                "mNativeExtensionsToolbarAndroid\n"
                "long nativeExtensionsMenuDelegateAndroid\n"
                "long nativeExtensionsToolbarAndroid\n"
                "        assert mNative != 0;\n"
            )
            toolbar.write_text(
                "@NativeMethods\ninterface Natives {\n"
                "        void executeUserAction(\n"
                "                JniPtr<NativeExtensionsToolbarAndroid> self);\n"
                "}\n"
            )

            self.assertTrue(PATCH.migrate_source_tree(root))
            for path in (menu, toolbar):
                result = path.read_text()
                self.assertNotIn("mNativeExtensions", result)
                self.assertNotIn("long nativeExtensions", result)
                self.assertNotIn("assert mNative != 0", result)
            self.assertFalse(PATCH.migrate_source_tree(root))


if __name__ == "__main__":
    unittest.main()
