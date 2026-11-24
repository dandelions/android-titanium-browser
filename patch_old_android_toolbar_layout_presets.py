#!/usr/bin/env python3
"""Add selectable address-bar button layout presets to old-android."""

from pathlib import Path
import sys


PREF_KEYS = Path(
    "chrome/browser/preferences/android/java/src/org/chromium/chrome/browser/preferences/"
    "ChromePreferenceKeys.java"
)
SETTINGS_XML = Path("chrome/browser/ui/android/toolbar/java/res/xml/address_bar_settings.xml")
SETTINGS_FRAGMENT = Path(
    "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/settings/"
    "AddressBarSettingsFragment.java"
)
TOOLBAR_PHONE = Path(
    "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/top/"
    "ToolbarPhone.java"
)

PREF_MARKER = "HELIUM_TOOLBAR_LAYOUT_PRESET"
PREF_OLD = '    public static final String TOOLBAR_TOP_ANCHORED = "Chrome.Toolbar.TopAnchored";\n'
PREF_NEW = PREF_OLD + """
    // Helium: old-android address-bar button layout preset.
    public static final String HELIUM_TOOLBAR_LAYOUT_PRESET = "helium_toolbar_layout_preset";
"""

XML_MARKER = 'android:key="toolbar_layout_preset"'
XML_OLD = """    <org.chromium.components.browser_ui.settings.ChromeSwitchPreference
        android:key="hide_desktop_tab_strip"
        android:title="@string/hide_desktop_tab_strip_title" />
"""
XML_NEW = XML_OLD + """
    <org.chromium.components.browser_ui.settings.ChromeBasePreference
        android:key="toolbar_layout_preset"
        android:title="地址栏按钮布局" />
"""

FRAGMENT_IMPORT_OLD = "import org.chromium.chrome.browser.settings.ChromeBaseSettingsFragment;\n"
FRAGMENT_IMPORT_NEW = (
    "import org.chromium.chrome.browser.preferences.ChromePreferenceKeys;\n"
    "import org.chromium.chrome.browser.preferences.ChromeSharedPreferences;\n"
    "import org.chromium.chrome.browser.settings.ChromeBaseSettingsFragment;\n"
)
FRAGMENT_CALL_OLD = "        updateHideDesktopTabsPreference();\n    }\n\n    @Override\n    public void onConfigurationChanged"
FRAGMENT_CALL_NEW = (
    "        updateHideDesktopTabsPreference();\n"
    "        setupToolbarLayoutPreference();\n"
    "    }\n\n    @Override\n    public void onConfigurationChanged"
)
FRAGMENT_MARKER = "setupToolbarLayoutPreference();"
FRAGMENT_METHODS = """    private void setupToolbarLayoutPreference() {
        Preference preference = findPreference("toolbar_layout_preset");
        if (preference == null) {
            return;
        }
        preference.setOnPreferenceClickListener(
                p -> {
                    showToolbarLayoutDialog();
                    return true;
                });
        updateToolbarLayoutSummary(preference);
    }

    private void updateToolbarLayoutSummary(Preference preference) {
        preference.setSummary(toolbarLayoutLabels()[toolbarLayoutPreset()]);
    }

    private static String[] toolbarLayoutLabels() {
        return new String[] {"当前布局", "左到右布局", "反向布局"};
    }

    private static String[] toolbarLayoutDialogOptions() {
        return new String[] {
            "当前布局：主页 - 地址栏 - 扩展 - 窗口 - 菜单",
            "左到右：主页 - 窗口 - 地址栏 - 扩展 - 菜单",
            "反向：菜单 - 扩展 - 地址栏 - 窗口 - 主页"
        };
    }

    private static int toolbarLayoutPreset() {
        int preset =
                ChromeSharedPreferences.getInstance()
                        .readInt(ChromePreferenceKeys.HELIUM_TOOLBAR_LAYOUT_PRESET, 0);
        return (preset == 1 || preset == 2) ? preset : 0;
    }

    private void showToolbarLayoutDialog() {
        new android.app.AlertDialog.Builder(getContext())
                .setTitle("地址栏按钮布局")
                .setSingleChoiceItems(
                        toolbarLayoutDialogOptions(),
                        toolbarLayoutPreset(),
                        (dialog, which) -> {
                            ChromeSharedPreferences.getInstance()
                                    .writeInt(
                                            ChromePreferenceKeys.HELIUM_TOOLBAR_LAYOUT_PRESET,
                                            which);
                            dialog.dismiss();
                            Preference preference = findPreference("toolbar_layout_preset");
                            if (preference != null) {
                                updateToolbarLayoutSummary(preference);
                            }
                            if (getActivity() != null) {
                                getActivity().recreate();
                            }
                        })
                .setNegativeButton("取消", null)
                .show();
    }

"""
FRAGMENT_ANCHOR = "    private void updateHideDesktopTabsPreference() {\n"

