#!/usr/bin/env python3
"""
patch_store_inline_install.py
Implements native inline installation mechanism for Chrome Web Store (CWS)
and Microsoft Edge Addons in Helium Browser for Android.

1. Updates download_crx_util.cc to whitelist Google and Edge extension domains
   for CRX installation and ensure .crx downloads trigger CrxInstaller.
2. Updates ChromeActivity.java to inject inline install hooks and desktop UA
   spoofing when browsing Chrome Web Store and Edge Addons.
"""

import os
import re
import sys
from pathlib import Path

CWS_SCRIPT = r"""(function() {
    if (window._helium_cws_injected) return;
    window._helium_cws_injected = true;

    try {
        var desktopUA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36';
        Object.defineProperty(navigator, 'userAgent', { get: function() { return desktopUA; }, configurable: true });
        Object.defineProperty(navigator, 'appVersion', { get: function() { return '5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36'; }, configurable: true });
        Object.defineProperty(navigator, 'platform', { get: function() { return 'Linux x86_64'; }, configurable: true });
    } catch(e) {}

    try {
        var vp = document.querySelector('meta[name="viewport"]');
        if (vp) {
            vp.setAttribute('content', 'width=device-width, initial-scale=1.0');
        } else {
            var meta = document.createElement('meta');
            meta.name = 'viewport';
            meta.content = 'width=device-width, initial-scale=1.0';
            document.head && document.head.appendChild(meta);
        }
    } catch(e) {}

    function getExtId() {
        var m = location.pathname.match(/\/([a-z]{32})(?:\/|$|\?)/i);
        return m ? m[1] : '';
    }

    function triggerInstall(extId) {
        var id = extId || getExtId();
        if (!/^[a-p]{32}$/i.test(id || '')) return false;
        var crxUrl = 'https://clients2.google.com/service/update2/crx?response=redirect&prodversion=156.0.8078.79&acceptformat=crx2,crx3&x=id%3D' + id + '%26uc';
        window.location.assign(crxUrl);
        return true;
    }

    function reportInstallStart(id, cb) {
        var started = triggerInstall(id);
        if (typeof cb === 'function') cb(started ? 'success' : 'error');
    }

    try {
        window.chrome = window.chrome || {};
        window.chrome.webstorePrivate = window.chrome.webstorePrivate || {};
        window.chrome.webstorePrivate.install = function(id, cb) {
            reportInstallStart(id, cb);
        };
        window.chrome.webstorePrivate.beginInstallWithManifest3 = function(details, cb) {
            var id = (details && details.id) ? details.id : getExtId();
            reportInstallStart(id, cb);
        };
        window.chrome.webstorePrivate.completeInstall = function(id, cb) {
            if (typeof cb === 'function') cb();
        };
    } catch(e) {}

    function attachButtonHooks() {
        var id = getExtId();
        if (!/^[a-p]{32}$/i.test(id)) return;
        var buttons = document.querySelectorAll('button, [role="button"]');
        buttons.forEach(function(btn) {
            if (btn._helium_hooked) return;
            var text = (btn.innerText || btn.textContent || btn.getAttribute('aria-label') || '').trim();
            if (text.match(/add to chrome|添加到 chrome|add to chromium|添加到 chromium|install|获取/i)) {
                btn._helium_hooked = true;
                btn.removeAttribute('disabled');
                btn.addEventListener('click', function(e) {
                    if (!triggerInstall(id)) return;
                    e.preventDefault();
                    e.stopPropagation();
                }, true);
            }
        });
    }

    setInterval(attachButtonHooks, 1000);
    attachButtonHooks();
})();"""

EDGE_SCRIPT = r"""(function() {
    if (window._helium_edge_injected) return;
    window._helium_edge_injected = true;

    try {
        var edgeUA = navigator.userAgent + ' Edg/156.0.0.0';
        Object.defineProperty(navigator, 'userAgent', { get: function() { return edgeUA; }, configurable: true });
    } catch(e) {}

    function getEdgeExtId() {
        var m = location.pathname.match(/\/([a-z0-9]{32})(?:\/|$|\?)/i);
        return m ? m[1] : '';
    }

    function triggerEdgeInstall(extId) {
        var id = extId || getEdgeExtId();
        if (!/^[a-p]{32}$/i.test(id || '')) return false;
        var crxUrl = 'https://edge.microsoft.com/extensionwebstorebase/v1/crx?response=redirect&acceptformat=crx3&x=id%3D' + id + '%26installsource%3Dondemand%26uc';
        window.location.assign(crxUrl);
        return true;
    }

    function attachEdgeHooks() {
        var id = getEdgeExtId();
        var buttons = document.querySelectorAll('button[id*="getOrRemoveButton"], button[aria-label*="Get"], button[aria-label*="获取"]');
        buttons.forEach(function(btn) {
            if (btn._helium_hooked) return;
            btn._helium_hooked = true;
            btn.removeAttribute('disabled');
            var btnId = btn.id ? btn.id.split('-')[1] : id;
            btn.addEventListener('click', function(e) {
                if (!triggerEdgeInstall(btnId || id)) return;
                e.preventDefault();
                e.stopPropagation();
            }, true);
        });
    }

    setInterval(attachEdgeHooks, 1000);
    attachEdgeHooks();
})();"""


