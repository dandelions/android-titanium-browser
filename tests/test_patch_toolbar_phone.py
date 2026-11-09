import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("patch_toolbar_phone", ROOT / "patch_toolbar_phone.py")
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)

MOCK_TOOLBAR_PHONE = """package org.chromium.chrome.browser.toolbar.top;

public class ToolbarPhone extends ToolbarLayout {
    private boolean layoutLocationBarWithoutAnimationExpansion(int containerWidth) {
        if (mLayoutLocationBarInFocusedMode
                || (mVisualState == VisualState.NEW_TAB_NORMAL
                        && mTabSwitcherState == STATIC_TAB)) {
            width = getFocusedLocationBarWidth(containerWidth, priorVisibleWidth, mLayoutLocationBarInFocusedMode);
        }
        return true;
    }

    private int getViewBoundsLeftOfLocationBar(@VisualState int visualState) {
        if (visualState == VisualState.NEW_TAB_NORMAL && mTabSwitcherState == STATIC_TAB) {
            return mToolbarSidePaddingForNtp;
        } else if (getLayoutDirection() == LAYOUT_DIRECTION_RTL) {
            return getBoundsAfterAccountingForRightButtons();
        } else {
            return getBoundsAfterAccountingForLeftButton();
        }
    }

    private int getViewBoundsRightOfLocationBar(@VisualState int visualState) {
        if (visualState == VisualState.NEW_TAB_NORMAL && mTabSwitcherState == STATIC_TAB) {
            return getMeasuredWidth() - mToolbarSidePaddingForNtp;
        } else if (getLayoutDirection() == LAYOUT_DIRECTION_RTL) {
            return getMeasuredWidth() - getBoundsAfterAccountingForLeftButton();
        } else {
            return getMeasuredWidth() - getBoundsAfterAccountingForRightButtons();
        }
    }

    private @VisualState int computeVisualState() {
        if (isLocationBarShownInNtp()) return VisualState.NEW_TAB_NORMAL;
        if (isLocationBarShownInGeneralNtp()) {
            return VisualState.NEW_TAB_SEARCH_ENGINE_NO_LOGO;
        }
        if (isIncognitoBranded()) return VisualState.INCOGNITO;
        if (getToolbarDataProvider().isUsingBrandColor()) return VisualState.BRAND_COLOR;
        return VisualState.NORMAL;
    }
}
"""


class ToolbarPhonePatchTest(unittest.TestCase):
    def test_patches_toolbar_phone_for_bottom_toolbar_ntp_bounds(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ToolbarPhone.java"
            path.write_text(MOCK_TOOLBAR_PHONE, encoding="utf-8")

            self.assertTrue(PATCH.patch_toolbar_phone(path))
            result = path.read_text(encoding="utf-8")
            self.assertIn("private boolean isBottomToolbar()", result)
            self.assertIn("if (isBottomToolbar()) {", result)
            self.assertIn("if (!isBottomToolbar() && visualState == VisualState.NEW_TAB_NORMAL", result)
            self.assertIn("if (mLayoutLocationBarInFocusedMode\n                || (!isBottomToolbar()", result)

            # Idempotency test
            self.assertFalse(PATCH.patch_toolbar_phone(path))
            self.assertEqual(result, path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
