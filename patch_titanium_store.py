#!/usr/bin/env python3
"""Restore Titanium's native extension-store installation path."""

import re
import sys
from pathlib import Path

CHROME_ACTIVITY = Path(
    "chrome/android/java/src/org/chromium/chrome/browser/app/ChromeActivity.java"
)
DOWNLOAD_CRX_UTIL = Path("chrome/browser/download/download_crx_util.cc")
EXTENSION_UTIL = Path("extensions/browser/extension_util.cc")
DESKTOP_SITE_UTILS = Path(
    "chrome/browser/ui/android/desktop_site/java/src/org/chromium/chrome/browser/desktop_site/DesktopSiteUtils.java"
)
WEBSTORE_PRIVATE_PATHS = (
    Path("extensions/browser/api/webstore_private/webstore_private_api.cc"),
    Path("chrome/browser/extensions/api/webstore_private/webstore_private_api.cc"),
)
MANIFEST_V2_HANDLER = Path("extensions/browser/manifest_v2_handler.cc")
API_FEATURES = Path("extensions/common/api/_api_features.json")
VERSION_INFO = Path("base/version_info/version_info.cc")

TITANIUM_ALLOWLIST = '''
  if (const auto& o = item.GetRequestInitiator(); o && o->scheme() == "chrome-extension") return true;
  for (const char* d : {"addons.opera.com", "operacdn.com", "microsoftedge.microsoft.com", "edge.microsoft.com", "delivery.mp.microsoft.com"}) if (item.GetURL().DomainIs(d) || item.GetReferrerUrl().DomainIs(d)) return true;'''


def _matching_brace(text: str, open_index: int) -> int:
    depth = 0
    in_string = False
    escaped = False
    for index in range(open_index, len(text)):
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
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    raise RuntimeError("Unclosed generated code block")


def clean_chrome_activity(path: Path) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    original = text
    text = re.sub(
        r"(?m)^[ \t]*injectStoreInlineInstallSupport\(tab\);[ \t]*\n?", "", text
    )

    for name in ("HELIUM_CWS_SCRIPT", "HELIUM_EDGE_SCRIPT"):
        marker = f"private static final String {name}"
        while marker in text:
            start = text.rfind("\n", 0, text.index(marker)) + 1
            semicolon = text.index("=", text.index(marker)) + 1
            in_string = False
            escaped = False
            end = -1
            for index in range(semicolon, len(text)):
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
                raise RuntimeError(f"Could not find end of {name} in {path}")
            text = text[:start] + text[end:]

    method_marker = "private void injectStoreInlineInstallSupport(Tab tab)"
    while method_marker in text:
        method_start = text.index(method_marker)
        line_start = text.rfind("\n", 0, method_start) + 1
        comment = text.rfind("// Helium: Native inline installation", 0, method_start)
        if comment >= line_start - 100:
            line_start = text.rfind("\n", 0, comment) + 1
        open_brace = text.find("{", method_start)
        close_brace = _matching_brace(text, open_brace)
        text = text[:line_start] + text[close_brace + 1:]

    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def restore_titanium_allowlist(path: Path) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    original = text
    text = re.sub(
        r'(?m)^[ \t]*download_item\.GetURL\(\)\.path\(\)\.ends_with\("\.crx"\) \|\|[ \t]*\n',
        "",
        text,
    )
    text = re.sub(
        r'(?m)^[ \t]*download_item\.GetTargetFilePath\(\)\.MatchesExtension\(FILE_PATH_LITERAL\("\.crx"\)\) \|\|[ \t]*\n',
        "",
        text,
    )
    marker = "bool OffStoreInstallAllowedByPrefs("
    start = text.find(marker)
    if start < 0:
        raise RuntimeError(f"OffStoreInstallAllowedByPrefs not found in {path}")
    open_brace = text.find("{", start)
    close_brace = _matching_brace(text, open_brace)
    function = text[start:close_brace + 1]
    body_start = function.find("{") + 1
    body_end = len(function) - 1
    body = function[body_start:body_end]

    body = re.sub(
        r"(?m)^[ \t]*// Helium: Whitelist store domains for inline CRX installation\n[\s\S]*?^[ \t]{2,}\}[ \t]*\n?",
        "",
        body,
        count=1,
    )
    # Remove the exact multiline CWS allowlist generated by the old compatibility patch.
    body = re.sub(
        r'(?m)^[ \t]*for \(const char\* d : \{"clients2\.google\.com", "clients2\.googleusercontent\.com",\n'
        r'[ \t]*"chromewebstore\.google\.com", "chrome\.google\.com",\n'
        r'[ \t]*"google\.com", "googleusercontent\.com"\}\) \{\n'
        r'[ \t]*if \(item\.GetURL\(\)\.DomainIs\(d\) \|\| item\.GetReferrerUrl\(\)\.DomainIs\(d\)\) return true;\n'
        r'[ \t]*\}[ \t]*\n?', "", body,
    )
    body = re.sub(
        r"(?m)^[ \t]*if \(const auto& o = item\.GetRequestInitiator\(\);[^\n]*\n?",
        "",
        body,
    )
    body = re.sub(
        r"(?m)^[ \t]*for \(const char\* d : \{[^}\n]*\}\) if \(item\.GetURL\(\)\.DomainIs\(d\) \|\| item\.GetReferrerUrl\(\)\.DomainIs\(d\)\) return true;[ \t]*\n?",
        "",
        body,
    )

    normalized = function[:body_start] + TITANIUM_ALLOWLIST + body + "}"
    result = text[:start] + normalized + text[close_brace + 1:]
    if result != original:
        path.write_text(result, encoding="utf-8")
        return True
    return False


