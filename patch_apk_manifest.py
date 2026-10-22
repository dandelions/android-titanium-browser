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

# Android AXML constants
RES_XML_TYPE = 0x0003
RES_STRING_POOL_TYPE = 0x0001
RES_XML_RESOURCE_MAP_TYPE = 0x0180
RES_XML_START_ELEMENT_TYPE = 0x0102

ATTR_MIN_SDK_VERSION = 0x0101020C
ATTR_TARGET_SDK_VERSION = 0x01010270
ATTR_COMPILE_SDK_VERSION = 0x01010572
ATTR_GLES_VERSION = 0x01010281


def parse_string(data, offset, is_utf8):
    try:
        if is_utf8:
            u16len = data[offset]
            offset += 1
            if u16len & 0x80:
                offset += 1
            ulen = data[offset]
            offset += 1
            if ulen & 0x80:
                ulen = ((ulen & 0x7F) << 8) | data[offset]
                offset += 1
            return data[offset:offset + ulen].decode("utf-8", "replace")
        else:
            u16len = struct.unpack_from("<H", data, offset)[0]
            offset += 2
            if u16len & 0x8000:
                u16len = ((u16len & 0x7FFF) << 16) | struct.unpack_from("<H", data, offset)[0]
                offset += 2
            ulen = u16len * 2
            return data[offset:offset + ulen].decode("utf-16le", "replace")
    except Exception:
        return ""


def patch_axml_bytes(data: bytearray, min_sdk=24, target_sdk=34, compile_sdk=34, gles=0x00020000) -> bool:
    if len(data) < 8:
        return False
    header_type, header_size, file_size = struct.unpack_from("<HHI", data, 0)
    if header_type != RES_XML_TYPE:
        return False

    offset = header_size
    strings = []
    res_ids = []
    modified = False

    while offset < len(data) - 8:
        chunk_type, chunk_hdr_size, chunk_size = struct.unpack_from("<HHI", data, offset)
        if chunk_size == 0 or offset + chunk_size > len(data):
            break

        if chunk_type == RES_STRING_POOL_TYPE and not strings:
            str_count = struct.unpack_from("<I", data, offset + 8)[0]
            flags = struct.unpack_from("<I", data, offset + 16)[0]
            is_utf8 = bool(flags & (1 << 8))
            strings_start = offset + struct.unpack_from("<I", data, offset + 20)[0]

            offsets_start = offset + 28
            for i in range(str_count):
                if offsets_start + i * 4 + 4 <= len(data):
                    str_off = struct.unpack_from("<I", data, offsets_start + i * 4)[0]
                    s = parse_string(data, strings_start + str_off, is_utf8)
                    strings.append(s)
                else:
                    strings.append("")

        elif chunk_type == RES_XML_RESOURCE_MAP_TYPE and not res_ids:
            count = (chunk_size - chunk_hdr_size) // 4
            for i in range(count):
                rid = struct.unpack_from("<I", data, offset + chunk_hdr_size + i * 4)[0]
                res_ids.append(rid)

        elif chunk_type == RES_XML_START_ELEMENT_TYPE:
            elem_hdr_size = chunk_hdr_size
            attr_start = struct.unpack_from("<H", data, offset + elem_hdr_size + 4)[0]
            attr_size = struct.unpack_from("<H", data, offset + elem_hdr_size + 6)[0]
            attr_count = struct.unpack_from("<H", data, offset + elem_hdr_size + 8)[0]

            if attr_size >= 20:
                first_attr_offset = offset + elem_hdr_size + attr_start
                for a_idx in range(attr_count):
                    a_offset = first_attr_offset + a_idx * attr_size
                    if a_offset + 20 > len(data):
                        break

                    name_idx = struct.unpack_from("<I", data, a_offset + 4)[0]
                    res_id = res_ids[name_idx] if name_idx < len(res_ids) else 0
                    name_str = strings[name_idx] if name_idx < len(strings) else ""

                    current_val = struct.unpack_from("<I", data, a_offset + 16)[0]

                    if res_id == ATTR_MIN_SDK_VERSION or name_str == "minSdkVersion":
                        if current_val != min_sdk:
                            struct.pack_into("<I", data, a_offset + 16, min_sdk)
                            data[a_offset + 15] = 0x10  # TYPE_INT_DEC
                            modified = True
                            print(f"[patch_apk_manifest] Set minSdkVersion: {current_val} -> {min_sdk}")

                    elif res_id == ATTR_TARGET_SDK_VERSION or name_str == "targetSdkVersion":
                        if current_val != target_sdk:
                            struct.pack_into("<I", data, a_offset + 16, target_sdk)
                            data[a_offset + 15] = 0x10  # TYPE_INT_DEC
                            modified = True
                            print(f"[patch_apk_manifest] Set targetSdkVersion: {current_val} -> {target_sdk}")

                    elif res_id == ATTR_COMPILE_SDK_VERSION or name_str == "compileSdkVersion":
                        if current_val != compile_sdk:
                            struct.pack_into("<I", data, a_offset + 16, compile_sdk)
                            data[a_offset + 15] = 0x10  # TYPE_INT_DEC
                            modified = True
                            print(f"[patch_apk_manifest] Set compileSdkVersion: {current_val} -> {compile_sdk}")

                    elif name_str == "platformBuildVersionCode":
                        if current_val != compile_sdk:
                            struct.pack_into("<I", data, a_offset + 16, compile_sdk)
                            data[a_offset + 15] = 0x10  # TYPE_INT_DEC
                            modified = True
                            print(f"[patch_apk_manifest] Set platformBuildVersionCode: {current_val} -> {compile_sdk}")

                    elif res_id == ATTR_GLES_VERSION or name_str == "glEsVersion":
                        if current_val != gles:
                            struct.pack_into("<I", data, a_offset + 16, gles)
                            data[a_offset + 15] = 0x11  # TYPE_INT_HEX
                            modified = True
                            print(f"[patch_apk_manifest] Set glEsVersion: 0x{current_val:08x} -> 0x{gles:08x}")

        offset += chunk_size

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
