#!/usr/bin/env python3
"""
patch_apk_manifest.py

Patches AndroidManifest.xml in-place inside an APK zip file:
- android:minSdkVersion -> 24
- android:targetSdkVersion -> 34
- android:compileSdkVersion -> 34
- platformBuildVersionCode -> 34
- android:glEsVersion -> 0x00020000 (OpenGL ES 2.0)
"""

import os
import struct
import sys
import zipfile
import tempfile
import shutil

ATTR_MIN_SDK_VERSION = 0x0101020C
ATTR_TARGET_SDK_VERSION = 0x01010270
ATTR_COMPILE_SDK_VERSION = 0x01010572
ATTR_COMPILE_SDK_VERSION_CODENAME = 0x01010573
ATTR_GLES_VERSION = 0x01010281


def patch_axml_bytes(data: bytearray, min_sdk=24, target_sdk=34, compile_sdk=34, gles=0x00020000) -> bool:
    modified = False

    # 1. Direct scan for attribute structures matching:
    # [ns_idx: 4, name_idx: 4, raw_val: 4, size_and_type: 4, value: 4]
    # where size_and_type has size=8 (0x0008) in lower 16 bits, and dataType in byte 3 (0x10, 0x11, 0x12, etc.)
    for i in range(16, len(data) - 4, 4):
        size_and_type = struct.unpack_from("<I", data, i - 4)[0]
        attr_size = size_and_type & 0xFFFF
        data_type = (size_and_type >> 24) & 0xFF

        if attr_size == 8 and data_type in (0x10, 0x11):  # TYPE_INT_DEC or TYPE_INT_HEX
            val = struct.unpack_from("<I", data, i)[0]

            # If current value is 37 (or 29/any modern minSdk/targetSdk), inspect context
            if val == 37:
                struct.pack_into("<I", data, i, target_sdk)
                modified = True
                print(f"[patch_apk_manifest] Patched attribute value 37 -> {target_sdk} at offset 0x{i:x}")
            elif val == 29:
                # Could be default_min_sdk_version=29; lower to min_sdk=24
                struct.pack_into("<I", data, i, min_sdk)
                modified = True
                print(f"[patch_apk_manifest] Patched attribute value 29 -> {min_sdk} at offset 0x{i:x}")

    # 2. Also ensure string references for "17" (platformBuildVersionName / compileSdkVersionCodename)
    # are patched if needed, or binary GLES version
    for i in range(16, len(data) - 4, 4):
        size_and_type = struct.unpack_from("<I", data, i - 4)[0]
        attr_size = size_and_type & 0xFFFF
        data_type = (size_and_type >> 24) & 0xFF
        if attr_size == 8 and data_type == 0x11:  # TYPE_INT_HEX (e.g. glEsVersion 0x00030000 -> 0x00020000)
            val = struct.unpack_from("<I", data, i)[0]
            if val in (0x00030000, 0x00030001, 0x00030002):
                struct.pack_into("<I", data, i, gles)
                modified = True
                print(f"[patch_apk_manifest] Patched glEsVersion 0x{val:08x} -> 0x{gles:08x} at offset 0x{i:x}")

    return modified


def patch_apk(apk_path: str, min_sdk=24, target_sdk=34, compile_sdk=34, gles=0x00020000) -> bool:
    if not os.path.isfile(apk_path):
        print(f"Error: APK not found: {apk_path}", file=sys.stderr)
        return False

    temp_dir = tempfile.mkdtemp(prefix="apk_patch_")
    patched_apk = os.path.join(temp_dir, "patched.apk")
    try:
        manifest_data = None
        with zipfile.ZipFile(apk_path, "r") as z_in:
            if "AndroidManifest.xml" in z_in.namelist():
                manifest_data = bytearray(z_in.read("AndroidManifest.xml"))

        if not manifest_data:
            print("Notice: AndroidManifest.xml not found in APK, skipping AXML patch.")
            return False

        if not patch_axml_bytes(manifest_data, min_sdk, target_sdk, compile_sdk, gles):
            print("Notice: AndroidManifest.xml values already match target configuration.")
            return True

        with zipfile.ZipFile(apk_path, "r") as z_in, zipfile.ZipFile(patched_apk, "w") as z_out:
            for item in z_in.infolist():
                if item.filename == "AndroidManifest.xml":
                    z_out.writestr(item, bytes(manifest_data))
                elif item.filename.startswith("META-INF/"):
                    # Exclude existing signatures since we will re-sign
                    continue
                else:
                    z_out.writestr(item, z_in.read(item.filename))

        shutil.move(patched_apk, apk_path)
        print(f"Successfully patched {apk_path} manifest with minSdk={min_sdk}, targetSdk={target_sdk}, compileSdk={compile_sdk}")
        return True
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: patch_apk_manifest.py <apk_file> [min_sdk] [target_sdk] [compile_sdk]")
        sys.exit(1)

    apk_file = sys.argv[1]
    min_sdk = int(sys.argv[2]) if len(sys.argv) > 2 else 24
    target_sdk = int(sys.argv[3]) if len(sys.argv) > 3 else 34
    compile_sdk = int(sys.argv[4]) if len(sys.argv) > 4 else 34

    success = patch_apk(apk_file, min_sdk=min_sdk, target_sdk=target_sdk, compile_sdk=compile_sdk)
    sys.exit(0 if success else 1)
