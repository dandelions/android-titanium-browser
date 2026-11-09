#!/usr/bin/env python3
"""Restore the Android extension toolbar host used by Chromium's desktop mode."""

from pathlib import Path
import re
import sys


TOOLBAR_PHONE = Path(
    "chrome/browser/ui/android/toolbar/java/res/layout/toolbar_phone.xml"
)
TOOLBAR_MANAGER = Path(
    "chrome/android/java/src/org/chromium/chrome/browser/toolbar/ToolbarManager.java"
)
TOOLBAR_PHONE_JAVA = Path(
    "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/top/ToolbarPhone.java"
)

STUB = """        <ViewStub
            android:id="@+id/extensions_toolbar_container_stub"
            android:inflatedId="@+id/extensions_toolbar_container"
            android:layout_width="wrap_content"
            android:layout_height="?attr/toolbarButtonHeight"
            android:layout_marginVertical="?attr/toolbarButtonMarginVertical" />

"""

DRAW_BLOCK = """        // Draw the extension toolbar after the optional button is positioned.
        View extContainer = findViewById(R.id.extensions_toolbar_container);
        if (extContainer != null
                && extContainer.getVisibility() != View.GONE
                && extContainer.getWidth() != 0) {
            canvas.save();
            ViewUtils.translateCanvasToView(mToolbarButtonsContainer, extContainer, canvas);
            extContainer.draw(canvas);
            canvas.restore();
        }

"""


def patch_toolbar_phone_layout(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if "extensions_toolbar_container_stub" in text:
        return False
    anchor = re.search(
        r"^[ \t]*<ViewStub\s+android:id=\"@\+id/signin_button_stub\"",
        text,
        re.MULTILINE,
    )
    if anchor:
        idx = anchor.start()
        path.write_text(text[:idx] + STUB + text[idx:], encoding="utf-8")
        return True
    anchor_opt = re.search(
        r"^[ \t]*<ViewStub\s+android:id=\"@\+id/optional_button_stub\"[\s\S]*?/>\n",
        text,
        re.MULTILINE,
    )
    if anchor_opt:
        idx = anchor_opt.end()
        path.write_text(text[:idx] + STUB + text[idx:], encoding="utf-8")
        return True
    raise SystemExit(f"toolbar buttons anchor not found in {path}")


def patch_toolbar_manager(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if "(ToolbarTablet)" not in text:
        return False
    new_text = re.sub(
        r"\([ \t]*ToolbarTablet[ \t]*\)[ \t]*mToolbarLayout,",
        "mToolbarLayout,",
        text,
    )
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        return True
    return False


def patch_toolbar_phone_java(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if "View extContainer = findViewById(R.id.extensions_toolbar_container);" in text:
        return False
    anchor = re.search(
        r"^[ \t]*// Draw the signin button if visible\.\n",
        text,
        re.MULTILINE,
    )
    if not anchor:
        raise SystemExit(f"toolbar draw anchor not found in {path}")
    idx = anchor.start()
    path.write_text(text[:idx] + DRAW_BLOCK + text[idx:], encoding="utf-8")
    return True


def patch_source(source_root: Path) -> bool:
    changed = False
    for relative, patch in (
        (TOOLBAR_PHONE, patch_toolbar_phone_layout),
        (TOOLBAR_MANAGER, patch_toolbar_manager),
        (TOOLBAR_PHONE_JAVA, patch_toolbar_phone_java),
    ):
        path = source_root / relative
        if not path.is_file():
            raise SystemExit(f"Expected Chromium file not found: {path}")
        changed |= patch(path)
    return changed


if __name__ == "__main__":
    source_root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    changed = patch_source(source_root)
    print(
        "Patched Android extension toolbar host"
        if changed
        else "Android extension toolbar host already patched"
    )
