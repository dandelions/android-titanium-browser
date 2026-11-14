#!/usr/bin/env python3
"""Grow the modern linker's address-space reservation for old-android builds.

The modern linker reserves one fixed-size virtual range and then asks
``android_dlopen_ext()`` to load libchrome.so into it, so that the relocated
RELRO region can be shared between processes. Upstream reserves 192 MiB, which
fits a modern libchrome.so, but the old-android build links a much larger
library: its load size is about 223.6 MiB. The system linker therefore rejects
the load:

  reserved address space -33153024 smaller than 234479616 bytes needed

Chromium then falls back to a plain ``dlopen()``, and every process keeps its
own private copy of the relocated ``.data.rel.ro`` section instead of sharing
it. That is roughly 60 MiB of extra private memory per process on a device that
already runs short of memory, which is what makes the renderer disappear.

Raise the reservation to 320 MiB. The extra range is ``PROT_NONE`` and the tail
is unmapped once the library is loaded, so this costs address space only.
"""
import os
import sys

HEADER_FILE = "base/android/linker/linker_jni.h"

ORIGINAL = "static const size_t kAddressSpaceReservationSize = 192 * 1024 * 1024;"
REPLACEMENT = """// Helium: the old-android libchrome.so has a load size of about 224 MiB, which
// does not fit in the upstream 192 MiB reservation.
static const size_t kAddressSpaceReservationSize = 320 * 1024 * 1024;"""


def _read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _write(path, content):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def patch_source_tree(src_dir):
    path = os.path.join(src_dir, HEADER_FILE)
    if not os.path.isfile(path):
        return False
    content = _read(path)
    if REPLACEMENT in content:
        return False
    if ORIGINAL not in content:
        print(
            f"Warning: could not find the linker reservation size in {path}",
            file=sys.stderr,
        )
        return False
    _write(path, content.replace(ORIGINAL, REPLACEMENT, 1))
    print(f"Patched linker address space reservation: {path}")
    return True


def main():
    patch_source_tree(sys.argv[1] if len(sys.argv) > 1 else ".")


if __name__ == "__main__":
    main()
