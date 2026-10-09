#!/usr/bin/env python3
from pathlib import Path
import sys


MENU_BUTTON_REL = (
    "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/menu_button/"
    "MenuButton.java"
)
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
EXT_TOOLBAR_COORD_REL = (
    "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/"
    "ExtensionsToolbarCoordinator.java"
)
EXT_TOOLBAR_COORD_IMPL_REL = (
    "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/"
    "ExtensionsToolbarCoordinatorImpl.java"
)
EXT_MENU_COORD_REL = (
    "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/"
    "ExtensionsMenuCoordinator.java"
)
EXT_MENU_MEDIATOR_REL = (
    "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/"
    "ExtensionsMenuMediator.java"
)


def patch_menu_button(src_dir: Path) -> None:
    """Replaces the three-dot toolbar icon with Lemur's three-horizontal-lines icon (☰)."""
    path = src_dir / MENU_BUTTON_REL
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    text = path.read_text(encoding="utf-8")

    inflate_anchor = """        mMenuImageButton = findViewById(R.id.menu_button);
        mUpdateBadgeView = findViewById(R.id.menu_badge);
        mOriginalBackground = getBackground();"""
    inflate_replacement = """        mMenuImageButton = findViewById(R.id.menu_button);
        mMenuImageButton.setImageDrawable(createHeliumThreeLinesMenuDrawable());
        mUpdateBadgeView = findViewById(R.id.menu_badge);
        mOriginalBackground = getBackground();"""
    if "createHeliumThreeLinesMenuDrawable()" not in text:
        if inflate_anchor not in text:
            raise SystemExit(f"onFinishInflate anchor not found in {path}")
        text = text.replace(inflate_anchor, inflate_replacement, 1)

    helper_marker = "    private BitmapDrawable createHeliumThreeLinesMenuDrawable() {\n"
    helper_anchor = "    void setOriginalBackgroundForTesting(Drawable background) {\n"
    helper_method = """    private BitmapDrawable createHeliumThreeLinesMenuDrawable() {
        float density = getResources().getDisplayMetrics().density;
        int sizePx = Math.max(24, Math.round(24f * density));
        android.graphics.Bitmap bitmap =
                android.graphics.Bitmap.createBitmap(
                        sizePx, sizePx, android.graphics.Bitmap.Config.ARGB_8888);
        Canvas canvas = new Canvas(bitmap);
        android.graphics.Paint paint =
                new android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG);
        paint.setColor(0xFFFFFFFF);
        paint.setStyle(android.graphics.Paint.Style.STROKE);
        paint.setStrokeWidth(2.0f * density);
        paint.setStrokeCap(android.graphics.Paint.Cap.ROUND);
        float xStart = 4.2f * density;
        float xEnd = 19.8f * density;
        canvas.drawLine(xStart, 6.5f * density, xEnd, 6.5f * density, paint);
        canvas.drawLine(xStart, 12.0f * density, xEnd, 12.0f * density, paint);
        canvas.drawLine(xStart, 17.5f * density, xEnd, 17.5f * density, paint);
        return new BitmapDrawable(getResources(), bitmap);
    }

"""
    if helper_marker in text:
        start_idx = text.find(helper_marker)
        end_idx = text.find(helper_anchor, start_idx)
        if end_idx == -1:
            raise SystemExit(f"setOriginalBackgroundForTesting anchor not found in {path}")
        text = text[:start_idx] + helper_method + text[end_idx:]
    else:
        if helper_anchor not in text:
            raise SystemExit(f"setOriginalBackgroundForTesting anchor not found in {path}")
        text = text.replace(helper_anchor, helper_method + helper_anchor, 1)

    path.write_text(text, encoding="utf-8")


def patch_extensions_toolbar_coordinator(src_dir: Path) -> None:
    path = src_dir / EXT_TOOLBAR_COORD_REL
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    text = path.read_text(encoding="utf-8")

    # Migrate older @Nullable qualified-type syntax if already patched
    text = text.replace(
        "@Nullable org.chromium.content_public.browser.WebContents",
        "org.chromium.content_public.browser.@Nullable WebContents",
    )
    text = text.replace(
        "@Nullable android.graphics.Bitmap",
        "android.graphics.@Nullable Bitmap",
    )
    text = text.replace(
        "@Nullable android.view.View",
        "android.view.@Nullable View",
    )

    anchor = (
        "    /** Returns the {@link ToolbarWidthConsumer} for the action list container. */\n"
        "    ToolbarWidthConsumer getActionListWidthConsumer();\n"
    )
    addition = """    /** Returns the {@link ToolbarWidthConsumer} for the action list container. */
    ToolbarWidthConsumer getActionListWidthConsumer();

    /** Per-Activity opener for the Lemur-style extensions & common tools bottom sheet. */
    java.util.Map<android.app.Activity, org.chromium.base.Callback<android.view.@Nullable View>>
            CUSTOM_EXTENSIONS_MENU_OPENERS =
                    java.util.Collections.synchronizedMap(new java.util.WeakHashMap<>());

    /** Returns all enabled extension action IDs (pinned first, then unpinned). */
    default String[] getAllExtensionActionIds() {
        return new String[0];
    }

    /** Returns the display title/name for the given extension action on the given WebContents. */
    default @Nullable String getExtensionActionTitle(
            String actionId,
            org.chromium.content_public.browser.@Nullable WebContents webContents) {
        return null;
    }

    /** Returns the rendered Bitmap icon (including badge) for the given extension action. */
    default android.graphics.@Nullable Bitmap getExtensionActionIcon(
            String actionId,
            org.chromium.content_public.browser.@Nullable WebContents webContents) {
        return null;
    }

    /** Executes the primary action (or opens the popup) for an extension from the custom AppMenu. */
    default void executeExtensionActionFromAppMenu(
            String actionId, android.view.@Nullable View fallbackAnchorView) {}

    /** Shows the context menu for an extension from the custom AppMenu. */
    default void showExtensionContextMenuFromAppMenu(
            String actionId, android.view.@Nullable View fallbackAnchorView) {}
}"""

    if anchor not in text:
        raise SystemExit(f"getActionListWidthConsumer anchor not found in {path}")

    start_idx = text.find(anchor)
    text = text[:start_idx] + addition + "\n"
    path.write_text(text, encoding="utf-8")


def patch_extensions_toolbar_coordinator_impl(src_dir: Path) -> None:
    path = src_dir / EXT_TOOLBAR_COORD_IMPL_REL
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    text = path.read_text(encoding="utf-8")

    # Migrate older @Nullable qualified-type syntax if already patched
    text = text.replace(
        "@Nullable org.chromium.content_public.browser.WebContents",
        "org.chromium.content_public.browser.@Nullable WebContents",
    )
    text = text.replace(
        "@Nullable android.graphics.Bitmap",
        "android.graphics.@Nullable Bitmap",
    )
    text = text.replace(
        "@Nullable android.view.View",
        "android.view.@Nullable View",
    )

    # Always keep the 4-small-squares extensions button visible on phone/tablet toolbars
    old_should_show = """    private boolean shouldShowMenuIcon() {
        return mExtensionsMenuCoordinator.isExtensionsMenuOpen()
                || mShowExtensionsMenuPending
                || (mCanShowMenuIcon && isMenuButtonPinned());
    }"""
    new_should_show = """    private boolean shouldShowMenuIcon() {
        return !mIsWebApp && mCanShowMenuIcon;
    }"""
    if old_should_show in text:
        text = text.replace(old_should_show, new_should_show, 1)

    old_show_ext_menu = """    @Override
    public void showExtensionsMenu() {
        mShowExtensionsMenuPending = true;
        updateMenuIconVisibility();

        ListMenuButton extensionsMenuButton = mContainer.findViewById(R.id.extensions_menu_button);
        assert extensionsMenuButton != null;

        // Post to click after the layout pass.
        extensionsMenuButton.post(
                () -> {
                    extensionsMenuButton.performClick();
                });
    }"""
    new_show_ext_menu = """    @Override
    public void showExtensionsMenu() {
        Activity activity = mWindowAndroid.getActivity().get();
        org.chromium.base.Callback<@Nullable View> customOpener =
                activity != null ? CUSTOM_EXTENSIONS_MENU_OPENERS.get(activity) : null;
        if (customOpener != null) {
            View btn = mContainer != null ? mContainer.findViewById(R.id.extensions_menu_button) : null;
            customOpener.onResult(btn);
            return;
        }
        mShowExtensionsMenuPending = true;
        updateMenuIconVisibility();

        ListMenuButton extensionsMenuButton = mContainer.findViewById(R.id.extensions_menu_button);
        assert extensionsMenuButton != null;

        // Post to click after the layout pass.
        extensionsMenuButton.post(
                () -> {
                    extensionsMenuButton.performClick();
                });
    }"""
    if old_show_ext_menu in text:
        text = text.replace(old_show_ext_menu, new_show_ext_menu, 1)

    if "public String[] getAllExtensionActionIds()" in text:
        path.write_text(text, encoding="utf-8")
        return

    anchor = """    @Override
    public ToolbarWidthConsumer getActionListWidthConsumer() {
        return mActionListWidthConsumer;
    }"""

    addition = """    @Override
    public ToolbarWidthConsumer getActionListWidthConsumer() {
        return mActionListWidthConsumer;
    }

    @Override
    public String[] getAllExtensionActionIds() {
        if (mIsDestroyed || mExtensionsToolbarBridge == null) {
            return new String[0];
        }
        String[] pinned = mExtensionsToolbarBridge.getPinnedActionIds();
        String[] all = mExtensionsToolbarBridge.getAllActionIds();
        if (all == null || all.length == 0) {
            return new String[0];
        }
        java.util.LinkedHashSet<String> ordered = new java.util.LinkedHashSet<>();
        if (pinned != null) {
            for (String id : pinned) {
                if (id != null && !id.isEmpty()) {
                    ordered.add(id);
                }
            }
        }
        for (String id : all) {
            if (id != null && !id.isEmpty()) {
                ordered.add(id);
            }
        }
        return ordered.toArray(new String[0]);
    }

    @Override
    public @Nullable String getExtensionActionTitle(
            String actionId,
            org.chromium.content_public.browser.@Nullable WebContents webContents) {
        if (mIsDestroyed || mExtensionsToolbarBridge == null) {
            return null;
        }
        org.chromium.chrome.browser.ui.extensions.ExtensionAction action =
                mExtensionsToolbarBridge.getAction(actionId, webContents);
        if (action == null) {
            return null;
        }
        String name = action.getName();
        if (name != null && !name.trim().isEmpty()) {
            return name.trim();
        }
        String title = action.getTitle();
        if (title != null && !title.trim().isEmpty()) {
            int newlineIdx = title.indexOf('\\n');
            return (newlineIdx >= 0 ? title.substring(0, newlineIdx) : title).trim();
        }
        return actionId;
    }

    @Override
    public android.graphics.@Nullable Bitmap getExtensionActionIcon(
            String actionId,
            org.chromium.content_public.browser.@Nullable WebContents webContents) {
        if (mIsDestroyed || mExtensionsToolbarBridge == null || mContainer == null) {
            return null;
        }
        return ExtensionActionIconUtil.getIcon(
                mContainer.getContext(),
                mWindowAndroid,
                mExtensionsToolbarBridge,
                actionId,
                webContents);
    }

    @Override
    public void executeExtensionActionFromAppMenu(
            String actionId, @Nullable View fallbackAnchorView) {
        if (mIsDestroyed || mExtensionsMenuCoordinator == null) {
            return;
        }
        mExtensionsMenuCoordinator.executeActionFromAppMenu(actionId, fallbackAnchorView);
    }

    @Override
    public void showExtensionContextMenuFromAppMenu(
            String actionId, @Nullable View fallbackAnchorView) {
        if (mIsDestroyed || mExtensionsMenuCoordinator == null) {
            return;
        }
        mExtensionsMenuCoordinator.showContextMenuFromAppMenu(actionId, fallbackAnchorView);
    }"""

    if anchor not in text:
        raise SystemExit(f"getActionListWidthConsumer anchor not found in {path}")

    path.write_text(text.replace(anchor, addition, 1), encoding="utf-8")


