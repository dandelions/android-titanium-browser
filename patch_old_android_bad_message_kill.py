#!/usr/bin/env python3
"""Keep the browser alive when a bad IPC message is reported in single-process mode.

The old-android build runs Chromium with --single-process so the renderer shares
the browser process. RenderProcessHostImpl::ShutdownForBadMessage() assumes a
separate renderer process and calls NOTREACHED(), which compiles to
base::ImmediateCrash() (SIGTRAP) and terminates the whole browser. Dropping the
message matches the multi-process behavior of killing only the sender.
"""
import os
import re
import sys

TARGET = "content/browser/renderer_host/render_process_host_impl.cc"
ORIGINAL = re.compile(
    r"  if \(run_renderer_in_process\(\)\) \{\n"
    r"(?:[ ]*//[^\n]*\n)*"
    r"    NOTREACHED\(\);\n"
    r"  \}\n"
)
PATCHED = """  if (run_renderer_in_process()) {
    // VMOS Android 9 keeps the renderer inside the browser process, so killing
    // it would terminate the whole browser. Drop the message instead.
    return;
  }
"""
MARKER = "VMOS Android 9 keeps the renderer inside the browser process"


def patch_source_tree(src_dir: str) -> bool:
    path = os.path.join(src_dir, TARGET)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read()

    if MARKER in content:
        return False
    if not ORIGINAL.search(content):
        raise RuntimeError(f"bad message shutdown hook not found in {path}")

    content = ORIGINAL.sub(PATCHED, content, count=1)

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    print(f"Patched old-android bad message shutdown: {path}")
    return True


if __name__ == "__main__":
    try:
        patch_source_tree(sys.argv[1] if len(sys.argv) > 1 else ".")
    except (FileNotFoundError, RuntimeError) as error:
        print(f"[patch_old_android_bad_message_kill] {error}", file=sys.stderr)
        raise SystemExit(1)