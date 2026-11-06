#!/usr/bin/env python3
"""Restore Chrome Web Store installation compatibility after Chromium hotfixes."""

import re
import sys
from pathlib import Path

CHROME_ACTIVITY = Path(
    "chrome/android/java/src/org/chromium/chrome/browser/app/ChromeActivity.java"
)
DOWNLOAD_CRX_UTIL = Path("chrome/browser/download/download_crx_util.cc")

CWS_INLINE_SCRIPT = r'''(function() {
  if (window._helium_cws_inline_install) return;
  window._helium_cws_inline_install = true;
  var version = "__VERSION__";
  var desktopUA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 " +
      "(KHTML, like Gecko) Chrome/" + version + " Safari/537.36";
  try {
    Object.defineProperty(navigator, "userAgent", {get: function() { return desktopUA; }, configurable: true});
    Object.defineProperty(navigator, "appVersion", {get: function() { return desktopUA.substring(16); }, configurable: true});
    Object.defineProperty(navigator, "platform", {get: function() { return "Linux x86_64"; }, configurable: true});
  } catch (e) {}
  function extensionId() {
    var match = location.pathname.match(/\/([a-p]{32})(?:\/|$)/i);
    return match ? match[1] : "";
  }
  function install(id) {
    id = id || extensionId();
    if (!/^[a-p]{32}$/i.test(id)) return false;
    var url = "https://clients2.google.com/service/update2/crx?response=redirect" +
        "&os=win&arch=x64&prod=chromecrx&prodversion=" + version +
        "&acceptformat=crx3,puff&x=id%3D" + id + "%26installsource%3Dondemand%26uc";
    window.location.assign(url);
    return true;
  }
  try {
    window.chrome = window.chrome || {};
    window.chrome.webstorePrivate = window.chrome.webstorePrivate || {};
    window.chrome.webstorePrivate.install = function(id, callback) {
      var ok = install(id);
      if (typeof callback === "function") callback(ok ? "success" : "error");
    };
    window.chrome.webstorePrivate.beginInstallWithManifest3 = function(details, callback) {
      var ok = install(details && details.id);
      if (typeof callback === "function") callback(ok ? "success" : "error");
    };
    window.chrome.webstorePrivate.completeInstall = function(id, callback) {
      if (typeof callback === "function") callback();
    };
  } catch (e) {}
  function hookButtons() {
    var id = extensionId();
    if (!id) return;
    document.querySelectorAll("button, [role=button]").forEach(function(button) {
      if (button._helium_cws_hooked) return;
      var text = (button.innerText || button.textContent || button.getAttribute("aria-label") || "").trim();
      if (!/add to chrome|add to chromium|添加到 chrome|添加到 chromium|install|获取/i.test(text)) return;
      button._helium_cws_hooked = true;
      button.removeAttribute("disabled");
      button.setAttribute("aria-disabled", "false");
      button.addEventListener("click", function(event) {
        if (!install(id)) return;
        event.preventDefault();
        event.stopPropagation();
      }, true);
    });
  }
  hookButtons();
  setInterval(hookButtons, 1000);
})();'''

CWS_ALLOWLIST = '''  if (const auto& o = item.GetRequestInitiator(); o && o->scheme() == "chrome-extension") return true;
  for (const char* d : {"clients2.google.com", "clients2.googleusercontent.com",
                       "chromewebstore.google.com", "chrome.google.com",
                       "google.com", "googleusercontent.com"}) {
    if (item.GetURL().DomainIs(d) || item.GetReferrerUrl().DomainIs(d)) return true;
  }
'''


def _target_version() -> str:
    root = Path(__file__).resolve().parent
    for path in (root / "vanadium" / "args.gn", root / "args.gn"):
        if path.is_file():
            match = re.search(r"[0-9]+(?:\.[0-9]+){3}", path.read_text(encoding="utf-8"))
            if match:
                return match.group(0)
    return "156.0.8078.79"


def _java_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return '"' + escaped.replace("\n", "\\n\"\n            + \"") + '"'