def patch_extensions_menu_coordinator(src_dir: Path) -> None:
    path = src_dir / EXT_MENU_COORD_REL
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    text = path.read_text(encoding="utf-8")

    field_marker = "    private boolean mSuppressNextMenuShow;\n"
    field_anchor = "    @Nullable @VisibleForTesting ExtensionsMenuMediator mMediator;\n"
    if field_marker not in text:
        if field_anchor not in text:
            raise SystemExit(f"mMediator anchor not found in {path}")
        text = text.replace(
            field_anchor,
            field_anchor
            + field_marker
            + "    private @Nullable ListMenuButton mAppMenuContextMenuButton;\n",
            1,
        )

    # Set 4-small-squares icon on mExtensionsMenuButton and open Lemur Extensions sheet on click
    old_click_v1 = """        mExtensionsMenuButton.setOnClickListener(
                (view) -> {
                    if (mMediator != null) {
                        mExtensionsMenuButton.dismiss();
                        destroyMediator();
                        return;
                    }"""
    old_click_v2 = """        mExtensionsMenuButton.setOnClickListener(
                (view) -> {
                    if (mMediator != null) {
                        boolean wasOpen = mIsMenuOpen;
                        mExtensionsMenuButton.dismiss();
                        destroyMediator();
                        if (wasOpen) {
                            return;
                        }
                    }"""
    old_click_vanilla = """        mExtensionsMenuButton.setOnClickListener(
                (view) -> {"""
    new_click_block = """        mExtensionsMenuButton.setImageDrawable(createHeliumFourSquaresDrawable());
        mExtensionsMenuButton.setOnClickListener(
                (view) -> {
                    Activity activity = mWindowAndroid.getActivity().get();
                    Callback<@Nullable View> customOpener =
                            activity != null
                                    ? ExtensionsToolbarCoordinator.CUSTOM_EXTENSIONS_MENU_OPENERS
                                            .get(activity)
                                    : null;
                    if (customOpener != null) {
                        customOpener.onResult(mExtensionsMenuButton);
                        return;
                    }
                    if (mMediator != null) {
                        boolean wasOpen = mIsMenuOpen;
                        mExtensionsMenuButton.dismiss();
                        destroyMediator();
                        if (wasOpen) {
                            return;
                        }
                    }"""
    if "createHeliumFourSquaresDrawable()" not in text:
        if old_click_v2 in text:
            text = text.replace(old_click_v2, new_click_block, 1)
        elif old_click_v1 in text:
            text = text.replace(old_click_v1, new_click_block, 1)
        elif old_click_vanilla in text:
            text = text.replace(old_click_vanilla, new_click_block, 1)
        else:
            raise SystemExit(f"mExtensionsMenuButton.setOnClickListener anchor not found in {path}")

    # Keep the 4-small-squares icon in updateButtonState instead of overwriting with puzzle icon
    old_update_icon = """        if (state.getIcon() != null) {
            mExtensionsMenuButton.setImageBitmap(state.getIcon());
        } else {
            // Fallback just in case.
            int iconResId = R.drawable.chrome_extension;
            mExtensionsMenuButton.setImageResource(iconResId);
        }"""
    new_update_icon = """        mExtensionsMenuButton.setImageDrawable(createHeliumFourSquaresDrawable());"""
    if old_update_icon in text:
        text = text.replace(old_update_icon, new_update_icon, 1)

    old_on_ready = """                        /* onReady= */ () -> {
                            mExtensionsMenuButton.showMenu();
                        });"""
    new_on_ready = """                        /* onReady= */ () -> {
                            if (mSuppressNextMenuShow) {
                                mSuppressNextMenuShow = false;
                                return;
                            }
                            mExtensionsMenuButton.showMenu();
                        });"""
    if "if (mSuppressNextMenuShow)" not in text:
        if old_on_ready not in text:
            raise SystemExit(f"onReady anchor not found in {path}")
        text = text.replace(old_on_ready, new_on_ready, 1)

    helper_marker = "    public void executeActionFromAppMenu("
    helper_anchor = "    @VisibleForTesting\n    View getContentView() {"
    helper_methods = """    public void executeActionFromAppMenu(
            String actionId, @Nullable View fallbackAnchorView) {
        if (mMediator == null) {
            mSuppressNextMenuShow = true;
            createMediator();
            mSuppressNextMenuShow = false;
        }
        if (mMediator != null) {
            View anchorView = resolveAppMenuPopupAnchor(fallbackAnchorView);
            ListMenuButton contextButton = ensureAppMenuContextMenuButton();
            mMediator.executeActionFromAppMenu(actionId, anchorView, contextButton);
        }
    }

    public void showContextMenuFromAppMenu(
            String actionId, @Nullable View fallbackAnchorView) {
        if (mMediator == null) {
            mSuppressNextMenuShow = true;
            createMediator();
            mSuppressNextMenuShow = false;
        }
        if (mMediator != null) {
            ListMenuButton contextButton = ensureAppMenuContextMenuButton();
            if (contextButton != null) {
                mMediator.showContextMenuFromAppMenu(actionId, contextButton);
            }
        }
    }

    private android.graphics.drawable.BitmapDrawable createHeliumFourSquaresDrawable() {
        float density = mContext.getResources().getDisplayMetrics().density;
        int sizePx = Math.max(24, Math.round(24f * density));
        android.graphics.Bitmap bitmap =
                android.graphics.Bitmap.createBitmap(
                        sizePx, sizePx, android.graphics.Bitmap.Config.ARGB_8888);
        android.graphics.Canvas canvas = new android.graphics.Canvas(bitmap);
        android.graphics.Paint paint =
                new android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG);
        paint.setColor(0xFFFFFFFF);
        paint.setStyle(android.graphics.Paint.Style.STROKE);
        paint.setStrokeWidth(1.9f * density);
        paint.setStrokeJoin(android.graphics.Paint.Join.ROUND);
        paint.setStrokeCap(android.graphics.Paint.Cap.ROUND);
        float r = 2.0f * density;
        android.graphics.RectF rect = new android.graphics.RectF();
        rect.set(4.0f * density, 4.0f * density, 10.6f * density, 10.6f * density);
        canvas.drawRoundRect(rect, r, r, paint);
        rect.set(13.4f * density, 4.0f * density, 20.0f * density, 10.6f * density);
        canvas.drawRoundRect(rect, r, r, paint);
        rect.set(4.0f * density, 13.4f * density, 10.6f * density, 20.0f * density);
        canvas.drawRoundRect(rect, r, r, paint);
        rect.set(13.4f * density, 13.4f * density, 20.0f * density, 20.0f * density);
        canvas.drawRoundRect(rect, r, r, paint);
        return new android.graphics.drawable.BitmapDrawable(mContext.getResources(), bitmap);
    }

    private @Nullable View resolveAppMenuPopupAnchor(@Nullable View fallbackAnchorView) {
        if (mExtensionsMenuButton != null && mExtensionsMenuButton.isShown()) {
            return mExtensionsMenuButton;
        }
        if (fallbackAnchorView != null && fallbackAnchorView.isShown()) {
            return fallbackAnchorView;
        }
        Activity activity = mWindowAndroid.getActivity().get();
        if (activity != null) {
            View menuBtn = activity.findViewById(R.id.menu_button_wrapper);
            if (menuBtn != null && menuBtn.isShown()) {
                return menuBtn;
            }
            View toolbar = activity.findViewById(R.id.toolbar);
            if (toolbar != null && toolbar.isShown()) {
                return toolbar;
            }
            return activity.getWindow().getDecorView();
        }
        return mExtensionsMenuButton;
    }

    private @Nullable ListMenuButton ensureAppMenuContextMenuButton() {
        if (mAppMenuContextMenuButton != null && mAppMenuContextMenuButton.isAttachedToWindow()) {
            return mAppMenuContextMenuButton;
        }
        if (!(mExtensionsMenuButton.getParent() instanceof android.view.ViewGroup)) {
            return null;
        }
        android.view.ViewGroup parent = (android.view.ViewGroup) mExtensionsMenuButton.getParent();
        ListMenuButton btn =
                (ListMenuButton)
                        LayoutInflater.from(mContext)
                                .inflate(R.layout.extension_action_button, parent, false);
        btn.setAlpha(0f);
        btn.setClickable(false);
        btn.setFocusable(false);
        btn.setVisibility(View.VISIBLE);
        parent.addView(btn, new android.view.ViewGroup.LayoutParams(1, 1));
        mAppMenuContextMenuButton = btn;
        return mAppMenuContextMenuButton;
    }

"""
    if helper_marker in text:
        start_idx = text.find(helper_marker)
        end_idx = text.find(helper_anchor, start_idx)
        if end_idx == -1:
            raise SystemExit(f"getContentView anchor not found after helper_marker in {path}")
        text = text[:start_idx] + helper_methods + text[end_idx:]
    else:
        if helper_anchor not in text:
            raise SystemExit(f"getContentView anchor not found in {path}")
        text = text.replace(helper_anchor, helper_methods + helper_anchor, 1)

    path.write_text(text, encoding="utf-8")


