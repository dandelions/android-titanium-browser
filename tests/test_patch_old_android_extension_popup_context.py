import tempfile
import unittest
from pathlib import Path

import patch_old_android_extension_popup_context as patch


DIRECT_SOURCE = """  if (helium_android_popup_direct_query) {
    base::ListValue direct_result;
    direct_result.Append(tabs_internal::CreateTabObjectHelper(
                             android_popup_direct_web_contents, extension(),
                             source_context_type(), nullptr, -1)
                             .ToValue());
    return RespondNow(WithArguments(std::move(direct_result)));
  }
"""
OPTIONS_SOURCE = """import org.chromium.base.lifetime.Destroyable;
import org.chromium.base.supplier.NullableObservableSupplier;

class ExtensionsMenuMediator implements Destroyable {
    private final NullableObservableSupplier<Tab> mCurrentTabSupplier;
    private ExtensionsToolbarBridge mToolbarBridge;
        mToolbarBridge = toolbarBridge;
        mMenuBridge =
                new ExtensionsMenuBridge(mTask, mProfile, toolbarBridge, /* observer= */ this);

    public void destroy() {
    }

        if (mToolbarBridge != null) {
            mToolbarBridge.executeUserAction(extensionId, InvocationSource.TOOLBAR_BUTTON);
            return;
        }
        mMenuBridge.executeAction(extensionId, getCurrentWebContents());
"""


class OldAndroidExtensionPopupContextPatchTest(unittest.TestCase):
    def test_patches_popup_context_and_options_path_idempotently(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tabs_api = root / patch.TABS_API
            mediator = root / patch.MENU_MEDIATOR
            tabs_api.parent.mkdir(parents=True, exist_ok=True)
            mediator.parent.mkdir(parents=True, exist_ok=True)
            tabs_api.write_text(DIRECT_SOURCE, encoding="utf-8")
            mediator.write_text(OPTIONS_SOURCE, encoding="utf-8")
            tab_util = root / patch.TAB_UTIL
            tab_util.parent.mkdir(parents=True, exist_ok=True)
            tab_util.write_text(patch.TAB_UTIL_ANCHOR, encoding="utf-8")

            self.assertTrue(patch.patch_source(root))
            direct = tabs_api.read_text(encoding="utf-8")
            options = mediator.read_text(encoding="utf-8")
            self.assertIn(patch.DIRECT_MARKER, direct)
            self.assertIn("kDontScrubTab", direct)
            self.assertIn(patch.OPTIONS_MARKER, options)
            self.assertIn(patch.MENU_TAB_SYNC_MARKER, options)
            self.assertIn("mCurrentTabSupplier.addSyncObserver(mHeliumTabSupplierObserver)", options)
            self.assertIn("mHeliumTabSupplierObserver.onResult(mCurrentTabSupplier.get());", options)
            self.assertIn("mToolbarBridge.setActiveWebContents(webContents)", options)
            self.assertIn("updateMenuEntries();", options)
            self.assertIn("openUrlFromMenu(optionsUrl);", options)
            util = tab_util.read_text(encoding="utf-8")
            self.assertIn(patch.TAB_UTIL_MARKER, util)
            self.assertIn("if (!target_contents) {", util)
            self.assertFalse(patch.patch_source(root))
            self.assertEqual(direct, tabs_api.read_text(encoding="utf-8"))
            self.assertEqual(options, mediator.read_text(encoding="utf-8"))
            self.assertEqual(util, tab_util.read_text(encoding="utf-8"))

    def test_migrates_options_page_call_from_previous_hotfix(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / patch.MENU_MEDIATOR
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(patch.OPTIONS_LEGACY, encoding="utf-8")

            self.assertTrue(patch.patch_options_path(path))
            result = path.read_text(encoding="utf-8")
            self.assertIn("mMenuBridge.getOptionsPageUrl(extensionId)", result)
            self.assertNotIn("mMenuBridge.openOptionsPage(extensionId)", result)
            self.assertFalse(patch.patch_options_path(path))

    def test_migrates_duplicate_options_url_check_from_interrupted_hotfix(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / patch.MENU_MEDIATOR
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                patch.OPTIONS_EXISTING_URL_CHECK
                + "        // Helium: open extension options through the native Android options path.\n"
                + "        mMenuBridge.openOptionsPage(extensionId);\n",
                encoding="utf-8",
            )

            self.assertTrue(patch.patch_options_path(path))
            result = path.read_text(encoding="utf-8")
            self.assertEqual(result.count("String optionsUrl ="), 1)
            self.assertIn("mMenuBridge.executeAction(extensionId, getCurrentWebContents());", result)
            self.assertNotIn("mMenuBridge.openOptionsPage(extensionId)", result)
            self.assertFalse(patch.patch_options_path(path))


if __name__ == "__main__":
    unittest.main()
