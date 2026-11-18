#!/usr/bin/env python3
"""Allow same-extension resources in old-android single-process mode."""
import os
import sys

TARGET = "extensions/browser/extension_protocols.cc"
ANCHOR = """  if (process_map.Contains(request.url.GetHost(), child_id)) {
    return true;
  }
"""
PATCH = """  // VMOS Android 9 uses one renderer process for all extension pages, so
  // the ProcessMap cannot identify a page loading its own extension resources.
  // Preserve same-origin access only in old-android single-process mode.
  if (content::RenderProcessHost::run_renderer_in_process() && extension &&
      !extension->is_hosted_app() && request.request_initiator &&
      request.request_initiator.value() == extension->origin() &&
      url::Origin::Create(request.url) == extension->origin()) {
    return true;
  }
"""
MARKER = "VMOS Android 9 uses one renderer process for all extension pages"


def patch_source_tree(src_dir: str) -> bool:
    path = os.path.join(src_dir, TARGET)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read()

    if MARKER in content:
        return False
    if ANCHOR not in content:
        raise RuntimeError(f"extension resource policy anchor not found in {path}")

    content = content.replace(ANCHOR, ANCHOR + "\n" + PATCH, 1)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    print(f"Patched old-android same-extension resource loading: {path}")
    return True


if __name__ == "__main__":
    try:
        patch_source_tree(sys.argv[1] if len(sys.argv) > 1 else ".")
    except (FileNotFoundError, RuntimeError) as error:
        print(f"[patch_old_android_extension_resources] {error}", file=sys.stderr)
        raise SystemExit(1)
