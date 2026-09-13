#!/usr/bin/env python3

from pathlib import Path
import sys


if len(sys.argv) != 5:
    raise SystemExit(
        "usage: patch_extension_popup_width.py POPUP_JAVA CONTENTS_JAVA "
        "CONTENTS_CC CONTENTS_H"
    )


def replace_if_missing(path, text, marker, old, new):
    if marker in text:
        return text
    if old not in text:
        raise SystemExit(f"Extension popup width pattern not found in {path}: {marker}")
    return text.replace(old, new, 1)


popup = Path(sys.argv[1])
java_contents = Path(sys.argv[2])
native_contents = Path(sys.argv[3])
native_header = Path(sys.argv[4])

popup_text = popup.read_text()
popup_text = replace_if_missing(
    popup,
    popup_text,
    "import android.content.Context;",
    "import android.app.Activity;\n",
    "import android.app.Activity;\nimport android.content.Context;\n",
)
popup_text = replace_if_missing(
    popup,
    popup_text,
    "import android.graphics.Rect;",
    "import android.graphics.Color;\n",
    "import android.graphics.Color;\nimport android.graphics.Rect;\n",
)
popup_text = popup_text.replace(
    "import android.graphics.drawable.ColorDrawable;\nimport android.graphics.Rect;\n",
    "import android.graphics.Rect;\nimport android.graphics.drawable.ColorDrawable;\n",
    1,
)
popup_text = replace_if_missing(
    popup,
    popup_text,
    "import android.widget.FrameLayout;",
    "import android.widget.PopupWindow.OnDismissListener;\n",
    "import android.widget.FrameLayout;\nimport android.widget.PopupWindow.OnDismissListener;\n",
)
popup_text = replace_if_missing(
    popup,
    popup_text,
    "private static final int POPUP_EDGE_MARGIN_DP = 8;",
    "class ExtensionActionPopup implements Destroyable {\n",
    "class ExtensionActionPopup implements Destroyable {\n"
    "    private static final int POPUP_EDGE_MARGIN_DP = 8;\n",
)
old_popup_size = (
    "        Resources resources = mActivity.getResources();\n"
    "        int popupMarginPx = ViewUtils.dpToPx(mActivity, POPUP_EDGE_MARGIN_DP);\n"
    "        View rootView = mActivity.getWindow().getDecorView();\n"
    "        int rootViewWidthPx = rootView.getWidth();\n"
    "        if (rootViewWidthPx <= 0) {\n"
    "            rootViewWidthPx = resources.getDisplayMetrics().widthPixels;\n"
    "        }\n"
    "        int maxContentWidthPx = Math.max(rootViewWidthPx - 2 * popupMarginPx, 1);\n"
    "        int maxContentWidthDp =\n"
    "                Math.max(\n"
    "                        (int)\n"
    "                                (maxContentWidthPx\n"
    "                                        / resources.getDisplayMetrics().density),\n"
    "                        1);\n"
    "        mContents.setMaxWidth(maxContentWidthDp);\n"
    "        mPopupWindow.setMargin(popupMarginPx);\n"
    "        mPopupWindow.setElevation(\n"
)
new_popup_size = (
    "        Resources resources = mActivity.getResources();\n"
    "        int popupMarginPx = ViewUtils.dpToPx(mActivity, POPUP_EDGE_MARGIN_DP);\n"
    "        View rootView = mActivity.getWindow().getDecorView();\n"
    "        Rect visibleWindowRect = new Rect();\n"
    "        rootView.getWindowVisibleDisplayFrame(visibleWindowRect);\n"
    "        int[] rootLocationOnScreen = new int[2];\n"
    "        rootView.getLocationOnScreen(rootLocationOnScreen);\n"
    "        visibleWindowRect.offset(-rootLocationOnScreen[0], -rootLocationOnScreen[1]);\n"
    "        if (visibleWindowRect.isEmpty()) {\n"
    "            int rootWidthPx =\n"
    "                    rootView.getWidth() > 0\n"
    "                            ? rootView.getWidth()\n"
    "                            : resources.getDisplayMetrics().widthPixels;\n"
    "            int rootHeightPx =\n"
    "                    rootView.getHeight() > 0\n"
    "                            ? rootView.getHeight()\n"
    "                            : resources.getDisplayMetrics().heightPixels;\n"
    "            visibleWindowRect.set(0, 0, rootWidthPx, rootHeightPx);\n"
    "        }\n"
    "        int[] rootLocationInWindow = new int[2];\n"
    "        int[] anchorLocationInWindow = new int[2];\n"
    "        rootView.getLocationInWindow(rootLocationInWindow);\n"
    "        anchorView.getLocationInWindow(anchorLocationInWindow);\n"
    "        int anchorTopPx = anchorLocationInWindow[1] - rootLocationInWindow[1];\n"
    "        int anchorBottomPx = anchorTopPx + anchorView.getHeight();\n"
    "        int availableAbovePx = anchorTopPx - visibleWindowRect.top - popupMarginPx;\n"
    "        int availableBelowPx = visibleWindowRect.bottom - anchorBottomPx - popupMarginPx;\n"
    "        int maxContentWidthPx =\n"
    "                Math.max(visibleWindowRect.width() - 2 * popupMarginPx, 1);\n"
    "        int maxContentHeightPx =\n"
    "                Math.max(Math.max(availableAbovePx, availableBelowPx), 1);\n"
    "        float density = resources.getDisplayMetrics().density;\n"
    "        int maxContentWidthDp = Math.max((int) (maxContentWidthPx / density), 1);\n"
    "        int maxContentHeightDp = Math.max((int) (maxContentHeightPx / density), 1);\n"
    "        mContents.setMaxSize(maxContentWidthDp, maxContentHeightDp);\n"
    "        mPopupWindow.setMargin(popupMarginPx);\n"
    "        mPopupWindow.setElevation(\n"
)
popup_text = popup_text.replace(old_popup_size, new_popup_size, 1)
popup_text = replace_if_missing(
    popup,
    popup_text,
    "mContents.setMaxSize(maxContentWidthDp, maxContentHeightDp);",
    "        Resources resources = mActivity.getResources();\n"
    "        mPopupWindow.setElevation(\n",
    new_popup_size,
)
popup_text = replace_if_missing(
    popup,
    popup_text,
    "private final ScaledContentView mScaledContentView;",
    "    private final ThinWebView mThinWebView;\n",
    "    private final ThinWebView mThinWebView;\n\n"
    "    /** Keeps the renderer at its original size while displaying it proportionally scaled. */\n"
    "    private final ScaledContentView mScaledContentView;\n",
)
popup_text = replace_if_missing(
    popup,
    popup_text,
    "mScaledContentView = new ScaledContentView(activity, mThinWebView.getView());",
    "        mPopupWindow =\n"
    "                new AnchoredPopupWindow(\n"
    "                        activity,\n"
    "                        activity.getWindow().getDecorView(),\n"
    "                        new ColorDrawable(Color.WHITE),\n"
    "                        mThinWebView.getView(),\n"
    "                        new ViewRectProvider(anchorView));\n",
    "        mScaledContentView = new ScaledContentView(activity, mThinWebView.getView());\n"
    "        mPopupWindow =\n"
    "                new AnchoredPopupWindow(\n"
    "                        activity,\n"
    "                        activity.getWindow().getDecorView(),\n"
    "                        new ColorDrawable(Color.WHITE),\n"
    "                        mScaledContentView,\n"
    "                        new ViewRectProvider(anchorView));\n",
)
old_initial_size = (
    "        // Set the content size to the minimum initially.\n"
    "        mPopupWindow.setDesiredContentSize(\n"
    "                resources.getDimensionPixelSize(R.dimen.extension_action_popup_min_width),\n"
    "                resources.getDimensionPixelSize(R.dimen.extension_action_popup_min_height));\n"
)
new_initial_size = (
    "        // Set the content size to the minimum initially.\n"
    "        int initialWidthPx =\n"
    "                resources.getDimensionPixelSize(R.dimen.extension_action_popup_min_width);\n"
    "        int initialHeightPx =\n"
    "                resources.getDimensionPixelSize(R.dimen.extension_action_popup_min_height);\n"
    "        mScaledContentView.setContentSize(initialWidthPx, initialHeightPx, 1.0f);\n"
    "        mPopupWindow.setDesiredContentSize(initialWidthPx, initialHeightPx);\n"
)
popup_text = popup_text.replace(old_initial_size, new_initial_size, 1)
old_resize_delegate = (
    "        public void resizeDueToAutoResize(int width, int height) {\n"
    "            if (Build.VERSION.SDK_INT >= 34) {\n"
    "                // Disable transition animations for the popup window. On Android, {@link\n"
    "                // onLoaded()} is called first, and then {@link resizeDueToAutoResize()} is called.\n"
    "                // A transition would result in a sliding animation from the original bounds to the\n"
    "                // updated bounds.\n"
    "                // TODO(crbug.com/478100096): Figure out what to do for lower API levels.\n"
    "                ((WindowManager.LayoutParams) mContentView.getRootView().getLayoutParams())\n"
    "                        .setCanPlayMoveAnimation(false);\n"
    "            }\n\n"
    "            mPopupWindow.setDesiredContentSize(\n"
    "                    ViewUtils.dpToPx(mActivity, width), ViewUtils.dpToPx(mActivity, height));\n"
    "        }\n"
)
old_resize_delegate_153 = (
    "        public void resizeDueToAutoResize(int width, int height) {\n"
    "            if (Build.VERSION.SDK_INT >= 34) {\n"
    "                // Disable transition animations for the popup window. On Android, {@link\n"
    "                // onLoaded()} is called first, and then {@link resizeDueToAutoResize()} is called.\n"
    "                // A transition would result in a sliding animation from the original bounds to the\n"
    "                // updated bounds.\n"
    "                // TODO(crbug.com/478100096): Figure out what to do for lower API levels.\n"
    "                ((WindowManager.LayoutParams) mContentView.getRootView().getLayoutParams())\n"
    "                        .setCanPlayMoveAnimation(false);\n"
    "            }\n\n"
    "            int targetWidthPx = ViewUtils.dpToPx(mActivity, width);\n"
    "            int targetHeightPx = ViewUtils.dpToPx(mActivity, height);\n\n"
    "            View decorView = mActivity.getWindow().getDecorView();\n"
    "            int maxAvailableWidthPx = decorView.getWidth();\n"
    "            int maxAvailableHeightPx = decorView.getHeight();\n\n"
    "            if (maxAvailableWidthPx > 0) {\n"
    "                targetWidthPx = Math.min(targetWidthPx, maxAvailableWidthPx);\n"
    "            }\n"
    "            if (maxAvailableHeightPx > 0) {\n"
    "                targetHeightPx = Math.min(targetHeightPx, maxAvailableHeightPx);\n"
    "            }\n\n"
    "            mPopupWindow.setDesiredContentSize(targetWidthPx, targetHeightPx);\n"
    "        }\n"
)
new_resize_delegate = (
    "        public void resizeDueToAutoResize(int width, int height, float scale) {\n"
    "            if (Build.VERSION.SDK_INT >= 34) {\n"
    "                // Disable transition animations for the popup window. On Android, {@link\n"
    "                // onLoaded()} is called first, and then {@link resizeDueToAutoResize()} is called.\n"
    "                // A transition would result in a sliding animation from the original bounds to the\n"
    "                // updated bounds.\n"
    "                // TODO(crbug.com/478100096): Figure out what to do for lower API levels.\n"
    "                ((WindowManager.LayoutParams) mContentView.getRootView().getLayoutParams())\n"
    "                        .setCanPlayMoveAnimation(false);\n"
    "            }\n\n"
    "            int contentWidthPx = ViewUtils.dpToPx(mActivity, width);\n"
    "            int contentHeightPx = ViewUtils.dpToPx(mActivity, height);\n"
    "            mScaledContentView.setContentSize(contentWidthPx, contentHeightPx, scale);\n"
    "            mPopupWindow.setDesiredContentSize(\n"
    "                    Math.max(Math.round(contentWidthPx * scale), 1),\n"
    "                    Math.max(Math.round(contentHeightPx * scale), 1));\n"
    "        }\n"
)
popup_text = popup_text.replace(old_resize_delegate, new_resize_delegate, 1).replace(old_resize_delegate_153, new_resize_delegate, 1)
scaled_content_view = (
    "    private static class ScaledContentView extends FrameLayout {\n"
    "        private final View mChildView;\n"
    "        private int mContentWidthPx = 1;\n"
    "        private int mContentHeightPx = 1;\n"
    "        private float mScale = 1.0f;\n\n"
    "        ScaledContentView(Context context, View childView) {\n"
    "            super(context);\n"
    "            mChildView = childView;\n"
    "            mChildView.setPivotX(0.0f);\n"
    "            mChildView.setPivotY(0.0f);\n"
    "            addView(mChildView, new FrameLayout.LayoutParams(1, 1));\n"
    "        }\n\n"
    "        void setContentSize(int widthPx, int heightPx, float scale) {\n"
    "            mContentWidthPx = Math.max(widthPx, 1);\n"
    "            mContentHeightPx = Math.max(heightPx, 1);\n"
    "            mScale = Math.min(Math.max(scale, 0.01f), 1.0f);\n"
    "            mChildView.setScaleX(mScale);\n"
    "            mChildView.setScaleY(mScale);\n"
    "            requestLayout();\n"
    "        }\n\n"
    "        @Override\n"
    "        protected void onMeasure(int widthMeasureSpec, int heightMeasureSpec) {\n"
    "            mChildView.measure(\n"
    "                    View.MeasureSpec.makeMeasureSpec(\n"
    "                            mContentWidthPx, View.MeasureSpec.EXACTLY),\n"
    "                    View.MeasureSpec.makeMeasureSpec(\n"
    "                            mContentHeightPx, View.MeasureSpec.EXACTLY));\n"
    "            int scaledWidthPx = Math.max(Math.round(mContentWidthPx * mScale), 1);\n"
    "            int scaledHeightPx = Math.max(Math.round(mContentHeightPx * mScale), 1);\n"
    "            setMeasuredDimension(\n"
    "                    resolveSize(scaledWidthPx, widthMeasureSpec),\n"
    "                    resolveSize(scaledHeightPx, heightMeasureSpec));\n"
    "        }\n\n"
    "        @Override\n"
    "        protected void onLayout(boolean changed, int left, int top, int right, int bottom) {\n"
    "            mChildView.layout(0, 0, mContentWidthPx, mContentHeightPx);\n"
    "        }\n"
    "    }\n\n"
)
popup_text = replace_if_missing(
    popup,
    popup_text,
    "private static class ScaledContentView extends FrameLayout",
    "    private class ContentsDelegate implements ExtensionActionPopupContents.Delegate {\n",
    scaled_content_view
    + "    private class ContentsDelegate implements ExtensionActionPopupContents.Delegate {\n",
)
java_text = java_contents.read_text()
old_java_set_max_width = (
    "    /** Sets the maximum displayed popup width in device-independent pixels. */\n"
    "    public void setMaxWidth(int maxWidth) {\n"
    "        assert mNativeExtensionActionPopupContents != 0;\n"
    "        ExtensionActionPopupContentsJni.get()\n"
    "                .setMaxWidth(mNativeExtensionActionPopupContents, maxWidth);\n"
    "    }\n"
)
new_java_set_max_size = (
    "    /** Sets the maximum displayed popup size in device-independent pixels. */\n"
    "    public void setMaxSize(int maxWidth, int maxHeight) {\n"
    "        assert mNativeExtensionActionPopupContents != 0;\n"
    "        ExtensionActionPopupContentsJni.get()\n"
    "                .setMaxSize(mNativeExtensionActionPopupContents, maxWidth, maxHeight);\n"
    "    }\n"
)
java_text = java_text.replace(old_java_set_max_width, new_java_set_max_size, 1)
java_text = replace_if_missing(
    java_contents,
    java_text,
    "public void setMaxSize(int maxWidth, int maxHeight)",
    "    /**\n"
    "     * Instructs to load the initial page for the extension popup into its {@link WebContents}.\n",
    new_java_set_max_size
    + "\n"
    "    /**\n"
    "     * Instructs to load the initial page for the extension popup into its {@link WebContents}.\n",
)
old_jni_set_max_width = (
    "        /** Sets the maximum displayed popup width in device-independent pixels. */\n"
    "        void setMaxWidth(\n"
    "                long nativeExtensionActionPopupContents, int maxWidth);\n"
)
new_jni_set_max_size = (
    "        /** Sets the maximum displayed popup size in device-independent pixels. */\n"
    "        void setMaxSize(\n"
    "                long nativeExtensionActionPopupContents, int maxWidth, int maxHeight);\n"
)
java_text = java_text.replace(old_jni_set_max_width, new_jni_set_max_size, 1)
java_text = replace_if_missing(
    java_contents,
    java_text,
    "long nativeExtensionActionPopupContents, int maxWidth, int maxHeight);",
    "        /**\n"
    "         * Triggers the loading of the initial URL in the native ExtensionActionPopupContents.\n",
    new_jni_set_max_size
    + "\n"
    "        /**\n"
    "         * Triggers the loading of the initial URL in the native ExtensionActionPopupContents.\n",
)
old_java_resize_callback = (
    "    @CalledByNative\n"
    "    private void resizeDueToAutoResize(int width, int height) {\n"
    "        if (mDelegate != null) {\n"
    "            mDelegate.resizeDueToAutoResize(width, height);\n"
    "        }\n"
    "    }\n"
)
new_java_resize_callback = (
    "    @CalledByNative\n"
    "    private void resizeDueToAutoResize(int width, int height, float scale) {\n"
    "        if (mDelegate != null) {\n"
    "            mDelegate.resizeDueToAutoResize(width, height, scale);\n"
    "        }\n"
    "    }\n"
)
java_text = java_text.replace(old_java_resize_callback, new_java_resize_callback, 1)
java_text = replace_if_missing(
    java_contents,
    java_text,
    "void resizeDueToAutoResize(int width, int height, float scale);",
    "        void resizeDueToAutoResize(int width, int height);\n",
    "        void resizeDueToAutoResize(int width, int height, float scale);\n",
)

