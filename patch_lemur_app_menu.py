#!/usr/bin/env python3
from pathlib import Path
import sys


DELEGATE_INTERFACE_REL = (
    "chrome/browser/ui/android/appmenu/java/src/org/chromium/chrome/browser/ui/appmenu/"
    "AppMenuPropertiesDelegate.java"
)
HANDLER_IMPL_REL = (
    "chrome/browser/ui/android/appmenu/internal/java/src/org/chromium/chrome/browser/ui/appmenu/"
    "AppMenuHandlerImpl.java"
)
TABBED_DELEGATE_REL = (
    "chrome/android/java/src/org/chromium/chrome/browser/tabbed_mode/"
    "TabbedAppMenuPropertiesDelegate.java"
)


def patch_app_menu_properties_delegate(src_dir: Path) -> None:
    path = src_dir / DELEGATE_INTERFACE_REL
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    text = path.read_text(encoding="utf-8")
    if "default boolean showCustomAppMenu(" in text:
        return

    anchor = "    /** Returns whether the icon row is showing. */\n    boolean shouldShowIconRow();\n}"
    addition = """    /** Returns whether the icon row is showing. */
    boolean shouldShowIconRow();

    /**
     * Attempts to show a custom Lemur-style bottom popup app menu for page mode.
     */
    default boolean showCustomAppMenu(
            AppMenuHandler appMenuHandler,
            @Nullable View anchorView,
            boolean startDragging,
            boolean isFromBottomBar,
            Runnable showNativeMenuRunnable,
            Runnable onDismissRunnable) {
        return false;
    }

    /** Returns whether the custom app menu is currently showing. */
    default boolean isCustomAppMenuShowing() {
        return false;
    }

    /** Dismisses the custom app menu if it is showing. */
    default void hideCustomAppMenu() {}
}"""

    if anchor not in text:
        raise SystemExit(f"shouldShowIconRow anchor not found in {path}")

    path.write_text(text.replace(anchor, addition, 1), encoding="utf-8")


def patch_app_menu_handler_impl(src_dir: Path) -> None:
    path = src_dir / HANDLER_IMPL_REL
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    text = path.read_text(encoding="utf-8")

    field_marker = "    private boolean mForceNativeMenuOnce;\n"
    field_anchor = "    private boolean mShouldScrollHighlight;\n"
    if field_marker not in text:
        if field_anchor not in text:
            raise SystemExit(f"mShouldScrollHighlight anchor not found in {path}")
        text = text.replace(field_anchor, field_anchor + field_marker, 1)

    show_marker = "mDelegate.showCustomAppMenu("
    show_anchor = """        if (!shouldShowAppMenu() || isAppMenuShowing()) return false;

        TextBubble.dismissBubbles();"""
    show_replacement = """        if (!shouldShowAppMenu() || isAppMenuShowing()) return false;

        TextBubble.dismissBubbles();
        if (!mForceNativeMenuOnce
                && !startDragging
                && mDelegate.showCustomAppMenu(
                        this,
                        anchorView,
                        startDragging,
                        isFromBottomBar,
                        () -> {
                            mForceNativeMenuOnce = true;
                            try {
                                showAppMenu(anchorView, false, isFromBottomBar);
                            } finally {
                                mForceNativeMenuOnce = false;
                            }
                        },
                        () -> {
                            mDelegate.onMenuDismissed();
                            onMenuVisibilityChanged(false);
                        })) {
            clearMenuHighlight();
            RecordUserAction.record("MobileMenuShow");
            mDelegate.onMenuShown();
            onMenuVisibilityChanged(true);
            return true;
        }"""
    if show_marker not in text:
        if show_anchor not in text:
            raise SystemExit(f"showAppMenu anchor not found in {path}")
        text = text.replace(show_anchor, show_replacement, 1)

    old_is_showing = """    @Override
    public boolean isAppMenuShowing() {
        return mAppMenu != null && mAppMenu.isShowing();
    }"""
    new_is_showing = """    @Override
    public boolean isAppMenuShowing() {
        return (mAppMenu != null && mAppMenu.isShowing()) || mDelegate.isCustomAppMenuShowing();
    }"""
    if "mDelegate.isCustomAppMenuShowing()" not in text:
        if old_is_showing not in text:
            raise SystemExit(f"isAppMenuShowing anchor not found in {path}")
        text = text.replace(old_is_showing, new_is_showing, 1)

    old_hide = """    @Override
    public void hideAppMenu() {
        if (mAppMenu != null && mAppMenu.isShowing()) {
            mAppMenu.dismiss();
        }
    }"""
    new_hide = """    @Override
    public void hideAppMenu() {
        if (mAppMenu != null && mAppMenu.isShowing()) {
            mAppMenu.dismiss();
        }
        mDelegate.hideCustomAppMenu();
    }"""
    if "mDelegate.hideCustomAppMenu();" not in text:
        if old_hide not in text:
            raise SystemExit(f"hideAppMenu anchor not found in {path}")
        text = text.replace(old_hide, new_hide, 1)

    path.write_text(text, encoding="utf-8")


