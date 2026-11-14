#!/usr/bin/env python3
"""Open /proc files without O_CLOEXEC on old-android builds.

Chromium's stack sampler reads ``/proc/self/maps`` and ``/proc/self/mem``
through the vendored libunwindstack. Every open uses
``O_RDONLY | O_CLOEXEC``.

On the VMOS-based target that aborts the process:

  FORTIFY: fcntl(F_SETFD) passed non-FD_CLOEXEC flag: 0x80000

The FORTIFY check belongs to the host bionic, which the virtualization layer
forwards the call to. ``F_SETFD`` only accepts ``FD_CLOEXEC`` (1), and
``O_CLOEXEC`` is ``0x80000``, so the check kills the process. The crash lands on
``ThreadPoolForegroundWorker`` inside ``base::StackSampler::WalkStack`` ->
``unwindstack::MemoryFileAtOffset::Init``, which is why it appeared a few
seconds after startup and looked unrelated to page loading.

Open the file first and set the close-on-exec flag with ``FD_CLOEXEC``, which is
what ``F_SETFD`` actually accepts and is valid on every API level.
"""
import os
import sys

MEMORY_FILE = "third_party/libunwindstack/src/libunwindstack/Memory.cpp"
PROCESS_MAP_FILE = (
    "third_party/libunwindstack/src/libprocinfo/include/procinfo/process_map.h"
)

MEMORY_ORIGINAL = """  android::base::unique_fd fd(TEMP_FAILURE_RETRY(open(file.c_str(), O_RDONLY | O_CLOEXEC)));"""

MEMORY_PATCHED = """  // Helium: O_CLOEXEC forwarded to F_SETFD aborts under the VMOS libc, so set
  // the descriptor flag explicitly with FD_CLOEXEC instead.
  int helium_fd = TEMP_FAILURE_RETRY(open(file.c_str(), O_RDONLY));
  if (helium_fd != -1) {
    TEMP_FAILURE_RETRY(fcntl(helium_fd, F_SETFD, FD_CLOEXEC));
  }
  android::base::unique_fd fd(helium_fd);"""

PROCESS_MAP_ORIGINAL = """  int fd = open(map_file, O_RDONLY | O_CLOEXEC);
  if (fd == -1) {
    return false;
  }"""

PROCESS_MAP_PATCHED = """  // Helium: see Memory.cpp; O_CLOEXEC reaches F_SETFD and aborts the process.
  int fd = open(map_file, O_RDONLY);
  if (fd == -1) {
    return false;
  }
  TEMP_FAILURE_RETRY(fcntl(fd, F_SETFD, FD_CLOEXEC));"""


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
    changed = False
    if _replace_once(
        os.path.join(src_dir, MEMORY_FILE),
        MEMORY_ORIGINAL,
        MEMORY_PATCHED,
        "unwindstack file mapping open",
    ):
        changed = True
    if _replace_once(
        os.path.join(src_dir, PROCESS_MAP_FILE),
        PROCESS_MAP_ORIGINAL,
        PROCESS_MAP_PATCHED,
        "unwindstack process map open",
    ):
        changed = True
    return changed


def main():
    patch_source_tree(sys.argv[1] if len(sys.argv) > 1 else ".")


if __name__ == "__main__":
    main()
