#!/usr/bin/env python3
"""Migrate old Android extension bridge injections to Chromium 158 JNI pointers."""

from pathlib import Path
import sys

BRIDGES = (
    Path(
        "chrome/browser/ui/android/extensions/java/src/org/chromium/chrome/browser/ui/"
        "extensions/ExtensionsMenuBridge.java"
    ),
    Path(
        "chrome/browser/ui/android/extensions/java/src/org/chromium/chrome/browser/ui/"
        "extensions/ExtensionsToolbarBridge.java"
    ),
)

TOOLBAR_NATIVES_MARKER = "void setActiveWebContents("
TOOLBAR_NATIVES_METHOD = """        void setActiveWebContents(
                JniPtr<NativeExtensionsToolbarAndroid> self,
                @Nullable @JniType("content::WebContents*") WebContents webContents);
"""

REPLACEMENTS = (
    ("mNativeExtensionsMenuDelegateAndroid", "mNative"),
    ("mNativeExtensionsToolbarAndroid", "mNative"),
    (
        "long nativeExtensionsMenuDelegateAndroid",
        "JniPtr<NativeExtensionsMenuDelegateAndroid> self",
    ),
    (
        "long nativeExtensionsToolbarAndroid",
        "JniPtr<NativeExtensionsToolbarAndroid> self",
    ),
    ("        assert mNative != 0;\n", ""),
)


def migrate_source_tree(source_root: Path) -> bool:
    changed = False
    for relative in BRIDGES:
        path = source_root / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        text = path.read_text(encoding="utf-8")
        original = text
        for old, new in REPLACEMENTS:
            text = text.replace(old, new)
        if path.name == "ExtensionsToolbarBridge.java" and TOOLBAR_NATIVES_MARKER not in text:
            anchor = "        void executeUserAction("
            if anchor not in text:
                raise RuntimeError(f"Toolbar Natives anchor not found in {path}")
            text = text.replace(anchor, TOOLBAR_NATIVES_METHOD + "\n" + anchor, 1)
        if text != original:
            path.write_text(text, encoding="utf-8")
            changed = True
            print(f"Migrated old-android v158 JNI bridge: {path}")
    return changed


if __name__ == "__main__":
    try:
        migrate_source_tree(Path(sys.argv[1] if len(sys.argv) > 1 else "."))
    except (FileNotFoundError, RuntimeError) as error:
        print(f"[patch_old_android_v158_extension_jni] {error}", file=sys.stderr)
        raise SystemExit(1)