TABBED_IMPORTS = [
    "import android.app.Activity;\n",
    "import android.app.Dialog;\n",
    "import android.content.res.ColorStateList;\n",
    "import android.content.res.Configuration;\n",
    "import android.graphics.Color;\n",
    "import android.graphics.Typeface;\n",
    "import android.graphics.drawable.ColorDrawable;\n",
    "import android.graphics.drawable.GradientDrawable;\n",
    "import android.graphics.drawable.RippleDrawable;\n",
    "import android.text.TextUtils;\n",
    "import android.util.TypedValue;\n",
    "import android.view.Gravity;\n",
    "import android.view.ViewGroup;\n",
    "import android.view.Window;\n",
    "import android.view.WindowManager;\n",
    "import android.widget.FrameLayout;\n",
    "import android.widget.GridLayout;\n",
    "import android.widget.ImageView;\n",
    "import android.widget.LinearLayout;\n",
    "import android.widget.ScrollView;\n",
    "import android.widget.TextView;\n",
    "import org.chromium.chrome.browser.night_mode.NightModeUtils;\n",
    "import org.chromium.chrome.browser.night_mode.ThemeType;\n",
    "import org.chromium.chrome.browser.night_mode.WebContentsDarkModeController;\n",
    "import org.chromium.chrome.browser.preferences.ChromePreferenceKeys;\n",
    "import org.chromium.chrome.browser.preferences.ChromeSharedPreferences;\n",
    "import org.chromium.chrome.browser.toolbar.ToolbarPositionController.ToolbarPositionAndSource;\n",
    "import org.chromium.chrome.browser.toolbar.settings.AddressBarPreference;\n",
]

