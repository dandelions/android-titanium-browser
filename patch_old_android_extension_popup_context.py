#!/usr/bin/env python3
"""Keep Android extension popup tabs and options pages in the real browser context."""

from pathlib import Path
import re
import sys


TABS_API = Path("chrome/browser/extensions/api/tabs/tabs_api.cc")
TAB_UTIL = Path("chrome/browser/extensions/extension_tab_util.cc")
TAB_UTIL_MARKER = "Helium: skip restored tabs that have no WebContents yet."
TAB_UTIL_ANCHOR = """    for (int i = 0; i < window->GetTabCount(); ++i) {
      WebContents* target_contents = window->GetWebContentsAt(i);
      int target_tab_id = sessions::SessionTabHelper::IdForTab(target_contents).id();
"""
TAB_UTIL_REPLACEMENT = """    for (int i = 0; i < window->GetTabCount(); ++i) {
      WebContents* target_contents = window->GetWebContentsAt(i);
      // Helium: skip restored tabs that have no WebContents yet. Multi-tab session
      // restore starts navigations before every tab is attached, and the null
      // WebContents used to crash inside SessionTabHelper.
      if (!target_contents) {
        continue;
      }
      int target_tab_id = sessions::SessionTabHelper::IdForTab(target_contents).id();
"""
MENU_MEDIATOR = Path(
    "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/"
    "ExtensionsMenuMediator.java"
)
MENU_TAB_SYNC_MARKER = "Helium: refresh extension menu action titles for the active tab."
MENU_TAB_SYNC_IMPORT = "import org.chromium.base.Callback;\n"
MENU_TAB_SYNC_FIELD = """    private final Callback<@Nullable Tab> mHeliumTabSupplierObserver =
            (tab) -> {
                WebContents webContents = getCurrentWebContents();
                mToolbarBridge.setActiveWebContents(webContents);
                if (getCurrentPage() == ExtensionsMenuProperties.Page.MAIN) {
                    updateMenuEntries();
                }
            };
"""
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
OPTIONS_EXISTING_URL_CHECK = """        String optionsUrl = mMenuBridge.getOptionsPageUrl(extensionId);
        if (optionsUrl != null && !optionsUrl.isEmpty()) {
            openUrlFromMenu(optionsUrl);
            return;
        }
"""
OPTIONS_NEW = """        // Helium: open extension options from the extension's declared page URL.
        String optionsUrl = mMenuBridge.getOptionsPageUrl(extensionId);
        if (optionsUrl != null && !optionsUrl.isEmpty()) {
            openUrlFromMenu(optionsUrl);
            return;
        }
        mMenuBridge.executeAction(extensionId, getCurrentWebContents());
"""
OPTIONS_DUPLICATE = """        String optionsUrl = mMenuBridge.getOptionsPageUrl(extensionId);
        if (optionsUrl != null && !optionsUrl.isEmpty()) {
            openUrlFromMenu(optionsUrl);
            return;
        }
        // Helium: open extension options from the extension's declared page URL.
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


def patch_menu_tab_sync(path: Path) -> bool:
    if not path.is_file():
        raise SystemExit(f"Expected Chromium file not found: {path}")
    text = path.read_text(encoding="utf-8")
    if MENU_TAB_SYNC_MARKER in text:
        return False
    if MENU_TAB_SYNC_IMPORT not in text:
        import_anchor = "import org.chromium.base.lifetime.Destroyable;\n"
        if import_anchor not in text:
            raise SystemExit(f"ExtensionsMenuMediator import anchor not found: {path}")
        text = text.replace(import_anchor, MENU_TAB_SYNC_IMPORT + import_anchor, 1)
    constructor_anchor = "        mToolbarBridge = toolbarBridge;\n"
    if constructor_anchor not in text:
        raise SystemExit(f"ExtensionsMenuMediator constructor anchor not found: {path}")
    text = text.replace(MENU_TAB_SYNC_IMPORT, MENU_TAB_SYNC_IMPORT, 1)
    text = text.replace(
        "import org.chromium.base.Callback;\n",
        "import org.chromium.base.Callback;\n",
        1,
    )
    # Add the callback field after the current tab supplier declaration.
    field_anchor = "    private final NullableObservableSupplier<Tab> mCurrentTabSupplier;\n"
    if field_anchor not in text:
        raise SystemExit(f"ExtensionsMenuMediator tab supplier anchor not found: {path}")
    text = text.replace(field_anchor, field_anchor + MENU_TAB_SYNC_FIELD, 1)
    text = text.replace(
        constructor_anchor,
        constructor_anchor + "        mCurrentTabSupplier.addSyncObserver(mHeliumTabSupplierObserver);\n",
        1,
    )
    destroy_anchor = "    public void destroy() {\n"
    if destroy_anchor not in text:
        raise SystemExit(f"ExtensionsMenuMediator destroy anchor not found: {path}")
    text = text.replace(
        destroy_anchor,
        destroy_anchor + "        mCurrentTabSupplier.removeObserver(mHeliumTabSupplierObserver);\n",
        1,
    )
    text = text.replace(
        "        mToolbarBridge = toolbarBridge;\n",
        "        mToolbarBridge = toolbarBridge;\n"
        "        // Helium: refresh extension menu action titles for the active tab.\n",
        1,
    )
    path.write_text(text, encoding="utf-8")
    return True


def patch_options_path(path: Path) -> bool:
    if not path.is_file():
        raise SystemExit(f"Expected Chromium file not found: {path}")
    text = path.read_text(encoding="utf-8")

    # Keep exactly one declared options URL check inside the helper. This also
    # migrates partially applied older patches without duplicate locals.
    method_start = text.find("private void openExtensionOptionsFromMenu(String extensionId)")
    if method_start >= 0:
        brace_start = text.find("{", method_start)
        method_end = -1
        if brace_start >= 0:
            depth = 0
            for index in range(brace_start, len(text)):
                if text[index] == "{":
                    depth += 1
                elif text[index] == "}":
                    depth -= 1
                    if depth == 0:
                        method_end = index
                        break
        if method_end >= 0:
            method = text[method_start:method_end]
            check = OPTIONS_EXISTING_URL_CHECK.strip("\n")
            occurrences = method.count(check)
            if occurrences > 1:
                first = method.find(check)
                method = method[:first + len(check)] + method[first + len(check):].replace(check, "", 1)
                text = text[:method_start] + method + text[method_end:]
                path.write_text(text, encoding="utf-8")
                return True

    if OPTIONS_DUPLICATE in text:
        text = text.replace(OPTIONS_DUPLICATE, OPTIONS_NEW, 1)
        path.write_text(text, encoding="utf-8")
        return True
    if OPTIONS_MARKER in text:
        return False
    if OPTIONS_OLD in text:
        text = text.replace(OPTIONS_OLD, OPTIONS_NEW, 1)
    elif OPTIONS_EXISTING_URL_CHECK + OPTIONS_LEGACY in text:
        text = text.replace(OPTIONS_EXISTING_URL_CHECK + OPTIONS_LEGACY, OPTIONS_NEW, 1)
    elif OPTIONS_LEGACY in text:
        text = text.replace(OPTIONS_LEGACY, OPTIONS_NEW, 1)
    else:
        raise SystemExit(f"Expected one popup context anchor in {path}")
    path.write_text(text, encoding="utf-8")
    return True


def patch_tab_util(path: Path) -> bool:
    if not path.is_file():
        raise SystemExit(f"ExtensionTabUtil not found: {path}")
    text = path.read_text(encoding="utf-8")
    if TAB_UTIL_MARKER in text:
        return False
    if text.count(TAB_UTIL_ANCHOR) != 1:
        raise SystemExit(f"ExtensionTabUtil anchor not found exactly once: {path}")
    path.write_text(text.replace(TAB_UTIL_ANCHOR, TAB_UTIL_REPLACEMENT, 1), encoding="utf-8")
    return True


def patch_source(root: Path) -> bool:
    changed = patch_direct_query(root / TABS_API)
    changed |= patch_options_path(root / MENU_MEDIATOR)
    changed |= patch_menu_tab_sync(root / MENU_MEDIATOR)
    changed |= patch_tab_util(root / TAB_UTIL)
    return changed


if __name__ == "__main__":
    source_root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    changed = patch_source(source_root)
    print(
        "Patched old-android extension popup context"
        if changed
        else "Old-android extension popup context already patched"
    )