def patch_download_crx_util(src_dir: Path) -> None:
    path = src_dir / "chrome/browser/download/download_crx_util.cc"
    if not path.is_file():
        print(f"Skipping download_crx_util: {path} not found")
        return

    content = path.read_text(encoding="utf-8")

    whitelist_injection = '''  // Helium: Whitelist store domains for inline CRX installation
  if (const auto& o = item.GetRequestInitiator(); o && o->scheme() == "chrome-extension") return true;
  for (const char* d : {"clients2.google.com", "clients2.googleusercontent.com",
                       "chromewebstore.google.com", "chrome.google.com",
                       "google.com", "googleusercontent.com",
                       "microsoftedge.microsoft.com", "edge.microsoft.com",
                       "delivery.mp.microsoft.com", "addons.opera.com", "operacdn.com"}) {
    if (item.GetURL().DomainIs(d) || item.GetReferrerUrl().DomainIs(d)) return true;
  }
'''

    if "Helium: Whitelist store domains for inline CRX installation" not in content:
        if "bool OffStoreInstallAllowedByPrefs(" not in content:
            raise RuntimeError("Could not find OffStoreInstallAllowedByPrefs in download_crx_util.cc")
        old_oneliner = re.search(
            r'''bool OffStoreInstallAllowedByPrefs\([^)]*\)\s*\{\s*(if \(const auto& o = item\.GetRequestInitiator\(\)[\s\S]*?return true;\s*)''',
            content,
        )
        if old_oneliner:
            content = content.replace(old_oneliner.group(1), whitelist_injection, 1)
        else:
            content, replacements = re.subn(
                r'''(bool OffStoreInstallAllowedByPrefs\([^)]*\)\s*\{\n)''',
                lambda match: match.group(1) + whitelist_injection,
                content,
                count=1,
            )
            if replacements != 1:
                raise RuntimeError("Could not insert store allowlist in download_crx_util.cc")

    crx_target_check = 'download_item.GetTargetFilePath().MatchesExtension(FILE_PATH_LITERAL(".crx"))'
    if crx_target_check not in content:
        old_crx_check = re.search(
            r'''  if \(download_item\.GetMimeType\(\) == extensions::Extension::kMimeType \|\|\s*extensions::UserScript::IsURLUserScript\(download_item\.GetURL\(\),\s*download_item\.GetMimeType\(\)\)\) \{''',
            content,
        )
        if not old_crx_check:
            raise RuntimeError("Could not find the CRX download check in download_crx_util.cc")
        crx_check = '''  if (download_item.GetMimeType() == extensions::Extension::kMimeType ||
      download_item.GetURL().path().ends_with(".crx") ||
      download_item.GetTargetFilePath().MatchesExtension(FILE_PATH_LITERAL(".crx")) ||
      extensions::UserScript::IsURLUserScript(download_item.GetURL(),
                                              download_item.GetMimeType())) {'''
        content = content.replace(old_crx_check.group(0), crx_check, 1)

    path.write_text(content, encoding="utf-8")
    print("Patched download_crx_util.cc for store inline installation")


