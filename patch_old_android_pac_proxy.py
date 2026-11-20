#!/usr/bin/env python3
"""Preserve Chromium's upstream PAC resolver restriction in single-process mode.

The old-android build runs with --single-process. Chromium explicitly disables
the V8 proxy resolver in this mode. A previous workaround enabled it without
validating thread-safety on VMOS Android 9; the device reproduced a SIGSEGV in
the Proxy Resolver thread followed by a browser-process SIGTRAP. Restore the
upstream guard. PAC / SwitchyOmega auto-switch remains unsupported until the
resolver can be run safely in a separate process or fixed upstream.
"""
import os
import sys

TARGET = "chrome/browser/net/system_network_context_manager.cc"
ORIGINAL = """    if (command_line.HasSwitch(switches::kSingleProcess)) {
      LOG(ERROR) << "Cannot use V8 Proxy resolver in single process mode.";
    } else {
"""
UNSAFE_SINGLE_PROCESS_OVERRIDE = """    // VMOS Android 9 keeps the network service inside the browser process. The
    // V8 resolver still works there, and PAC proxy rules require it.
    {
"""
UPSTREAM_RESTRICTION_MARKER = (
    'LOG(ERROR) << "Cannot use V8 Proxy resolver in single process mode.";'
)
UNSAFE_OVERRIDE_MARKER = "V8 resolver still works there, and PAC proxy rules require it."
DEDICATED_PROCESS_MARKER = "Helium: the PAC resolver runs in a dedicated utility process."


def patch_source_tree(src_dir: str) -> bool:
    path = os.path.join(src_dir, TARGET)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read()

    if UPSTREAM_RESTRICTION_MARKER in content:
        return False
    if DEDICATED_PROCESS_MARKER in content:
        return False
    if content.count(UNSAFE_SINGLE_PROCESS_OVERRIDE) != 1:
        raise RuntimeError(f"unsafe single-process PAC resolver override not found in {path}")

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content.replace(UNSAFE_SINGLE_PROCESS_OVERRIDE, ORIGINAL, 1))
    print(f"Restored Chromium single-process PAC resolver restriction: {path}")
    return True


if __name__ == "__main__":
    try:
        patch_source_tree(sys.argv[1] if len(sys.argv) > 1 else ".")
    except (FileNotFoundError, RuntimeError) as error:
        print(f"[patch_old_android_pac_proxy] {error}", file=sys.stderr)
        raise SystemExit(1)
