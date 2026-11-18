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
LINKER_HEADER = Path("base/android/linker/linker_jni.h")
LINKER_JAVA = Path("base/android/java/src/org/chromium/base/library_loader/Linker.java")
UNWINDSTACK_MEMORY = Path("third_party/libunwindstack/src/libunwindstack/Memory.cpp")
UNWINDSTACK_PROCESS_MAP = Path(
    "third_party/libunwindstack/src/libprocinfo/include/procinfo/process_map.h"
)
NTP_URL_RESOLVER = Path(
    "chrome/browser/url_constants/android/java/src/org/chromium/chrome/browser/"
    "url_constants/UrlConstantResolver.java"
)
ACCESSIBILITY_STATE_DELEGATE = Path(
    "ui/accessibility/android/java/src/org/chromium/ui/accessibility/"
    "AccessibilityStateDelegateImpl.java"
)
NAVIGATION_REQUEST = Path("content/browser/renderer_host/navigation_request.cc")
COMMIT_RUNNER = Path("content/browser/renderer_host/commit_deferring_condition_runner.cc")
RENDER_FRAME_IMPL = Path("content/renderer/render_frame_impl.cc")
CONTENT_MAIN = Path("content/app/content_main.cc")
CONTENT_MAIN_RUNNER = Path("content/app/content_main_runner_impl.cc")
RENDERER_MAIN = Path("content/renderer/renderer_main.cc")
CHILD_THREAD = Path("content/child/child_thread_impl.cc")


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
    if "VMOS still performs the executable-memory transition" not in policy:
        raise SystemExit(
            f"renderer mprotect policy patch is missing: {policy_path}"
        )

    delegate_path, delegate = read(root, RENDERER_DELEGATE)
    if "Helium sandbox: renderer policy=" in delegate:
        raise SystemExit(
            f"renderer policy was broadened beyond Chromium's Android selection: {delegate_path}"
        )
    if "std::make_unique<sandbox::BaselinePolicyAndroid>" not in delegate:
        raise SystemExit(
            f"Android baseline renderer policy fallback is missing: {delegate_path}"
        )

    print("Verified old-android renderer mprotect patch preserves Chromium policy selection")


def verify_native_abort_backtrace(root):
    main_path, main = read(root, CONTENT_MAIN_ANDROID)
    if "HeliumFatalSignalLogger" not in main:
        raise SystemExit(
            f"native abort backtrace patch is missing: {main_path}"
        )
    if "HeliumInstallFatalSignalLogger();" not in main:
        raise SystemExit(
            f"native abort backtrace handler is not installed: {main_path}"
        )

    print("Verified old-android native abort backtrace patches")


def verify_linker_reservation_size(root):
    header_path, header = read(root, LINKER_HEADER)
    if "320 * 1024 * 1024" not in header:
        raise SystemExit(
            f"linker address space reservation patch is missing: {header_path}"
        )

    print("Verified old-android linker address space reservation patch")

def verify_linker_relro_sharing(root):
    linker_path, linker = read(root, LINKER_JAVA)
    if "attemptLoadLibraryLocked(library, RelroSharingMode.NO_SHARING);" not in linker:
        raise SystemExit(
            f"linker RELRO sharing patch is missing: {linker_path}"
        )
    if "mRelroProducer ? RelroSharingMode.PRODUCE" in linker:
        raise SystemExit(
            f"linker still selects shared RELRO: {linker_path}"
        )

    print("Verified old-android linker RELRO sharing is disabled")

def verify_unwindstack_cloexec(root):
    memory_path, memory = read(root, UNWINDSTACK_MEMORY)
    if "fcntl(helium_fd, F_SETFD, FD_CLOEXEC)" not in memory:
        raise SystemExit(
            f"unwindstack FD_CLOEXEC patch is missing: {memory_path}"
        )
    if "O_RDONLY | O_CLOEXEC" in memory:
        raise SystemExit(
            f"unwindstack still opens with O_CLOEXEC: {memory_path}"
        )

    map_path, process_map = read(root, UNWINDSTACK_PROCESS_MAP)
    if "fcntl(fd, F_SETFD, FD_CLOEXEC)" not in process_map:
        raise SystemExit(
            f"unwindstack process map FD_CLOEXEC patch is missing: {map_path}"
        )
    if "open(map_file, O_RDONLY | O_CLOEXEC)" in process_map:
        raise SystemExit(
            f"unwindstack still opens the process map with O_CLOEXEC: {map_path}"
        )

    print("Verified old-android unwindstack close-on-exec patches")