TOOLBAR_FIELDS_OLD = "    private View mToolbarBackButton;\n"
TOOLBAR_IMPORT_OLD = "import android.view.Gravity;\n"
TOOLBAR_IMPORT_NEW = "import android.view.Gravity;\nimport android.widget.FrameLayout;\n"
TOOLBAR_FIELDS_NEW = TOOLBAR_FIELDS_OLD + """    // Helium: address-bar button layout presets for old-android.
    private static final int HELIUM_LAYOUT_CURRENT = 0;
    private static final int HELIUM_LAYOUT_START = 1;
    private static final int HELIUM_LAYOUT_REVERSE = 2;
    private @Nullable ViewGroup mHeliumStartButtons;
    private View mHeliumTabs;
    private View mHeliumMenu;
    private final java.util.ArrayList<View> mHeliumEndOrder = new java.util.ArrayList<>();
"""

TOOLBAR_INFLATE_OLD = """            mToolbarButtonsContainer = findViewById(R.id.toolbar_buttons);
            mHomeButton = findViewById(R.id.home_button);
            mToolbarBackButton = findViewById(R.id.back_button);
"""
TOOLBAR_INFLATE_NEW = TOOLBAR_INFLATE_OLD + """            mHeliumTabs = findViewById(R.id.tab_switcher_button);
            mHeliumMenu = findViewById(R.id.menu_button_wrapper);
            mHeliumEndOrder.clear();
            for (int heliumIndex = 0; heliumIndex < mToolbarButtonsContainer.getChildCount();
                    heliumIndex++) {
                mHeliumEndOrder.add(mToolbarButtonsContainer.getChildAt(heliumIndex));
            }
"""
TOOLBAR_INFLATE_MARKER = "mHeliumEndOrder.clear();"

TOOLBAR_APPLY_OLD = """            mActiveLocationBarBackgroundView = findViewById(R.id.location_bar_background_view);
            if (ChromeFeatureList.sToolbarPhoneAnimationRefactor.isEnabled()) {
                mActiveLocationBarBackgroundView.setVisibility(View.VISIBLE);
            }
"""
TOOLBAR_APPLY_NEW = TOOLBAR_APPLY_OLD + """            applyHeliumToolbarLayoutPreset();
"""
TOOLBAR_APPLY_MARKER = "applyHeliumToolbarLayoutPreset();"

