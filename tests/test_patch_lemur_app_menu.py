import shutil
import tempfile
import unittest
from pathlib import Path

from patch_lemur_app_menu import (
    DELEGATE_INTERFACE_REL,
    EXT_MENU_COORD_REL,
    EXT_MENU_MEDIATOR_REL,
    EXT_TOOLBAR_COORD_IMPL_REL,
    HANDLER_IMPL_REL,
    TABBED_DELEGATE_REL,
    is_lemur_branch,
    patch_app_menu_handler_impl,
    patch_app_menu_properties_delegate,
    patch_extensions_menu_coordinator,
    patch_extensions_menu_mediator,
    patch_extensions_toolbar_coordinator_impl,
    patch_tabbed_app_menu_delegate,
    unpatch_app_menu_handler_impl,
    unpatch_app_menu_properties_delegate,
    unpatch_extensions_menu_coordinator,
    unpatch_extensions_menu_mediator,
    unpatch_extensions_toolbar_coordinator_impl,
    unpatch_lemur_app_menu,
    unpatch_tabbed_app_menu_delegate,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DELEGATE_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "chromium_157" / "AppMenuPropertiesDelegate.java"
HANDLER_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "chromium_157" / "AppMenuHandlerImpl.java"
TABBED_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "chromium_157" / "TabbedAppMenuPropertiesDelegate.java"
MEDIATOR_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "chromium_157" / "ExtensionsMenuMediator.java"
MENU_COORD_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "chromium_157" / "ExtensionsMenuCoordinator.java"
TOOLBAR_IMPL_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "chromium_157" / "ExtensionsToolbarCoordinatorImpl.java"


class TestPatchLemurAppMenu(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self.temp_dir.name)

        self.delegate_path = self.work_dir / DELEGATE_INTERFACE_REL
        self.delegate_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(DELEGATE_FIXTURE, self.delegate_path)

        self.handler_path = self.work_dir / HANDLER_IMPL_REL
        self.handler_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(HANDLER_FIXTURE, self.handler_path)

        self.tabbed_path = self.work_dir / TABBED_DELEGATE_REL
        self.tabbed_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(TABBED_FIXTURE, self.tabbed_path)

        self.mediator_path = self.work_dir / EXT_MENU_MEDIATOR_REL
        self.mediator_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(MEDIATOR_FIXTURE, self.mediator_path)
        text = self.mediator_path.read_text(encoding="utf-8")
        text = text.replace(
            "private final TabCreator mTabCreator;",
            "private final TabCreator mTabCreator;\n    private @Nullable View mPendingActionAnchorView;",
        )
        text = text.replace(
            "private void openUrlFromMenu(String url) {",
            "private void onPrimaryActionClicked(View anchorView, String extensionId) {}\n\n    private void openUrlFromMenu(String url) {",
        )
        self.mediator_path.write_text(text, encoding="utf-8")

        self.menu_coord_path = self.work_dir / EXT_MENU_COORD_REL
        self.menu_coord_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(MENU_COORD_FIXTURE, self.menu_coord_path)

        self.toolbar_impl_path = self.work_dir / EXT_TOOLBAR_COORD_IMPL_REL
        self.toolbar_impl_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(TOOLBAR_IMPL_FIXTURE, self.toolbar_impl_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_roundtrip_extensions_menu_mediator(self):
        original = self.mediator_path.read_text(encoding="utf-8")
        patch_extensions_menu_mediator(self.work_dir)
        patched = self.mediator_path.read_text(encoding="utf-8")
        self.assertIn("mPendingFallbackContextMenuButton", patched)
        self.assertIn("executeActionFromAppMenu", patched)

        unpatch_extensions_menu_mediator(self.work_dir)
        unpatched = self.mediator_path.read_text(encoding="utf-8")
        self.assertNotIn("mPendingFallbackContextMenuButton", unpatched)
        self.assertNotIn("executeActionFromAppMenu", unpatched)
        self.assertEqual(original, unpatched)

    def test_roundtrip_app_menu_properties_delegate(self):
        original = self.delegate_path.read_text(encoding="utf-8")
        patch_app_menu_properties_delegate(self.work_dir)
        patched = self.delegate_path.read_text(encoding="utf-8")
        self.assertIn("default boolean showCustomAppMenu(", patched)

        unpatch_app_menu_properties_delegate(self.work_dir)
        unpatched = self.delegate_path.read_text(encoding="utf-8")
        self.assertEqual(original, unpatched)

    def test_roundtrip_app_menu_handler_impl(self):
        original = self.handler_path.read_text(encoding="utf-8")
        patch_app_menu_handler_impl(self.work_dir)
        patched = self.handler_path.read_text(encoding="utf-8")
        self.assertIn("mForceNativeMenuOnce", patched)

        unpatch_app_menu_handler_impl(self.work_dir)
        unpatched = self.handler_path.read_text(encoding="utf-8")
        self.assertEqual(original, unpatched)

    def test_roundtrip_tabbed_app_menu_properties_delegate(self):
        original = self.tabbed_path.read_text(encoding="utf-8")
        patch_tabbed_app_menu_delegate(self.work_dir)
        patched = self.tabbed_path.read_text(encoding="utf-8")
        self.assertIn("registerLemurExtensionsMenuOpener();", patched)
        self.assertIn("hideCustomAppMenu();", patched)
        self.assertIn("Helium: Lemur Browser-style rounded bottom popup menu panel.", patched)
        self.assertIn("new android.os.Handler(android.os.Looper.getMainLooper())", patched)
        self.assertNotIn("triggerMenuAction(dialog, menuId);", patched)

        unpatch_tabbed_app_menu_delegate(self.work_dir)
        unpatched = self.tabbed_path.read_text(encoding="utf-8")
        self.assertNotIn("registerLemurExtensionsMenuOpener();", unpatched)
        self.assertNotIn("hideCustomAppMenu();", unpatched)
        self.assertNotIn("Helium: Lemur Browser-style", unpatched)
        self.assertEqual(original, unpatched)

    def test_unpatch_corrupted_tabbed_delegate_state(self):
        """Tests that when Lemur methods were wiped out but ctor/destroy calls remain, unpatch cleans them."""
        text = self.tabbed_path.read_text(encoding="utf-8")
        corrupted = text.replace(
            "mAppMenuDelegate = appMenuDelegate;\n",
            "mAppMenuDelegate = appMenuDelegate;\n        registerLemurExtensionsMenuOpener();\n",
        ).replace(
            "super.destroy();\n",
            "hideCustomAppMenu();\n        super.destroy();\n",
        )
        self.tabbed_path.write_text(corrupted, encoding="utf-8")

        unpatch_tabbed_app_menu_delegate(self.work_dir)
        repaired = self.tabbed_path.read_text(encoding="utf-8")
        self.assertNotIn("registerLemurExtensionsMenuOpener", repaired)
        self.assertNotIn("hideCustomAppMenu", repaired)

    def test_unpatch_corrupted_extensions_menu_mediator_state(self):
        """Tests that when fallback context menu button is used without declaration, unpatch repairs it."""
        patch_extensions_menu_mediator(self.work_dir)
        # Simulate field removed but methods remaining
        text = self.mediator_path.read_text(encoding="utf-8")
        corrupted = text.replace("    private @Nullable ListMenuButton mPendingFallbackContextMenuButton;\n", "")
        self.mediator_path.write_text(corrupted, encoding="utf-8")

        unpatch_extensions_menu_mediator(self.work_dir)
        repaired = self.mediator_path.read_text(encoding="utf-8")
        self.assertNotIn("mPendingFallbackContextMenuButton", repaired)
        self.assertNotIn("executeActionFromAppMenu", repaired)

    def test_unpatch_all_is_idempotent(self):
        unpatch_lemur_app_menu(self.work_dir)
        unpatch_lemur_app_menu(self.work_dir)
        repaired = self.tabbed_path.read_text(encoding="utf-8")
        self.assertNotIn("registerLemurExtensionsMenuOpener", repaired)

    def test_extensions_menu_coordinator_four_squares_and_tint(self):
        original = self.menu_coord_path.read_text(encoding="utf-8")
        patch_extensions_menu_coordinator(self.work_dir)
        patched = self.menu_coord_path.read_text(encoding="utf-8")
        self.assertIn("createHeliumFourSquaresDrawable()", patched)
        self.assertIn("activityFocusTintList != null ? activityFocusTintList : tintList", patched)
        self.assertIn("mThemeColorProvider.getTint(),", patched)
        self.assertIn("ThemeUtils.getThemedToolbarIconTint(", patched)

        unpatch_extensions_menu_coordinator(self.work_dir)
        unpatched = self.menu_coord_path.read_text(encoding="utf-8")
        self.assertNotIn("createHeliumFourSquaresDrawable()", unpatched)
        self.assertEqual(original, unpatched)

    def test_extensions_toolbar_coordinator_impl_keeps_icon_visible(self):
        original = self.toolbar_impl_path.read_text(encoding="utf-8")
        patch_extensions_toolbar_coordinator_impl(self.work_dir)
        patched = self.toolbar_impl_path.read_text(encoding="utf-8")
        self.assertIn("return !mIsWebApp;", patched)
        self.assertIn("mCanShowMenuIcon = true;", patched)

        unpatch_extensions_toolbar_coordinator_impl(self.work_dir)
        unpatched = self.toolbar_impl_path.read_text(encoding="utf-8")
        self.assertEqual(original, unpatched)


if __name__ == "__main__":
    unittest.main()