LEMUR_MENU_METHODS = """    // Helium: Lemur Browser-style rounded bottom popup menu panel.
    private @Nullable Dialog mCustomAppMenuDialog;
    private boolean mSuppressCustomDismissCallback;

    @Override
    public boolean isCustomAppMenuShowing() {
        return mCustomAppMenuDialog != null && mCustomAppMenuDialog.isShowing();
    }

    @Override
    public void hideCustomAppMenu() {
        if (mCustomAppMenuDialog != null) {
            Dialog dialog = mCustomAppMenuDialog;
            mCustomAppMenuDialog = null;
            if (dialog.isShowing()) {
                dialog.dismiss();
            }
        }
    }

    @Override
    public boolean showCustomAppMenu(
            AppMenuHandler appMenuHandler,
            @Nullable View anchorView,
            boolean startDragging,
            boolean isFromBottomBar,
            Runnable showNativeMenuRunnable,
            Runnable onDismissRunnable) {
        if (getMenuGroup() != MenuGroup.PAGE_MENU) {
            return false;
        }
        if (!(mContext instanceof Activity)) {
            return false;
        }
        Activity activity = (Activity) mContext;
        if (activity.isFinishing() || activity.isDestroyed()) {
            return false;
        }

        hideCustomAppMenu();

        final boolean isIncognito = isIncognitoShowing();
        final boolean isNight =
                isIncognito
                        || ((mContext.getResources().getConfiguration().uiMode
                                        & Configuration.UI_MODE_NIGHT_MASK)
                                == Configuration.UI_MODE_NIGHT_YES);

        final int panelBgColor =
                isIncognito
                        ? 0xFF202124
                        : (isNight ? 0xFF1E1F23 : 0xFFF7F8FC);
        final int surfaceColor =
                isIncognito
                        ? 0xFF2D2E33
                        : (isNight ? 0xFF2A2C32 : 0xFFFFFFFF);
        final int activeSurfaceColor =
                isNight ? 0x388AB4F8 : 0x1F1A73E8;
        final int textPrimaryColor =
                isNight ? 0xFFE8EAED : 0xFF1F1F1F;
        final int textSecondaryColor =
                isNight ? 0xFF9AA0A6 : 0xFF5F6368;
        final int accentColor =
                isNight ? 0xFF8AB4F8 : 0xFF1A73E8;
        final int dividerColor =
                isNight ? 0x22FFFFFF : 0x16000000;
        final int rippleColor =
                isNight ? 0x33FFFFFF : 0x1F000000;

        final Dialog dialog = new Dialog(activity);
        dialog.requestWindowFeature(Window.FEATURE_NO_TITLE);
        dialog.setCanceledOnTouchOutside(true);
        mCustomAppMenuDialog = dialog;
        mSuppressCustomDismissCallback = false;

        dialog.setOnDismissListener(
                d -> {
                    if (mCustomAppMenuDialog == d) {
                        mCustomAppMenuDialog = null;
                    }
                    if (!mSuppressCustomDismissCallback) {
                        onDismissRunnable.run();
                    }
                });

        FrameLayout outerHost = new FrameLayout(mContext);
        outerHost.setClickable(true);
        outerHost.setOnClickListener(v -> dialog.dismiss());
        int outerPadH = dpToPx(10);
        int outerPadBottom = dpToPx(10);
        int outerPadTop = dpToPx(24);
        outerHost.setPadding(outerPadH, outerPadTop, outerPadH, outerPadBottom);

        LinearLayout card = new LinearLayout(mContext);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setClickable(true);
        GradientDrawable cardBg = new GradientDrawable();
        cardBg.setShape(GradientDrawable.RECTANGLE);
        cardBg.setCornerRadius(dpToPx(24));
        cardBg.setColor(panelBgColor);
        cardBg.setStroke(dpToPx(1), dividerColor);
        card.setBackground(cardBg);
        card.setElevation(dpToPx(12));
        int cardPadH = dpToPx(14);
        card.setPadding(cardPadH, dpToPx(10), cardPadH, dpToPx(12));

        int screenWidthPx = mContext.getResources().getDisplayMetrics().widthPixels;
        int maxCardWidthPx = dpToPx(480);
        int cardWidth =
                screenWidthPx - outerPadH * 2 > maxCardWidthPx
                        ? maxCardWidthPx
                        : ViewGroup.LayoutParams.MATCH_PARENT;
        FrameLayout.LayoutParams cardLp =
                new FrameLayout.LayoutParams(
                        cardWidth,
                        ViewGroup.LayoutParams.WRAP_CONTENT,
                        Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL);
        outerHost.addView(card, cardLp);

        // 1. Top drag handle indicator
        View handleView = new View(mContext);
        GradientDrawable handleBg = new GradientDrawable();
        handleBg.setShape(GradientDrawable.RECTANGLE);
        handleBg.setCornerRadius(dpToPx(2));
        handleBg.setColor(isNight ? 0x44FFFFFF : 0x33000000);
        handleView.setBackground(handleBg);
        LinearLayout.LayoutParams handleLp =
                new LinearLayout.LayoutParams(dpToPx(36), dpToPx(4));
        handleLp.gravity = Gravity.CENTER_HORIZONTAL;
        handleLp.bottomMargin = dpToPx(10);
        card.addView(handleView, handleLp);

        Tab currentTab = mActivityTabProvider.get();
        GURL url = currentTab != null ? currentTab.getUrl() : GURL.emptyGURL();
        final boolean isNativePage =
                UrlUtilities.isChromeScheme(url)
                        || (currentTab != null && currentTab.isNativePage());
        final boolean hasWebContents =
                currentTab != null && !isNativePage && currentTab.getWebContents() != null;
        Profile profile = getProfileFromTabModel();

        // 2. Quick settings pills row (Theme cycle, Dark web toggle, Toolbar position toggle)
        LinearLayout quickBar = new LinearLayout(mContext);
        quickBar.setOrientation(LinearLayout.HORIZONTAL);
        quickBar.setGravity(Gravity.CENTER_VERTICAL);
        LinearLayout.LayoutParams quickBarLp =
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        quickBarLp.bottomMargin = dpToPx(10);

        int currentTheme =
                ChromeSharedPreferences.getInstance()
                        .readInt(
                                ChromePreferenceKeys.UI_THEME_SETTING,
                                ThemeType.SYSTEM_DEFAULT);
        CharSequence themeLabel =
                NightModeUtils.getThemeSettingTitle(mContext, currentTheme);
        boolean isThemeCustom = currentTheme != ThemeType.SYSTEM_DEFAULT;
        View themePill =
                buildQuickSettingPill(
                        R.drawable.ic_brightness_medium_24dp,
                        mContext.getString(R.string.appearance_settings) + ": " + themeLabel,
                        isThemeCustom,
                        true,
                        surfaceColor,
                        activeSurfaceColor,
                        textPrimaryColor,
                        accentColor,
                        rippleColor,
                        v -> {
                            int nextTheme;
                            if (currentTheme == ThemeType.SYSTEM_DEFAULT) {
                                nextTheme = ThemeType.DARK;
                            } else if (currentTheme == ThemeType.DARK) {
                                nextTheme = ThemeType.LIGHT;
                            } else {
                                nextTheme = ThemeType.SYSTEM_DEFAULT;
                            }
                            int actionId =
                                    nextTheme == ThemeType.DARK
                                            ? R.id.appearance_dark_menu_id
                                            : (nextTheme == ThemeType.LIGHT
                                                    ? R.id.appearance_light_menu_id
                                                    : R.id.appearance_system_default_menu_id);
                            triggerMenuAction(dialog, actionId);
                        });
        LinearLayout.LayoutParams pillLp1 =
                new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1.15f);
        pillLp1.setMarginEnd(dpToPx(6));
        quickBar.addView(themePill, pillLp1);

        boolean autoDarkEnabled =
                currentTab != null
                        && !isNativePage
                        && profile != null
                        && WebContentsDarkModeController.isEnabledForUrl(
                                profile, currentTab.getUrl());
        boolean canToggleAutoDark = currentTab != null && !isNativePage && profile != null;
        View autoDarkPill =
                buildQuickSettingPill(
                        R.drawable.ic_brightness_medium_24dp,
                        mContext.getString(R.string.menu_auto_dark_web_contents),
                        autoDarkEnabled,
                        canToggleAutoDark,
                        surfaceColor,
                        activeSurfaceColor,
                        textPrimaryColor,
                        accentColor,
                        rippleColor,
                        v -> triggerMenuAction(dialog, R.id.auto_dark_web_contents_id));
        LinearLayout.LayoutParams pillLp2 =
                new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1.0f);
        pillLp2.setMarginEnd(dpToPx(6));
        quickBar.addView(autoDarkPill, pillLp2);

        boolean isToolbarTop = AddressBarPreference.isToolbarConfiguredToShowOnTop();
        String toolbarPosText = isToolbarTop ? "地址栏: 顶部" : "地址栏: 底部";
        View toolbarPosPill =
                buildQuickSettingPill(
                        R.drawable.ic_settings_tune_24dp,
                        toolbarPosText,
                        !isToolbarTop,
                        true,
                        surfaceColor,
                        activeSurfaceColor,
                        textPrimaryColor,
                        accentColor,
                        rippleColor,
                        v -> {
                            dialog.dismiss();
                            AddressBarPreference.setToolbarPositionAndSource(
                                    isToolbarTop
                                            ? ToolbarPositionAndSource.BOTTOM_SETTINGS
                                            : ToolbarPositionAndSource.TOP_SETTINGS);
                        });
        LinearLayout.LayoutParams pillLp3 =
                new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 0.95f);
        quickBar.addView(toolbarPosPill, pillLp3);

        card.addView(quickBar, quickBarLp);

        // 3. Scrollable 4-column grid of common actions & quick settings
        ScrollView scrollView = new ScrollView(mContext);
        scrollView.setVerticalScrollBarEnabled(false);
        scrollView.setOverScrollMode(View.OVER_SCROLL_IF_CONTENT_SCROLLS);
        int maxGridHeight =
                (int) (mContext.getResources().getDisplayMetrics().heightPixels * 0.52f);
        LinearLayout.LayoutParams scrollLp =
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        card.addView(scrollView, scrollLp);

        GridLayout grid = new GridLayout(mContext);
        grid.setColumnCount(4);
        grid.setUseDefaultMargins(false);
        scrollView.addView(
                grid,
                new FrameLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        boolean isBookmarked = currentTab != null && shouldCheckBookmarkStar(currentTab);
        boolean isDesktopSite =
                hasWebContents
                        && assumeNonNull(currentTab.getWebContents())
                                .getNavigationController()
                                .getUseDesktopUserAgent();
        boolean isReaderMode = isReaderModeShowing(currentTab);
        boolean canFindInPage = shouldShowFindInPageItem(currentTab);
        boolean canTranslate = shouldShowTranslateMenuItem(currentTab);
        boolean canZoom = shouldShowPageZoomItem(currentTab) && !isReaderMode;
        boolean canShare = ShareUtils.shouldEnableShare(currentTab);
        boolean canDownloadPage = shouldEnableDownloadPage(currentTab);
        boolean canAddToHome =
                shouldShowHomeScreenMenuItem(
                        isNativePage,
                        url.getScheme().equals(UrlConstants.FILE_SCHEME),
                        url.getScheme().equals(UrlConstants.CONTENT_SCHEME),
                        isIncognito,
                        url);

        // Row 1: Extensions, Manage Extensions, New Tab, Incognito Tab
        addLemurGridTile(
                grid,
                R.drawable.ic_extension_24dp,
                mContext.getString(R.string.menu_extensions),
                true,
                false,
                surfaceColor,
                activeSurfaceColor,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.extensions_menu_menu_id),
                v -> {
                    triggerMenuAction(dialog, R.id.manage_extensions_menu_id);
                    return true;
                });
        addLemurGridTile(
                grid,
                R.drawable.ic_extension_24dp,
                mContext.getString(R.string.menu_manage_extensions),
                true,
                false,
                surfaceColor,
                activeSurfaceColor,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.manage_extensions_menu_id),
                null);
        addLemurGridTile(
                grid,
                R.drawable.ic_add_box_rounded_corner,
                mContext.getString(R.string.menu_new_tab),
                !IncognitoUtils.isIncognitoModeForced(profile),
                false,
                surfaceColor,
                activeSurfaceColor,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.new_tab_menu_id),
                null);
        addLemurGridTile(
                grid,
                R.drawable.ic_incognito,
                mContext.getString(R.string.menu_new_incognito_tab),
                isIncognitoEnabled() && !isIncognitoReauthShowing(),
                isIncognito,
                surfaceColor,
                activeSurfaceColor,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.new_incognito_tab_menu_id),
                null);

        // Row 2: Bookmark Page, Bookmarks, History, Downloads
        addLemurGridTile(
                grid,
                isBookmarked ? R.drawable.ic_star_filled_24dp : R.drawable.ic_star_24dp,
                mContext.getString(
                        isBookmarked ? R.string.edit_bookmark : R.string.menu_bookmark),
                currentTab != null,
                isBookmarked,
                surfaceColor,
                activeSurfaceColor,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.bookmark_this_page_id),
                null);
        addLemurGridTile(
                grid,
                R.drawable.ic_folder_outline_24dp,
                mContext.getString(R.string.menu_bookmarks),
                true,
                false,
                surfaceColor,
                activeSurfaceColor,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.all_bookmarks_menu_id),
                null);
        addLemurGridTile(
                grid,
                R.drawable.ic_history_24dp,
                mContext.getString(R.string.menu_history),
                !isIncognito,
                false,
                surfaceColor,
                activeSurfaceColor,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.open_history_menu_id),
                null);
        addLemurGridTile(
                grid,
                R.drawable.ic_download_done_24dp,
                mContext.getString(R.string.menu_downloads),
                true,
                false,
                surfaceColor,
                activeSurfaceColor,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.downloads_menu_id),
                null);

        // Row 3: Desktop Site, Find in Page, Translate, Page Zoom
        addLemurGridTile(
                grid,
                R.drawable.ic_desktop_windows,
                mContext.getString(R.string.menu_request_desktop_site),
                hasWebContents,
                isDesktopSite,
                surfaceColor,
                activeSurfaceColor,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.request_desktop_site_id),
                null);
        addLemurGridTile(
                grid,
                R.drawable.ic_find_in_page,
                mContext.getString(R.string.menu_find_in_page),
                canFindInPage,
                false,
                surfaceColor,
                activeSurfaceColor,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.find_in_page_id),
                null);
        addLemurGridTile(
                grid,
                R.drawable.ic_translate,
                mContext.getString(R.string.menu_translate),
                canTranslate,
                false,
                surfaceColor,
                activeSurfaceColor,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.translate_id),
                null);
        addLemurGridTile(
                grid,
                R.drawable.ic_zoom,
                mContext.getString(R.string.page_zoom_menu_title),
                canZoom,
                false,
                surfaceColor,
                activeSurfaceColor,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.page_zoom_id),
                null);

        // Row 4: Share, Clear Data, Site Info / Permissions, Recent Tabs
        addLemurGridTile(
                grid,
                R.drawable.ic_share_white_24dp,
                mContext.getString(R.string.menu_share_page),
                canShare,
                false,
                surfaceColor,
                activeSurfaceColor,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.share_menu_id),
                null);
        addLemurGridTile(
                grid,
                R.drawable.material_ic_delete_24dp,
                mContext.getString(R.string.menu_quick_delete),
                shouldShowQuickDeleteItem(),
                false,
                surfaceColor,
                activeSurfaceColor,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.quick_delete_menu_id),
                null);
        addLemurGridTile(
                grid,
                R.drawable.ic_settings_tune_24dp,
                mContext.getString(R.string.menu_site_controls),
                currentTab != null && !UrlUtilities.isNtpUrl(url),
                false,
                surfaceColor,
                activeSurfaceColor,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.info_menu_id),
                null);
        addLemurGridTile(
                grid,
                R.drawable.devices_black_24dp,
                mContext.getString(R.string.menu_recent_tabs),
                !isIncognito,
                false,
                surfaceColor,
                activeSurfaceColor,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.recent_tabs_menu_id),
                null);

        // Row 5: Reader Mode, Download Page, Add to Home Screen, DevTools
        addLemurGridTile(
                grid,
                R.drawable.ic_mobile_friendly_24dp,
                mContext.getString(
                        isReaderMode
                                ? R.string.hide_reading_mode_text
                                : R.string.show_reading_mode_text),
                mMoreToolsItemBuilder.shouldShowReaderModeItem(currentTab),
                isReaderMode,
                surfaceColor,
                activeSurfaceColor,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.reader_mode_menu_id),
                null);
        addLemurGridTile(
                grid,
                R.drawable.ic_file_download_white_24dp,
                mContext.getString(R.string.menu_download),
                canDownloadPage,
                false,
                surfaceColor,
                activeSurfaceColor,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.offline_page_id),
                null);
        addLemurGridTile(
                grid,
                R.drawable.ic_add_to_home_screen,
                mContext.getString(R.string.menu_install_create_shortcut),
                canAddToHome,
                false,
                surfaceColor,
                activeSurfaceColor,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.universal_install),
                null);
        addLemurGridTile(
                grid,
                R.drawable.ic_more_tools_24dp,
                mContext.getString(R.string.menu_dev_tools),
                hasWebContents,
                false,
                surfaceColor,
                activeSurfaceColor,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.dev_tools),
                null);

        scrollView.post(
                () -> {
                    if (scrollView.getHeight() > maxGridHeight) {
                        LinearLayout.LayoutParams lp =
                                (LinearLayout.LayoutParams) scrollView.getLayoutParams();
                        lp.height = maxGridHeight;
                        scrollView.setLayoutParams(lp);
                    }
                });

        // Divider before bottom action bar
        View bottomDivider = new View(mContext);
        bottomDivider.setBackgroundColor(dividerColor);
        LinearLayout.LayoutParams divLp =
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT, dpToPx(1));
        divLp.topMargin = dpToPx(8);
        divLp.bottomMargin = dpToPx(8);
        card.addView(bottomDivider, divLp);

        // 4. Bottom navigation & settings action bar
        LinearLayout bottomBar = new LinearLayout(mContext);
        bottomBar.setOrientation(LinearLayout.HORIZONTAL);
        bottomBar.setGravity(Gravity.CENTER_VERTICAL);

        boolean canGoBack = currentTab != null && currentTab.canGoBack();
        boolean canGoForward = currentTab != null && currentTab.canGoForward();
        boolean canReload = currentTab != null;
        boolean isLoading = currentTab != null && currentTab.isLoading();

        bottomBar.addView(
                buildBottomBarButton(
                        R.drawable.btn_back,
                        null,
                        mContext.getString(R.string.accessibility_menu_back),
                        canGoBack,
                        false,
                        surfaceColor,
                        textPrimaryColor,
                        textSecondaryColor,
                        rippleColor,
                        v -> triggerMenuAction(dialog, R.id.back_menu_id)),
                new LinearLayout.LayoutParams(0, dpToPx(42), 0.85f));

        bottomBar.addView(
                buildBottomBarButton(
                        R.drawable.btn_forward,
                        null,
                        mContext.getString(R.string.accessibility_menu_forward),
                        canGoForward,
                        false,
                        surfaceColor,
                        textPrimaryColor,
                        textSecondaryColor,
                        rippleColor,
                        v -> triggerMenuAction(dialog, R.id.forward_menu_id)),
                new LinearLayout.LayoutParams(0, dpToPx(42), 0.85f));

        bottomBar.addView(
                buildBottomBarButton(
                        R.drawable.btn_reload_stop,
                        null,
                        mContext.getString(
                                isLoading
                                        ? R.string.accessibility_btn_stop_loading
                                        : R.string.accessibility_btn_refresh),
                        canReload,
                        isLoading,
                        surfaceColor,
                        textPrimaryColor,
                        textSecondaryColor,
                        rippleColor,
                        v -> triggerMenuAction(dialog, R.id.reload_menu_id)),
                new LinearLayout.LayoutParams(0, dpToPx(42), 0.85f));

        bottomBar.addView(
                buildBottomBarButton(
                        R.drawable.settings_cog,
                        mContext.getString(R.string.menu_settings),
                        mContext.getString(R.string.menu_settings),
                        true,
                        false,
                        surfaceColor,
                        textPrimaryColor,
                        textSecondaryColor,
                        rippleColor,
                        v -> triggerMenuAction(dialog, R.id.preferences_id)),
                new LinearLayout.LayoutParams(0, dpToPx(42), 1.35f));

        bottomBar.addView(
                buildBottomBarButton(
                        R.drawable.ic_more_tools_24dp,
                        "原菜单",
                        "原菜单",
                        true,
                        false,
                        surfaceColor,
                        textPrimaryColor,
                        textSecondaryColor,
                        rippleColor,
                        v -> {
                            mSuppressCustomDismissCallback = true;
                            dialog.dismiss();
                            onDismissRunnable.run();
                            showNativeMenuRunnable.run();
                        }),
                new LinearLayout.LayoutParams(0, dpToPx(42), 1.35f));

        card.addView(
                bottomBar,
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        dialog.setContentView(
                outerHost,
                new ViewGroup.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.MATCH_PARENT));

        Window window = dialog.getWindow();
        if (window != null) {
            window.setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));
            window.setLayout(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.MATCH_PARENT);
            window.setGravity(Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL);
            WindowManager.LayoutParams wlp = window.getAttributes();
            wlp.dimAmount = 0.36f;
            window.addFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND);
            window.setAttributes(wlp);
        }

        dialog.show();
        return true;
    }

    private void triggerMenuAction(Dialog dialog, int itemId) {
        if (dialog.isShowing()) {
            dialog.dismiss();
        }
        mAppMenuDelegate.onOptionsItemSelected(itemId, null, null);
    }

    private View buildQuickSettingPill(
            int iconRes,
            String text,
            boolean isActive,
            boolean isEnabled,
            int surfaceColor,
            int activeSurfaceColor,
            int textPrimaryColor,
            int accentColor,
            int rippleColor,
            View.OnClickListener onClickListener) {
        LinearLayout pill = new LinearLayout(mContext);
        pill.setOrientation(LinearLayout.HORIZONTAL);
        pill.setGravity(Gravity.CENTER);
        int padH = dpToPx(8);
        int padV = dpToPx(8);
        pill.setPadding(padH, padV, padH, padV);

        GradientDrawable shape = new GradientDrawable();
        shape.setShape(GradientDrawable.RECTANGLE);
        shape.setCornerRadius(dpToPx(12));
        shape.setColor(isActive ? activeSurfaceColor : surfaceColor);
        if (isActive) {
            shape.setStroke(dpToPx(1), accentColor);
        }
        pill.setBackground(
                new RippleDrawable(ColorStateList.valueOf(rippleColor), shape, null));

        ImageView iconView = new ImageView(mContext);
        Drawable icon = AppCompatResources.getDrawable(mContext, iconRes);
        if (icon != null) {
            icon = icon.mutate();
            DrawableCompat.setTint(icon, isActive ? accentColor : textPrimaryColor);
            iconView.setImageDrawable(icon);
        }
        LinearLayout.LayoutParams iconLp =
                new LinearLayout.LayoutParams(dpToPx(16), dpToPx(16));
        iconLp.setMarginEnd(dpToPx(4));
        pill.addView(iconView, iconLp);

        TextView labelView = new TextView(mContext);
        labelView.setText(text);
        labelView.setTextSize(TypedValue.COMPLEX_UNIT_SP, 11.5f);
        labelView.setSingleLine(true);
        labelView.setEllipsize(TextUtils.TruncateAt.END);
        labelView.setTextColor(isActive ? accentColor : textPrimaryColor);
        if (isActive) {
            labelView.setTypeface(Typeface.DEFAULT_BOLD);
        }
        pill.addView(
                labelView,
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.WRAP_CONTENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT));

        pill.setEnabled(isEnabled);
        pill.setAlpha(isEnabled ? 1.0f : 0.42f);
        if (isEnabled) {
            pill.setOnClickListener(onClickListener);
        }
        return pill;
    }

    private void addLemurGridTile(
            GridLayout grid,
            int iconRes,
            String title,
            boolean isEnabled,
            boolean isActive,
            int surfaceColor,
            int activeSurfaceColor,
            int textPrimaryColor,
            int textSecondaryColor,
            int accentColor,
            int rippleColor,
            View.OnClickListener clickListener,
            View.@Nullable OnLongClickListener longClickListener) {
        LinearLayout cell = new LinearLayout(mContext);
        cell.setOrientation(LinearLayout.VERTICAL);
        cell.setGravity(Gravity.CENTER_HORIZONTAL);
        int cellPadH = dpToPx(4);
        int cellPadV = dpToPx(6);
        cell.setPadding(cellPadH, cellPadV, cellPadH, cellPadV);

        FrameLayout iconBox = new FrameLayout(mContext);
        GradientDrawable boxBg = new GradientDrawable();
        boxBg.setShape(GradientDrawable.RECTANGLE);
        boxBg.setCornerRadius(dpToPx(15));
        boxBg.setColor(isActive ? activeSurfaceColor : surfaceColor);
        if (isActive) {
            boxBg.setStroke(dpToPx(1), accentColor);
        }
        iconBox.setBackground(
                new RippleDrawable(ColorStateList.valueOf(rippleColor), boxBg, null));

        ImageView iconView = new ImageView(mContext);
        Drawable drawable = AppCompatResources.getDrawable(mContext, iconRes);
        if (drawable != null) {
            drawable = drawable.mutate();
            DrawableCompat.setTint(drawable, isActive ? accentColor : textPrimaryColor);
            iconView.setImageDrawable(drawable);
        }
        FrameLayout.LayoutParams iconLp =
                new FrameLayout.LayoutParams(dpToPx(24), dpToPx(24), Gravity.CENTER);
        iconBox.addView(iconView, iconLp);

        LinearLayout.LayoutParams boxLp =
                new LinearLayout.LayoutParams(dpToPx(48), dpToPx(48));
        boxLp.bottomMargin = dpToPx(5);
        cell.addView(iconBox, boxLp);

        TextView textView = new TextView(mContext);
        textView.setText(title);
        textView.setTextSize(TypedValue.COMPLEX_UNIT_SP, 11.5f);
        textView.setGravity(Gravity.CENTER);
        textView.setSingleLine(true);
        textView.setEllipsize(TextUtils.TruncateAt.END);
        textView.setTextColor(
                isActive ? accentColor : (isEnabled ? textPrimaryColor : textSecondaryColor));
        if (isActive) {
            textView.setTypeface(Typeface.DEFAULT_BOLD);
        }
        cell.addView(
                textView,
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT));

        cell.setEnabled(isEnabled);
        cell.setAlpha(isEnabled ? 1.0f : 0.40f);
        if (isEnabled) {
            cell.setOnClickListener(clickListener);
            iconBox.setOnClickListener(clickListener);
            if (longClickListener != null) {
                cell.setOnLongClickListener(longClickListener);
                iconBox.setOnLongClickListener(longClickListener);
            }
        } else {
            iconBox.setClickable(false);
        }

        GridLayout.LayoutParams gridLp =
                new GridLayout.LayoutParams(
                        GridLayout.spec(GridLayout.UNDEFINED, 1f),
                        GridLayout.spec(GridLayout.UNDEFINED, 1f));
        gridLp.width = 0;
        gridLp.height = ViewGroup.LayoutParams.WRAP_CONTENT;
        grid.addView(cell, gridLp);
    }

    private View buildBottomBarButton(
            int iconRes,
            @Nullable String label,
            String contentDesc,
            boolean isEnabled,
            boolean useStopLevel,
            int surfaceColor,
            int textPrimaryColor,
            int textSecondaryColor,
            int rippleColor,
            View.OnClickListener clickListener) {
        LinearLayout btn = new LinearLayout(mContext);
        btn.setOrientation(LinearLayout.HORIZONTAL);
        btn.setGravity(Gravity.CENTER);
        btn.setContentDescription(contentDesc);
        int marginH = dpToPx(3);
        int padH = dpToPx(8);
        btn.setPadding(padH, 0, padH, 0);

        GradientDrawable bg = new GradientDrawable();
        bg.setShape(GradientDrawable.RECTANGLE);
        bg.setCornerRadius(dpToPx(12));
        bg.setColor(label != null ? surfaceColor : Color.TRANSPARENT);
        btn.setBackground(
                new RippleDrawable(ColorStateList.valueOf(rippleColor), bg, null));

        ImageView iconView = new ImageView(mContext);
        Drawable drawable = AppCompatResources.getDrawable(mContext, iconRes);
        if (drawable != null) {
            drawable = drawable.mutate();
            if (iconRes == R.drawable.btn_reload_stop) {
                Resources resources = mContext.getResources();
                drawable.setLevel(
                        useStopLevel
                                ? resources.getInteger(R.integer.reload_button_level_stop)
                                : resources.getInteger(R.integer.reload_button_level_reload));
            }
            DrawableCompat.setTint(
                    drawable, isEnabled ? textPrimaryColor : textSecondaryColor);
            iconView.setImageDrawable(drawable);
        }
        LinearLayout.LayoutParams iconLp =
                new LinearLayout.LayoutParams(dpToPx(20), dpToPx(20));
        if (label != null) {
            iconLp.setMarginEnd(dpToPx(5));
        }
        btn.addView(iconView, iconLp);

        if (label != null) {
            TextView tv = new TextView(mContext);
            tv.setText(label);
            tv.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12f);
            tv.setSingleLine(true);
            tv.setEllipsize(TextUtils.TruncateAt.END);
            tv.setTextColor(isEnabled ? textPrimaryColor : textSecondaryColor);
            tv.setTypeface(Typeface.DEFAULT_BOLD);
            btn.addView(
                    tv,
                    new LinearLayout.LayoutParams(
                            ViewGroup.LayoutParams.WRAP_CONTENT,
                            ViewGroup.LayoutParams.WRAP_CONTENT));
        }

        btn.setEnabled(isEnabled);
        btn.setAlpha(isEnabled ? 1.0f : 0.38f);
        if (isEnabled) {
            btn.setOnClickListener(clickListener);
        }
        return btn;
    }

    private int dpToPx(float dp) {
        return Math.round(
                TypedValue.applyDimension(
                        TypedValue.COMPLEX_UNIT_DIP,
                        dp,
                        mContext.getResources().getDisplayMetrics()));
    }

"""


