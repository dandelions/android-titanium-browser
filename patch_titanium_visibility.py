#!/usr/bin/env python3
"""Hide the bundled Titanium ID from developer_private management UI."""

import sys
from pathlib import Path


TITANIUM_ID = "jlbggdgofbcndkkdimpeccablefilpkm"
GENERATOR = Path("chrome/browser/extensions/api/developer_private/extension_info_generator.cc")
ROUTER = Path("chrome/browser/extensions/api/developer_private/developer_private_event_router.cc")

REPLACEMENTS = {
    GENERATOR: (
        (
            "  if (ext && ui_util::ShouldDisplayInExtensionSettings(*ext)) {",
            f'  if (ext && id != "{TITANIUM_ID}" &&\n'
            "      ui_util::ShouldDisplayInExtensionSettings(*ext)) {",
        ),
        (
            "      if (ui_util::ShouldDisplayInExtensionSettings(*extension)) {",
            f'      if (extension->id() != "{TITANIUM_ID}" &&\n'
            "          ui_util::ShouldDisplayInExtensionSettings(*extension)) {",
        ),
    ),
    ROUTER: (
        (
            "    const ExtensionId& extension_id) {\n"
            "  auto info_generator = std::make_unique<ExtensionInfoGenerator>(profile_);",
            "    const ExtensionId& extension_id) {\n"
            f'  if (extension_id == "{TITANIUM_ID}") {{\n'
            "    return;\n"
            "  }\n"
            "  auto info_generator = std::make_unique<ExtensionInfoGenerator>(profile_);",
        ),
    ),
}


def patch_source_tree(root: Path) -> bool:
    pending = {}
    for relative, replacements in REPLACEMENTS.items():
        path = root / relative
        original = path.read_text(encoding="utf-8")
        text = original
        for old, new in replacements:
            if text.count(new) == 1 and text.count(old) == 0:
                continue
            if text.count(old) != 1 or text.count(new):
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