TOOLBAR_METHODS = """    // Helium: address-bar button layout presets for old-android.
    private int heliumToolbarLayoutPreset() {
        int preset =
                org.chromium.chrome.browser.preferences.ChromeSharedPreferences.getInstance()
                        .readInt(
                                org.chromium.chrome.browser.preferences.ChromePreferenceKeys
                                        .HELIUM_TOOLBAR_LAYOUT_PRESET,
                                HELIUM_LAYOUT_CURRENT);
        return (preset == HELIUM_LAYOUT_START || preset == HELIUM_LAYOUT_REVERSE)
                ? preset
                : HELIUM_LAYOUT_CURRENT;
    }

    private ViewGroup heliumStartButtons() {
        if (mHeliumStartButtons == null) {
            android.widget.LinearLayout container = new android.widget.LinearLayout(getContext());
            container.setOrientation(android.widget.LinearLayout.HORIZONTAL);
            FrameLayout.LayoutParams params =
                    new FrameLayout.LayoutParams(
                            LayoutParams.WRAP_CONTENT, LayoutParams.WRAP_CONTENT);
            params.gravity = Gravity.TOP | Gravity.START;
            container.setLayoutParams(params);
            addView(container);
            mHeliumStartButtons = container;
        }
        return mHeliumStartButtons;
    }

    private @Nullable View heliumExtensionsView() {
        View view = findViewById(R.id.extensions_toolbar_container);
        return view != null ? view : findViewById(R.id.extensions_toolbar_container_stub);
    }

    private void detachHeliumToolbarView(@Nullable View view) {
        if (view == null) {
            return;
        }
        android.view.ViewParent parent = view.getParent();
        if (parent instanceof ViewGroup) {
            ((ViewGroup) parent).removeView(view);
        }
    }

    private ViewGroup heliumContainerFor(@Nullable View view) {
        if (view != null && view.getParent() instanceof ViewGroup) {
            return (ViewGroup) view.getParent();
        }
        return mToolbarButtonsContainer;
    }

    private void heliumUseLinearParams(@Nullable View view) {
        if (view == null) {
            return;
        }
        if (!(view.getLayoutParams() instanceof android.widget.LinearLayout.LayoutParams)) {
            view.setLayoutParams(
                    new android.widget.LinearLayout.LayoutParams(
                            LayoutParams.WRAP_CONTENT, LayoutParams.WRAP_CONTENT));
        }
    }

    private void heliumUseFrameParams(@Nullable View view) {
        if (view == null) {
            return;
        }
        if (!(view.getLayoutParams() instanceof FrameLayout.LayoutParams)) {
            FrameLayout.LayoutParams params =
                    new FrameLayout.LayoutParams(
                            LayoutParams.WRAP_CONTENT, LayoutParams.MATCH_PARENT);
            params.gravity = Gravity.TOP | Gravity.START;
            view.setLayoutParams(params);
        }
    }

    private void applyHeliumToolbarLayoutPreset() {
        if (mToolbarButtonsContainer == null || mHeliumEndOrder.isEmpty()) {
            return;
        }
        int preset = heliumToolbarLayoutPreset();
        ViewGroup start = heliumStartButtons();
        View extensions = heliumExtensionsView();
        start.removeAllViews();
        detachHeliumToolbarView(mHomeButton);
        detachHeliumToolbarView(mHeliumTabs);
        detachHeliumToolbarView(mHeliumMenu);
        detachHeliumToolbarView(extensions);
        mToolbarButtonsContainer.removeAllViews();
        java.util.ArrayList<View> endOrder = new java.util.ArrayList<>();
        for (View child : mHeliumEndOrder) {
            if (child == mHomeButton || child == mHeliumTabs || child == mHeliumMenu
                    || child == extensions) {
                continue;
            }
            endOrder.add(child);
        }
        if (preset == HELIUM_LAYOUT_START) {
            if (mHomeButton != null) {
                heliumUseLinearParams(mHomeButton);
                start.addView(mHomeButton);
            }
            if (mHeliumTabs != null) {
                heliumUseLinearParams(mHeliumTabs);
                start.addView(mHeliumTabs);
            }
            if (extensions != null) {
                heliumUseLinearParams(extensions);
                endOrder.add(extensions);
            }
            if (mHeliumMenu != null) {
                heliumUseLinearParams(mHeliumMenu);
                endOrder.add(mHeliumMenu);
            }
        } else if (preset == HELIUM_LAYOUT_REVERSE) {
            if (mHeliumMenu != null) {
                heliumUseLinearParams(mHeliumMenu);
                start.addView(mHeliumMenu);
            }
            if (extensions != null) {
                heliumUseLinearParams(extensions);
                start.addView(extensions);
            }
            if (mHeliumTabs != null) {
                heliumUseLinearParams(mHeliumTabs);
                endOrder.add(mHeliumTabs);
            }
            if (mHomeButton != null) {
                heliumUseLinearParams(mHomeButton);
                endOrder.add(mHomeButton);
            }
        } else {
            endOrder.clear();
            for (View child : mHeliumEndOrder) {
                if (child == mHomeButton) {
                    continue;
                }
                endOrder.add(child);
            }
            if (mHomeButton != null) {
                heliumUseFrameParams(mHomeButton);
                FrameLayout.LayoutParams params =
                        (FrameLayout.LayoutParams) mHomeButton.getLayoutParams();
                params.gravity = Gravity.TOP | Gravity.START;
                mHomeButton.setLayoutParams(params);
                addView(mHomeButton);
            }
        }
        for (View child : endOrder) {
            mToolbarButtonsContainer.addView(child);
        }
        start.setVisibility(mToolbarButtonsContainer.getVisibility());
        requestLayout();
        invalidate();
    }

"""
TOOLBAR_METHODS_ANCHOR = "    private boolean isBottomToolbar() {\n"

