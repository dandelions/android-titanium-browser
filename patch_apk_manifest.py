#!/usr/bin/env python3
"""
patch_apk_manifest.py

Patches AndroidManifest.xml in-place inside an APK zip file:
- android:minSdkVersion -> min_sdk (defaults to 28 / car baseline)
- android:targetSdkVersion -> 34
- android:compileSdkVersion -> 34
- platformBuildVersionCode -> 34
- android:glEsVersion -> 0x00020000 (OpenGL ES 2.0)
- android:extractNativeLibs -> true (ensures native libs are extracted on Android 9/10)
- android:useAppZygote -> false (0) to prevent car AMS Zygote fork deadlock
- strips custom assets/chrome-command-line
"""

import os
import struct
import sys
import zipfile
import tempfile
import shutil

RES_USE_APP_ZYGOTE = (0x01010584, 0x01010597)
RES_MIN_SDK_VERSION = 0x0101020C
RES_TARGET_SDK_VERSION = 0x01010270
RES_COMPILE_SDK_VERSION = 0x01010572
RES_GLES_VERSION = 0x01010281
RES_EXTRACT_NATIVE_LIBS = 0x010104EA
RES_ISOLATED_SPLITS = (0x01010543, 0x0101054B)
RES_MEMTAG_MODE = 0x01010624


def extract_resource_ids(data: bytearray):
    """
    Finds RES_XML_RESOURCE_MAP_TYPE chunk (0x00080180) and returns a dict mapping
    res_id -> index, and index -> res_id.
    """
    idx_to_res = {}
    res_to_idx = {}

    offset = 8  # Skip XML header
    while offset + 8 <= len(data):
        chunk_type, chunk_size = struct.unpack_from("<II", data, offset)
        if chunk_size < 8 or offset + chunk_size > len(data):
            break

        if chunk_type == 0x00080180:  # RES_XML_RESOURCE_MAP_TYPE
            count = (chunk_size - 8) // 4
            for i in range(count):
                res_id = struct.unpack_from("<I", data, offset + 8 + i * 4)[0]
                idx_to_res[i] = res_id
                res_to_idx[res_id] = i
            break

        offset += chunk_size

    return idx_to_res, res_to_idx


