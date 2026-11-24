#!/usr/bin/env python3
"""Migrate the old-android DevTools JNI declaration to Chromium 158."""

from pathlib import Path
import sys

TARGET = Path(
    "chrome/browser/devtools/android/java/src/org/chromium/chrome/browser/devtools/"
    "DevToolsWindowAndroid.java"
)
DECL = "        void activateInspectedPage(WebContents webContents);\n"


def patch_source_tree(source_root: Path) -> bool:
    path = source_root / TARGET
    if not path.is_file():
        raise FileNotFoundError(path)
    original = path.read_text()
    lines = [line for line in original.splitlines(keepends=True) if line != DECL]
    start = next((i for i, line in enumerate(lines) if "interface Natives {" in line), None)
    if start is None:
        raise RuntimeError(f"DevTools Natives interface not found in {path}")
    brace = lines[start].find("{")
    depth = 0
    end = None
    for i in range(start, len(lines)):
        depth += lines[i].count("{") - lines[i].count("}")
        if depth == 0:
            end = i
            break
    if end is None:
        raise RuntimeError(f"DevTools Natives interface end not found in {path}")
    body = lines[start + 1 : end]
    insert_at = next((i for i, line in enumerate(body) if "void attachToBrowser(" in line), None)
    if insert_at is None:
        raise RuntimeError(f"DevTools attachToBrowser anchor not found in {path}")
    body.insert(insert_at, DECL)
    lines[start + 1 : end] = body
    updated = "".join(lines)
    if updated == original:
        return False
    path.write_text(updated)
    print(f"Patched old-android v158 DevTools JNI declaration: {path}")
    return True


if __name__ == "__main__":
    try:
        patch_source_tree(Path(sys.argv[1] if len(sys.argv) > 1 else "."))
    except (FileNotFoundError, RuntimeError) as error:
        print(f"[patch_old_android_v158_devtools_jni] {error}", file=sys.stderr)
        raise SystemExit(1)
