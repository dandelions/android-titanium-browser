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
DEVICE_FORM_FACTOR = Path(
    "ui/android/java/src/org/chromium/ui/base/DeviceFormFactor.java"
)
EVENT_FORWARDER = Path(
    "ui/android/java/src/org/chromium/ui/base/EventForwarder.java"
)
NEWTAB_OVERRIDES = Path("chrome/browser/extensions/extension_url_overrides.cc")
RENDERER_POLICY = Path("sandbox/policy/linux/bpf_renderer_policy_linux.cc")
RENDERER_DELEGATE = Path("content/renderer/renderer_main_platform_delegate_android.cc")
CONTENT_MAIN_ANDROID = Path("content/app/android/content_main_android.cc")
NTP_URL_RESOLVER = Path(
    "chrome/browser/url_constants/android/java/src/org/chromium/chrome/browser/"
    "url_constants/UrlConstantResolver.java"
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
    if re.search(r"\([ \t]*ToolbarTablet[ \t]*\)[ \t]*mToolbarLayout,", manager):
        raise SystemExit(f"toolbar layout cast patch is missing: {manager_path}")

    dff_path = root / DEVICE_FORM_FACTOR
    if dff_path.is_file():
        dff = dff_path.read_text(encoding="utf-8")
        for required_symbol in (
            "public static final int MINIMUM_TABLET_WIDTH_DP",
            "SCREEN_BUCKET_TABLET = 2",
            "SCREEN_BUCKET_LARGE_TABLET = 3",
            "sIsTabletForTesting;",
        ):
            if required_symbol not in dff:
                raise SystemExit(
                    f"DeviceFormFactor is missing Chromium symbol {required_symbol}: {dff_path}"
                )
        if dff.count("markUiModeStartupSuccess()") > 1:
            raise SystemExit(
                f"DeviceFormFactor contains duplicate UI mode methods: {dff_path}"
            )

    forwarder_path = root / EVENT_FORWARDER
    if forwarder_path.is_file():
        forwarder = forwarder_path.read_text(encoding="utf-8")
        # 注释里会提到被替换掉的 API 名称，只检查实际代码行。
        forwarder_code = "\n".join(
            line for line in forwarder.splitlines() if not line.lstrip().startswith("//")
        )
        if re.search(r"getRaw[XY]\([^)]", forwarder_code):
            raise SystemExit(
                f"MotionEvent.getRawX(int) API 29 input compat patch is missing: {forwarder_path}"
            )
        if "int gestureClassification = event.getClassification();" in forwarder_code:
            raise SystemExit(
                "MotionEvent.getClassification() API 29 input compat patch is missing: "
                f"{forwarder_path}"
            )

    print("Verified old-android extension management and bottom address bar patches")


def verify_newtab_override(root):
    overrides_path, overrides = read(root, NEWTAB_OVERRIDES)
    if "HeliumNtp: pref list missing" not in overrides:
        raise SystemExit(
            f"extension new tab override fallback patch is missing: {overrides_path}"
        )

    resolver_path, resolver = read(root, NTP_URL_RESOLVER)
    if '"HeliumNtp"' not in resolver:
        raise SystemExit(
            f"new tab URL resolver logging patch is missing: {resolver_path}"
        )

    print("Verified old-android extension new tab page override patches")


def verify_renderer_mprotect(root):
    policy_path, policy = read(root, RENDERER_POLICY)
    if "jitless mode is forced on" not in policy:
        raise SystemExit(
            f"renderer mprotect policy patch is missing: {policy_path}"
        )

    delegate_path, delegate = read(root, RENDERER_DELEGATE)
    if "Helium sandbox: renderer policy=" not in delegate:
        raise SystemExit(
            f"renderer sandbox policy patch is missing: {delegate_path}"
        )

    print("Verified old-android renderer sandbox mprotect patches")


def verify_native_abort_backtrace(root):
    main_path, main = read(root, CONTENT_MAIN_ANDROID)
    if "HeliumAbortLogger" not in main:
        raise SystemExit(
            f"native abort backtrace patch is missing: {main_path}"
        )
    if "HeliumInstallAbortLogger();" not in main:
        raise SystemExit(
            f"native abort backtrace handler is not installed: {main_path}"
        )

    print("Verified old-android native abort backtrace patches")


if __name__ == "__main__":
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    verify(root)
    verify_newtab_override(root)
    verify_renderer_mprotect(root)
    verify_native_abort_backtrace(root)
