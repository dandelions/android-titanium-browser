import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "patch_extension_toolbar", ROOT / "patch_extension_toolbar.py"
)
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)

MOCK_TOOLBAR_PHONE_XML = """<?xml version="1.0" encoding="utf-8"?>
<org.chromium.chrome.browser.toolbar.top.ToolbarPhone
    xmlns:android="http://schemas.android.com/apk/res/android">
    <LinearLayout
        android:id="@+id/toolbar_buttons">
        <ViewStub
            android:id="@+id/optional_button_stub"
            android:inflatedId="@+id/optional_toolbar_button_container"/>
        <ViewStub
            android:id="@+id/signin_button_stub"
            android:layout="@layout/signin_button_view"/>
        <include layout="@layout/menu_button"/>
    </LinearLayout>
</org.chromium.chrome.browser.toolbar.top.ToolbarPhone>
"""

MOCK_TOOLBAR_MANAGER_JAVA = """package org.chromium.chrome.browser.toolbar;

public class ToolbarManager {
    void initialize() {
        mExtensionsToolbarCoordinator =
                (ExtensionsToolbarCoordinator)
                        task.addFeature(
                                key,
                                () ->
                                        ExtensionsToolbarCoordinator.maybeCreate(
                                                mActivity,
                                                extensionsToolbarStub,
                                                mWindowAndroid,
                                                task,
                                                tabModelProfile,
                                                mActivityTabProvider.asObservable(),
                                                mTabCreatorManager.getTabCreator(false),
                                                getBrowsingModeThemeColorProvider(),
                                                (ToolbarTablet) mToolbarLayout,
                                                contextMenuPopulatorFactory,
                                                selectionDropdownMenuDelegate,
                                                mTabModelSelector,
                                                mModalDialogManagerSupplier.get(),
                                                cleanup,
                                                this::enterDraftingNoFocusOrEndInput,
                                                /* isWebApp= */ false));
    }
}
"""

MOCK_TOOLBAR_PHONE_JAVA = """package org.chromium.chrome.browser.toolbar.top;

public class ToolbarPhone extends ToolbarLayout {
    void drawWithoutBackground(Canvas canvas) {
        if (mOptionalButtonCoordinator != null) {
            canvas.restore();
        }

        // Draw the signin button if visible.
        if (mSigninButtonCoordinator != null) {
            signinButtonView.draw(canvas);
        }
    }
}
"""


class ExtensionToolbarPatchTest(unittest.TestCase):
    def test_patches_source_tree_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            layout_path = root / PATCH.TOOLBAR_PHONE
            manager_path = root / PATCH.TOOLBAR_MANAGER
            phone_java_path = root / PATCH.TOOLBAR_PHONE_JAVA

            layout_path.parent.mkdir(parents=True, exist_ok=True)
            manager_path.parent.mkdir(parents=True, exist_ok=True)
            phone_java_path.parent.mkdir(parents=True, exist_ok=True)

            layout_path.write_text(MOCK_TOOLBAR_PHONE_XML, encoding="utf-8")
            manager_path.write_text(MOCK_TOOLBAR_MANAGER_JAVA, encoding="utf-8")
            phone_java_path.write_text(MOCK_TOOLBAR_PHONE_JAVA, encoding="utf-8")

            self.assertTrue(PATCH.patch_source(root))

            layout_result = layout_path.read_text(encoding="utf-8")
            self.assertIn("extensions_toolbar_container_stub", layout_result)
            self.assertIn("extensions_toolbar_container", layout_result)

            manager_result = manager_path.read_text(encoding="utf-8")
            self.assertIn("mToolbarLayout,", manager_result)
            self.assertNotIn("(ToolbarTablet) mToolbarLayout,", manager_result)

            phone_result = phone_java_path.read_text(encoding="utf-8")
            self.assertIn(
                "View extContainer = findViewById(R.id.extensions_toolbar_container);",
                phone_result,
            )

            # Idempotency: second run does not change files
            self.assertFalse(PATCH.patch_source(root))
            self.assertEqual(layout_result, layout_path.read_text(encoding="utf-8"))
            self.assertEqual(manager_result, manager_path.read_text(encoding="utf-8"))
            self.assertEqual(phone_result, phone_java_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
