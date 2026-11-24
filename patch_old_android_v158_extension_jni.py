#!/usr/bin/env python3
"""Migrate old Android extension bridge injections to Chromium 158 JNI pointers."""

from pathlib import Path
import re
import sys

COORDINATOR = Path(
    "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/"
    "ExtensionActionListCoordinator.java"
)
COORDINATOR_METHOD = "public View getContainerView() { return mContainer; }\n"

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

MENU_OVERLOAD_MARKER = "getActionIcon(int actionIndex, @Nullable WebContents webContents)"
MENU_OVERLOAD_BLOCK = """    public ExtensionsMenuTypes.MenuEntryState getMenuEntry(
            int actionIndex, @Nullable WebContents webContents) {
        return ExtensionsMenuBridgeJni.get().getMenuEntry(mNative, actionIndex, webContents);
    }

    public List<ExtensionsMenuTypes.MenuEntryState> getMenuEntries(
            @Nullable WebContents webContents) {
        return ExtensionsMenuBridgeJni.get().getMenuEntries(mNative, webContents);
    }

    public @Nullable Bitmap getActionIcon(int actionIndex, @Nullable WebContents webContents) {
        return ExtensionsMenuBridgeJni.get().getActionIcon(mNative, actionIndex, webContents);
    }

    public void executeAction(String extensionId, @Nullable WebContents webContents) {
        ExtensionsMenuBridgeJni.get().executeAction(mNative, extensionId, webContents);
    }

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
    coordinator = source_root / COORDINATOR
    if coordinator.is_file():
        text = coordinator.read_text(encoding="utf-8")
        lines = text.splitlines(keepends=True)
        kept = []
        seen = False
        for line in lines:
            if line == COORDINATOR_METHOD:
                if seen:
                    continue
                seen = True
            kept.append(line)
        updated = "".join(kept)
        if updated != text:
            coordinator.write_text(updated, encoding="utf-8")
            changed = True
            print(f"Deduped old-android toolbar container accessor: {coordinator}")
    for relative in BRIDGES:
        path = source_root / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        text = path.read_text(encoding="utf-8")
        original = text
        for old, new in REPLACEMENTS:
            text = text.replace(old, new)
        if path.name == "ExtensionsMenuBridge.java":
            anchor = "    public List<ExtensionsMenuTypes.MenuEntryState> getMenuEntries() {"
            if MENU_OVERLOAD_MARKER not in text:
                if anchor not in text:
                    raise RuntimeError(f"Menu bridge overload anchor not found in {path}")
                text = text.replace(anchor, MENU_OVERLOAD_BLOCK + anchor, 1)
            elif "getMenuEntries(\n            @Nullable WebContents webContents)" not in text and anchor in text:
                menu_entries = """    public List<ExtensionsMenuTypes.MenuEntryState> getMenuEntries(
            @Nullable WebContents webContents) {
        return ExtensionsMenuBridgeJni.get().getMenuEntries(mNative, webContents);
    }

