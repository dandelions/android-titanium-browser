#!/usr/bin/env python3
"""Hide the bundled Titanium ID from developer_private management UI."""

import json
import re
import sys
from pathlib import Path

GENERATOR = Path("chrome/browser/extensions/api/developer_private/extension_info_generator.cc")
ROUTER = Path("chrome/browser/extensions/api/developer_private/developer_private_event_router.cc")


def bundled_titanium_id(root: Path) -> str:
    index_path = root / "helium/dist/bundled.json"
    if not index_path.is_file():
        index_path = Path(__file__).resolve().parent / "extensions/dist/bundled.json"
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
        ids = [key for key, value in index.items()
               if isinstance(value, dict) and value.get("external_crx") == "titanium.crx"]
    except (OSError, ValueError, AttributeError) as error:
        raise RuntimeError(f"Cannot read bundled Titanium ID from {index_path}: {error}") from error
    if len(ids) != 1 or not re.fullmatch(r"[a-p]{32}", ids[0]):
        raise RuntimeError(f"Expected one valid bundled Titanium ID in {index_path}")
    return ids[0]


def replacements(titanium_id: str):
    return {
        GENERATOR: (
            ("  if (ext && ui_util::ShouldDisplayInExtensionSettings(*ext)) {",
             f'  if (ext && id != "{titanium_id}" &&\n'
             "      ui_util::ShouldDisplayInExtensionSettings(*ext)) {"),
            ("      if (ui_util::ShouldDisplayInExtensionSettings(*extension)) {",
             f'      if (extension->id() != "{titanium_id}" &&\n'
             "          ui_util::ShouldDisplayInExtensionSettings(*extension)) {"),
        ),
        ROUTER: (
            ("    const ExtensionId& extension_id) {\n"
             "  auto info_generator = std::make_unique<ExtensionInfoGenerator>(profile_);",
             "    const ExtensionId& extension_id) {\n"
             f'  if (extension_id == "{titanium_id}") {{\n'
             "    return;\n"
             "  }\n"
             "  auto info_generator = std::make_unique<ExtensionInfoGenerator>(profile_);"),
        ),
    }


def patch_source_tree(root: Path) -> bool:
    titanium_id = bundled_titanium_id(root)
    pending = {}
    for relative, changes in replacements(titanium_id).items():
        path = root / relative
        original = path.read_text(encoding="utf-8")
        text = original
        for old, new in changes:
            # Recognize the exact generated guard with either the current or an old ID.
            pattern = re.escape(new).replace(re.escape(titanium_id), r'[a-p]{32}')
            matches = list(re.finditer(pattern, text))
            if len(matches) == 1 and text.count(old) == 0:
                text = text[:matches[0].start()] + new + text[matches[0].end():]
                continue
            if text.count(old) != 1 or matches:
                raise RuntimeError(f"Unexpected source shape in {path}")
            text = text.replace(old, new, 1)
        if text != original:
            pending[path] = text
    for path, text in pending.items():
        path.write_text(text, encoding="utf-8")
    return bool(pending)


if __name__ == "__main__":
    try:
        changed = patch_source_tree(Path(sys.argv[1] if len(sys.argv) > 1 else "."))
    except (OSError, RuntimeError) as error:
        print(f"[patch_titanium_visibility] {error}", file=sys.stderr)
        raise SystemExit(1)
    print("[patch_titanium_visibility] " + ("patched" if changed else "already patched"))
