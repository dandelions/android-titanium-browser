#!/usr/bin/env python3
"""Keep Android extension popup tabs and options pages in the real browser context."""

from pathlib import Path
import sys


TABS_API = Path("chrome/browser/extensions/api/tabs/tabs_api.cc")
MENU_MEDIATOR = Path(
    "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/"
    "ExtensionsMenuMediator.java"
)
DIRECT_MARKER = "Helium: preserve the Android popup tab context without scrubbing."
OPTIONS_MARKER = "Helium: open extension options from the extension's declared page URL."
DIRECT_OLD = """  if (helium_android_popup_direct_query) {
    base::ListValue direct_result;
    direct_result.Append(tabs_internal::CreateTabObjectHelper(
                             android_popup_direct_web_contents, extension(),
                             source_context_type(), nullptr, -1)
                             .ToValue());
    return RespondNow(WithArguments(std::move(direct_result)));
  }
"""
DIRECT_NEW = """  if (helium_android_popup_direct_query) {
    // Helium: preserve the Android popup tab context without scrubbing.
    ExtensionTabUtil::ScrubTabBehavior dont_scrub = {
        ExtensionTabUtil::kDontScrubTab, ExtensionTabUtil::kDontScrubTab};
    base::ListValue direct_result;
    direct_result.Append(ExtensionTabUtil::CreateTabObject(
                             android_popup_direct_web_contents, dont_scrub,
                             extension(), nullptr, -1)
                             .ToValue());
    return RespondNow(WithArguments(std::move(direct_result)));
  }
"""
OPTIONS_OLD = """        if (mToolbarBridge != null) {
            mToolbarBridge.executeUserAction(extensionId, InvocationSource.TOOLBAR_BUTTON);
            return;
        }
        mMenuBridge.executeAction(extensionId, getCurrentWebContents());
"""
OPTIONS_LEGACY = """        // Helium: open extension options through the native Android options path.
        mMenuBridge.openOptionsPage(extensionId);
"""
OPTIONS_NEW = """        // Helium: open extension options from the extension's declared page URL.
        String optionsUrl = mMenuBridge.getOptionsPageUrl(extensionId);
        if (optionsUrl != null && !optionsUrl.isEmpty()) {
            openUrlFromMenu(optionsUrl);
            return;
        }
        mMenuBridge.executeAction(extensionId, getCurrentWebContents());
"""


def patch_file(path: Path, old: str, new: str, marker: str) -> bool:
    if not path.is_file():
        raise SystemExit(f"Expected Chromium file not found: {path}")
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return False
    if text.count(old) != 1:
        raise SystemExit(f"Expected one popup context anchor in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return True


def patch_direct_query(path: Path) -> bool:
    if not path.is_file():
        raise SystemExit(f"Expected Chromium file not found: {path}")
    text = path.read_text(encoding="utf-8")
    if DIRECT_MARKER in text:
        return False
    if DIRECT_OLD in text:
        path.write_text(text.replace(DIRECT_OLD, DIRECT_NEW, 1), encoding="utf-8")
        return True
    if "ExtensionTabUtil::kDontScrubTab" in text:
        anchor = "    ExtensionTabUtil::ScrubTabBehavior dont_scrub = {\n"
        if text.count(anchor) < 1:
            raise SystemExit(f"Existing popup context patch found without a migration anchor in {path}")
        path.write_text(
            text.replace(
                anchor,
                "    // Helium: preserve the Android popup tab context without scrubbing.\n" + anchor,
                1,
            ),
            encoding="utf-8",
        )
        return True
    raise SystemExit(f"Expected one popup context anchor in {path}")


def patch_options_path(path: Path) -> bool:
    if not path.is_file():
        raise SystemExit(f"Expected Chromium file not found: {path}")
    text = path.read_text(encoding="utf-8")
    if OPTIONS_MARKER in text:
        return False
    if OPTIONS_OLD in text:
        text = text.replace(OPTIONS_OLD, OPTIONS_NEW, 1)
    elif OPTIONS_LEGACY in text:
        text = text.replace(OPTIONS_LEGACY, OPTIONS_NEW, 1)
    else:
        raise SystemExit(f"Expected one popup context anchor in {path}")
    path.write_text(text, encoding="utf-8")
    return True


def patch_source(root: Path) -> bool:
    changed = patch_direct_query(root / TABS_API)
    changed |= patch_options_path(root / MENU_MEDIATOR)
    return changed


if __name__ == "__main__":
    source_root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    changed = patch_source(source_root)
    print(
        "Patched old-android extension popup context"
        if changed
        else "Old-android extension popup context already patched"
    )