header_text = native_header.read_text()
header_text = header_text.replace(
    "  void SetMaxWidth(JNIEnv* env, int max_width);\n",
    "  void SetMaxSize(JNIEnv* env, int max_width, int max_height);\n",
    1,
)
header_text = replace_if_missing(
    native_header,
    header_text,
    "void SetMaxSize(JNIEnv* env, int max_width, int max_height);",
    "  void LoadInitialPage(JNIEnv* env);\n",
    "  void LoadInitialPage(JNIEnv* env);\n\n"
    "  void SetMaxSize(JNIEnv* env, int max_width, int max_height);\n",
)
old_header_size = (
    "  // Maximum displayed popup width in device-independent pixels.\n"
    "  int max_width_ = 800;\n"
)
new_header_size = (
    "  // Maximum displayed popup size in device-independent pixels.\n"
    "  int max_width_ = 800;\n"
    "  int max_height_ = 600;\n"
)
header_text = header_text.replace(old_header_size, new_header_size, 1)
header_text = replace_if_missing(
    native_header,
    header_text,
    "int max_height_ = 600;",
    "  std::unique_ptr<ExtensionViewHost> host_;\n",
    "  std::unique_ptr<ExtensionViewHost> host_;\n"
    + new_header_size,
)
header_text = header_text.replace(
    "  // Maximum content width in CSS/device-independent pixels.\n",
    "  // Maximum displayed popup size in device-independent pixels.\n",
    1,
)
native_text = native_contents.read_text()
if "#include <algorithm>" not in native_text:
    anchor = '#include "chrome/browser/ui/android/extensions/extension_action_popup_contents.h"\n'
    if anchor not in native_text:
        raise SystemExit(f"Extension popup include anchor not found in {native_contents}")
    native_text = native_text.replace(anchor, anchor + "\n#include <algorithm>\n", 1)