def clean_legacy_extension_detection(path: Path) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    marker = "bool IsExtensionDownload(const download::DownloadItem& download_item) {"
    start = text.find(marker)
    if start < 0:
        return False
    end = _matching_brace(text, text.find("{", start)) + 1
    function = text[start:end]
    legacy = ('\n      || download_item.GetURL().path().ends_with(".crx")'
              '\n      || download_item.GetTargetFilePath().MatchesExtension(FILE_PATH_LITERAL(".crx"))')
    cleaned = function.replace(legacy, "", 1)
    if cleaned == function:
        return False
    path.write_text(text[:start] + cleaned + text[end:], encoding="utf-8")
    return True


STORE_DESKTOP_CHECK = """        if (!GURL.isEmptyOrInvalid(url)) {
            String host = url.getHost();
            if ("chromewebstore.google.com".equals(host) || "chrome.google.com".equals(host)) {
                return true;
            }
        }
"""


def patch_desktop_site_utils(path: Path) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    original = text

    # Remove historical custom scope call in maybeDefaultEnableWindowSetting
    text = re.sub(
        r"(?m)^[ \t]*WebsitePreferenceBridge\.setContentSettingCustomScope\([^\n]*chromewebstore\.google\.com[^\n]*\);?[ \t]*\n?",
        "",
        text,
    )
    # Remove existing store check if present to ensure clean idempotent re-application
    text = re.sub(
        r'(?m)^[ \t]*if \(!GURL\.isEmptyOrInvalid\(url\)\) \{\n[ \t]*String host = url\.getHost\(\);\n[ \t]*if \("chromewebstore\.google\.com"\.equals\(host\) \|\| "chrome\.google\.com"\.equals\(host\)\) \{\n[ \t]*return true;\n[ \t]*\}\n[ \t]*\}\n?',
        "",
        text,
    )

    pattern1 = re.compile(
        r"(?m)^([ \t]*public static boolean shouldOverrideDesktopSite\s*\([\s\S]*?\)\s*\{[ \t]*\n)"
    )
    match1 = pattern1.search(text)
    if match1:
        text = text[:match1.end()] + STORE_DESKTOP_CHECK + text[match1.end():]

    pattern2 = re.compile(
        r"(?m)^([ \t]*public static boolean isDesktopSiteEnabled\s*\([\s\S]*?\)\s*\{[ \t]*\n)"
    )
    match2 = pattern2.search(text)
    if match2:
        text = text[:match2.end()] + STORE_DESKTOP_CHECK + text[match2.end():]

    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def patch_webstore_api_features(path: Path) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    original = text
    for api_name in ('"webstorePrivate":', '"management":'):
        start = text.find(api_name)
        if start < 0:
            raise RuntimeError(f"{api_name} feature block not found in {path}")
        block_match = re.search(r"\n[ \t]*\}\],?", text[start:])
        if block_match is None:
            raise RuntimeError(f"{api_name} feature block end not found in {path}")
        block_end = start + block_match.start()
        block = text[start:block_end]
        old = '"matches": ["https://chromewebstore.google.com/*"]'
        new = (
            '"matches": ["https://chromewebstore.google.com/*",\n'
            '                  "https://chrome.google.com/webstore/*"]'
        )
        if new not in block:
            if old not in block:
                raise RuntimeError(f"{api_name} store match anchor not found in {path}")
            block = block.replace(old, new, 1)
            text = text[:start] + block + text[block_end:]
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def patch_webstore_private_api(source_root: Path) -> bool:
    changed = patch_webstore_api_features(source_root / API_FEATURES)
    old_version_stmt = "  GetFullChromeVersion::Results::Info info;\n  info.version_number = std::string(version);"
    new_version_stmt = (
        "  size_t dot_count = 0;\n"
        "  size_t trim_pos = version.size();\n"
        "  for (size_t i = 0; i < version.size(); ++i) {\n"
        "    if (version[i] == '.' && ++dot_count == 4) {\n"
        "      trim_pos = i;\n"
        "      break;\n"
        "    }\n"
        "  }\n"
        "  GetFullChromeVersion::Results::Info info;\n"
        "  info.version_number = std::string(version.substr(0, trim_pos));"
    )
    for rel_path in WEBSTORE_PRIVATE_PATHS:
        path = source_root / rel_path
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        original = text
        text = text.replace(
            "api::webstore_private::MV2DeprecationStatus::kHardDisable",
            "api::webstore_private::MV2DeprecationStatus::kNone",
        )
        if new_version_stmt not in text and old_version_stmt in text:
            text = text.replace(old_version_stmt, new_version_stmt, 1)
        if text != original:
            path.write_text(text, encoding="utf-8")
            changed = True
    return changed


