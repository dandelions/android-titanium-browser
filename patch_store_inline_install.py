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
        if (!id || id.length !== 32) return false;
        var crxUrl = 'https://clients2.google.com/service/update2/crx?response=redirect&prodversion=156.0.8078.79&acceptformat=crx2,crx3&x=id%3D' + id + '%26uc';
        var a = document.createElement('a');
        a.href = crxUrl;
        a.download = id + '.crx';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        return true;
    }

    try {
        window.chrome = window.chrome || {};
        window.chrome.webstorePrivate = window.chrome.webstorePrivate || {};
        window.chrome.webstorePrivate.install = function(id, cb) {
            triggerInstall(id);
            if (typeof cb === 'function') cb('success');
        };
        window.chrome.webstorePrivate.beginInstallWithManifest3 = function(details, cb) {
            var id = (details && details.id) ? details.id : getExtId();
            triggerInstall(id);
            if (typeof cb === 'function') cb('success');
        };
        window.chrome.webstorePrivate.completeInstall = function(id, cb) {
            if (typeof cb === 'function') cb();
        };
    } catch(e) {}

    function attachButtonHooks() {
        var id = getExtId();
        if (!id) return;
        var buttons = document.querySelectorAll('button, [role="button"]');
        buttons.forEach(function(btn) {
            if (btn._helium_hooked) return;
            var text = (btn.innerText || btn.textContent || btn.getAttribute('aria-label') || '').trim();
            if (text.match(/add to chrome|添加到 chrome|add to chromium|添加到 chromium|install|获取/i)) {
                btn._helium_hooked = true;
                btn.removeAttribute('disabled');
                btn.addEventListener('click', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    triggerInstall(id);
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
        if (!id) return;
        var crxUrl = 'https://edge.microsoft.com/extensionwebstorebase/v1/crx?response=redirect&acceptformat=crx3&x=id%3D' + id + '%26installsource%3Dondemand%26uc';
        var a = document.createElement('a');
        a.href = crxUrl;
        a.download = id + '.crx';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
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
                e.preventDefault();
                e.stopPropagation();
                triggerEdgeInstall(btnId || id);
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
    if "Helium: Whitelist store domains for inline CRX installation" in content:
        print("download_crx_util.cc already patched for store inline install")
        return

    # 1. Update OffStoreInstallAllowedByPrefs to whitelist Google and Edge domains
    whitelist_injection = (
        "  // Helium: Whitelist store domains for inline CRX installation\n"
        "  if (const auto& o = item.GetRequestInitiator(); o && o->scheme() == \"chrome-extension\") return true;\n"
        "  for (const char* d : {\"clients2.google.com\", \"clients2.googleusercontent.com\",\n"
        "                       \"chromewebstore.google.com\", \"chrome.google.com\",\n"
        "                       \"google.com\", \"googleusercontent.com\",\n"
        "                       \"microsoftedge.microsoft.com\", \"edge.microsoft.com\",\n"
        "                       \"delivery.mp.microsoft.com\", \"addons.opera.com\", \"operacdn.com\"}) {\n"
        "    if (item.GetURL().DomainIs(d) || item.GetReferrerUrl().DomainIs(d)) return true;\n"
        "  }\n"
    )

    if "bool OffStoreInstallAllowedByPrefs(" in content:
        # Check if an older one-liner was present
        old_oneliner = re.search(r"bool OffStoreInstallAllowedByPrefs\([^)]*\)\s*\{\s*(if \(const auto& o = item\.GetRequestInitiator\(\)[\s\S]*?return true;\s*)", content)
        if old_oneliner:
            content = content.replace(old_oneliner.group(1), whitelist_injection, 1)
        else:
            content = re.sub(
                r"(bool OffStoreInstallAllowedByPrefs\([^)]*\)\s*\{\n)",
                r"\1" + whitelist_injection,
                content,
                count=1,
            )

    # 2. Update IsExtensionDownload to also identify .crx files
    crx_check = (
        "  if (download_item.GetMimeType() == extensions::Extension::kMimeType ||\n"
        "      download_item.GetURL().path().ends_with(\".crx\") ||\n"
        "      download_item.GetTargetFilePath().MatchesExtension(FILE_PATH_LITERAL(\".crx\")) ||\n"
        "      extensions::UserScript::IsURLUserScript(download_item.GetURL(),\n"
        "                                              download_item.GetMimeType())) {\n"
    )
    old_crx_check = re.search(
        r"  if \(download_item\.GetMimeType\(\) == extensions::Extension::kMimeType \|\|\s*extensions::UserScript::IsURLUserScript\([^)]*\)\) \{",
        content,
    )
    if old_crx_check:
        content = content.replace(old_crx_check.group(0), crx_check, 1)

    path.write_text(content, encoding="utf-8")
    print("Patched download_crx_util.cc for store inline installation")


def patch_chrome_activity(src_dir: Path) -> None:
    path = src_dir / "chrome/android/java/src/org/chromium/chrome/browser/app/ChromeActivity.java"
    if not path.is_file():
        print(f"Skipping ChromeActivity: {path} not found")
        return

    content = path.read_text(encoding="utf-8")
    if "injectStoreInlineInstallSupport" in content:
        print("ChromeActivity.java already patched for store inline install")
        return

    # Escape quotes and backslashes for Java string literal
    def to_java_string(js_code: str) -> str:
        escaped = js_code.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n\"\n            + \"")
        return f'"{escaped}"'

    java_cws = to_java_string(CWS_SCRIPT)
    java_edge = to_java_string(EDGE_SCRIPT)

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
