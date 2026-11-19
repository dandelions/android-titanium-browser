#!/usr/bin/env python3
"""Allow extension messaging between extension pages in single-process mode.

VMOS Android 9 renders every extension page in the browser process, so
ProcessMap never attributes the frame to its extension. The messaging bindings
treat that as a message from a sandboxed process and report the renderer, which
in single-process mode terminates the browser (SIGTRAP). The origin has already
been validated by CanRendererHostExtensionOrigin() before the ProcessMap check,
so accepting in-process senders keeps the same trust level.
"""
import os
import sys

TARGET = "extensions/browser/api/messaging/message_service_bindings.cc"
EXTENSION_SOURCE_OLD = """      if (!ProcessMap::Get(process.GetBrowserContext())
               ->Contains(*source_endpoint_extension_id, process.GetID())) {
"""
EXTENSION_SOURCE_NEW = """      if (!RenderProcessHost::run_renderer_in_process() &&
          !ProcessMap::Get(process.GetBrowserContext())
               ->Contains(*source_endpoint_extension_id, process.GetID())) {
"""
CHANNEL_PRECURSOR_OLD = """  if (precursor_origin.scheme() == kExtensionScheme &&
      !ProcessMap::Get(process.GetBrowserContext())
           ->Contains(precursor_origin.host(), process.GetID())) {
"""
CHANNEL_PRECURSOR_NEW = """  if (precursor_origin.scheme() == kExtensionScheme &&
      !RenderProcessHost::run_renderer_in_process() &&
      !ProcessMap::Get(process.GetBrowserContext())
           ->Contains(precursor_origin.host(), process.GetID())) {
"""
MARKER = "RenderProcessHost::run_renderer_in_process() &&"


def patch_source_tree(src_dir: str) -> bool:
    path = os.path.join(src_dir, TARGET)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read()

    if content.count(MARKER) == 2:
        return False
    if MARKER in content:
        raise RuntimeError(f"partially patched messaging sources in {path}")
    if content.count(EXTENSION_SOURCE_OLD) != 1:
        raise RuntimeError(f"messaging source check not found in {path}")
    if content.count(CHANNEL_PRECURSOR_OLD) != 1:
        raise RuntimeError(f"messaging channel check not found in {path}")

    content = content.replace(EXTENSION_SOURCE_OLD, EXTENSION_SOURCE_NEW, 1)
    content = content.replace(CHANNEL_PRECURSOR_OLD, CHANNEL_PRECURSOR_NEW, 1)

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    print(f"Patched old-android extension messaging: {path}")
    return True


if __name__ == "__main__":
    try:
        patch_source_tree(sys.argv[1] if len(sys.argv) > 1 else ".")
    except (FileNotFoundError, RuntimeError) as error:
        print(f"[patch_old_android_extension_messaging] {error}", file=sys.stderr)
        raise SystemExit(1)