LEFT_BOUNDS_OLD = """    private int getBoundsAfterAccountingForLeftButton() {
        int padding = mToolbarSidePaddingForNtp;
"""
LEFT_BOUNDS_NEW = """    private int getBoundsAfterAccountingForLeftButton() {
        if (mHeliumStartButtons != null
                && mHeliumStartButtons.getVisibility() != GONE
                && mHeliumStartButtons.getChildCount() > 0) {
            return Math.max(mToolbarSidePaddingForNtp, mHeliumStartButtons.getMeasuredWidth());
        }
        int padding = mToolbarSidePaddingForNtp;
"""
LEFT_BOUNDS_MARKER = "mHeliumStartButtons.getMeasuredWidth()"

TRANSLATION_OLD = """        mToolbarButtonsContainer.setTranslationY(transY);
        mHomeButton.setTranslationY(transY);
"""
TRANSLATION_NEW = TRANSLATION_OLD + """        if (mHeliumStartButtons != null) {
            mHeliumStartButtons.setTranslationY(transY);
        }
"""
TRANSLATION_MARKER = "mHeliumStartButtons.setTranslationY(transY);"

BUTTON_VISIBILITY_OLD = """        int toolbarButtonVisibility = getToolbarButtonVisibility();
        mToolbarButtonsContainer.setVisibility(toolbarButtonVisibility);
"""
BUTTON_VISIBILITY_NEW = BUTTON_VISIBILITY_OLD + """        if (mHeliumStartButtons != null) {
            mHeliumStartButtons.setVisibility(toolbarButtonVisibility);
        }
"""
BUTTON_VISIBILITY_MARKER = "mHeliumStartButtons.setVisibility(toolbarButtonVisibility);"

DRAW_EXT_OLD = "            ViewUtils.translateCanvasToView(mToolbarButtonsContainer, extContainer, canvas);"
DRAW_EXT_NEW = (
    "            ViewUtils.translateCanvasToView(heliumContainerFor(extContainer), extContainer, canvas);"
)

DRAW_SIGNIN_OLD = (
    "                ViewUtils.translateCanvasToView(mToolbarButtonsContainer, signinButtonView, canvas);"
)
DRAW_SIGNIN_NEW = (
    "                ViewUtils.translateCanvasToView(heliumContainerFor(signinButtonView), signinButtonView, canvas);"
)

DRAW_TABS_OLD = "            tabSwitcherButtonCoordinator.draw(mToolbarButtonsContainer, canvas);"
DRAW_TABS_NEW = (
    "            tabSwitcherButtonCoordinator.draw(heliumContainerFor(mHeliumTabs), canvas);"
)

DRAW_MENU_OLD = """            menuButtonCoordinator.drawTabSwitcherAnimationOverlay(
                    mToolbarButtonsContainer, canvas, rgbAlpha);"""
DRAW_MENU_NEW = """            menuButtonCoordinator.drawTabSwitcherAnimationOverlay(
                    heliumContainerFor(mHeliumMenu), canvas, rgbAlpha);"""

CHILD_LEFT_OLD = """    private boolean isChildLeft(View child) {
        return (child == mHomeButton) ^ LocalizationUtils.isLayoutRtl();
    }"""
CHILD_LEFT_NEW = """    private boolean isChildLeft(View child) {
        if (mHeliumStartButtons != null && child.getParent() == mHeliumStartButtons) {
            return true;
        }
        if (mToolbarButtonsContainer != null && child.getParent() == mToolbarButtonsContainer) {
            return false;
        }
        return (child == mHomeButton) ^ LocalizationUtils.isLayoutRtl();
    }"""
CHILD_LEFT_MARKER = "child.getParent() == mHeliumStartButtons"


def _replace_once(text: str, old: str, new: str, marker: str, path: Path) -> tuple[str, bool]:
    if marker in text:
        return text, False
    if text.count(old) != 1:
        raise RuntimeError(f"Expected one anchor in {path}: {marker}")
    return text.replace(old, new, 1), True


def patch_preference_keys(root: Path) -> bool:
    path = root / PREF_KEYS
    text = path.read_text(encoding="utf-8")
    text, changed = _replace_once(text, PREF_OLD, PREF_NEW, PREF_MARKER, path)
    if changed:
        path.write_text(text, encoding="utf-8")
    return changed