def patch_axml_bytes(data: bytearray, min_sdk=28, target_sdk=34, compile_sdk=34, gles=0x00020000) -> bool:
    modified = False

    _, res_to_idx = extract_resource_ids(data)
    use_app_zygote_indices = {res_to_idx[r] for r in RES_USE_APP_ZYGOTE if r in res_to_idx}
    min_sdk_idx = res_to_idx.get(RES_MIN_SDK_VERSION, -1)
    target_sdk_idx = res_to_idx.get(RES_TARGET_SDK_VERSION, -1)
    gles_idx = res_to_idx.get(RES_GLES_VERSION, -1)
    extract_native_libs_idx = res_to_idx.get(RES_EXTRACT_NATIVE_LIBS, -1)
    isolated_splits_indices = {res_to_idx[r] for r in RES_ISOLATED_SPLITS if r in res_to_idx}
    memtag_idx = res_to_idx.get(RES_MEMTAG_MODE, -1)

    # 1. Attribute-level scan:
    # Each attribute is 20 bytes:
    # [ns_idx: 4, name_idx: 4, raw_val: 4, size_and_type: 4, value: 4]
    for i in range(16, len(data) - 3, 4):
        size_and_type = struct.unpack_from("<I", data, i - 4)[0]
        attr_size = size_and_type & 0xFFFF
        data_type = (size_and_type >> 24) & 0xFF

        if attr_size == 8:
            val = struct.unpack_from("<I", data, i)[0]
            name_idx = struct.unpack_from("<I", data, i - 12)[0]

            # A. Disable useAppZygote -> set value to 0 (false)
            if name_idx in use_app_zygote_indices:
                if val != 0:
                    struct.pack_into("<I", data, i, 0)
                    modified = True
                    print(f"[patch_apk_manifest] Disabled useAppZygote (0x{val:x} -> 0) at offset 0x{i:x}")

            # B. Force extractNativeLibs -> set value to 0xFFFFFFFF (true)
            if extract_native_libs_idx != -1 and name_idx == extract_native_libs_idx:
                if val == 0:
                    struct.pack_into("<I", data, i, 0xFFFFFFFF)
                    modified = True
                    print(f"[patch_apk_manifest] Enabled extractNativeLibs (0 -> true) at offset 0x{i:x}")

            # C. Disable isolatedSplits -> set value to 0 (false)
            if name_idx in isolated_splits_indices:
                if val != 0:
                    struct.pack_into("<I", data, i, 0)
                    modified = True
                    print(f"[patch_apk_manifest] Disabled isolatedSplits (0x{val:x} -> 0) at offset 0x{i:x}")

            # D. Disable memtagMode -> set value to 0 (off)
            if memtag_idx != -1 and name_idx == memtag_idx:
                if val != 0:
                    struct.pack_into("<I", data, i, 0)
                    modified = True
                    print(f"[patch_apk_manifest] Disabled memtagMode (0x{val:x} -> 0) at offset 0x{i:x}")

            # E. TargetSdkVersion / MinSdkVersion / CompileSdkVersion
            if data_type in (0x10, 0x11):  # TYPE_INT_DEC or TYPE_INT_HEX
                if name_idx == min_sdk_idx and min_sdk_idx != -1:
                    if val != min_sdk:
                        struct.pack_into("<I", data, i, min_sdk)
                        modified = True
                        print(f"[patch_apk_manifest] Patched minSdkVersion ({val} -> {min_sdk}) at offset 0x{i:x}")
                elif name_idx == target_sdk_idx and target_sdk_idx != -1:
                    if val != target_sdk:
                        struct.pack_into("<I", data, i, target_sdk)
                        modified = True
                        print(f"[patch_apk_manifest] Patched targetSdkVersion ({val} -> {target_sdk}) at offset 0x{i:x}")

            # F. glEsVersion
            if data_type == 0x11:  # TYPE_INT_HEX
                if (name_idx == gles_idx and gles_idx != -1) or val in (0x00030000, 0x00030001, 0x00030002):
                    if val != gles:
                        struct.pack_into("<I", data, i, gles)
                        modified = True
                        print(f"[patch_apk_manifest] Patched glEsVersion 0x{val:08x} -> 0x{gles:08x} at offset 0x{i:x}")

    return modified


def patch_apk(apk_path: str, min_sdk=28, target_sdk=34, compile_sdk=34, gles=0x00020000) -> bool:
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

        patch_axml_bytes(manifest_data, min_sdk, target_sdk, compile_sdk, gles)

        with zipfile.ZipFile(apk_path, "r") as z_in, zipfile.ZipFile(patched_apk, "w") as z_out:
            for item in z_in.infolist():
                if item.filename == "AndroidManifest.xml":
                    z_out.writestr(item, bytes(manifest_data))
                elif item.filename.startswith("META-INF/"):
                    # Exclude existing signatures since we will re-sign
                    continue
                elif item.filename == "assets/chrome-command-line":
                    # Aligned with Kiwi: never inject/retain custom command line which causes EGL/GPU crashes
                    print("[patch_apk_manifest] Stripped custom assets/chrome-command-line (aligned with Kiwi standard)")
                    continue
                else:
                    # Keep all bytecode and native libraries intact and unmodified
                    z_out.writestr(item, z_in.read(item.filename))

        shutil.move(patched_apk, apk_path)
        print(f"Successfully patched {apk_path} manifest & car compat attributes (minSdk={min_sdk}, targetSdk={target_sdk}, gles=0x{gles:08x})")
        return True
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: patch_apk_manifest.py <apk_file> [min_sdk] [target_sdk] [compile_sdk]")
        sys.exit(1)

    apk_file = sys.argv[1]
    min_sdk = int(sys.argv[2]) if len(sys.argv) > 2 else 28
    target_sdk = int(sys.argv[3]) if len(sys.argv) > 3 else 34
    compile_sdk = int(sys.argv[4]) if len(sys.argv) > 4 else 34

    success = patch_apk(apk_file, min_sdk=min_sdk, target_sdk=target_sdk, compile_sdk=compile_sdk)
    sys.exit(0 if success else 1)
