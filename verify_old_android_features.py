#!/usr/bin/env python3
from pathlib import Path
import re
import sys


EXTENSIONS_TOOLBAR = Path(
    "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/"
    "ExtensionsToolbarCoordinatorImpl.java"
)
APP_MENU = Path(
    "chrome/android/java/src/org/chromium/chrome/browser/app/appmenu/"
    "AppMenuPropertiesDelegateImpl.java"
)
TOOLBAR_POSITION = Path(
    "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/"
    "ToolbarPositionController.java"
)
NTP_COORDINATOR = Path(
    "chrome/android/java/src/org/chromium/chrome/browser/ntp/NewTabPageCoordinator.java"
)
TOOLBAR_PHONE_LAYOUT = Path(
    "chrome/browser/ui/android/toolbar/java/res/layout/toolbar_phone.xml"
)
TOOLBAR_MANAGER = Path(
    "chrome/android/java/src/org/chromium/chrome/browser/toolbar/ToolbarManager.java"
)


def read(root, relative):
    path = root / relative
    if not path.is_file():
        raise SystemExit(f"old-android feature source file is missing: {path}")
    return path, path.read_text(encoding="utf-8")


def verify(root):
    toolbar_path, toolbar = read(root, EXTENSIONS_TOOLBAR)
    if (
        "return !mIsWebApp;" not in toolbar
        and "return !mIsWebApp && mCanShowMenuIcon;" not in toolbar
        and "return true; // Helium: Extensions button pinned by default" not in toolbar
    ):
        raise SystemExit(f"extension management toolbar patch is missing: {toolbar_path}")

    menu_path, menu = read(root, APP_MENU)
    match = re.search(
        r"shouldShowExtensionsItem\(\)\s*\{(?P<body>.*?)\n\s*\}",
        menu,
        re.S,
    )
    if not match or "return true;" not in match.group("body"):
        raise SystemExit(f"extension management menu patch is missing: {menu_path}")

    position_path, position = read(root, TOOLBAR_POSITION)
    if "Helium: follow the toolbar preference on the NTP and while editing" not in position:
        raise SystemExit(f"bottom toolbar position patch is missing: {position_path}")

    ntp_path, ntp = read(root, NTP_COORDINATOR)
    if "AddressBarPreference.isToolbarConfiguredToShowOnTop()" not in ntp:
        raise SystemExit(f"bottom address bar NTP patch is missing: {ntp_path}")

    layout_path, layout = read(root, TOOLBAR_PHONE_LAYOUT)
    if "extensions_toolbar_container_stub" not in layout:
        raise SystemExit(f"extension toolbar layout patch is missing: {layout_path}")

    manager_path, manager = read(root, TOOLBAR_MANAGER)
    if "(ToolbarTablet) mToolbarLayout" in manager:
        raise SystemExit(f"toolbar layout cast patch is missing: {manager_path}")

    print("Verified old-android extension management and bottom address bar patches")


if __name__ == "__main__":
    verify(Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve())
