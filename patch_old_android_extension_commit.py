#!/usr/bin/env python3
"""Allow extension pages to commit in old-android single-process mode.

The old Android compatibility build keeps the renderer in the browser process
because VMOS loses the cross-process CommitNavigation handoff. Chromium's
extension ProcessMap check normally rejects extension URLs in that shared
process. Limit the exception to the explicit single-process compatibility mode;
normal multi-process extension isolation remains unchanged.
"""
import os
import sys

TARGET = "chrome/browser/extensions/chrome_content_browser_client_extensions_part.cc"
INCLUDE_ANCHOR = '#include "content/public/common/child_process_id.h"\n'
INCLUDE_PATCH = INCLUDE_ANCHOR + '#include "content/public/common/content_switches.h"\n'
ORIGINAL = """  ProcessMap* process_map = ProcessMap::Get(process_host->GetBrowserContext());
  if (process_map->Contains(extension->id(), process_host->GetID())) {
    return true;
  }
"""
PATCHED = """  ProcessMap* process_map = ProcessMap::Get(process_host->GetBrowserContext());
  if (process_map->Contains(extension->id(), process_host->GetID())) {
    return true;
  }

  // VMOS Android 9 uses the old-android single-process compatibility mode.
  // The browser process owns the page there, so it cannot appear in the
  // extension ProcessMap. Keep the normal multi-process check unchanged.
  if (base::CommandLine::ForCurrentProcess()->HasSwitch(
          ::switches::kSingleProcess)) {
    return true;
  }
"""
MARKER = "VMOS Android 9 uses the old-android single-process compatibility mode."
OLD_SWITCH = "          switches::kSingleProcess)) {"
NEW_SWITCH = "          ::switches::kSingleProcess)) {"


def patch_source_tree(src_dir: str) -> bool:
    path = os.path.join(src_dir, TARGET)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read()
    if MARKER in content:
        if OLD_SWITCH in content:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(content.replace(OLD_SWITCH, NEW_SWITCH, 1))
            print(f"Updated old-android switch namespace: {path}")
            return True
        return False
    if INCLUDE_ANCHOR not in content:
        raise RuntimeError(f"content switch include anchor not found in {path}")
    if ORIGINAL not in content:
        raise RuntimeError(f"extension commit check not found in {path}")
    content = content.replace(INCLUDE_ANCHOR, INCLUDE_PATCH, 1)
    content = content.replace(ORIGINAL, PATCHED, 1)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    print(f"Patched old-android extension commit check: {path}")
    return True


if __name__ == "__main__":
    try:
        patch_source_tree(sys.argv[1] if len(sys.argv) > 1 else ".")
    except (FileNotFoundError, RuntimeError) as error:
        print(f"[patch_old_android_extension_commit] {error}", file=sys.stderr)
        raise SystemExit(1)
