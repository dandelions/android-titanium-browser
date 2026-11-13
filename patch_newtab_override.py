#!/usr/bin/env python3
"""Make extension new tab page overrides work on the Android 9 car build.

`ExtensionUrlOverrides` keeps the active overrides in the
`extensions.chrome_url_overrides` profile pref, and that pref is only written
when an extension loads *after* `ExtensionUrlOverridesRegistrar` exists. On
Android the registrar is created lazily (the profile is built before the
keyed service factories are registered), so an extension that is already
loaded never reaches the pref and `chrome://newtab` keeps resolving to the
native new tab page.

The patch adds a fallback that reads the overrides straight from the enabled
extension set when the pref has no entry for the requested host, and logs the
decision to logcat so the remaining cases stay diagnosable.
"""
import os
import sys


OVERRIDES_FILE = "chrome/browser/extensions/extension_url_overrides.cc"
RESOLVER_FILE = (
    "chrome/browser/url_constants/android/java/src/org/chromium/chrome/browser/"
    "url_constants/UrlConstantResolver.java"
)

ORIGINAL_LOOKUP = """  const base::ListValue* url_list = overrides.FindListByDottedPath(url.host());
  if (!url_list) {
    return {};  // No overrides present for this host.
  }

  extensions::ExtensionRegistry* registry =
      extensions::ExtensionRegistry::Get(browser_context);
  const extensions::ExtensionSet& extensions = registry->enabled_extensions();
"""

PATCHED_LOOKUP = """  extensions::ExtensionRegistry* registry =
      extensions::ExtensionRegistry::Get(browser_context);
  const extensions::ExtensionSet& extensions = registry->enabled_extensions();

  const base::ListValue* url_list = overrides.FindListByDottedPath(url.host());
  if (!url_list) {
    // The pref list is only filled when an extension loads after the
    // registrar exists. On Android the registrar can be created after the
    // extensions load, so read the overrides from the enabled set instead.
    const std::string override_host(url.host());
    std::vector<GURL> fallback;
    if (!profile->IsOffTheRecord()) {
      for (const auto& extension : extensions) {
        const URLOverrides::URLOverrideMap& extension_overrides =
            URLOverrides::GetChromeURLOverrides(extension.get());
        auto override_iter = extension_overrides.find(override_host);
        if (override_iter == extension_overrides.end() ||
            !override_iter->second.is_valid()) {
          continue;
        }
        if (extensions::Manifest::IsComponentLocation(extension->location())) {
          continue;
        }
        fallback.push_back(override_iter->second);
      }
    }
    if (url.host() == chrome::kChromeUINewTabHost) {
      LOG(INFO) << "HeliumNtp: pref list missing, enabled overrides="
                << fallback.size();
    }
    return fallback;
  }
  if (url.host() == chrome::kChromeUINewTabHost) {
    LOG(INFO) << "HeliumNtp: pref list entries=" << url_list->size();
  }
"""

ORIGINAL_NTP_URL = """    public String getNtpUrl() {
        return getUrlOverrideIfPresent(getOriginalNativeNtpUrl());
    }
"""

PATCHED_NTP_URL = """    public String getNtpUrl() {
        String url = getUrlOverrideIfPresent(getOriginalNativeNtpUrl());
        Log.i(
                "HeliumNtp",
                "resolver ntp="
                        + url
                        + " overrideEnabled="
                        + ExtensionsUrlOverrideRegistry.getNtpOverrideEnabled());
        return url;
    }
"""


BROKEN_LOOKUP = """        auto override_iter = extension_overrides.find(url.host());
"""

BROKEN_FALLBACK_HEAD = """    std::vector<GURL> fallback;
    if (!profile->IsOffTheRecord()) {
"""

FIXED_LOOKUP = """        auto override_iter = extension_overrides.find(override_host);
"""

FIXED_FALLBACK_HEAD = """    const std::string override_host(url.host());
    std::vector<GURL> fallback;
    if (!profile->IsOffTheRecord()) {
"""


def upgrade_previous_revision(path):
    """Rewrite a tree patched by the first revision of this script."""
    content = _read(path)
    if BROKEN_LOOKUP not in content:
        return False
    new_content = content.replace(BROKEN_LOOKUP, FIXED_LOOKUP, 1)
    new_content = new_content.replace(BROKEN_FALLBACK_HEAD, FIXED_FALLBACK_HEAD, 1)
    if new_content == content:
        return False
    _write(path, new_content)
    print(f"Upgraded new tab override fallback: {path}")
    return True


def _read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _write(path, content):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def patch_override_fallback(src_dir):
    path = os.path.join(src_dir, OVERRIDES_FILE)
    if not os.path.isfile(path):
        return False
    content = _read(path)
    if "HeliumNtp: pref list missing" in content:
        return upgrade_previous_revision(path)
    if ORIGINAL_LOOKUP not in content:
        print(
            "Warning: could not find the chrome URL override lookup in "
            f"{path}",
            file=sys.stderr,
        )
        return False

    new_content = content.replace(ORIGINAL_LOOKUP, PATCHED_LOOKUP, 1)
    if '#include "base/logging.h"' not in new_content:
        new_content = new_content.replace(
            '#include "base/functional/bind.h"\n',
            '#include "base/functional/bind.h"\n#include "base/logging.h"\n',
            1,
        )
    _write(path, new_content)
    print(f"Patched new tab override fallback: {path}")
    return True


def patch_resolver_logging(src_dir):
    path = os.path.join(src_dir, RESOLVER_FILE)
    if not os.path.isfile(path):
        return False
    content = _read(path)
    if '"HeliumNtp"' in content:
        return False
    if ORIGINAL_NTP_URL not in content:
        print(
            f"Warning: could not find getNtpUrl() in {path}",
            file=sys.stderr,
        )
        return False

    new_content = content.replace(ORIGINAL_NTP_URL, PATCHED_NTP_URL, 1)
    if "import android.util.Log;" not in new_content:
        new_content = new_content.replace(
            "import org.chromium.build.annotations.NullMarked;\n",
            "import android.util.Log;\n\n"
            "import org.chromium.build.annotations.NullMarked;\n",
            1,
        )
    _write(path, new_content)
    print(f"Patched new tab URL resolver logging: {path}")
    return True


def patch_source_tree(src_dir):
    changed = patch_override_fallback(src_dir)
    changed = patch_resolver_logging(src_dir) or changed
    return changed


def main():
    src_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    patch_source_tree(src_dir)


if __name__ == "__main__":
    main()