def _replace_java_constant(text: str, name: str, value: str) -> str:
    marker = f"private static final String {name}"
    start = text.find(marker)
    if start < 0:
        return text
    quote = text.find('"', start)
    if quote < 0:
        raise RuntimeError(f"Could not find {name} value")
    escaped = False
    in_string = False
    end = -1
    for index in range(quote, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == ";":
            end = index + 1
            break
    if end < 0:
        raise RuntimeError(f"Could not find end of {name} declaration")
    replacement = f"private static final String {name} =\n            {_java_string(value)};"
    return text[:start] + replacement + text[end:]


def patch_chrome_activity(root: Path) -> bool:
    path = root / CHROME_ACTIVITY
    if not path.is_file():
        return False
    script = CWS_INLINE_SCRIPT.replace("__VERSION__", _target_version())
    text = path.read_text(encoding="utf-8")
    original = text
    text = _replace_java_constant(text, "HELIUM_CWS_SCRIPT", script)
    if "private static final String HELIUM_CWS_SCRIPT" not in text:
        helper = f'''\n    // Helium: keep Chrome Web Store installation available on Android.\n    private static final String HELIUM_CWS_SCRIPT =\n            {_java_string(script)};\n\n    private void injectStoreInlineInstallSupport(Tab tab) {{\n        if (tab == null || tab.getWebContents() == null || tab.getUrl() == null) return;\n        String spec = tab.getUrl().getSpec();\n        if (spec != null && (spec.startsWith("https://chromewebstore.google.com")\n                || spec.startsWith("https://chrome.google.com/webstore"))) {{\n            tab.getWebContents().evaluateJavaScript(HELIUM_CWS_SCRIPT, null);\n        }}\n    }}\n'''
        closing = text.rfind("}")
        if closing < 0:
            raise RuntimeError(f"Could not find ChromeActivity closing brace in {path}")
        text = text[:closing] + helper + text[closing:]
    if "injectStoreInlineInstallSupport(tab);" not in text:
        load_finished = re.compile(
            r"(?m)^(?P<indent>[ \t]*)public void onPageLoadFinished\(Tab tab, GURL url\)\s*\{"
        )
        matches = list(load_finished.finditer(text))
        if len(matches) == 1:
            match = matches[0]
            insertion = "\n" + match.group("indent") + "    injectStoreInlineInstallSupport(tab);"
            text = text[:match.end()] + insertion + text[match.end():]
        elif len(matches) > 1:
            raise RuntimeError(f"Ambiguous page load hooks in {path}")
        else:
            anchor = "PersonalizeResults.Execute(tab);"
            if text.count(anchor) != 1:
                raise RuntimeError(f"Could not find an unambiguous page update hook in {path}")
            text = text.replace(anchor, anchor + "\n              injectStoreInlineInstallSupport(tab);", 1)
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def patch_download_crx_util(root: Path) -> bool:
    path = root / DOWNLOAD_CRX_UTIL
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    original = text
    marker = "bool OffStoreInstallAllowedByPrefs("
    start = text.find(marker)
    if start < 0:
        raise RuntimeError(f"Could not find {marker} in {path}")
    open_brace = text.find("{", start)
    if "clients2.google.com" not in text[start:open_brace + 500]:
        text = text[:open_brace + 1] + "\n" + CWS_ALLOWLIST + text[open_brace + 1:]
    if 'download_item.GetTargetFilePath().MatchesExtension(FILE_PATH_LITERAL(".crx"))' not in text:
        old = re.compile(
            r"  if \(download_item\.GetMimeType\(\) == extensions::Extension::kMimeType \|\|\s*"
            r"extensions::UserScript::IsURLUserScript\(download_item\.GetURL\(\),\s*"
            r"download_item\.GetMimeType\(\)\)\) \{"
        )
        replacement = '''  if (download_item.GetMimeType() == extensions::Extension::kMimeType ||
      download_item.GetURL().path().ends_with(".crx") ||
      download_item.GetTargetFilePath().MatchesExtension(FILE_PATH_LITERAL(".crx")) ||
      extensions::UserScript::IsURLUserScript(download_item.GetURL(),
                                              download_item.GetMimeType())) {'''
        text, count = old.subn(replacement, text, count=1)
        if count != 1:
            raise RuntimeError(f"Could not extend CRX download detection in {path}")
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def patch_source_tree(root: Path) -> bool:
    changed = patch_chrome_activity(root)
    download_changed = patch_download_crx_util(root)
    return changed or download_changed


if __name__ == "__main__":
    try:
        changed = patch_source_tree(Path(sys.argv[1] if len(sys.argv) > 1 else "."))
    except (OSError, RuntimeError, ValueError) as error:
        print(f"[patch_store_compatibility] {error}", file=sys.stderr)
        raise SystemExit(1)
    print("[patch_store_compatibility] Chrome Web Store compatibility active" if changed
          else "[patch_store_compatibility] Chrome Web Store compatibility already active")
