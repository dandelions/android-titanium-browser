import tempfile
import unittest
from pathlib import Path

import patch_old_android_toolbar_layout_presets as patch


PREF_KEYS_SOURCE = """public final class ChromePreferenceKeys {
    // If the toolbar should be shown on top.
    public static final String TOOLBAR_TOP_ANCHORED = "Chrome.Toolbar.TopAnchored";
}
"""

SETTINGS_XML_SOURCE = """<PreferenceScreen>
    <org.chromium.components.browser_ui.settings.ChromeSwitchPreference
        android:key="hide_desktop_tab_strip"
        android:title="@string/hide_desktop_tab_strip_title" />
</PreferenceScreen>
"""

SETTINGS_FRAGMENT_SOURCE = """import org.chromium.chrome.browser.settings.ChromeBaseSettingsFragment;
import org.chromium.components.browser_ui.settings.SettingsUtils;

public class AddressBarSettingsFragment extends ChromeBaseSettingsFragment {
    @Override
    public void onCreatePreferences(@Nullable Bundle savedInstanceState, @Nullable String rootKey) {
        SettingsUtils.addPreferencesFromResource(this, R.xml.address_bar_settings);
        updateHideDesktopTabsPreference();
    }

    @Override
    public void onConfigurationChanged(Configuration newConfig) {
        super.onConfigurationChanged(newConfig);
        overrideDescriptionIfFoldable();
    }

    private void updateHideDesktopTabsPreference() {
    }
}
"""

TOOLBAR_PHONE_SOURCE = """package org.chromium.chrome.browser.toolbar.top;

public class ToolbarPhone extends ToolbarLayout {
    private View mToolbarBackButton;

    @Override
    public void onFinishInflate() {
        try (TraceEvent te = TraceEvent.scoped("ToolbarPhone.onFinishInflate")) {
            super.onFinishInflate();

            mToolbarButtonsContainer = findViewById(R.id.toolbar_buttons);
            mHomeButton = findViewById(R.id.home_button);
            mToolbarBackButton = findViewById(R.id.back_button);

            setLayoutTransition(null);

            mActiveLocationBarBackgroundView = findViewById(R.id.location_bar_background_view);
            if (ChromeFeatureList.sToolbarPhoneAnimationRefactor.isEnabled()) {
                mActiveLocationBarBackgroundView.setVisibility(View.VISIBLE);
            }
        }
    }

    private boolean isBottomToolbar() {
        return false;
    }

    private int getBoundsAfterAccountingForLeftButton() {
        int padding = mToolbarSidePaddingForNtp;

        if (mHomeButton.getVisibility() != GONE) {
            padding = mHomeButton.getMeasuredWidth();
        }

        return padding;
    }

    private void updateButtonsTranslationY() {
        int transY = 0;
        mToolbarButtonsContainer.setTranslationY(transY);
        mHomeButton.setTranslationY(transY);
    }

    private void updateUrlExpansionAnimation() {
        int toolbarButtonVisibility = getToolbarButtonVisibility();
        mToolbarButtonsContainer.setVisibility(toolbarButtonVisibility);
    }

    void drawWithoutBackground(Canvas canvas) {
        View extContainer = findViewById(R.id.extensions_toolbar_container);
        if (extContainer != null) {
            canvas.save();
            ViewUtils.translateCanvasToView(mToolbarButtonsContainer, extContainer, canvas);
            extContainer.draw(canvas);
            canvas.restore();
        }
        if (mSigninButtonCoordinator != null) {
            View signinButtonView = mSigninButtonCoordinator.getViewForDrawing();
            if (signinButtonView != null) {
                canvas.save();
                ViewUtils.translateCanvasToView(mToolbarButtonsContainer, signinButtonView, canvas);
                signinButtonView.draw(canvas);
                canvas.restore();
            }
        }
        ToggleTabStackButtonCoordinator tabSwitcherButtonCoordinator = null;
        if (tabSwitcherButtonCoordinator != null) {
            tabSwitcherButtonCoordinator.draw(mToolbarButtonsContainer, canvas);
        }
        final MenuButtonCoordinator menuButtonCoordinator = getMenuButtonCoordinator();
        if (menuButtonCoordinator != null) {
            int rgbAlpha = 255;
            menuButtonCoordinator.drawTabSwitcherAnimationOverlay(
                    mToolbarButtonsContainer, canvas, rgbAlpha);
        }
    }

    private boolean isChildLeft(View child) {
        return (child == mHomeButton) ^ LocalizationUtils.isLayoutRtl();
    }
}
"""


class ToolbarLayoutPresetsPatchTest(unittest.TestCase):
    def _write_sources(self, root: Path) -> None:
        files = {
            patch.PREF_KEYS: PREF_KEYS_SOURCE,
            patch.SETTINGS_XML: SETTINGS_XML_SOURCE,
            patch.SETTINGS_FRAGMENT: SETTINGS_FRAGMENT_SOURCE,
            patch.TOOLBAR_PHONE: TOOLBAR_PHONE_SOURCE,
        }
        for relative, text in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)

    def test_adds_preset_preference_settings_and_toolbar_layout(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_sources(root)

            self.assertTrue(patch.patch_source_tree(root))

            keys = (root / patch.PREF_KEYS).read_text()
            self.assertIn(patch.PREF_MARKER, keys)
            self.assertIn('"helium_toolbar_layout_preset"', keys)

            xml = (root / patch.SETTINGS_XML).read_text()
            self.assertIn(patch.XML_MARKER, xml)

            fragment = (root / patch.SETTINGS_FRAGMENT).read_text()
            self.assertIn("setupToolbarLayoutPreference();", fragment)
            self.assertIn("ChromePreferenceKeys.HELIUM_TOOLBAR_LAYOUT_PRESET", fragment)

            toolbar = (root / patch.TOOLBAR_PHONE).read_text()
            self.assertIn("applyHeliumToolbarLayoutPreset();", toolbar)
            self.assertIn("HELIUM_LAYOUT_START", toolbar)
            self.assertIn("HELIUM_LAYOUT_REVERSE", toolbar)
            self.assertIn(patch.LEFT_BOUNDS_MARKER, toolbar)
            self.assertIn(patch.CHILD_LEFT_MARKER, toolbar)
            self.assertEqual(toolbar.count("private void applyHeliumToolbarLayoutPreset()"), 1)

    def test_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_sources(root)

            self.assertTrue(patch.patch_source_tree(root))
            snapshot = {
                relative: (root / relative).read_text()
                for relative in (
                    patch.PREF_KEYS,
                    patch.SETTINGS_XML,
                    patch.SETTINGS_FRAGMENT,
                    patch.TOOLBAR_PHONE,
                )
            }
            self.assertFalse(patch.patch_source_tree(root))
            for relative, text in snapshot.items():
                self.assertEqual(text, (root / relative).read_text())


if __name__ == "__main__":
    unittest.main()
