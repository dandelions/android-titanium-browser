#!/usr/bin/env python3
"""Disable cross-process RELRO sharing for old-android builds.

Chromium shares the relocated ``.data.rel.ro`` section between processes: the
browser process exports it as a file descriptor, and every child receives that
descriptor through Binder (``ParcelFileDescriptor.fromFd``) so the library can
be mapped at the same address.

On the VMOS-based target this handoff does not work. With sharing enabled the
renderer never finishes ``ChildProcessService.setupConnection``: the browser
retries ``ChildProcessLauncherHelperImpl.createAndStart`` in a tight loop, the
service binding stays at the weak ``W`` level, and the navigation never commits.
After 30 seconds ``NavigationRequest::OnCommitTimeout`` marks the renderer
unresponsive and the tab shows the crash page.

Load the library with ``RelroSharingMode.NO_SHARING`` instead. The address-space
reservation from patch_linker_reservation_size.py is kept, so the library is
still loaded by the modern linker at a fixed address rather than falling back to
the system linker; only the descriptor handoff is skipped.
"""
import os
import sys

LINKER_FILE = "base/android/java/src/org/chromium/base/library_loader/Linker.java"

ORIGINAL = """                attemptLoadLibraryLocked(
                        library,
                        mRelroProducer ? RelroSharingMode.PRODUCE : RelroSharingMode.CONSUME);"""

REPLACEMENT = """                // Helium: the VMOS Binder fd handoff used for RELRO sharing does
                // not complete, which leaves the child process unbound and the
                // navigation stuck before commit. Load without sharing instead.
                attemptLoadLibraryLocked(library, RelroSharingMode.NO_SHARING);"""


def _read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _write(path, content):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def patch_source_tree(src_dir):
    path = os.path.join(src_dir, LINKER_FILE)
    if not os.path.isfile(path):
        return False
    content = _read(path)
    if REPLACEMENT in content:
        return False
    if ORIGINAL not in content:
        print(
            f"Warning: could not find the RELRO mode selection in {path}",
            file=sys.stderr,
        )
        return False
    _write(path, content.replace(ORIGINAL, REPLACEMENT, 1))
    print(f"Patched RELRO sharing mode: {path}")
    return True


def main():
    patch_source_tree(sys.argv[1] if len(sys.argv) > 1 else ".")


if __name__ == "__main__":
    main()
