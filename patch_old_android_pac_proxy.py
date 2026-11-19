#!/usr/bin/env python3
"""Keep the V8 proxy resolver available in old-android single-process mode.

With --single-process the network service runs inside the browser process and
Chromium deliberately skips the V8 proxy resolver, which makes every PAC based
proxy configuration unusable (SwitchyOmega's "auto switch" mode, PAC URLs in the
system proxy settings). The switch is a leftover workaround from before the
resolver used a private V8 isolate, so keep the resolver installed.
"""
import os
import sys

TARGET = "chrome/browser/net/system_network_context_manager.cc"
ORIGINAL = """    if (command_line.HasSwitch(switches::kSingleProcess)) {
      LOG(ERROR) << "Cannot use V8 Proxy resolver in single process mode.";
    } else {
"""
PATCHED = """    // VMOS Android 9 keeps the network service inside the browser process. The
    // V8 resolver still works there, and PAC proxy rules require it.
    {
"""
MARKER = "V8 resolver still works there, and PAC proxy rules require it."


def patch_source_tree(src_dir: str) -> bool:
    path = os.path.join(src_dir, TARGET)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read()

    if MARKER in content:
        return False
    if ORIGINAL not in content:
        raise RuntimeError(f"single process proxy resolver branch not found in {path}")

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content.replace(ORIGINAL, PATCHED, 1))
    print(f"Patched old-android PAC proxy resolver: {path}")
    return True


if __name__ == "__main__":
    try:
        patch_source_tree(sys.argv[1] if len(sys.argv) > 1 else ".")
    except (FileNotFoundError, RuntimeError) as error:
        print(f"[patch_old_android_pac_proxy] {error}", file=sys.stderr)
        raise SystemExit(1)
