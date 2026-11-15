#!/usr/bin/env python3
"""Report why a restored tab loses its saved state on old-android builds.

``TabPersistentStoreImpl`` restores a tab from its ``TabState`` file. When the
file cannot be read it silently falls back to creating a fresh tab that loads the
tab's last known URL:

  Failed to restore TabState and not reparenting; creating Tab with last known URL.

On the target device that fallback runs for every saved tab, so a launch with a
dozen tabs creates a dozen tabs that all start loading at once. The renderer
processes they need are created and torn down repeatedly, and the visible tab
ends up without a renderer, which shows as the crash page.

The read failure itself is only logged at DEBUG level, so the release capture
never shows it. Log which candidate files exist and raise the restore failure to
a warning with the file path and size, so the reason a state is unusable becomes
visible.
"""
import os
import sys

TAB_STATE_FILE = (
    "chrome/browser/tabpersistence/android/java/src/org/chromium/chrome/browser/"
    "tabpersistence/TabStateFileManager.java"
)

EXISTS_ORIGINAL = """        TabState tabState = null;
        if (flatBufferRegularExists || flatBufferEncryptedExists) {"""

EXISTS_PATCHED = """        // Helium: restore silently falls back to a fresh tab when every candidate
        // file is missing, which hides a lost or unreadable saved state.
        Log.w(TAG, "Helium restore: id=" + id
                + " flatRegular=" + flatBufferRegularExists
                + " flatEncrypted=" + flatBufferEncryptedExists
                + " legacyRegular=" + legacyRegularExists
                + " legacyEncrypted=" + legacyEncryptedExists);
        TabState tabState = null;
        if (flatBufferRegularExists || flatBufferEncryptedExists) {"""

CATCH_ORIGINAL = """            } catch (Exception e) {
                Log.d(TAG, "Error restoring TabState using FlatBuffer", e);
            }"""

CATCH_PATCHED = """            } catch (Exception e) {
                // Helium: keep the file identity so a corrupt state is traceable.
                Log.w(TAG, "Helium restore failed: id=" + id
                        + " encrypted=" + flatBufferEncryptedExists
                        + " size=" + (flatBufferEncryptedExists
                                ? flatBufferEncrypted.length() : flatBufferRegular.length()), e);
            }"""


def _read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _write(path, content):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def _replace_once(path, original, patched, label):
    if not os.path.isfile(path):
        return False
    content = _read(path)
    if patched in content:
        return False
    if original not in content:
        print(f"Warning: could not find {label} in {path}", file=sys.stderr)
        return False
    _write(path, content.replace(original, patched, 1))
    print(f"Patched {label}: {path}")
    return True


def patch_source_tree(src_dir):
    path = os.path.join(src_dir, TAB_STATE_FILE)
    changed = False
    if _replace_once(path, EXISTS_ORIGINAL, EXISTS_PATCHED, "tab state file presence"):
        changed = True
    if _replace_once(path, CATCH_ORIGINAL, CATCH_PATCHED, "tab state restore failure"):
        changed = True
    return changed


def main():
    patch_source_tree(sys.argv[1] if len(sys.argv) > 1 else ".")


if __name__ == "__main__":
    main()
