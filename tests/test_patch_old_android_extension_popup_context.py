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
OPTIONS_SOURCE = """        if (mToolbarBridge != null) {
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

            self.assertTrue(patch.patch_source(root))
            direct = tabs_api.read_text(encoding="utf-8")
            options = mediator.read_text(encoding="utf-8")
            self.assertIn(patch.DIRECT_MARKER, direct)
            self.assertIn("kDontScrubTab", direct)
            self.assertIn(patch.OPTIONS_MARKER, options)
            self.assertIn("mMenuBridge.getOptionsPageUrl(extensionId)", options)
            self.assertIn("openUrlFromMenu(optionsUrl);", options)
            self.assertFalse(patch.patch_source(root))
            self.assertEqual(direct, tabs_api.read_text(encoding="utf-8"))
            self.assertEqual(options, mediator.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