def patch_tabbed_app_menu_delegate(src_dir: Path) -> None:
    path = src_dir / TABBED_DELEGATE_REL
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    text = path.read_text(encoding="utf-8")

    import_anchor = "import android.view.View;\n"
    if import_anchor not in text:
        raise SystemExit(f"import android.view.View anchor not found in {path}")
    missing_imports = "".join(imp for imp in TABBED_IMPORTS if imp not in text)
    if missing_imports:
        text = text.replace(import_anchor, import_anchor + missing_imports, 1)

    destroy_anchor = "    public void destroy() {\n        super.destroy();\n"
    destroy_replacement = (
        "    public void destroy() {\n"
        "        hideCustomAppMenu();\n"
        "        super.destroy();\n"
    )
    if "hideCustomAppMenu();" not in text:
        if destroy_anchor not in text:
            raise SystemExit(f"destroy() anchor not found in {path}")
        text = text.replace(destroy_anchor, destroy_replacement, 1)

    start_marker = "    // Helium: Lemur Browser-style rounded bottom popup menu panel.\n"
    method_anchor = "    private ListItem buildSettingsItem() {\n"
    if start_marker in text:
        start_idx = text.find(start_marker)
        end_idx = text.find(method_anchor, start_idx)
        if end_idx == -1:
            raise SystemExit(f"buildSettingsItem anchor not found after Lemur marker in {path}")
        text = text[:start_idx] + LEMUR_MENU_METHODS + text[end_idx:]
    else:
        if method_anchor not in text:
            raise SystemExit(f"buildSettingsItem anchor not found in {path}")
        text = text.replace(method_anchor, LEMUR_MENU_METHODS + method_anchor, 1)

    path.write_text(text, encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: patch_lemur_app_menu.py <chromium-src-dir>")

    src_dir = Path(sys.argv[1]).resolve()
    patch_app_menu_properties_delegate(src_dir)
    patch_app_menu_handler_impl(src_dir)
    patch_tabbed_app_menu_delegate(src_dir)


if __name__ == "__main__":
    main()