def patch_chrome_activity(src_dir: Path) -> None:
    path = src_dir / "chrome/android/java/src/org/chromium/chrome/browser/app/ChromeActivity.java"
    if not path.is_file():
        print(f"Skipping ChromeActivity: {path} not found")
        return

    content = path.read_text(encoding="utf-8")

    # Clean up any bad historical injection inside onInitialLayoutInflationComplete where tab is not in scope
    bad_call = "        injectStoreInlineInstallSupport(tab);\n                mRootUiCoordinator.getStatusBarColorController().updateStatusBarColor();"
    if bad_call in content:
        content = content.replace(
            bad_call,
            "        mRootUiCoordinator.getStatusBarColorController().updateStatusBarColor();",
            1,
        )
        path.write_text(content, encoding="utf-8")
        print("Cleaned up invalid injectStoreInlineInstallSupport(tab) from onInitialLayoutInflationComplete")

    # Escape quotes and backslashes for Java string literal
    def to_java_string(js_code: str) -> str:
        escaped = js_code.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n\"\n            + \"")
        return f'"{escaped}"'

    java_cws = to_java_string(CWS_SCRIPT)
    java_edge = to_java_string(EDGE_SCRIPT)

    if "private void injectStoreInlineInstallSupport(Tab tab)" in content:
        for name, value in (("HELIUM_CWS_SCRIPT", java_cws), ("HELIUM_EDGE_SCRIPT", java_edge)):
            marker = f"private static final String {name}"
            start = content.find(marker)
            if start == -1:
                raise RuntimeError(f"Could not find {name} in ChromeActivity.java")
            literal_start = content.find('"', start)
            if literal_start == -1:
                raise RuntimeError(f"Could not find the value for {name} in ChromeActivity.java")
            in_string = False
            escaped = False
            end = -1
            for index in range(literal_start, len(content)):
                char = content[index]
                if in_string:
                    if escaped:
                        escaped = False
                    elif ord(char) == 92:
                        escaped = True
                    elif char == '"':
                        in_string = False
                elif char == '"':
                    in_string = True
                elif char == ";":
                    end = index + 1
                    break
            if end == -1:
                raise RuntimeError(f"Could not find the end of {name} in ChromeActivity.java")
            replacement = f"private static final String {name} =" + chr(10) + "            " + value + ";"
            content = content[:start] + replacement + content[end:]

        url_hook = content.find("PersonalizeResults.Execute(tab);")
        if url_hook >= 0 and "injectStoreInlineInstallSupport(tab);" not in content[url_hook:url_hook + 160]:
            content = content.replace(
                "PersonalizeResults.Execute(tab);",
                "PersonalizeResults.Execute(tab);" + chr(10) + "              injectStoreInlineInstallSupport(tab);",
                1,
            )
        path.write_text(content, encoding="utf-8")
        print("Updated ChromeActivity.java store inline install scripts")
        return


    helper_methods = f"""
    // Helium: Native inline installation for Chrome Web Store & Edge Addons
    private static final String HELIUM_CWS_SCRIPT =
            {java_cws};

    private static final String HELIUM_EDGE_SCRIPT =
            {java_edge};

    private void injectStoreInlineInstallSupport(Tab tab) {{
        if (tab == null || tab.getWebContents() == null || tab.getUrl() == null) return;
        String spec = tab.getUrl().getSpec();
        if (spec == null) return;
        if (spec.startsWith("https://chromewebstore.google.com")
                || spec.startsWith("https://chrome.google.com/webstore")) {{
            tab.getWebContents().evaluateJavaScript(HELIUM_CWS_SCRIPT, null);
        }} else if (spec.startsWith("https://microsoftedge.microsoft.com/addons")) {{
            tab.getWebContents().evaluateJavaScript(HELIUM_EDGE_SCRIPT, null);
        }}
    }}
"""

    # Inject the helper before the closing brace of ChromeActivity
    last_brace_idx = content.rfind("}")
    if last_brace_idx != -1:
        content = content[:last_brace_idx] + helper_methods + "\n}\n"

    # Hook into onPageLoadFinished and onUrlUpdated in TabModelObserver / TabObserver
    if "OfflinePageUtils.showOfflineSnackbarIfNecessary(tab);" in content:
        content = content.replace(
            "OfflinePageUtils.showOfflineSnackbarIfNecessary(tab);",
            "OfflinePageUtils.showOfflineSnackbarIfNecessary(tab);\n                injectStoreInlineInstallSupport(tab);",
            1,
        )

    if "PersonalizeResults.Execute(tab);" in content:
        content = content.replace(
            "PersonalizeResults.Execute(tab);",
            "PersonalizeResults.Execute(tab);\n              injectStoreInlineInstallSupport(tab);",
            1,
        )

    path.write_text(content, encoding="utf-8")
    print("Patched ChromeActivity.java with native store inline install hooks")


def main() -> None:
    src_dir = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(".").resolve()
    print(f"Applying store inline install patches to: {src_dir}")
    patch_download_crx_util(src_dir)
    patch_chrome_activity(src_dir)
    print("Store inline install patch completed successfully.")


if __name__ == "__main__":
    main()
