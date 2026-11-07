#!/usr/bin/env python3
"""Attach bundled extension assets to the Android non-pak asset group."""

import re
import sys
from pathlib import Path


def patch(path: Path) -> bool:
    source = path.read_text(encoding="utf-8")
    group = source.find('java_group("chrome_public_non_pak_assets")')
    if group < 0:
        raise RuntimeError(f"Android non-pak asset group not found in {path}")
    deps = source.find("deps = [", group)
    next_group = source.find('\n}', group)
    if deps < 0 or (next_group >= 0 and deps > next_group):
        raise RuntimeError(f"Android non-pak asset deps not found in {path}")
    start = deps + len("deps = [")
    end = source.find("]", start)
    if end < 0:
        raise RuntimeError(f"Android non-pak asset deps incomplete in {path}")
    target = '"//helium/dist:extension_assets",'
    body = source[start:end]
    if target in body:
        return False
    indent_match = re.search(r"\n([ \t]*)\S", body)
    indent = indent_match.group(1) if indent_match else "      "
    path.write_text(source[:start] + "\n" + indent + target + source[start:], encoding="utf-8")
    return True


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise RuntimeError("usage: patch_android_asset_group.py BUILD.gn")
        changed = patch(Path(sys.argv[1]))
    except (OSError, RuntimeError) as error:
        print(f"[patch_android_asset_group] {error}", file=sys.stderr)
        raise SystemExit(1)
    print("[patch_android_asset_group] " + ("patched" if changed else "already patched"))