def verify_accessibility_recommended_timeout(root):
    delegate_path, delegate = read(root, ACCESSIBILITY_STATE_DELEGATE)
    if "Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q" not in delegate:
        raise SystemExit(
            f"accessibility recommended timeout API level guard is missing: {delegate_path}"
        )
    if "int recommendedTimeout = nonA11yTimeout;" not in delegate:
        raise SystemExit(
            f"accessibility recommended timeout fallback is missing: {delegate_path}"
        )

    print("Verified old-android accessibility recommended timeout guard")

def verify_navigation_stage_diagnostics(root):
    nav_path, nav = read(root, NAVIGATION_REQUEST)
    for marker in (
        'HeliumNavTrace("begin"',
        'HeliumNavTrace("checks-complete"',
        'HeliumNavTrace("response"',
        'HeliumNavTrace("response-body-ready"',
        'HeliumNavTrace("ready-to-commit"',
        'HeliumNavTrace("conditions-start"',
        'HeliumNavTrace("commit-send"',
        'HeliumNavTrace("commit-timeout"',
        'HeliumNavTrace("commit"',
        'HeliumNavTrace("failed"',
        "helium-nav.log",
    ):
        if marker not in nav:
            raise SystemExit(
                f"navigation stage diagnostic '{marker}' is missing: {nav_path}"
            )

    runner_path, runner = read(root, COMMIT_RUNNER)
    for marker in (
        '"Helium commit: condition="',
        '"Helium commit: condition result="',
    ):
        if marker not in runner:
            raise SystemExit(
                f"commit stage diagnostic '{marker}' is missing: {runner_path}"
            )

    render_path, render = read(root, RENDER_FRAME_IMPL)
    for marker in (
        'HeliumRendererCommitTrace("received")',
        'HeliumRendererCommitTrace("params")',
        'HeliumRendererCommitTrace("blink-before")',
        'HeliumRendererCommitTrace("blink-after")',
        "/data/local/tmp/helium-renderer-commit.log",
    ):
        if marker not in render:
            raise SystemExit(
                f"renderer commit diagnostic '{marker}' is missing: {render_path}"
            )

    print("Verified old-android navigation stage diagnostics")

def verify_content_main_diagnostics(root):
    main_path, main = read(root, CONTENT_MAIN)
    for marker in (
        "Helium content main trace revision: 1",
        "Helium content main: type=",
        "Helium content main: initialize returned ",
        "Helium content main: run returned ",
    ):
        if marker not in main:
            raise SystemExit(
                f"content main diagnostic '{marker}' is missing: {main_path}"
            )

    runner_path, runner = read(root, CONTENT_MAIN_RUNNER)
    for marker in (
        "Helium child main: type=",
        "Helium child main: matched ",
        "Helium child main: no main function for type=",
    ):
        if marker not in runner:
            raise SystemExit(
                f"child main diagnostic '{marker}' is missing: {runner_path}"
            )

    print("Verified old-android content main diagnostics")

def verify_renderer_lifecycle_diagnostics(root):
    renderer_path, renderer = read(root, RENDERER_MAIN)
    for marker in (
        "Helium renderer lifecycle: main entered",
        "Helium renderer lifecycle: RenderThreadImpl ready",
        "Helium renderer lifecycle: message loop entered",
        "Helium renderer lifecycle: message loop exited",
    ):
        if marker not in renderer:
            raise SystemExit(
                f"renderer lifecycle diagnostic '{marker}' is missing: {renderer_path}"
            )

    child_path, child = read(root, CHILD_THREAD)
    if "Helium renderer lifecycle: child channel error" not in child:
        raise SystemExit(
            f"renderer channel diagnostic is missing: {child_path}"
        )

    print("Verified old-android renderer lifecycle diagnostics")

if __name__ == "__main__":
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    verify(root)
    verify_newtab_override(root)
    verify_renderer_mprotect(root)
    verify_linker_reservation_size(root)
    verify_linker_relro_sharing(root)
    verify_unwindstack_cloexec(root)
    verify_native_abort_backtrace(root)
    verify_accessibility_recommended_timeout(root)
    verify_navigation_stage_diagnostics(root)
    verify_content_main_diagnostics(root)
    verify_renderer_lifecycle_diagnostics(root)