if "#include <cmath>" not in native_text:
    native_text = native_text.replace(
        "#include <algorithm>\n", "#include <algorithm>\n#include <cmath>\n", 1
    )
native_text = native_text.replace(
    "constexpr gfx::Size kMinSize = {25, 25};",
    "constexpr gfx::Size kMinSize = {256, 25};",
    1,
)
old_set_max_width_with_frame = (
    "void ExtensionActionPopupContents::SetMaxWidth(JNIEnv* env, int max_width) {\n"
    "  max_width_ = std::clamp(max_width, 1, kMaxSize.width());\n"
    "  RenderFrameHost* main_frame =\n"
    "      host_->host_contents()->GetPrimaryMainFrame();\n"
    "  if (main_frame->IsRenderFrameLive()) {\n"
    "    SetUpNewMainFrame(main_frame);\n"
    "  }\n"
    "}\n"
)
old_set_max_width = (
    "void ExtensionActionPopupContents::SetMaxWidth(JNIEnv* env, int max_width) {\n"
    "  max_width_ = std::clamp(max_width, 1, kMaxSize.width());\n"
    "}\n"
)
new_set_max_size = (
    "void ExtensionActionPopupContents::SetMaxSize(\n"
    "    JNIEnv* env,\n"
    "    int max_width,\n"
    "    int max_height) {\n"
    "  max_width_ = std::clamp(max_width, 1, kMaxSize.width());\n"
    "  max_height_ = std::clamp(max_height, 1, kMaxSize.height());\n"
    "}\n"
)
native_text = native_text.replace(old_set_max_width_with_frame, new_set_max_size, 1)
native_text = native_text.replace(old_set_max_width, new_set_max_size, 1)
native_text = replace_if_missing(
    native_contents,
    native_text,
    new_set_max_size,
    "void ExtensionActionPopupContents::LoadInitialPage(JNIEnv* env) {\n"
    "  host_->CreateRendererSoon();\n"
    "}\n",
    "void ExtensionActionPopupContents::LoadInitialPage(JNIEnv* env) {\n"
    "  host_->CreateRendererSoon();\n"
    "}\n\n"
    + new_set_max_size,
)
old_resize = (
    "void ExtensionActionPopupContents::ResizeDueToAutoResize(\n"
    "    content::WebContents* web_contents,\n"
    "    const gfx::Size& new_size) {\n"
    "  Java_ExtensionActionPopupContents_resizeDueToAutoResize(\n"
    "      AttachCurrentThread(), java_object_, new_size.width(), new_size.height());\n"
    "}\n"
)
old_scaled_resize = (
    "void ExtensionActionPopupContents::ResizeDueToAutoResize(\n"
    "    content::WebContents* web_contents,\n"
    "    const gfx::Size& new_size) {\n"
    "  const float scale =\n"
    "      new_size.width() > max_width_\n"
    "          ? static_cast<float>(max_width_) / new_size.width()\n"
    "          : 1.0f;\n"
    "  web_contents->SetPageScale(scale);\n"
    "  const int popup_width = std::max(\n"
    "      1, static_cast<int>(std::lround(new_size.width() * scale)));\n"
    "  const int popup_height = std::max(\n"
    "      1, static_cast<int>(std::lround(new_size.height() * scale)));\n"
    "  Java_ExtensionActionPopupContents_resizeDueToAutoResize(\n"
    "      AttachCurrentThread(), java_object_, popup_width, popup_height);\n"
    "}\n"
)
new_resize = (
    "void ExtensionActionPopupContents::ResizeDueToAutoResize(\n"
    "    content::WebContents* web_contents,\n"
    "    const gfx::Size& new_size) {\n"
    "  const float width_scale =\n"
    "      static_cast<float>(max_width_) / new_size.width();\n"
    "  const float height_scale =\n"
    "      static_cast<float>(max_height_) / new_size.height();\n"
    "  const float scale = std::min({1.0f, width_scale, height_scale});\n"
    "  web_contents->SetPageScale(scale);\n"
    "  const int popup_width = std::max(\n"
    "      1, static_cast<int>(std::lround(new_size.width() * scale)));\n"
    "  const int popup_height = std::max(\n"
    "      1, static_cast<int>(std::lround(new_size.height() * scale)));\n"
    "  Java_ExtensionActionPopupContents_resizeDueToAutoResize(\n"
    "      AttachCurrentThread(), java_object_, popup_width, popup_height);\n"
    "}\n"
)
native_text = native_text.replace(old_scaled_resize, new_resize, 1)
native_text = replace_if_missing(
    native_contents,
    native_text,
    "const float height_scale =",
    old_resize,
    new_resize,
)
view_scaled_resize = (
    "void ExtensionActionPopupContents::ResizeDueToAutoResize(\n"
    "    content::WebContents* web_contents,\n"
    "    const gfx::Size& new_size) {\n"
    "  const float width_scale =\n"
    "      static_cast<float>(max_width_) / new_size.width();\n"
    "  const float height_scale =\n"
    "      static_cast<float>(max_height_) / new_size.height();\n"
    "  const float scale = std::min({1.0f, width_scale, height_scale});\n"
    "  Java_ExtensionActionPopupContents_resizeDueToAutoResize(\n"
    "      AttachCurrentThread(), java_object_, new_size.width(), new_size.height(),\n"
    "      scale);\n"
    "}\n"
)
native_text = native_text.replace(new_resize, view_scaled_resize, 1)
native_text = native_text.replace("#include <cmath>\n", "", 1)
old_auto_resize = (
    "  const gfx::Size max_size(max_width_, kMaxSize.height());\n"
    "  const gfx::Size min_size(std::min(kMinSize.width(), max_width_),\n"
    "                           kMinSize.height());\n"
    "  render_frame_host->GetView()->EnableAutoResize(min_size, max_size);\n"
)
native_text = native_text.replace(
    old_auto_resize,
    "  render_frame_host->GetView()->EnableAutoResize(kMinSize, kMaxSize);\n",
    1,
)
required = (
    "constexpr gfx::Size kMinSize = {256, 25};",
    new_set_max_size,
    "new_size.height(),\n      scale);",
    "EnableAutoResize(kMinSize, kMaxSize);",
)
for marker in required:
    if marker not in native_text:
        raise SystemExit(f"Extension popup width marker missing in {native_contents}: {marker}")
if "SetPageScale(scale)" in native_text:
    raise SystemExit(f"Renderer page scaling was not removed from {native_contents}")

required_outputs = (
    (
        popup,
        popup_text,
        (
            "private static class ScaledContentView extends FrameLayout",
            "mScaledContentView = new ScaledContentView(activity, mThinWebView.getView());",
            "resizeDueToAutoResize(int width, int height, float scale)",
        ),
    ),
    (
        java_contents,
        java_text,
        (
            "private void resizeDueToAutoResize(int width, int height, float scale)",
            "void resizeDueToAutoResize(int width, int height, float scale);",
        ),
    ),
)
for path, text, markers in required_outputs:
    for marker in markers:
        if marker not in text:
            raise SystemExit(f"Extension popup view scaling marker missing in {path}: {marker}")

popup.write_text(popup_text)
java_contents.write_text(java_text)
native_contents.write_text(native_text)
native_header.write_text(header_text)
