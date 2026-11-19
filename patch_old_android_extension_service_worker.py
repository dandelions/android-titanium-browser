#!/usr/bin/env python3
"""Start extension service workers in old-android single-process mode.

ServiceWorkerHost silently drops the service worker startup notifications when
the renderer process is missing from ProcessMap. In single-process mode the
renderer is the browser process and never gets registered, so MV3 extensions end
up with an unregistered background worker: extension API calls fail with
"No SW" and chrome.proxy settings are never applied.
"""
import os
import sys

TARGET = "extensions/browser/service_worker/service_worker_host.cc"
ORIGINAL = """  if (!process_map || !process_map->Contains(extension_id, render_process_id)) {
"""
PATCHED = """  if (!content::RenderProcessHost::run_renderer_in_process() &&
      (!process_map || !process_map->Contains(extension_id, render_process_id))) {
"""
MARKER = "content::RenderProcessHost::run_renderer_in_process() &&"
EXPECTED_SITES = 3


def patch_source_tree(src_dir: str) -> bool:
    path = os.path.join(src_dir, TARGET)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read()

    if content.count(MARKER) == EXPECTED_SITES:
        return False
    if MARKER in content:
        raise RuntimeError(f"partially patched service worker hosts in {path}")
    if content.count(ORIGINAL) != EXPECTED_SITES:
        raise RuntimeError(
            f"expected {EXPECTED_SITES} service worker process checks in {path}"
        )

    content = content.replace(ORIGINAL, PATCHED)

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    print(f"Patched old-android extension service worker: {path}")
    return True


if __name__ == "__main__":
    try:
        patch_source_tree(sys.argv[1] if len(sys.argv) > 1 else ".")
    except (FileNotFoundError, RuntimeError) as error:
        print(f"[patch_old_android_extension_service_worker] {error}", file=sys.stderr)
        raise SystemExit(1)