def patch_extensions_menu_mediator(src_dir: Path) -> None:
    path = src_dir / EXT_MENU_MEDIATOR_REL
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    text = path.read_text(encoding="utf-8")

    field_marker = "    private @Nullable ListMenuButton mPendingFallbackContextMenuButton;\n"
    field_anchor = "    private @Nullable View mPendingActionAnchorView;\n"
    if field_marker not in text:
        if field_anchor not in text:
            raise SystemExit(f"mPendingActionAnchorView anchor not found in {path}")
        text = text.replace(field_anchor, field_anchor + field_marker, 1)

    old_ctx_click = """    private void onContextMenuButtonClicked(ListMenuButton buttonView, String actionId) {
        Tab currentTab = mCurrentTabSupplier.get();
        if (currentTab == null) {
            return;
        }

        WebContents webContents = currentTab.getWebContents();
        if (webContents == null) {
            return;
        }"""
    new_ctx_click = """    private void onContextMenuButtonClicked(ListMenuButton buttonView, String actionId) {
        WebContents webContents = getCurrentWebContents();
        if (webContents == null) {
            Tab currentTab = mCurrentTabSupplier.get();
            webContents = currentTab != null ? currentTab.getWebContents() : null;
        }
        if (webContents == null) {
            return;
        }"""
    if old_ctx_click in text:
        text = text.replace(old_ctx_click, new_ctx_click, 1)

    old_find_ctx = """    private @Nullable ListMenuButton findContextMenuButtonForPendingAction() {
        View current = mPendingActionAnchorView;
        while (current != null) {
            View button = current.findViewById(R.id.extensions_menu_item_context_menu);
            if (button instanceof ListMenuButton) {
                return (ListMenuButton) button;
            }
            if (!(current.getParent() instanceof View)) {
                return null;
            }
            current = (View) current.getParent();
        }
        return null;
    }"""
    new_find_ctx = """    private @Nullable ListMenuButton findContextMenuButtonForPendingAction() {
        View current = mPendingActionAnchorView;
        while (current != null) {
            if (current instanceof ListMenuButton) {
                return (ListMenuButton) current;
            }
            View button = current.findViewById(R.id.extensions_menu_item_context_menu);
            if (button instanceof ListMenuButton) {
                return (ListMenuButton) button;
            }
            if (!(current.getParent() instanceof View)) {
                break;
            }
            current = (View) current.getParent();
        }
        ListMenuButton fallback = mPendingFallbackContextMenuButton;
        mPendingFallbackContextMenuButton = null;
        return fallback;
    }"""
    if old_find_ctx in text:
        text = text.replace(old_find_ctx, new_find_ctx, 1)

    app_menu_methods_marker = "    public void executeActionFromAppMenu("
    app_menu_methods_anchor = "    private void onPrimaryActionClicked(View anchorView, String extensionId) {"
    app_menu_methods = """    public void executeActionFromAppMenu(
            String extensionId,
            @Nullable View anchorView,
            @Nullable ListMenuButton fallbackContextMenuButton) {
        mPendingFallbackContextMenuButton = fallbackContextMenuButton;
        onPrimaryActionClicked(anchorView, extensionId);
    }

    public void showContextMenuFromAppMenu(
            String extensionId, ListMenuButton contextMenuButton) {
        onContextMenuButtonClicked(contextMenuButton, extensionId);
    }

"""
    if app_menu_methods_marker not in text:
        if app_menu_methods_anchor not in text:
            raise SystemExit(f"onPrimaryActionClicked anchor not found in {path}")
        text = text.replace(
            app_menu_methods_anchor, app_menu_methods + app_menu_methods_anchor, 1
        )

    path.write_text(text, encoding="utf-8")


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
    old_show_replacement_v1 = """        if (!shouldShowAppMenu() || isAppMenuShowing()) return false;

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
    old_show_replacement_v2 = """        if (!shouldShowAppMenu() || isAppMenuShowing()) return false;

        TextBubble.dismissBubbles();
        final View customMenuAnchorView = anchorView;
        if (!mForceNativeMenuOnce
                && !startDragging
                && mDelegate.showCustomAppMenu(
                        this,
                        customMenuAnchorView,
                        startDragging,
                        isFromBottomBar,
                        () -> {
                            mForceNativeMenuOnce = true;
                            try {
                                showAppMenu(customMenuAnchorView, false, isFromBottomBar);
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
    show_replacement = """        if (!shouldShowAppMenu() || isAppMenuShowing()) return false;

        TextBubble.dismissBubbles();
        final View customMenuAnchorView = anchorView;
        if (!mForceNativeMenuOnce
                && mDelegate.showCustomAppMenu(
                        this,
                        customMenuAnchorView,
                        startDragging,
                        isFromBottomBar,
                        () -> {
                            mForceNativeMenuOnce = true;
                            try {
                                showAppMenu(customMenuAnchorView, false, isFromBottomBar);
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
    if old_show_replacement_v1 in text:
        text = text.replace(old_show_replacement_v1, show_replacement, 1)
    elif old_show_replacement_v2 in text:
        text = text.replace(old_show_replacement_v2, show_replacement, 1)
    elif show_marker not in text:
        if show_anchor not in text:
            raise SystemExit(f"showAppMenu anchor not found in {path}")
        text = text.replace(show_anchor, show_replacement, 1)

    old_drag_helper = """    @Nullable AppMenuDragHelper getAppMenuDragHelper() {
        return mAppMenuDragHelper;
    }"""
    new_drag_helper = """    @Nullable AppMenuDragHelper getAppMenuDragHelper() {
        if (mDelegate.isCustomAppMenuShowing()) return null;
        return mAppMenuDragHelper;
    }"""
    if "if (mDelegate.isCustomAppMenuShowing()) return null;" not in text:
        if old_drag_helper not in text:
            raise SystemExit(f"getAppMenuDragHelper anchor not found in {path}")
        text = text.replace(old_drag_helper, new_drag_helper, 1)

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
    "import android.graphics.Bitmap;\n",
    "import android.graphics.Canvas;\n",
    "import android.graphics.Color;\n",
    "import android.graphics.Paint;\n",
    "import android.graphics.Path;\n",
    "import android.graphics.RectF;\n",
    "import android.graphics.Typeface;\n",
    "import android.graphics.drawable.BitmapDrawable;\n",
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
    "import org.chromium.base.ContextUtils;\n",
    "import org.chromium.chrome.browser.night_mode.NightModeUtils;\n",
    "import org.chromium.chrome.browser.night_mode.ThemeType;\n",
    "import org.chromium.chrome.browser.night_mode.WebContentsDarkModeController;\n",
    "import org.chromium.chrome.browser.preferences.ChromePreferenceKeys;\n",
    "import org.chromium.chrome.browser.preferences.ChromeSharedPreferences;\n",
    "import org.chromium.chrome.browser.settings.SettingsNavigationFactory;\n",
    "import org.chromium.chrome.browser.tab.TabLaunchType;\n",
    "import org.chromium.chrome.browser.toolbar.ToolbarPositionController.ToolbarPositionAndSource;\n",
    "import org.chromium.chrome.browser.toolbar.extensions.ExtensionsToolbarCoordinator;\n",
    "import org.chromium.chrome.browser.toolbar.settings.AddressBarPreference;\n",
    "import org.chromium.components.browser_ui.accessibility.PageZoomUtils;\n",
    "import org.chromium.components.browser_ui.settings.SettingsNavigation;\n",
    "import org.chromium.content_public.browser.LoadUrlParams;\n",
    "import org.chromium.content_public.browser.WebContents;\n",
    "import org.chromium.ui.base.PageTransition;\n",
]

LEMUR_MENU_METHODS = """    // Helium: Lemur Browser-style rounded bottom popup menu panel.
    private @Nullable Dialog mCustomAppMenuDialog;
    private @Nullable Dialog mCustomExtensionsDialog;
    private boolean mSuppressCustomDismissCallback;

    private static final int ICON_SETTINGS_HEX = 1;
    private static final int ICON_BOOKMARKS_RIBBON = 2;
    private static final int ICON_HISTORY_CLOCK = 3;
    private static final int ICON_DOWNLOAD_TRAY = 4;
    private static final int ICON_REFRESH = 5;
    private static final int ICON_DESKTOP_MONITOR = 6;
    private static final int ICON_BOOKMARK_STAR = 7;
    private static final int ICON_SHARE_UP = 8;
    private static final int ICON_THEME_SUN = 9;
    private static final int ICON_THEME_MOON = 10;
    private static final int ICON_INCOGNITO_GLASSES = 11;
    private static final int ICON_POWER_EXIT = 12;
    private static final int ICON_PUZZLE_EXT = 13;
    private static final int ICON_FIND_DOC = 14;
    private static final int ICON_TRANSLATE = 15;
    private static final int ICON_ADD_HOME = 16;
    private static final int ICON_WINDOW_MGR = 17;
    private static final int ICON_VIDEO_ENHANCE = 18;
    private static final int ICON_ZOOM_PLUS = 19;
    private static final int ICON_DEVTOOLS_CODE = 20;
    private static final int ICON_CHEVRON_UP = 21;
    private static final int ICON_CHEVRON_DOWN = 22;

    private void registerLemurExtensionsMenuOpener() {
        Activity activity = ContextUtils.activityFromContext(mContext);
        if (activity == null && mContext instanceof Activity) {
            activity = (Activity) mContext;
        }
        if (activity != null) {
            ExtensionsToolbarCoordinator.CUSTOM_EXTENSIONS_MENU_OPENERS.put(
                    activity, this::showCustomExtensionsMenu);
        }
    }

    @Override
    public boolean isCustomAppMenuShowing() {
        return (mCustomAppMenuDialog != null && mCustomAppMenuDialog.isShowing())
                || (mCustomExtensionsDialog != null && mCustomExtensionsDialog.isShowing());
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
        if (mCustomExtensionsDialog != null) {
            Dialog dialog = mCustomExtensionsDialog;
            mCustomExtensionsDialog = null;
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
        registerLemurExtensionsMenuOpener();
        if (getMenuGroup() != MenuGroup.PAGE_MENU) {
            return false;
        }
        Activity activity = ContextUtils.activityFromContext(mContext);
        if (activity == null && mContext instanceof Activity) {
            activity = (Activity) mContext;
        }
        if (activity == null || activity.isFinishing() || activity.isDestroyed()) {
            return false;
        }
        final Activity hostActivity = activity;

        hideCustomAppMenu();

        final boolean isIncognito = isIncognitoShowing();
        final int savedTheme =
                ChromeSharedPreferences.getInstance()
                        .readInt(
                                ChromePreferenceKeys.UI_THEME_SETTING,
                                ThemeType.SYSTEM_DEFAULT);
        final boolean isSystemNight =
                (mContext.getResources().getConfiguration().uiMode
                                & Configuration.UI_MODE_NIGHT_MASK)
                        == Configuration.UI_MODE_NIGHT_YES;
        final boolean isDarkThemeActive =
                savedTheme == ThemeType.DARK
                        || (savedTheme == ThemeType.SYSTEM_DEFAULT && isSystemNight);
        final boolean isNight = isIncognito || isDarkThemeActive;

        final int sheetBgColor = isNight ? 0xFF222327 : 0xFFF7F8FA;
        final int textPrimaryColor = isNight ? 0xFFF1F3F4 : 0xFF1F1F1F;
        final int textSecondaryColor = isNight ? 0xFF9AA0A6 : 0xFF5F6368;
        final int accentColor = isNight ? 0xFF8AB4F8 : 0xFF1A73E8;
        final int rippleColor = isNight ? 0x26FFFFFF : 0x18000000;

        final Dialog dialog = new Dialog(hostActivity);
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

        LinearLayout sheet = new LinearLayout(mContext);
        sheet.setOrientation(LinearLayout.VERTICAL);
        sheet.setClickable(true);
        GradientDrawable sheetBg = new GradientDrawable();
        sheetBg.setShape(GradientDrawable.RECTANGLE);
        float topRadius = dpToPx(26);
        sheetBg.setCornerRadii(
                new float[] {
                    topRadius, topRadius, topRadius, topRadius, 0f, 0f, 0f, 0f
                });
        sheetBg.setColor(sheetBgColor);
        sheet.setBackground(sheetBg);
        sheet.setElevation(dpToPx(16));
        sheet.setPadding(dpToPx(10), dpToPx(16), dpToPx(10), dpToPx(24));

        int screenWidthPx = mContext.getResources().getDisplayMetrics().widthPixels;
        int maxSheetWidthPx = dpToPx(520);
        int sheetWidth =
                screenWidthPx > maxSheetWidthPx
                        ? maxSheetWidthPx
                        : ViewGroup.LayoutParams.MATCH_PARENT;
        FrameLayout.LayoutParams sheetLp =
                new FrameLayout.LayoutParams(
                        sheetWidth,
                        ViewGroup.LayoutParams.WRAP_CONTENT,
                        Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL);
        outerHost.addView(sheet, sheetLp);

        // Top row: Settings hexagon icon on the right (matches Screenshot 2)
        LinearLayout topRow = new LinearLayout(mContext);
        topRow.setOrientation(LinearLayout.HORIZONTAL);
        topRow.setGravity(Gravity.END | Gravity.CENTER_VERTICAL);
        topRow.setPadding(dpToPx(12), 0, dpToPx(14), dpToPx(8));

        FrameLayout settingsBtn = new FrameLayout(mContext);
        settingsBtn.setContentDescription(mContext.getString(R.string.menu_settings));
        GradientDrawable settingsRippleMask = new GradientDrawable();
        settingsRippleMask.setShape(GradientDrawable.OVAL);
        settingsRippleMask.setColor(Color.WHITE);
        settingsBtn.setBackground(
                new RippleDrawable(
                        ColorStateList.valueOf(rippleColor), null, settingsRippleMask));
        ImageView settingsIcon = new ImageView(mContext);
        settingsIcon.setImageDrawable(
                createLemurVectorIcon(ICON_SETTINGS_HEX, textPrimaryColor, 24));
        settingsBtn.addView(
                settingsIcon,
                new FrameLayout.LayoutParams(dpToPx(24), dpToPx(24), Gravity.CENTER));
        settingsBtn.setOnClickListener(v -> triggerMenuAction(dialog, R.id.preferences_id));
        topRow.addView(settingsBtn, new LinearLayout.LayoutParams(dpToPx(40), dpToPx(40)));
        sheet.addView(
                topRow,
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        Tab currentTab = mActivityTabProvider.get();
        if (currentTab == null && mTabModelSelector != null) {
            currentTab = mTabModelSelector.getCurrentTab();
        }
        final WebContents currentWebContents =
                currentTab != null ? currentTab.getWebContents() : null;
        GURL url = currentTab != null ? currentTab.getUrl() : GURL.emptyGURL();
        final boolean isNativePage =
                UrlUtilities.isChromeScheme(url)
                        || (currentTab != null && currentTab.isNativePage());
        final boolean hasWebContents =
                currentTab != null && !isNativePage && currentWebContents != null;

        boolean isBookmarked = currentTab != null && shouldCheckBookmarkStar(currentTab);
        boolean isDesktopSite =
                hasWebContents
                        && assumeNonNull(currentTab.getWebContents())
                                .getNavigationController()
                                .getUseDesktopUserAgent();
        boolean canShare = ShareUtils.shouldEnableShare(currentTab);

        // Main menu grid (5 columns x 2 rows matching Screenshot 2)
        GridLayout grid = new GridLayout(mContext);
        grid.setColumnCount(5);
        grid.setUseDefaultMargins(false);
        sheet.addView(
                grid,
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        // Row 1: 书签 | 历史记录 | 下载 | 刷新 | 桌面模式
        addLemurMainMenuTile(
                grid,
                ICON_BOOKMARKS_RIBBON,
                "书签",
                true,
                false,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.all_bookmarks_menu_id));
        addLemurMainMenuTile(
                grid,
                ICON_HISTORY_CLOCK,
                "历史记录",
                !isIncognito,
                false,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.open_history_menu_id));
        addLemurMainMenuTile(
                grid,
                ICON_DOWNLOAD_TRAY,
                "下载",
                true,
                false,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.downloads_menu_id));
        addLemurMainMenuTile(
                grid,
                ICON_REFRESH,
                "刷新",
                currentTab != null,
                false,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.reload_menu_id));
        addLemurMainMenuTile(
                grid,
                ICON_DESKTOP_MONITOR,
                "桌面模式",
                hasWebContents,
                isDesktopSite,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.request_desktop_site_id));

        // Row 2: 添加书签 | 分享 | 浅色模式/深色模式 | 无痕模式 | 退出
        addLemurMainMenuTile(
                grid,
                ICON_BOOKMARK_STAR,
                isBookmarked ? "编辑书签" : "添加书签",
                currentTab != null,
                isBookmarked,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.bookmark_this_page_id));
        addLemurMainMenuTile(
                grid,
                ICON_SHARE_UP,
                "分享",
                canShare,
                false,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.share_menu_id));

        // Theme toggle: shows "浅色模式" when currently in dark mode (switches to Light),
        // and "深色模式" when currently in light mode (switches to Dark).
        final String themeToggleTitle = isDarkThemeActive ? "浅色模式" : "深色模式";
        final int themeToggleIcon = isDarkThemeActive ? ICON_THEME_SUN : ICON_THEME_MOON;
        addLemurMainMenuTile(
                grid,
                themeToggleIcon,
                themeToggleTitle,
                true,
                false,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> {
                    int targetTheme = isDarkThemeActive ? ThemeType.LIGHT : ThemeType.DARK;
                    int menuId =
                            isDarkThemeActive
                                    ? R.id.appearance_light_menu_id
                                    : R.id.appearance_dark_menu_id;
                    ChromeSharedPreferences.getInstance()
                            .writeInt(ChromePreferenceKeys.UI_THEME_SETTING, targetTheme);
                    triggerMenuAction(dialog, menuId);
                });

        addLemurMainMenuTile(
                grid,
                ICON_INCOGNITO_GLASSES,
                "无痕模式",
                isIncognitoEnabled() && !isIncognitoReauthShowing(),
                isIncognito,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.new_incognito_tab_menu_id));
        addLemurMainMenuTile(
                grid,
                ICON_POWER_EXIT,
                "退出",
                true,
                false,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> {
                    if (dialog.isShowing()) {
                        dialog.dismiss();
                    }
                    hostActivity.finishAndRemoveTask();
                });

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
            wlp.dimAmount = 0.45f;
            window.addFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND);
            window.setAttributes(wlp);
        }

        dialog.show();
        return true;
    }

    /**
     * Shows the Lemur-style Extensions, Common Tools & Extension Stores bottom sheet
     * when the 4-small-squares toolbar icon (⊞) is clicked (matches Screenshot 1).
     */
    public void showCustomExtensionsMenu(@Nullable View anchorView) {
        Activity activity = ContextUtils.activityFromContext(mContext);
        if (activity == null && mContext instanceof Activity) {
            activity = (Activity) mContext;
        }
        if (activity == null || activity.isFinishing() || activity.isDestroyed()) {
            return;
        }
        if (mCustomExtensionsDialog != null && mCustomExtensionsDialog.isShowing()) {
            mCustomExtensionsDialog.dismiss();
            return;
        }
        hideCustomAppMenu();

        final @Nullable View popupAnchorView = anchorView != null ? anchorView : mDecorView;
        final boolean isIncognito = isIncognitoShowing();
        final boolean isNight =
                isIncognito
                        || ((mContext.getResources().getConfiguration().uiMode
                                        & Configuration.UI_MODE_NIGHT_MASK)
                                == Configuration.UI_MODE_NIGHT_YES);

        final int sheetBgColor = isNight ? 0xFF25262B : 0xFFF4F6FA;
        final int tileSurfaceColor = isNight ? 0xFF3A3B40 : 0xFFFFFFFF;
        final int activeSurfaceColor = isNight ? 0xFF2E4978 : 0xFFD2E3FC;
        final int textPrimaryColor = isNight ? 0xFFF1F3F4 : 0xFF1F1F1F;
        final int textSecondaryColor = isNight ? 0xFF9AA0A6 : 0xFF5F6368;
        final int accentColor = isNight ? 0xFF8AB4F8 : 0xFF1A73E8;
        final int rippleColor = isNight ? 0x28FFFFFF : 0x1A000000;

        final Dialog dialog = new Dialog(activity);
        dialog.requestWindowFeature(Window.FEATURE_NO_TITLE);
        dialog.setCanceledOnTouchOutside(true);
        mCustomExtensionsDialog = dialog;
        dialog.setOnDismissListener(
                d -> {
                    if (mCustomExtensionsDialog == d) {
                        mCustomExtensionsDialog = null;
                    }
                });

        FrameLayout outerHost = new FrameLayout(mContext);
        outerHost.setClickable(true);
        outerHost.setOnClickListener(v -> dialog.dismiss());

        LinearLayout sheet = new LinearLayout(mContext);
        sheet.setOrientation(LinearLayout.VERTICAL);
        sheet.setClickable(true);
        GradientDrawable sheetBg = new GradientDrawable();
        sheetBg.setShape(GradientDrawable.RECTANGLE);
        float topRadius = dpToPx(26);
        sheetBg.setCornerRadii(
                new float[] {
                    topRadius, topRadius, topRadius, topRadius, 0f, 0f, 0f, 0f
                });
        sheetBg.setColor(sheetBgColor);
        sheet.setBackground(sheetBg);
        sheet.setElevation(dpToPx(16));
        sheet.setPadding(dpToPx(16), dpToPx(20), dpToPx(16), dpToPx(22));

        int screenWidthPx = mContext.getResources().getDisplayMetrics().widthPixels;
        int maxSheetWidthPx = dpToPx(520);
        int sheetWidth =
                screenWidthPx > maxSheetWidthPx
                        ? maxSheetWidthPx
                        : ViewGroup.LayoutParams.MATCH_PARENT;
        FrameLayout.LayoutParams sheetLp =
                new FrameLayout.LayoutParams(
                        sheetWidth,
                        ViewGroup.LayoutParams.WRAP_CONTENT,
                        Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL);
        outerHost.addView(sheet, sheetLp);

        ScrollView scrollView = new ScrollView(mContext);
        scrollView.setVerticalScrollBarEnabled(false);
        scrollView.setOverScrollMode(View.OVER_SCROLL_IF_CONTENT_SCROLLS);
        final int maxScrollHeight =
                (int) (mContext.getResources().getDisplayMetrics().heightPixels * 0.78f);
        sheet.addView(
                scrollView,
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        LinearLayout contentCol = new LinearLayout(mContext);
        contentCol.setOrientation(LinearLayout.VERTICAL);
        scrollView.addView(
                contentCol,
                new FrameLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        Tab currentTab = mActivityTabProvider.get();
        if (currentTab == null && mTabModelSelector != null) {
            currentTab = mTabModelSelector.getCurrentTab();
        }
        final Tab activeTab = currentTab;
        final WebContents currentWebContents =
                currentTab != null ? currentTab.getWebContents() : null;
        GURL url = currentTab != null ? currentTab.getUrl() : GURL.emptyGURL();
        final boolean isNativePage =
                UrlUtilities.isChromeScheme(url)
                        || (currentTab != null && currentTab.isNativePage());
        final boolean hasWebContents =
                currentTab != null && !isNativePage && currentWebContents != null;

        // 1. Section: 扩展应用 (Installed Extensions)
        LinearLayout extHeaderRow = new LinearLayout(mContext);
        extHeaderRow.setOrientation(LinearLayout.HORIZONTAL);
        extHeaderRow.setGravity(Gravity.CENTER_VERTICAL);
        LinearLayout.LayoutParams extHeaderLp =
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        extHeaderLp.bottomMargin = dpToPx(12);

        TextView extHeaderTitle = new TextView(mContext);
        extHeaderTitle.setText("扩展应用");
        extHeaderTitle.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f);
        extHeaderTitle.setTypeface(Typeface.DEFAULT_BOLD);
        extHeaderTitle.setTextColor(textPrimaryColor);
        extHeaderRow.addView(
                extHeaderTitle,
                new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        final ImageView collapseArrow = new ImageView(mContext);
        collapseArrow.setImageDrawable(
                createLemurVectorIcon(ICON_CHEVRON_UP, textSecondaryColor, 20));
        LinearLayout.LayoutParams arrowLp =
                new LinearLayout.LayoutParams(dpToPx(28), dpToPx(28));
        extHeaderRow.addView(collapseArrow, arrowLp);
        contentCol.addView(extHeaderRow, extHeaderLp);

        final FrameLayout extBodyContainer = new FrameLayout(mContext);
        LinearLayout.LayoutParams extBodyLp =
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        extBodyLp.bottomMargin = dpToPx(20);
        contentCol.addView(extBodyContainer, extBodyLp);

        extHeaderRow.setOnClickListener(
                v -> {
                    boolean visible = extBodyContainer.getVisibility() == View.VISIBLE;
                    extBodyContainer.setVisibility(visible ? View.GONE : View.VISIBLE);
                    collapseArrow.setImageDrawable(
                            createLemurVectorIcon(
                                    visible ? ICON_CHEVRON_DOWN : ICON_CHEVRON_UP,
                                    textSecondaryColor,
                                    20));
                });

        final ExtensionsToolbarCoordinator extCoordinator =
                mToolbarManager != null ? mToolbarManager.getExtensionsToolbarCoordinator() : null;
        final String[] extIds =
                extCoordinator != null
                        ? extCoordinator.getAllExtensionActionIds()
                        : new String[0];

        if (extIds.length > 0 && extCoordinator != null) {
            GridLayout extGrid = new GridLayout(mContext);
            extGrid.setColumnCount(5);
            extGrid.setUseDefaultMargins(false);
            extBodyContainer.addView(
                    extGrid,
                    new FrameLayout.LayoutParams(
                            ViewGroup.LayoutParams.MATCH_PARENT,
                            ViewGroup.LayoutParams.WRAP_CONTENT));

            for (final String extId : extIds) {
                Bitmap extIcon =
                        extCoordinator.getExtensionActionIcon(extId, currentWebContents);
                String extName =
                        extCoordinator.getExtensionActionTitle(extId, currentWebContents);
                if (extName == null || extName.isEmpty()) {
                    extName = extId;
                }
                addLemurExtensionTile(
                        extGrid,
                        extIcon,
                        extName,
                        tileSurfaceColor,
                        textPrimaryColor,
                        rippleColor,
                        v -> {
                            if (dialog.isShowing()) {
                                dialog.dismiss();
                            }
                            extCoordinator.executeExtensionActionFromAppMenu(
                                    extId, popupAnchorView);
                        },
                        v -> {
                            if (dialog.isShowing()) {
                                dialog.dismiss();
                            }
                            extCoordinator.showExtensionContextMenuFromAppMenu(
                                    extId, popupAnchorView);
                            return true;
                        });
            }
        } else {
            LinearLayout emptyBox = new LinearLayout(mContext);
            emptyBox.setOrientation(LinearLayout.VERTICAL);
            emptyBox.setGravity(Gravity.CENTER);
            emptyBox.setPadding(dpToPx(12), dpToPx(14), dpToPx(12), dpToPx(14));

            ImageView emptyIllus = new ImageView(mContext);
            emptyIllus.setImageDrawable(createLemurEmptyExtensionsDrawable(isNight));
            LinearLayout.LayoutParams illusLp =
                    new LinearLayout.LayoutParams(dpToPx(140), dpToPx(110));
            illusLp.bottomMargin = dpToPx(8);
            emptyBox.addView(emptyIllus, illusLp);

            TextView emptyText = new TextView(mContext);
            emptyText.setText("还没有运行任何扩展");
            emptyText.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14.5f);
            emptyText.setTextColor(textSecondaryColor);
            emptyText.setGravity(Gravity.CENTER);
            emptyBox.addView(
                    emptyText,
                    new LinearLayout.LayoutParams(
                            ViewGroup.LayoutParams.WRAP_CONTENT,
                            ViewGroup.LayoutParams.WRAP_CONTENT));
            extBodyContainer.addView(
                    emptyBox,
                    new FrameLayout.LayoutParams(
                            ViewGroup.LayoutParams.MATCH_PARENT,
                            ViewGroup.LayoutParams.WRAP_CONTENT));
        }

        // 2. Section: 常用工具 (Common Tools - matches Screenshot 1)
        TextView toolsHeader = new TextView(mContext);
        toolsHeader.setText("常用工具");
        toolsHeader.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f);
        toolsHeader.setTypeface(Typeface.DEFAULT_BOLD);
        toolsHeader.setTextColor(textPrimaryColor);
        LinearLayout.LayoutParams toolsHeaderLp =
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        toolsHeaderLp.bottomMargin = dpToPx(12);
        contentCol.addView(toolsHeader, toolsHeaderLp);

        GridLayout toolsGrid = new GridLayout(mContext);
        toolsGrid.setColumnCount(5);
        toolsGrid.setUseDefaultMargins(false);
        LinearLayout.LayoutParams toolsGridLp =
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        toolsGridLp.bottomMargin = dpToPx(18);
        contentCol.addView(toolsGrid, toolsGridLp);

        boolean canFindInPage = shouldShowFindInPageItem(currentTab);
        boolean canTranslate = shouldShowTranslateMenuItem(currentTab);
        boolean canAddToHome =
                shouldShowHomeScreenMenuItem(
                        isNativePage,
                        url.getScheme().equals(UrlConstants.FILE_SCHEME),
                        url.getScheme().equals(UrlConstants.CONTENT_SCHEME),
                        isIncognito,
                        url);

        // Tool 1: 扩展管理
        addLemurToolSquareTile(
                toolsGrid,
                createLemurVectorIcon(ICON_PUZZLE_EXT, textPrimaryColor, 24),
                "扩展管理",
                true,
                false,
                tileSurfaceColor,
                activeSurfaceColor,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.manage_extensions_menu_id));

        // Tool 2: 网页查找
        addLemurToolSquareTile(
                toolsGrid,
                createLemurVectorIcon(ICON_FIND_DOC, textPrimaryColor, 24),
                "网页查找",
                canFindInPage,
                false,
                tileSurfaceColor,
                activeSurfaceColor,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.find_in_page_id));

        // Tool 3: 翻译…
        addLemurToolSquareTile(
                toolsGrid,
                createLemurVectorIcon(ICON_TRANSLATE, textPrimaryColor, 24),
                "翻译…",
                canTranslate,
                false,
                tileSurfaceColor,
                activeSurfaceColor,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.translate_id));

        // Tool 4: 添加到主屏幕
        addLemurToolSquareTile(
                toolsGrid,
                createLemurVectorIcon(ICON_ADD_HOME, textPrimaryColor, 24),
                "添加到主屏幕",
                canAddToHome,
                false,
                tileSurfaceColor,
                activeSurfaceColor,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.universal_install));

        // Tool 5: 窗口管理
        addLemurToolSquareTile(
                toolsGrid,
                createLemurVectorIcon(ICON_WINDOW_MGR, textPrimaryColor, 24),
                "窗口管理",
                true,
                false,
                tileSurfaceColor,
                activeSurfaceColor,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> {
                    if (dialog.isShowing()) {
                        dialog.dismiss();
                    }
                    View tabSwitcherBtn =
                            mDecorView != null
                                    ? mDecorView.findViewById(R.id.tab_switcher_button)
                                    : null;
                    if (tabSwitcherBtn != null) {
                        tabSwitcherBtn.performClick();
                    } else {
                        mAppMenuDelegate.onOptionsItemSelected(R.id.new_tab_menu_id, null, null);
                    }
                });

        // Tool 6: 默认缩放设置
        addLemurToolSquareTile(
                toolsGrid,
                createLemurVectorIcon(ICON_ZOOM_PLUS, textPrimaryColor, 24),
                "默认缩放设置",
                true,
                false,
                tileSurfaceColor,
                activeSurfaceColor,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> {
                    if (dialog.isShowing()) {
                        dialog.dismiss();
                    }
                    if (hasWebContents) {
                        PageZoomUtils.setShouldAlwaysShowZoomMenuItem(true);
                        boolean handled =
                                mAppMenuDelegate.onOptionsItemSelected(
                                        R.id.page_zoom_id, null, null);
                        if (handled) {
                            return;
                        }
                    }
                    SettingsNavigationFactory.createSettingsNavigation()
                            .startSettings(
                                    mContext, SettingsNavigation.SettingsFragment.ACCESSIBILITY);
                });

        // Tool 7: Devtools
        addLemurToolSquareTile(
                toolsGrid,
                createLemurVectorIcon(ICON_DEVTOOLS_CODE, textPrimaryColor, 24),
                "Devtools",
                true,
                false,
                tileSurfaceColor,
                activeSurfaceColor,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> {
                    if (dialog.isShowing()) {
                        dialog.dismiss();
                    }
                    if (hasWebContents) {
                        mAppMenuDelegate.onOptionsItemSelected(R.id.dev_tools, null, null);
                    } else if (mTabModelSelector != null) {
                        mTabModelSelector.openNewTab(
                                new LoadUrlParams(
                                        "https://example.com", PageTransition.AUTO_TOPLEVEL),
                                TabLaunchType.FROM_CHROME_UI,
                                activeTab,
                                isIncognito);
                    }
                });

        // Tool 8: 扩展商店 (Chrome Web Store)
        addLemurToolSquareTile(
                toolsGrid,
                createChromeStoreDrawable(),
                "扩展商店",
                true,
                false,
                tileSurfaceColor,
                activeSurfaceColor,
                textPrimaryColor,
                textSecondaryColor,
                accentColor,
                rippleColor,
                v -> triggerMenuAction(dialog, R.id.extensions_webstore_menu_id));

        scrollView.post(
                () -> {
                    if (scrollView.getHeight() > maxScrollHeight) {
                        LinearLayout.LayoutParams lp =
                                (LinearLayout.LayoutParams) scrollView.getLayoutParams();
                        lp.height = maxScrollHeight;
                        scrollView.setLayoutParams(lp);
                    }
                });

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
            wlp.dimAmount = 0.45f;
            window.addFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND);
            window.setAttributes(wlp);
        }

        dialog.show();
    }

    private void triggerMenuAction(Dialog dialog, int itemId) {
        if (dialog.isShowing()) {
            dialog.dismiss();
        }
        mAppMenuDelegate.onOptionsItemSelected(itemId, null, null);
    }

    private void addLemurMainMenuTile(
            GridLayout grid,
            int iconType,
            String title,
            boolean isEnabled,
            boolean isActive,
            int textPrimaryColor,
            int textSecondaryColor,
            int accentColor,
            int rippleColor,
            View.OnClickListener clickListener) {
        LinearLayout cell = new LinearLayout(mContext);
        cell.setOrientation(LinearLayout.VERTICAL);
        cell.setGravity(Gravity.CENTER_HORIZONTAL);
        cell.setPadding(dpToPx(4), dpToPx(12), dpToPx(4), dpToPx(12));

        GradientDrawable rippleMask = new GradientDrawable();
        rippleMask.setShape(GradientDrawable.RECTANGLE);
        rippleMask.setCornerRadius(dpToPx(14));
        rippleMask.setColor(Color.WHITE);
        cell.setBackground(
                new RippleDrawable(ColorStateList.valueOf(rippleColor), null, rippleMask));

        int iconColor =
                isActive ? accentColor : (isEnabled ? textPrimaryColor : textSecondaryColor);
        ImageView iconView = new ImageView(mContext);
        iconView.setImageDrawable(createLemurVectorIcon(iconType, iconColor, 26));
        LinearLayout.LayoutParams iconLp =
                new LinearLayout.LayoutParams(dpToPx(26), dpToPx(26));
        iconLp.bottomMargin = dpToPx(10);
        cell.addView(iconView, iconLp);

        TextView labelView = new TextView(mContext);
        labelView.setText(title);
        labelView.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12.5f);
        labelView.setGravity(Gravity.CENTER);
        labelView.setSingleLine(true);
        labelView.setEllipsize(TextUtils.TruncateAt.END);
        labelView.setTextColor(iconColor);
        if (isActive) {
            labelView.setTypeface(Typeface.DEFAULT_BOLD);
        }
        cell.addView(
                labelView,
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT));

        cell.setEnabled(isEnabled);
        cell.setAlpha(isEnabled ? 1.0f : 0.38f);
        if (isEnabled) {
            cell.setOnClickListener(clickListener);
        }

        GridLayout.LayoutParams gridLp =
                new GridLayout.LayoutParams(
                        GridLayout.spec(GridLayout.UNDEFINED, 1f),
                        GridLayout.spec(GridLayout.UNDEFINED, 1f));
        gridLp.width = 0;
        gridLp.height = ViewGroup.LayoutParams.WRAP_CONTENT;
        grid.addView(cell, gridLp);
    }

    private void addLemurToolSquareTile(
            GridLayout grid,
            Drawable iconDrawable,
            String title,
            boolean isEnabled,
            boolean isActive,
            int surfaceColor,
            int activeSurfaceColor,
            int textPrimaryColor,
            int textSecondaryColor,
            int accentColor,
            int rippleColor,
            View.OnClickListener clickListener) {
        LinearLayout cell = new LinearLayout(mContext);
        cell.setOrientation(LinearLayout.VERTICAL);
        cell.setGravity(Gravity.CENTER_HORIZONTAL);
        cell.setPadding(dpToPx(3), dpToPx(6), dpToPx(3), dpToPx(8));

        FrameLayout iconBox = new FrameLayout(mContext);
        GradientDrawable boxBg = new GradientDrawable();
        boxBg.setShape(GradientDrawable.RECTANGLE);
        boxBg.setCornerRadius(dpToPx(16));
        boxBg.setColor(isActive ? activeSurfaceColor : surfaceColor);
        if (isActive) {
            boxBg.setStroke(dpToPx(1), accentColor);
        }
        iconBox.setBackground(
                new RippleDrawable(ColorStateList.valueOf(rippleColor), boxBg, null));

        ImageView iconView = new ImageView(mContext);
        iconView.setScaleType(ImageView.ScaleType.FIT_CENTER);
        iconView.setImageDrawable(iconDrawable);
        iconBox.addView(
                iconView,
                new FrameLayout.LayoutParams(dpToPx(26), dpToPx(26), Gravity.CENTER));

        LinearLayout.LayoutParams boxLp =
                new LinearLayout.LayoutParams(dpToPx(52), dpToPx(52));
        boxLp.bottomMargin = dpToPx(6);
        cell.addView(iconBox, boxLp);

        TextView textView = new TextView(mContext);
        textView.setText(title);
        textView.setTextSize(TypedValue.COMPLEX_UNIT_SP, 11.5f);
        textView.setGravity(Gravity.CENTER);
        textView.setMaxLines(2);
        textView.setEllipsize(TextUtils.TruncateAt.END);
        textView.setTextColor(
                isActive ? accentColor : (isEnabled ? textPrimaryColor : textSecondaryColor));
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

    private void addLemurExtensionTile(
            GridLayout grid,
            @Nullable Bitmap iconBitmap,
            String title,
            int surfaceColor,
            int textPrimaryColor,
            int rippleColor,
            View.OnClickListener clickListener,
            View.OnLongClickListener longClickListener) {
        LinearLayout cell = new LinearLayout(mContext);
        cell.setOrientation(LinearLayout.VERTICAL);
        cell.setGravity(Gravity.CENTER_HORIZONTAL);
        cell.setPadding(dpToPx(3), dpToPx(6), dpToPx(3), dpToPx(8));

        FrameLayout iconBox = new FrameLayout(mContext);
        GradientDrawable boxBg = new GradientDrawable();
        boxBg.setShape(GradientDrawable.RECTANGLE);
        boxBg.setCornerRadius(dpToPx(16));
        boxBg.setColor(surfaceColor);
        iconBox.setBackground(
                new RippleDrawable(ColorStateList.valueOf(rippleColor), boxBg, null));

        ImageView iconView = new ImageView(mContext);
        iconView.setScaleType(ImageView.ScaleType.FIT_CENTER);
        if (iconBitmap != null) {
            iconView.setImageBitmap(iconBitmap);
        } else {
            iconView.setImageDrawable(
                    createLemurVectorIcon(ICON_PUZZLE_EXT, textPrimaryColor, 26));
        }
        iconBox.addView(
                iconView,
                new FrameLayout.LayoutParams(dpToPx(28), dpToPx(28), Gravity.CENTER));

        LinearLayout.LayoutParams boxLp =
                new LinearLayout.LayoutParams(dpToPx(52), dpToPx(52));
        boxLp.bottomMargin = dpToPx(6);
        cell.addView(iconBox, boxLp);

        TextView textView = new TextView(mContext);
        textView.setText(title);
        textView.setTextSize(TypedValue.COMPLEX_UNIT_SP, 11.5f);
        textView.setGravity(Gravity.CENTER);
        textView.setSingleLine(true);
        textView.setEllipsize(TextUtils.TruncateAt.END);
        textView.setTextColor(textPrimaryColor);
        cell.addView(
                textView,
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT));

        cell.setOnClickListener(clickListener);
        iconBox.setOnClickListener(clickListener);
        cell.setOnLongClickListener(longClickListener);
        iconBox.setOnLongClickListener(longClickListener);

        GridLayout.LayoutParams gridLp =
                new GridLayout.LayoutParams(
                        GridLayout.spec(GridLayout.UNDEFINED, 1f),
                        GridLayout.spec(GridLayout.UNDEFINED, 1f));
        gridLp.width = 0;
        gridLp.height = ViewGroup.LayoutParams.WRAP_CONTENT;
        grid.addView(cell, gridLp);
    }

    private Drawable createLemurVectorIcon(int iconType, int color, int sizeDp) {
        float d = mContext.getResources().getDisplayMetrics().density;
        int px = Math.max(24, Math.round(sizeDp * d));
        Bitmap bmp = Bitmap.createBitmap(px, px, Bitmap.Config.ARGB_8888);
        Canvas c = new Canvas(bmp);
        float s = px / 24f;

        Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        p.setColor(color);
        p.setStyle(Paint.Style.STROKE);
        p.setStrokeWidth(1.9f * s);
        p.setStrokeCap(Paint.Cap.ROUND);
        p.setStrokeJoin(Paint.Join.ROUND);

        Path path = new Path();
        RectF rf = new RectF();

        switch (iconType) {
            case ICON_SETTINGS_HEX:
                for (int i = 0; i < 6; i++) {
                    double angle = Math.toRadians(60 * i);
                    float x = (float) (12f + 8.5f * Math.cos(angle)) * s;
                    float y = (float) (12f + 8.5f * Math.sin(angle)) * s;
                    if (i == 0) path.moveTo(x, y);
                    else path.lineTo(x, y);
                }
                path.close();
                c.drawPath(path, p);
                c.drawCircle(12f * s, 12f * s, 2.8f * s, p);
                break;

            case ICON_BOOKMARKS_RIBBON:
                path.moveTo(6.5f * s, 4.5f * s);
                path.lineTo(17.5f * s, 4.5f * s);
                path.lineTo(17.5f * s, 19.5f * s);
                path.lineTo(12f * s, 15.2f * s);
                path.lineTo(6.5f * s, 19.5f * s);
                path.close();
                c.drawPath(path, p);
                break;

            case ICON_HISTORY_CLOCK:
                rf.set(4f * s, 4f * s, 20f * s, 20f * s);
                c.drawArc(rf, -60f, 300f, false, p);
                path.moveTo(12f * s, 7.5f * s);
                path.lineTo(12f * s, 12.2f * s);
                path.lineTo(15.2f * s, 14.2f * s);
                c.drawPath(path, p);
                break;

            case ICON_DOWNLOAD_TRAY:
                c.drawLine(12f * s, 4.5f * s, 12f * s, 15f * s, p);
                path.moveTo(8f * s, 11.2f * s);
                path.lineTo(12f * s, 15.2f * s);
                path.lineTo(16f * s, 11.2f * s);
                c.drawPath(path, p);
                c.drawLine(5.5f * s, 19f * s, 18.5f * s, 19f * s, p);
                break;

            case ICON_REFRESH:
                rf.set(4.5f * s, 4.5f * s, 19.5f * s, 19.5f * s);
                c.drawArc(rf, 35f, 295f, false, p);
                path.moveTo(15.5f * s, 4.2f * s);
                path.lineTo(19.5f * s, 8.0f * s);
                path.lineTo(14.8f * s, 8.8f * s);
                c.drawPath(path, p);
                break;

            case ICON_DESKTOP_MONITOR:
                rf.set(3.5f * s, 4.5f * s, 20.5f * s, 16f * s);
                c.drawRoundRect(rf, 2.2f * s, 2.2f * s, p);
                c.drawLine(8f * s, 19.5f * s, 16f * s, 19.5f * s, p);
                c.drawLine(12f * s, 16f * s, 12f * s, 19.5f * s, p);
                break;

            case ICON_BOOKMARK_STAR:
                for (int i = 0; i < 10; i++) {
                    double angle = Math.toRadians(-90 + i * 36);
                    float rad = (i % 2 == 0) ? 8.5f : 3.6f;
                    float x = (float) (12f + rad * Math.cos(angle)) * s;
                    float y = (float) (12.4f + rad * Math.sin(angle)) * s;
                    if (i == 0) path.moveTo(x, y);
                    else path.lineTo(x, y);
                }
                path.close();
                c.drawPath(path, p);
                break;

            case ICON_SHARE_UP:
                c.drawLine(12f * s, 14.5f * s, 12f * s, 4.5f * s, p);
                path.moveTo(8.2f * s, 8.2f * s);
                path.lineTo(12f * s, 4.4f * s);
                path.lineTo(15.8f * s, 8.2f * s);
                c.drawPath(path, p);
                path.reset();
                path.moveTo(5f * s, 13f * s);
                path.lineTo(5f * s, 18.2f * s);
                path.lineTo(19f * s, 18.2f * s);
                path.lineTo(19f * s, 13f * s);
                c.drawPath(path, p);
                break;

            case ICON_THEME_SUN:
                c.drawCircle(12f * s, 12f * s, 4.2f * s, p);
                for (int i = 0; i < 8; i++) {
                    double a = Math.toRadians(i * 45);
                    float x1 = (float) (12f + 6.8f * Math.cos(a)) * s;
                    float y1 = (float) (12f + 6.8f * Math.sin(a)) * s;
                    float x2 = (float) (12f + 9.0f * Math.cos(a)) * s;
                    float y2 = (float) (12f + 9.0f * Math.sin(a)) * s;
                    c.drawLine(x1, y1, x2, y2, p);
                }
                break;

            case ICON_THEME_MOON:
                rf.set(5.2f * s, 5.2f * s, 18.8f * s, 18.8f * s);
                c.drawArc(rf, 40f, 260f, false, p);
                c.drawLine(14.5f * s, 5.5f * s, 17.5f * s, 5.5f * s, p);
                c.drawLine(16.0f * s, 4.0f * s, 16.0f * s, 7.0f * s, p);
                break;

            case ICON_INCOGNITO_GLASSES:
                c.drawCircle(7.5f * s, 14.5f * s, 3.2f * s, p);
                c.drawCircle(16.5f * s, 14.5f * s, 3.2f * s, p);
                c.drawLine(10.7f * s, 14.2f * s, 13.3f * s, 14.2f * s, p);
                c.drawLine(4.5f * s, 13.5f * s, 6.2f * s, 7.0f * s, p);
                c.drawLine(19.5f * s, 13.5f * s, 17.8f * s, 7.0f * s, p);
                break;

            case ICON_POWER_EXIT:
                rf.set(5f * s, 5.5f * s, 19f * s, 19.5f * s);
                c.drawArc(rf, -55f, 290f, false, p);
                c.drawLine(12f * s, 3.8f * s, 12f * s, 11.5f * s, p);
                break;

            case ICON_PUZZLE_EXT:
                rf.set(5.5f * s, 6.5f * s, 17.5f * s, 18.5f * s);
                c.drawRoundRect(rf, 2.0f * s, 2.0f * s, p);
                c.drawCircle(11.5f * s, 5.2f * s, 1.8f * s, p);
                c.drawCircle(18.8f * s, 12.5f * s, 1.8f * s, p);
                break;

            case ICON_FIND_DOC:
                rf.set(5f * s, 4f * s, 17f * s, 19f * s);
                c.drawRoundRect(rf, 2f * s, 2f * s, p);
                c.drawLine(8f * s, 8f * s, 13f * s, 8f * s, p);
                c.drawLine(8f * s, 11.5f * s, 11.5f * s, 11.5f * s, p);
                c.drawCircle(14.5f * s, 14.5f * s, 3.0f * s, p);
                c.drawLine(16.8f * s, 16.8f * s, 19.5f * s, 19.5f * s, p);
                break;

            case ICON_TRANSLATE:
                rf.set(3.8f * s, 4.2f * s, 14.2f * s, 14.2f * s);
                c.drawRoundRect(rf, 2f * s, 2f * s, p);
                c.drawLine(6.5f * s, 7.5f * s, 11.5f * s, 7.5f * s, p);
                c.drawLine(9f * s, 6f * s, 9f * s, 11.5f * s, p);
                rf.set(9.8f * s, 9.8f * s, 20.2f * s, 19.8f * s);
                c.drawRoundRect(rf, 2f * s, 2f * s, p);
                c.drawLine(13f * s, 16.5f * s, 15f * s, 12.5f * s, p);
                c.drawLine(17f * s, 16.5f * s, 15f * s, 12.5f * s, p);
                break;

            case ICON_ADD_HOME:
                rf.set(5.5f * s, 4f * s, 17.5f * s, 19.5f * s);
                c.drawRoundRect(rf, 2.2f * s, 2.2f * s, p);
                c.drawCircle(16.5f * s, 16.5f * s, 4.0f * s, p);
                c.drawLine(14.7f * s, 16.5f * s, 18.3f * s, 16.5f * s, p);
                c.drawLine(16.5f * s, 14.7f * s, 16.5f * s, 18.3f * s, p);
                break;

            case ICON_WINDOW_MGR:
                rf.set(4.5f * s, 4.5f * s, 14.5f * s, 14.5f * s);
                c.drawRoundRect(rf, 2f * s, 2f * s, p);
                rf.set(9.5f * s, 9.5f * s, 19.5f * s, 19.5f * s);
                c.drawRoundRect(rf, 2f * s, 2f * s, p);
                c.drawLine(12.5f * s, 14.5f * s, 16.5f * s, 14.5f * s, p);
                c.drawLine(14.5f * s, 12.5f * s, 14.5f * s, 16.5f * s, p);
                break;

            case ICON_VIDEO_ENHANCE:
                rf.set(4f * s, 4f * s, 20f * s, 20f * s);
                c.drawArc(rf, 35f, 300f, false, p);
                path.moveTo(10.2f * s, 8.8f * s);
                path.lineTo(15.2f * s, 12f * s);
                path.lineTo(10.2f * s, 15.2f * s);
                path.close();
                c.drawPath(path, p);
                break;

            case ICON_ZOOM_PLUS:
                c.drawCircle(10.8f * s, 10.8f * s, 6.0f * s, p);
                c.drawLine(15.2f * s, 15.2f * s, 19.5f * s, 19.5f * s, p);
                c.drawLine(8.3f * s, 10.8f * s, 13.3f * s, 10.8f * s, p);
                c.drawLine(10.8f * s, 8.3f * s, 10.8f * s, 13.3f * s, p);
                break;

            case ICON_DEVTOOLS_CODE:
                path.moveTo(9.2f * s, 7.5f * s);
                path.lineTo(4.8f * s, 12f * s);
                path.lineTo(9.2f * s, 16.5f * s);
                c.drawPath(path, p);
                path.reset();
                path.moveTo(14.8f * s, 7.5f * s);
                path.lineTo(19.2f * s, 12f * s);
                path.lineTo(14.8f * s, 16.5f * s);
                c.drawPath(path, p);
                break;

            case ICON_CHEVRON_UP:
                path.moveTo(6.5f * s, 14.5f * s);
                path.lineTo(12f * s, 9.0f * s);
                path.lineTo(17.5f * s, 14.5f * s);
                c.drawPath(path, p);
                break;

            case ICON_CHEVRON_DOWN:
                path.moveTo(6.5f * s, 9.5f * s);
                path.lineTo(12f * s, 15.0f * s);
                path.lineTo(17.5f * s, 9.5f * s);
                c.drawPath(path, p);
                break;
        }
        return new BitmapDrawable(mContext.getResources(), bmp);
    }

    private Drawable createChromeStoreDrawable() {
        float d = mContext.getResources().getDisplayMetrics().density;
        int px = Math.max(28, Math.round(28f * d));
        Bitmap bmp = Bitmap.createBitmap(px, px, Bitmap.Config.ARGB_8888);
        Canvas c = new Canvas(bmp);
        float s = px / 28f;
        Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        RectF bag = new RectF(3f * s, 4f * s, 25f * s, 24f * s);
        p.setStyle(Paint.Style.FILL);
        p.setColor(0xFFF1F3F4);
        c.drawRoundRect(bag, 3.5f * s, 3.5f * s, p);
        p.setColor(0xFF9AA0A6);
        c.drawRoundRect(new RectF(10f * s, 6.5f * s, 18f * s, 9f * s), 1.2f * s, 1.2f * s, p);
        p.setColor(0xFFEA4335);
        c.drawArc(new RectF(7f * s, 11f * s, 21f * s, 25f * s), 180f, 180f, true, p);
        p.setColor(0xFFFBBC04);
        c.drawArc(new RectF(7f * s, 11f * s, 21f * s, 25f * s), 280f, 80f, true, p);
        p.setColor(0xFF34A853);
        c.drawArc(new RectF(7f * s, 11f * s, 21f * s, 25f * s), 180f, 65f, true, p);
        p.setColor(0xFFFFFFFF);
        c.drawCircle(14f * s, 18f * s, 3.8f * s, p);
        p.setColor(0xFF4285F4);
        c.drawCircle(14f * s, 18f * s, 2.8f * s, p);
        return new BitmapDrawable(mContext.getResources(), bmp);
    }

    private Drawable createLemurEmptyExtensionsDrawable(boolean isNight) {
        float d = mContext.getResources().getDisplayMetrics().density;
        int w = Math.max(120, Math.round(140f * d));
        int h = Math.max(96, Math.round(110f * d));
        Bitmap bmp = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888);
        Canvas c = new Canvas(bmp);
        float s = w / 140f;
        Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);

        int badgeBg = isNight ? 0xFF38393E : 0xFFE4E7EE;
        int badgeFg = isNight ? 0xFF9AA0A6 : 0xFF5F6368;
        p.setStyle(Paint.Style.FILL);
        p.setColor(badgeBg);
        c.drawCircle(86f * s, 22f * s, 11f * s, p);
        c.drawCircle(76f * s, 46f * s, 12f * s, p);
        c.drawCircle(94f * s, 66f * s, 11f * s, p);

        p.setColor(badgeFg);
        c.drawRoundRect(new RectF(81f * s, 17f * s, 91f * s, 27f * s), 2f * s, 2f * s, p);
        c.drawRoundRect(new RectF(71f * s, 41f * s, 81f * s, 51f * s), 2f * s, 2f * s, p);
        c.drawRoundRect(new RectF(89f * s, 61f * s, 99f * s, 71f * s), 2f * s, 2f * s, p);

        p.setColor(0xFFFF9800);
        c.drawRoundRect(new RectF(42f * s, 52f * s, 66f * s, 86f * s), 8f * s, 8f * s, p);
        p.setColor(isNight ? 0xFFE8D5C4 : 0xFFF5CBA7);
        c.drawCircle(54f * s, 38f * s, 9f * s, p);
        return new BitmapDrawable(mContext.getResources(), bmp);
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

    ctor_anchor = "        mAppMenuDelegate = appMenuDelegate;\n"
    ctor_replacement = (
        "        mAppMenuDelegate = appMenuDelegate;\n"
        "        registerLemurExtensionsMenuOpener();\n"
    )
    if "registerLemurExtensionsMenuOpener();" not in text:
        if ctor_anchor not in text:
            raise SystemExit(f"mAppMenuDelegate constructor anchor not found in {path}")
        text = text.replace(ctor_anchor, ctor_replacement, 1)

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
    patch_menu_button(src_dir)
    patch_extensions_toolbar_coordinator(src_dir)
    patch_extensions_toolbar_coordinator_impl(src_dir)
    patch_extensions_menu_coordinator(src_dir)
    patch_extensions_menu_mediator(src_dir)
    patch_app_menu_properties_delegate(src_dir)
    patch_app_menu_handler_impl(src_dir)
    patch_tabbed_app_menu_delegate(src_dir)
    print(f"Successfully applied Lemur-style toolbar icons, 3-line menu, and 4-square extensions sheet in {src_dir}")


if __name__ == "__main__":
    main()