"""
                text = text.replace(anchor, menu_entries + anchor, 1)
            text = re.sub(
                r"@Nullable Bitmap getActionIcon\(\s*JniPtr<NativeExtensionsMenuDelegateAndroid> self,\s*int actionIndex\);",
                '@Nullable Bitmap getActionIcon(\n'
                '                JniPtr<NativeExtensionsMenuDelegateAndroid> self,\n'
                '                int actionIndex,\n'
                '                @Nullable @JniType("content::WebContents*") WebContents webContents);',
                text,
                count=1,
                flags=re.S,
            )
            text = re.sub(
                r"void executeAction\(\s*JniPtr<NativeExtensionsMenuDelegateAndroid> self,\s*"
                r"@JniType\(\"std::string\"\) String extensionId\);",
                'void executeAction(\n'
                '                JniPtr<NativeExtensionsMenuDelegateAndroid> self,\n'
                '                @JniType("std::string") String extensionId,\n'
                '                @Nullable @JniType("content::WebContents*") WebContents webContents);',
                text,
                count=1,
                flags=re.S,
            )
            text = re.sub(
                r"List<ExtensionsMenuTypes\.MenuEntryState> getMenuEntries\(\s*"
                r"JniPtr<NativeExtensionsMenuDelegateAndroid> self\);",
                'List<ExtensionsMenuTypes.MenuEntryState> getMenuEntries(\n'
                '                JniPtr<NativeExtensionsMenuDelegateAndroid> self,\n'
                '                @Nullable @JniType("content::WebContents*") WebContents webContents);',
                text,
                count=1,
                flags=re.S,
            )
            text = re.sub(
                r"ExtensionsMenuTypes\.MenuEntryState getMenuEntry\(\s*"
                r"JniPtr<NativeExtensionsMenuDelegateAndroid> self, int actionIndex\);",
                'ExtensionsMenuTypes.MenuEntryState getMenuEntry(\n'
                '                JniPtr<NativeExtensionsMenuDelegateAndroid> self,\n'
                '                int actionIndex,\n'
                '                @Nullable @JniType("content::WebContents*") WebContents webContents);',
                text,
                count=1,
                flags=re.S,
            )
            text = re.sub(
                r"public void executeAction\(String extensionId\) \{\s*"
                r"ExtensionsMenuBridgeJni\.get\(\)\.executeAction\(mNative, extensionId\);\s*\}",
                "public void executeAction(String extensionId) {\n"
                "        executeAction(extensionId, null);\n"
                "    }",
                text,
                count=1,
                flags=re.S,
            )
            text = re.sub(
                r"public @Nullable Bitmap getActionIcon\(int actionIndex\) \{\s*"
                r"return ExtensionsMenuBridgeJni\.get\(\)\.getActionIcon\(mNative, actionIndex\);\s*\}",
                "public @Nullable Bitmap getActionIcon(int actionIndex) {\n"
                "        return getActionIcon(actionIndex, null);\n"
                "    }",
                text,
                count=1,
                flags=re.S,
            )
            text = re.sub(
                r"public List<ExtensionsMenuTypes\.MenuEntryState> getMenuEntries\(\) \{\s*"
                r"return ExtensionsMenuBridgeJni\.get\(\)\.getMenuEntries\(mNative\);\s*\}",
                "public List<ExtensionsMenuTypes.MenuEntryState> getMenuEntries() {\n"
                "        return getMenuEntries(null);\n"
                "    }",
                text,
                count=1,
                flags=re.S,
            )
            text = re.sub(
                r"public ExtensionsMenuTypes\.MenuEntryState getMenuEntry\(int actionIndex\) \{\s*"
                r"return ExtensionsMenuBridgeJni\.get\(\)\.getMenuEntry\(mNative, actionIndex\);\s*\}",
                "public ExtensionsMenuTypes.MenuEntryState getMenuEntry(int actionIndex) {\n"
                "        return getMenuEntry(actionIndex, null);\n"
                "    }",
                text,
                count=1,
                flags=re.S,
            )
        if path.name == "ExtensionsMenuBridge.java":
            method_start = text.find("private void openExtensionOptionsFromMenu(String extensionId)")
            if method_start >= 0:
                brace_start = text.find("{", method_start)
                depth = 0
                method_end = -1
                for index in range(brace_start, len(text)):
                    if text[index] == "{":
                        depth += 1
                    elif text[index] == "}":
                        depth -= 1
                        if depth == 0:
                            method_end = index
                            break
                if method_end >= 0:
                    method = text[method_start:method_end]
                    pattern = re.compile(r"(?ms)^        String optionsUrl = mMenuBridge\.getOptionsPageUrl\(extensionId\);.*?^        }\n")
                    matches = list(pattern.finditer(method))
                    if len(matches) > 1:
                        first_end = matches[0].end()
                        method = method[:first_end] + pattern.sub("", method[first_end:], count=1)
                        text = text[:method_start] + method + text[method_end:]
        if path.name == "ExtensionsToolbarBridge.java":
            natives_start = text.find("interface Natives {")
            if natives_start < 0:
                raise RuntimeError(f"Toolbar Natives interface not found in {path}")
            brace_start = text.find("{", natives_start)
            natives_end = -1
            depth = 0
            if brace_start >= 0:
                for index in range(brace_start, len(text)):
                    if text[index] == "{":
                        depth += 1
                    elif text[index] == "}":
                        depth -= 1
                        if depth == 0:
                            natives_end = index
                            break
            if natives_end < 0:
                raise RuntimeError(f"Toolbar Natives interface end not found in {path}")
            natives_body = text[natives_start:natives_end]
            if TOOLBAR_NATIVES_MARKER not in natives_body:
                anchor = "        void executeUserAction("
                if anchor not in natives_body:
                    raise RuntimeError(f"Toolbar Natives anchor not found in {path}")
                insertion = TOOLBAR_NATIVES_METHOD + "\n" + anchor
                text = text[:natives_start] + natives_body.replace(anchor, insertion, 1) + text[natives_end:]
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
