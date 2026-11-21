#!/usr/bin/env python3
"""Skip mini-origin layout mutations when old-android reparents the location bar."""

import os
import sys

TARGET = (
    "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/"
    "MiniOriginBarController.java"
)

ORIGINAL_FIELD = "    private FrameLayout.LayoutParams mDefaultLocationBarLayoutParams;\n"
PATCHED_FIELD = """    // Helium: the bottom address bar is hosted by a LinearLayout on old-android.
    private FrameLayout.@Nullable LayoutParams mDefaultLocationBarLayoutParams;
"""
FIELD_MARKER = "Helium: the bottom address bar is hosted by a LinearLayout"

ORIGINAL_INIT = """        mDefaultLocationBarRightPadding = mLocationBar.getContainerView().getPaddingRight();
        mDefaultLocationBarLayoutParams =
                (FrameLayout.LayoutParams) mLocationBar.getContainerView().getLayoutParams();
"""
PATCHED_INIT = """        mDefaultLocationBarRightPadding = mLocationBar.getContainerView().getPaddingRight();
        ViewGroup.LayoutParams locationBarLayoutParams =
                mLocationBar.getContainerView().getLayoutParams();
        mDefaultLocationBarLayoutParams =
                locationBarLayoutParams instanceof FrameLayout.LayoutParams
                        ? (FrameLayout.LayoutParams) locationBarLayoutParams
                        : null;
"""
INIT_MARKER = "locationBarLayoutParams instanceof FrameLayout.LayoutParams"
PARTIAL_INIT = """        mDefaultLocationBarRightPadding = mLocationBar.getContainerView().getPaddingRight();
        // Helium: skip transient desktop-mode location bar layout parameters.
        if (!(mLocationBar.getContainerView().getLayoutParams() instanceof FrameLayout.LayoutParams)) {
            mDefaultLocationBarLayoutParams = new FrameLayout.LayoutParams(0, 0);
        } else {
            // Helium: skip transient desktop-mode location bar layout parameters.
            if (mLocationBar.getContainerView().getLayoutParams() instanceof FrameLayout.LayoutParams) {
                mDefaultLocationBarLayoutParams =
                        (FrameLayout.LayoutParams) mLocationBar.getContainerView().getLayoutParams();
            }
        }
"""

ORIGINAL_STATE = """    private void updateMiniOriginBarState(@MiniOriginEvent int event) {
        @MiniOriginState int newMiniOriginState = getNewMiniOriginState(event);
"""
PATCHED_STATE = """    private void updateMiniOriginBarState(@MiniOriginEvent int event) {
        // The mini-origin controller changes the location bar's parent-specific parameters.
        // Leave the bottom address bar untouched when it has no FrameLayout parameters to restore.
        if (mDefaultLocationBarLayoutParams == null) return;
        @MiniOriginState int newMiniOriginState = getNewMiniOriginState(event);
"""
STATE_MARKER = "Leave the bottom address bar untouched"
PARTIAL_STATE = """    private void updateMiniOriginBarState(@MiniOriginEvent int event) {
        @MiniOriginState int newMiniOriginState = getNewMiniOriginState(event);
        if (newMiniOriginState == mMiniOriginBarState) return;
"""

ORIGINAL_TRANSITION = """        if (isMiniOriginBarVisibleForState(newMiniOriginState)) {
            // Cache the location bar's layout params now, since we are about to mutate them.
            mDefaultLocationBarLayoutParams =
                    (FrameLayout.LayoutParams) mLocationBar.getContainerView().getLayoutParams();
            showMiniOriginBar();
"""
PATCHED_TRANSITION = """        if (isMiniOriginBarVisibleForState(newMiniOriginState)) {
            // Cache the location bar's layout params now, since we are about to mutate them.
            ViewGroup.LayoutParams locationBarLayoutParams =
                    mLocationBar.getContainerView().getLayoutParams();
            if (!(locationBarLayoutParams instanceof FrameLayout.LayoutParams)) return;
            mDefaultLocationBarLayoutParams =
                    (FrameLayout.LayoutParams) locationBarLayoutParams;
            showMiniOriginBar();
"""
TRANSITION_MARKER = "if (!(locationBarLayoutParams instanceof FrameLayout.LayoutParams)) return;"


def patch_source_tree(src_dir: str) -> bool:
    path = os.path.join(src_dir, TARGET)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read()
    if (
        FIELD_MARKER in content
        and INIT_MARKER in content
        and STATE_MARKER in content
        and TRANSITION_MARKER in content
    ):
        return False

    if FIELD_MARKER not in content:
        if content.count(ORIGINAL_FIELD) != 1:
            raise RuntimeError(f"mini-origin field anchor not found in {path}")
        content = content.replace(ORIGINAL_FIELD, PATCHED_FIELD, 1)
    if INIT_MARKER not in content:
        if content.count(PARTIAL_INIT) == 1:
            content = content.replace(PARTIAL_INIT, PATCHED_INIT, 1)
        elif content.count(ORIGINAL_INIT) == 1:
            content = content.replace(ORIGINAL_INIT, PATCHED_INIT, 1)
        else:
            raise RuntimeError(f"mini-origin constructor anchor not found in {path}")
    if STATE_MARKER not in content:
        if content.count(ORIGINAL_STATE) == 1:
            content = content.replace(ORIGINAL_STATE, PATCHED_STATE, 1)
        elif content.count(PARTIAL_STATE) == 1:
            content = content.replace(PARTIAL_STATE, PATCHED_STATE, 1)
        else:
            raise RuntimeError(f"mini-origin state anchor not found in {path}")
    if TRANSITION_MARKER not in content:
        if content.count(ORIGINAL_TRANSITION) != 1:
            raise RuntimeError(f"mini-origin transition anchor not found in {path}")
        content = content.replace(ORIGINAL_TRANSITION, PATCHED_TRANSITION, 1)

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    print(f"Patched old-android mini-origin layout guard: {path}")
    return True


if __name__ == "__main__":
    try:
        patch_source_tree(sys.argv[1] if len(sys.argv) > 1 else ".")
    except (FileNotFoundError, RuntimeError) as error:
        print(f"[patch_old_android_mini_origin] {error}", file=sys.stderr)
        raise SystemExit(1)