def patch_settings_xml(root: Path) -> bool:
    path = root / SETTINGS_XML
    text = path.read_text(encoding="utf-8")
    text, changed = _replace_once(text, XML_OLD, XML_NEW, XML_MARKER, path)
    if changed:
        path.write_text(text, encoding="utf-8")
    return changed


def patch_settings_fragment(root: Path) -> bool:
    path = root / SETTINGS_FRAGMENT
    text = path.read_text(encoding="utf-8")
    text, imports_changed = _replace_once(
        text, FRAGMENT_IMPORT_OLD, FRAGMENT_IMPORT_NEW, "ChromePreferenceKeys;", path
    )
    text, call_changed = _replace_once(
        text, FRAGMENT_CALL_OLD, FRAGMENT_CALL_NEW, FRAGMENT_MARKER, path
    )
    methods_changed = False
    if "private void setupToolbarLayoutPreference()" not in text:
        if text.count(FRAGMENT_ANCHOR) != 1:
            raise RuntimeError(f"Expected one settings anchor in {path}")
        text = text.replace(FRAGMENT_ANCHOR, FRAGMENT_METHODS + FRAGMENT_ANCHOR, 1)
        methods_changed = True
    if imports_changed or call_changed or methods_changed:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def patch_toolbar_phone(root: Path) -> bool:
    path = root / TOOLBAR_PHONE
    text = path.read_text(encoding="utf-8")
    changed = False
    replacements = (
        (TOOLBAR_IMPORT_OLD, TOOLBAR_IMPORT_NEW, "import android.widget.FrameLayout;"),
        (TOOLBAR_FIELDS_OLD, TOOLBAR_FIELDS_NEW, "mHeliumStartButtons;"),
        (TOOLBAR_INFLATE_OLD, TOOLBAR_INFLATE_NEW, TOOLBAR_INFLATE_MARKER),
        (TOOLBAR_APPLY_OLD, TOOLBAR_APPLY_NEW, TOOLBAR_APPLY_MARKER),
        (LEFT_BOUNDS_OLD, LEFT_BOUNDS_NEW, LEFT_BOUNDS_MARKER),
        (TRANSLATION_OLD, TRANSLATION_NEW, TRANSLATION_MARKER),
        (BUTTON_VISIBILITY_OLD, BUTTON_VISIBILITY_NEW, BUTTON_VISIBILITY_MARKER),
        (DRAW_EXT_OLD, DRAW_EXT_NEW, DRAW_EXT_NEW.strip()),
        (DRAW_SIGNIN_OLD, DRAW_SIGNIN_NEW, DRAW_SIGNIN_NEW.strip()),
        (DRAW_TABS_OLD, DRAW_TABS_NEW, DRAW_TABS_NEW.strip()),
        (DRAW_MENU_OLD, DRAW_MENU_NEW, DRAW_MENU_NEW.strip()),
        (CHILD_LEFT_OLD, CHILD_LEFT_NEW, CHILD_LEFT_MARKER),
    )
    for old, new, marker in replacements:
        text, updated = _replace_once(text, old, new, marker, path)
        changed = changed or updated
    if "private void applyHeliumToolbarLayoutPreset()" not in text:
        if text.count(TOOLBAR_METHODS_ANCHOR) != 1:
            raise RuntimeError(f"Expected one ToolbarPhone method anchor in {path}")
        text = text.replace(TOOLBAR_METHODS_ANCHOR, TOOLBAR_METHODS + TOOLBAR_METHODS_ANCHOR, 1)
        changed = True
    if changed:
        path.write_text(text, encoding="utf-8")
    return changed


def patch_source_tree(root: Path) -> bool:
    changed = patch_preference_keys(root)
    changed |= patch_settings_xml(root)
    changed |= patch_settings_fragment(root)
    changed |= patch_toolbar_phone(root)
    if changed:
        print(f"Patched old-android address-bar layout presets: {root}")
    return changed


if __name__ == "__main__":
    try:
        patch_source_tree(Path(sys.argv[1] if len(sys.argv) > 1 else "."))
    except (OSError, RuntimeError) as error:
        print(f"[patch_old_android_toolbar_layout_presets] {error}", file=sys.stderr)
        raise SystemExit(1)
