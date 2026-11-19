#!/usr/bin/env python3
"""Provide the in-omnibox back button on wide screens in old-android builds.

The location bar children come from a <merge> layout that has two variants. The
default one includes omnibox_back_button.xml, the layout-sw600dp one does not,
because upstream tablets use LocationBarTablet and never report a back button in
the omnibox. old-android builds keep LocationBarPhone (and the refactored
toolbar) on wide car screens, so LocationBarPhone.mBackButton stays null and
LocationBarMediator.updateBackButtonVisibility() crashes the activity with an
NPE on setBackButtonVisibility(). Add the missing include and treat the view as
optional in code.
"""
import os
import sys

LAYOUT = "chrome/browser/ui/android/omnibox/java/res/layout-sw600dp/location_bar.xml"
LAYOUT_OLD = """    <include layout="@layout/location_status"/>
"""
LAYOUT_NEW = """    <include layout="@layout/omnibox_back_button"/>
    <include layout="@layout/location_status"/>
"""
LAYOUT_MARKER = """    <include layout="@layout/omnibox_back_button"/>
"""

JAVA = (
    "chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/"
    "LocationBarPhone.java"
)
JAVA_EDITS = (
    (
        """    protected ImageButton mBackButton;
""",
        """    protected @Nullable ImageButton mBackButton;
""",
    ),
    (
        """    @Override
    protected boolean isBackButtonVisible() {
        return mBackButton.getVisibility() == View.VISIBLE;
    }
""",
        """    @Override
    protected boolean isBackButtonVisible() {
        // Helium: the back button is absent from layouts that do not include it.
        ImageButton backButton = mBackButton;
        return backButton != null && backButton.getVisibility() == View.VISIBLE;
    }
""",
    ),
    (
        """    @Override
    /* package */ void setBackButtonVisibility(boolean shouldShow) {
        mBackButton.setVisibility(shouldShow ? VISIBLE : GONE);
        updateStartPadding();
    }
""",
        """    @Override
    /* package */ void setBackButtonVisibility(boolean shouldShow) {
        // Helium: the back button is absent from layouts that do not include it.
        ImageButton backButton = mBackButton;
        if (backButton == null) return;
        backButton.setVisibility(shouldShow ? VISIBLE : GONE);
        updateStartPadding();
    }
""",
    ),
    (
        """    @Override
    /* package */ void setBackButtonEnabled(boolean enabled) {
        mBackButton.setEnabled(enabled);
    }
""",
        """    @Override
    /* package */ void setBackButtonEnabled(boolean enabled) {
        ImageButton backButton = mBackButton;
        if (backButton == null) return;
        backButton.setEnabled(enabled);
    }
""",
    ),
    (
        """    @Override
    /* package */ void setBackButtonTint(ColorStateList colorStateList) {
        ImageViewCompat.setImageTintList(mBackButton, colorStateList);
    }
""",
        """    @Override
    /* package */ void setBackButtonTint(ColorStateList colorStateList) {
        ImageButton backButton = mBackButton;
        if (backButton == null) return;
        ImageViewCompat.setImageTintList(backButton, colorStateList);
    }
""",
    ),
    (
        """        ConstraintLayout.LayoutParams backButtonParams =
                (ConstraintLayout.LayoutParams) mBackButton.getLayoutParams();
""",
        """        ImageButton backButton = mBackButton;
        if (backButton == null) return;

        ConstraintLayout.LayoutParams backButtonParams =
                (ConstraintLayout.LayoutParams) backButton.getLayoutParams();
""",
    ),
    (
        """        mBackButton.setLayoutParams(backButtonParams);
    }
""",
        """        backButton.setLayoutParams(backButtonParams);
    }
""",
    ),
    (
        """            int backButtonWidth = getMeasuredWidthWithMargins(mBackButton, heightMeasureSpec);
""",
        """            ImageButton backButton = mBackButton;
            int backButtonWidth =
                    backButton != null
                            ? getMeasuredWidthWithMargins(backButton, heightMeasureSpec)
                            : 0;
""",
    ),
)
JAVA_MARKER = "ImageButton backButton = mBackButton;"


def patch_layout(src_dir: str) -> bool:
    path = os.path.join(src_dir, LAYOUT)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read()

    if LAYOUT_MARKER in content:
        return False
    if LAYOUT_OLD not in content:
        raise RuntimeError(f"location status include not found in {path}")

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content.replace(LAYOUT_OLD, LAYOUT_NEW, 1))
    print(f"Patched old-android wide screen back button layout: {path}")
    return True


def patch_location_bar_phone(src_dir: str) -> bool:
    path = os.path.join(src_dir, JAVA)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read()

    if JAVA_MARKER in content:
        return False

    for old, new in JAVA_EDITS:
        if content.count(old) != 1:
            raise RuntimeError(f"location bar back button anchor not found in {path}: {old!r}")
        content = content.replace(old, new, 1)

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    print(f"Patched old-android location bar back button guards: {path}")
    return True


def patch_source_tree(src_dir: str) -> bool:
    layout_changed = patch_layout(src_dir)
    java_changed = patch_location_bar_phone(src_dir)
    return layout_changed or java_changed


if __name__ == "__main__":
    try:
        patch_source_tree(sys.argv[1] if len(sys.argv) > 1 else ".")
    except (FileNotFoundError, RuntimeError) as error:
        print(f"[patch_old_android_location_bar_back_button] {error}", file=sys.stderr)
        raise SystemExit(1)
