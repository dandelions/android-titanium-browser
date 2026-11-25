#!/usr/bin/env python3
"""Add selectable address-bar button layout presets to old-android.

The preset is stored in SharedPreferences and applied to the live toolbar, so
picking a different order updates the buttons without restarting the browser.
"""

from pathlib import Path
import re
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
    "import org.chromium.chrome.browser.toolbar.top.ToolbarPhone;\n"
)
FRAGMENT_LEGACY_IMPORT = (
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
FRAGMENT_METHODS_START = "    private void setupToolbarLayoutPreference() {\n"
FRAGMENT_METHODS_END = "    private void updateHideDesktopTabsPreference() {\n"
FRAGMENT_METHODS_NEW = """    private void setupToolbarLayoutPreference() {
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
                            // The browser activity stays alive behind settings, so drive the
                            // toolbar directly instead of recreating this fragment.
                            ToolbarPhone.heliumRefreshLayoutPreset();
                        })
                .setNegativeButton("取消", null)
                .show();
    }

"""

TOOLBAR_FIELDS_OLD = "    private View mToolbarBackButton;\n"
TOOLBAR_FIELDS_START = (
    "    // Helium: address-bar button layout presets for old-android.\n"
    "    private static final int HELIUM_LAYOUT_CURRENT = 0;\n"
)
TOOLBAR_FIELDS_END = (
    "    private final java.util.ArrayList<View> mHeliumEndOrder = new java.util.ArrayList<>();\n"
)
TOOLBAR_FIELDS_NEW = """    // Helium: address-bar button layout presets for old-android.
    private static final int HELIUM_LAYOUT_CURRENT = 0;
    private static final int HELIUM_LAYOUT_START = 1;
    private static final int HELIUM_LAYOUT_REVERSE = 2;
    private static @Nullable ToolbarPhone sHeliumActiveToolbar;
    private @Nullable ViewGroup mHeliumStartButtons;
    private View mHeliumTabs;
    private View mHeliumMenu;
    private int mHeliumAppliedPreset = -1;
    private @Nullable View mHeliumPlacedExtensions;
    private final java.util.ArrayList<View> mHeliumEndOrder = new java.util.ArrayList<>();
"""
TOOLBAR_IMPORT_OLD = "import android.view.Gravity;\n"
TOOLBAR_IMPORT_NEW = "import android.view.Gravity;\nimport android.widget.FrameLayout;\n"

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
TOOLBAR_APPLY_NEW = TOOLBAR_APPLY_OLD + """            maybeApplyHeliumToolbarLayoutPreset();
"""
TOOLBAR_APPLY_MARKER = "maybeApplyHeliumToolbarLayoutPreset();"

TOOLBAR_WINDOW_VIS_PATTERN = re.compile(
    r"    public void onWindowVisibilityChanged\(int visibility\) \{\n"
    r"(?:        .*\n)*?"
    r"    \}\n"
)
TOOLBAR_WINDOW_VIS_NEW = """    public void onWindowVisibilityChanged(int visibility) {
        super.onWindowVisibilityChanged(visibility);
        updateButtonVisibility();
        // Re-check after the traversal: re-parenting the toolbar from inside this callback
        // races the first frame, which the renderer cannot survive in single-process mode.
        if (visibility == VISIBLE) {
            post(this::maybeApplyHeliumToolbarLayoutPreset);
        }
    }
"""
TOOLBAR_WINDOW_VIS_MARKER = "post(this::maybeApplyHeliumToolbarLayoutPreset);"

TOOLBAR_DESTROY_START = "    public void destroy() {\n"
TOOLBAR_DESTROY_END = "        cancelAnimations();\n"
TOOLBAR_DESTROY_NEW = """    public void destroy() {
        if (sHeliumActiveToolbar == this) {
            sHeliumActiveToolbar = null;
        }
        cancelAnimations();
"""

TOOLBAR_METHODS_START = (
    "    // Helium: address-bar button layout presets for old-android.\n"
    "    private int heliumToolbarLayoutPreset() {\n"
)
TOOLBAR_METHODS_ANCHOR = "    private boolean isBottomToolbar() {\n"
TOOLBAR_METHODS_NEW = """    // Helium: address-bar button layout presets for old-android.
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

    /** Re-applies the stored preset to the toolbar that is currently on screen. */
    public static void heliumRefreshLayoutPreset() {
        ToolbarPhone toolbar = sHeliumActiveToolbar;
        if (toolbar == null || toolbar.mToolbarButtonsContainer == null) {
            return;
        }
        toolbar.applyHeliumToolbarLayoutPreset();
        toolbar.updateButtonVisibility();
    }

    private void maybeApplyHeliumToolbarLayoutPreset() {
        if (mToolbarButtonsContainer == null || mHeliumEndOrder.isEmpty()) {
            return;
        }
        if (heliumToolbarLayoutPreset() == mHeliumAppliedPreset
                && heliumExtensionsView() == mHeliumPlacedExtensions) {
            return;
        }
        applyHeliumToolbarLayoutPreset();
    }

    private ViewGroup heliumStartButtons() {
        if (mHeliumStartButtons == null) {
            android.widget.LinearLayout container = new android.widget.LinearLayout(getContext());
            container.setOrientation(android.widget.LinearLayout.HORIZONTAL);
            FrameLayout.LayoutParams params =
                    new FrameLayout.LayoutParams(
                            ViewGroup.LayoutParams.WRAP_CONTENT,
                            ViewGroup.LayoutParams.WRAP_CONTENT);
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

    private void addHeliumToolbarView(ViewGroup container, @Nullable View view) {
        if (view == null) {
            return;
        }
        detachHeliumToolbarView(view);
        container.addView(view);
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
        ViewGroup.LayoutParams current = view.getLayoutParams();
        if (current instanceof android.widget.LinearLayout.LayoutParams) {
            return;
        }
        int width = current != null ? current.width : ViewGroup.LayoutParams.WRAP_CONTENT;
        int height = current != null ? current.height : ViewGroup.LayoutParams.WRAP_CONTENT;
        android.widget.LinearLayout.LayoutParams params =
                new android.widget.LinearLayout.LayoutParams(width, height);
        params.gravity = Gravity.CENTER_VERTICAL;
        view.setLayoutParams(params);
    }

    private void heliumUseFrameParams(@Nullable View view) {
        if (view == null) {
            return;
        }
        ViewGroup.LayoutParams current = view.getLayoutParams();
        if (current instanceof FrameLayout.LayoutParams) {
            return;
        }
        int width = current != null ? current.width : ViewGroup.LayoutParams.WRAP_CONTENT;
        int height = current != null ? current.height : ViewGroup.LayoutParams.MATCH_PARENT;
        FrameLayout.LayoutParams params = new FrameLayout.LayoutParams(width, height);
        params.gravity = Gravity.TOP | Gravity.START;
        view.setLayoutParams(params);
    }

    private int heliumExtensionsEndIndex(java.util.ArrayList<View> order) {
        for (int heliumIndex = 0; heliumIndex < order.size(); heliumIndex++) {
            View child = order.get(heliumIndex);
            if (child != null && child.getId() == R.id.signin_button_stub) {
                return heliumIndex;
            }
        }
        return order.size();
    }

    private void applyHeliumToolbarLayoutPreset() {
        if (mToolbarButtonsContainer == null || mHeliumEndOrder.isEmpty()) {
            return;
        }
        sHeliumActiveToolbar = this;
        int preset = heliumToolbarLayoutPreset();
        ViewGroup start = heliumStartButtons();
        View extensions = heliumExtensionsView();

        // Chromium inflates the optional, extensions and signin stubs in place, so the order has
        // to come from the live children. Replaying the stub references captured during inflation
        // would leave the real views behind and break the toolbar's draw translation.
        java.util.ArrayList<View> others = new java.util.ArrayList<>();
        for (int heliumIndex = 0; heliumIndex < mToolbarButtonsContainer.getChildCount();
                heliumIndex++) {
            View child = mToolbarButtonsContainer.getChildAt(heliumIndex);
            if (child == mHeliumTabs || child == mHeliumMenu) {
                continue;
            }
            others.add(child);
        }
        // Keep the extensions action where it already sits; re-adding a parented view throws.
        boolean extensionsInEnd = extensions != null && others.contains(extensions);

        for (int heliumIndex = start.getChildCount() - 1; heliumIndex >= 0; heliumIndex--) {
            View child = start.getChildAt(heliumIndex);
            if (child == mHomeButton || child == mHeliumTabs || child == mHeliumMenu
                    || child == extensions) {
                start.removeViewAt(heliumIndex);
            }
        }
        detachHeliumToolbarView(mHomeButton);
        detachHeliumToolbarView(mHeliumTabs);
        detachHeliumToolbarView(mHeliumMenu);

        java.util.ArrayList<View> startOrder = new java.util.ArrayList<>();
        java.util.ArrayList<View> endOrder = new java.util.ArrayList<>(others);
        if (preset == HELIUM_LAYOUT_REVERSE) {
            endOrder.remove(extensions);
            startOrder.add(mHeliumMenu);
            startOrder.add(extensions);
            endOrder.add(mHeliumTabs);
            endOrder.add(mHomeButton);
        } else {
            if (extensions != null && !extensionsInEnd) {
                endOrder.add(heliumExtensionsEndIndex(endOrder), extensions);
            }
            if (preset == HELIUM_LAYOUT_START) {
                startOrder.add(mHomeButton);
                startOrder.add(mHeliumTabs);
                endOrder.add(mHeliumMenu);
            } else {
                endOrder.add(mHeliumTabs);
                endOrder.add(mHeliumMenu);
            }
        }

        mToolbarButtonsContainer.removeAllViews();
        for (View view : startOrder) {
            heliumUseLinearParams(view);
            addHeliumToolbarView(start, view);
        }
        for (View view : endOrder) {
            heliumUseLinearParams(view);
            addHeliumToolbarView(mToolbarButtonsContainer, view);
        }
        if (preset == HELIUM_LAYOUT_CURRENT && mHomeButton != null) {
            heliumUseFrameParams(mHomeButton);
            FrameLayout.LayoutParams params =
                    (FrameLayout.LayoutParams) mHomeButton.getLayoutParams();
            params.gravity = Gravity.TOP | Gravity.START;
            mHomeButton.setLayoutParams(params);
            addHeliumToolbarView(this, mHomeButton);
        }

        start.setVisibility(mToolbarButtonsContainer.getVisibility());
        mHeliumAppliedPreset = preset;
        mHeliumPlacedExtensions = extensions;
        requestLayout();
        invalidate();
    }

"""

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


def _replace_section(
    text: str,
    start_needle: str,
    end_needle: str,
    new_section: str,
    path: Path,
    include_end: bool = False,
) -> tuple[str, bool]:
    """Replace text[start_needle:end_needle] with new_section, upgrading older versions."""
    start = text.find(start_needle)
    if start < 0:
        return text, False
    end = text.find(end_needle, start)
    if end < 0:
        raise RuntimeError(f"Expected section end in {path}: {start_needle.splitlines()[0]}")
    if include_end:
        end += len(end_needle)
    if text[start:end] == new_section:
        return text, False
    return text[:start] + new_section + text[end:], True


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
    changed = False
    if "ChromePreferenceKeys;" not in text:
        text, updated = _replace_once(
            text, FRAGMENT_IMPORT_OLD, FRAGMENT_IMPORT_NEW, "ChromePreferenceKeys;", path
        )
        changed = changed or updated
    elif "import org.chromium.chrome.browser.toolbar.top.ToolbarPhone;" not in text:
        text = text.replace(FRAGMENT_LEGACY_IMPORT, FRAGMENT_IMPORT_NEW, 1)
        changed = True
    text, updated = _replace_once(
        text, FRAGMENT_CALL_OLD, FRAGMENT_CALL_NEW, FRAGMENT_MARKER, path
    )
    changed = changed or updated
    if FRAGMENT_METHODS_START in text:
        text, updated = _replace_section(
            text, FRAGMENT_METHODS_START, FRAGMENT_METHODS_END, FRAGMENT_METHODS_NEW, path
        )
        changed = changed or updated
    else:
        if text.count(FRAGMENT_METHODS_END) != 1:
            raise RuntimeError(f"Expected one settings methods anchor in {path}")
        text = text.replace(
            FRAGMENT_METHODS_END, FRAGMENT_METHODS_NEW + FRAGMENT_METHODS_END, 1
        )
        changed = True
    if changed:
        path.write_text(text, encoding="utf-8")
    return changed


def patch_toolbar_phone(root: Path) -> bool:
    path = root / TOOLBAR_PHONE
    text = path.read_text(encoding="utf-8")
    changed = False
    replacements = (
        (TOOLBAR_IMPORT_OLD, TOOLBAR_IMPORT_NEW, "import android.widget.FrameLayout;"),
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

    # Older builds called the apply method directly; keep a single entry point.
    stale_call = (
        "            maybeApplyHeliumToolbarLayoutPreset();\n"
        "            applyHeliumToolbarLayoutPreset();\n"
    )
    if stale_call in text:
        text = text.replace(
            stale_call, "            maybeApplyHeliumToolbarLayoutPreset();\n", 1
        )
        changed = True

    if TOOLBAR_FIELDS_START in text:
        text, updated = _replace_section(
            text,
            TOOLBAR_FIELDS_START,
            TOOLBAR_FIELDS_END,
            TOOLBAR_FIELDS_NEW,
            path,
            include_end=True,
        )
        changed = changed or updated
    else:
        text, updated = _replace_once(
            text, TOOLBAR_FIELDS_OLD, TOOLBAR_FIELDS_OLD + TOOLBAR_FIELDS_NEW, "mHeliumStartButtons", path
        )
        changed = changed or updated

    if TOOLBAR_METHODS_START in text:
        text, updated = _replace_section(
            text, TOOLBAR_METHODS_START, TOOLBAR_METHODS_ANCHOR, TOOLBAR_METHODS_NEW, path
        )
        changed = changed or updated
    else:
        if text.count(TOOLBAR_METHODS_ANCHOR) != 1:
            raise RuntimeError(f"Expected one ToolbarPhone method anchor in {path}")
        text = text.replace(TOOLBAR_METHODS_ANCHOR, TOOLBAR_METHODS_NEW + TOOLBAR_METHODS_ANCHOR, 1)
        changed = True

    text, updated = _replace_section(
        text,
        TOOLBAR_DESTROY_START,
        TOOLBAR_DESTROY_END,
        TOOLBAR_DESTROY_NEW,
        path,
        include_end=True,
    )
    changed = changed or updated

    if TOOLBAR_WINDOW_VIS_MARKER not in text:
        text, replaced = TOOLBAR_WINDOW_VIS_PATTERN.subn(TOOLBAR_WINDOW_VIS_NEW, text, count=1)
        if replaced != 1:
            raise RuntimeError(f"Expected one visibility callback in {path}")
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