def patch_version_info(path: Path) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    original = text
    old = (
        "#if BUILDFLAG(IS_ANDROID)\n"
        "std::string_view GetVersionNumber() {\n"
        "  return base::android::apk_info::package_version_name();\n"
        "}\n"
        "#endif"
    )
    new = (
        "#if BUILDFLAG(IS_ANDROID)\n"
        "std::string_view GetVersionNumber() {\n"
        "  static const base::NoDestructor<std::string> version_number([] {\n"
        "    std::string_view name = base::android::apk_info::package_version_name();\n"
        "    size_t dot_count = 0;\n"
        "    for (size_t i = 0; i < name.size(); ++i) {\n"
        "      if (name[i] == '.' && ++dot_count == 4) {\n"
        "        return std::string(name.substr(0, i));\n"
        "      }\n"
        "    }\n"
        "    return std::string(name);\n"
        "  }());\n"
        "  return *version_number;\n"
        "}\n"
        "#endif"
    )
    if new in text:
        return False
    if old not in text:
        raise RuntimeError(f"GetVersionNumber anchor not found in {path}")
    text = text.replace(old, new, 1)
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def patch_manifest_v2_handler(path: Path) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    original = text
    text = text.replace(
        "bool g_allow_mv2_for_testing = false;",
        "bool g_allow_mv2_for_testing = true;",
    )
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


clean_extension_detection = clean_legacy_extension_detection


def patch_source_tree(source_root: Path) -> bool:
    changed = clean_chrome_activity(source_root / CHROME_ACTIVITY)
    changed = restore_titanium_allowlist(source_root / DOWNLOAD_CRX_UTIL) or changed
    changed = clean_legacy_extension_detection(source_root / EXTENSION_UTIL) or changed
    changed = patch_desktop_site_utils(source_root / DESKTOP_SITE_UTILS) or changed
    changed = patch_webstore_private_api(source_root) or changed
    changed = patch_manifest_v2_handler(source_root / MANIFEST_V2_HANDLER) or changed
    changed = patch_version_info(source_root / VERSION_INFO) or changed
    return changed


if __name__ == "__main__":
    try:
        changed = patch_source_tree(Path(sys.argv[1] if len(sys.argv) > 1 else "."))
    except (OSError, RuntimeError, ValueError) as error:
        print(f"[patch_titanium_store] {error}", file=sys.stderr)
        raise SystemExit(1)
    print("[patch_titanium_store] restored Titanium native store flow" if changed else
          "[patch_titanium_store] Titanium native store flow already active")
