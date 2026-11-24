#!/usr/bin/env python3
"""Hide bundled Titanium from old-android's four-square extensions sheet."""

import json
from pathlib import Path
import re
import sys

COORDINATOR = Path(
    "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/"
    "ExtensionsToolbarCoordinatorImpl.java"
)
MARKER = "Helium: hide bundled Titanium from the four-square extensions sheet."


def bundled_titanium_id(root: Path) -> str:
    index = root / "helium/dist/bundled.json"
    data = json.loads(index.read_text(encoding="utf-8"))
    ids = [key for key, value in data.items() if value.get("external_crx") == "titanium.crx"]
    if len(ids) != 1:
        raise RuntimeError(f"Expected one bundled Titanium ID in {index}")
    return ids[0]


def patch_source_tree(root: Path) -> bool:
    path = root / COORDINATOR
    if not path.is_file():
        raise FileNotFoundError(path)
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return False
    titanium_id = bundled_titanium_id(root)
    start_marker = "    public String[] getAllExtensionActionIds() {"
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"Four-square extension ID method not found in {path}")
    brace = text.find("{", start)
    depth = 0
    end = -1
    for index in range(brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                end = index + 1
                break
    if end < 0:
        raise RuntimeError(f"Four-square extension ID method end not found in {path}")
    method = text[start:end]
    pattern = re.compile(r"(?m)^(\s*)if \(id != null && !id\.isEmpty\(\)\) \{")
    matches = list(pattern.finditer(method))
    if len(matches) != 2:
        raise RuntimeError(f"Expected two four-square ID filters in {path}, found {len(matches)}")
    method = pattern.sub(
        lambda match: f'{match.group(1)}if (id != null && !id.isEmpty() && !"{titanium_id}".equals(id)) {{',
        method,
    )
    text = text[:start] + "    // " + MARKER + "\n" + method + text[end:]
    path.write_text(text, encoding="utf-8")
    print(f"Patched old-android four-square Titanium filter: {path}")
    return True


if __name__ == "__main__":
    try:
        patch_source_tree(Path(sys.argv[1] if len(sys.argv) > 1 else "."))
    except (FileNotFoundError, RuntimeError, OSError, ValueError) as error:
        print(f"[patch_old_android_four_square_titanium] {error}", file=sys.stderr)
        raise SystemExit(1)
