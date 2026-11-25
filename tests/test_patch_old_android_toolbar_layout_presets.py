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

import android.view.Gravity;

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

    @Override
    public void onWindowVisibilityChanged(int visibility) {
        super.onWindowVisibilityChanged(visibility);
        updateButtonVisibility();
    }

    @Override
    public void destroy() {
        cancelAnimations();
        super.destroy();
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
            self.assertIn("ToolbarPhone.heliumRefreshLayoutPreset();", fragment)
            self.assertNotIn(".recreate()", fragment)

            toolbar = (root / patch.TOOLBAR_PHONE).read_text()
            self.assertIn("maybeApplyHeliumToolbarLayoutPreset();", toolbar)
            self.assertIn("HELIUM_LAYOUT_START", toolbar)
            self.assertIn("HELIUM_LAYOUT_REVERSE", toolbar)
            self.assertIn("public static void heliumRefreshLayoutPreset()", toolbar)
            self.assertIn("sHeliumActiveToolbar == this", toolbar)
            self.assertNotIn("WeakReference", toolbar)
            self.assertIn(patch.TOOLBAR_WINDOW_VIS_MARKER, toolbar)
            self.assertIn(patch.LEFT_BOUNDS_MARKER, toolbar)
            self.assertIn(patch.CHILD_LEFT_MARKER, toolbar)
            self.assertEqual(toolbar.count("private void applyHeliumToolbarLayoutPreset()"), 1)

    def test_reads_live_children_instead_of_recorded_stub_references(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_sources(root)
            patch.patch_source_tree(root)

            toolbar = (root / patch.TOOLBAR_PHONE).read_text()
            apply_body = toolbar[toolbar.index("private void applyHeliumToolbarLayoutPreset()") :]
            apply_body = apply_body[: apply_body.index("\n    }\n")]

            # Inflated ViewStubs replace themselves, so the ordering must come from the
            # container's current children.
            self.assertIn("mToolbarButtonsContainer.getChildAt(heliumIndex)", apply_body)
            self.assertNotIn("extensionsStub", apply_body)
            self.assertIn("heliumExtensionsEndIndex(endOrder)", apply_body)
            self.assertIn("mHeliumPlacedExtensions = extensions;", apply_body)
            # Re-adding a view that still has a parent throws, so every move goes through
            # the detaching helper.
            self.assertIn("addHeliumToolbarView(mToolbarButtonsContainer, view);", apply_body)
            self.assertNotIn("mToolbarButtonsContainer.addView(view);", apply_body)
            self.assertIn("addHeliumToolbarView(this, mHomeButton);", apply_body)

    def test_upgrades_stale_preset_sections(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_sources(root)
            stale = TOOLBAR_PHONE_SOURCE.replace(
                "    private View mToolbarBackButton;\n",
                "    private View mToolbarBackButton;\n"
                + patch.TOOLBAR_FIELDS_START
                + "    private final java.util.ArrayList<View> mHeliumEndOrder = "
                + "new java.util.ArrayList<>();\n",
            ).replace(
                "    private boolean isBottomToolbar() {\n",
                patch.TOOLBAR_METHODS_START
                + "        return 0;\n"
                + "    }\n\n"
                + "    private boolean isBottomToolbar() {\n",
            )
            (root / patch.TOOLBAR_PHONE).write_text(stale)

            self.assertTrue(patch.patch_source_tree(root))

            toolbar = (root / patch.TOOLBAR_PHONE).read_text()
            self.assertNotIn("        return 0;\n", toolbar)
            self.assertIn("maybeApplyHeliumToolbarLayoutPreset()", toolbar)
            self.assertIn("sHeliumActiveToolbar", toolbar)
            self.assertEqual(
                toolbar.count("mHeliumEndOrder = new java.util.ArrayList<>()"), 1
            )
            self.assertEqual(toolbar.count("private int heliumToolbarLayoutPreset()"), 1)
            self.assertEqual(toolbar.count("private void applyHeliumToolbarLayoutPreset()"), 1)
            self.assertFalse(patch.patch_source_tree(root))

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
