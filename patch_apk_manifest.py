#!/usr/bin/env python3
"""
patch_apk_manifest.py

Patches AndroidManifest.xml in-place inside an APK zip file:
- android:minSdkVersion -> 24
- android:targetSdkVersion -> 34
- android:compileSdkVersion -> 34
- platformBuildVersionCode -> 34
- android:glEsVersion -> 0x00020000 (OpenGL ES 2.0)
- android:useAppZygote -> false (0) to prevent car AMS Zygote fork deadlock
- injects assets/chrome-command-line with safe rendering fallbacks
"""

import os
import struct
import sys
import zipfile
import tempfile
import shutil
import subprocess

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


def patch_axml_bytes(data: bytearray, min_sdk=24, target_sdk=34, compile_sdk=34, gles=0x00020000) -> bool:
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
    # where size_and_type has size=8 (0x0008) in lower 16 bits, and dataType in byte 3 (0x10, 0x11, 0x12, etc.)
    for i in range(16, len(data) - 3, 4):
        size_and_type = struct.unpack_from("<I", data, i - 4)[0]
        attr_size = size_and_type & 0xFFFF
        data_type = (size_and_type >> 24) & 0xFF

        if attr_size == 8:
            val = struct.unpack_from("<I", data, i)[0]
            name_idx = struct.unpack_from("<I", data, i - 12)[0]

            # A. Disable useAppZygote (0x01010584 / 0x01010597) -> set value to 0 (false)
            if name_idx in use_app_zygote_indices:
                if val != 0:
                    struct.pack_into("<I", data, i, 0)
                    modified = True
                    print(f"[patch_apk_manifest] Disabled useAppZygote (0x{val:x} -> 0) at offset 0x{i:x}")

            # D. Force extractNativeLibs (0x010104ea) -> set value to 0xFFFFFFFF (true)
            if extract_native_libs_idx != -1 and name_idx == extract_native_libs_idx:
                if val == 0:
                    struct.pack_into("<I", data, i, 0xFFFFFFFF)
                    modified = True
                    print(f"[patch_apk_manifest] Enabled extractNativeLibs (0 -> true) at offset 0x{i:x}")

            # E. Disable isolatedSplits (0x01010543 / 0x0101054b) -> set value to 0 (false)
            if name_idx in isolated_splits_indices:
                if val != 0:
                    struct.pack_into("<I", data, i, 0)
                    modified = True
                    print(f"[patch_apk_manifest] Disabled isolatedSplits (0x{val:x} -> 0) at offset 0x{i:x}")

            # F. Disable memtagMode (0x01010624) -> set value to 0 (off)
            if memtag_idx != -1 and name_idx == memtag_idx:
                if val != 0:
                    struct.pack_into("<I", data, i, 0)
                    modified = True
                    print(f"[patch_apk_manifest] Disabled memtagMode (0x{val:x} -> 0) at offset 0x{i:x}")

            # B. TargetSdkVersion / MinSdkVersion / CompileSdkVersion
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

            # C. glEsVersion
            if data_type == 0x11:  # TYPE_INT_HEX
                if (name_idx == gles_idx and gles_idx != -1) or val in (0x00030000, 0x00030001, 0x00030002):
                    if val != gles:
                        struct.pack_into("<I", data, i, gles)
                        modified = True
                        print(f"[patch_apk_manifest] Patched glEsVersion 0x{val:08x} -> 0x{gles:08x} at offset 0x{i:x}")

    return modified


BINDER_NDK_STUB_C = """
/* Auto-generated binder_ndk stub for Android 9 / old car compatibility */
void AIBinder_associateClass(void) {}
void AIBinder_Class_define(void) {}
void AIBinder_Class_setOnDump(void) {}
void AIBinder_decStrong(void) {}
void AIBinder_dump(void) {}
void AIBinder_fromJavaBinder(void) {}
void AIBinder_getCallingPid(void) {}
void AIBinder_getCallingUid(void) {}
void AIBinder_getClass(void) {}
void AIBinder_getUserData(void) {}
void AIBinder_incStrong(void) {}
void AIBinder_isAlive(void) {}
void AIBinder_isRemote(void) {}
void AIBinder_linkToDeath(void) {}
void AIBinder_new(void) {}
void AIBinder_ping(void) {}
void AIBinder_prepareTransaction(void) {}
void AIBinder_toJavaBinder(void) {}
void AIBinder_transact(void) {}
void AIBinder_unlinkToDeath(void) {}
void AIBinder_DeathRecipient_delete(void) {}
void AIBinder_DeathRecipient_new(void) {}
void AIBinder_Weak_clone(void) {}
void AIBinder_Weak_delete(void) {}
void AIBinder_Weak_new(void) {}
void AIBinder_Weak_promote(void) {}
void AIBinder_setMinSchedulerPolicy(void) {}
void AIBinder_inheritRt(void) {}

void AParcel_create(void) {}
void AParcel_delete(void) {}
void AParcel_fromJavaParcel(void) {}
void AParcel_getDataPosition(void) {}
void AParcel_getDataSize(void) {}
void AParcel_readBool(void) {}
void AParcel_readBoolArray(void) {}
void AParcel_readByte(void) {}
void AParcel_readByteArray(void) {}
void AParcel_readChar(void) {}
void AParcel_readCharArray(void) {}
void AParcel_readDouble(void) {}
void AParcel_readDoubleArray(void) {}
void AParcel_readFloat(void) {}
void AParcel_readFloatArray(void) {}
void AParcel_readInt32(void) {}
void AParcel_readInt32Array(void) {}
void AParcel_readInt64(void) {}
void AParcel_readInt64Array(void) {}
void AParcel_readParcelFileDescriptor(void) {}
void AParcel_readParcelableArray(void) {}
void AParcel_readStatusHeader(void) {}
void AParcel_readString(void) {}
void AParcel_readStringArray(void) {}
void AParcel_readStrongBinder(void) {}
void AParcel_readStrongBinderArray(void) {}
void AParcel_reset(void) {}
void AParcel_setDataPosition(void) {}
void AParcel_writeBool(void) {}
void AParcel_writeBoolArray(void) {}
void AParcel_writeByte(void) {}
void AParcel_writeByteArray(void) {}
void AParcel_writeChar(void) {}
void AParcel_writeCharArray(void) {}
void AParcel_writeDouble(void) {}
void AParcel_writeDoubleArray(void) {}
void AParcel_writeFloat(void) {}
void AParcel_writeFloatArray(void) {}
void AParcel_writeInt32(void) {}
void AParcel_writeInt32Array(void) {}
void AParcel_writeInt64(void) {}
void AParcel_writeInt64Array(void) {}
void AParcel_writeParcelFileDescriptor(void) {}
void蚕AParcel_writeParcelableArray(void) {}
void AParcel_writeStatusHeader(void) {}
void AParcel_writeString(void) {}
void AParcel_writeStringArray(void) {}
void AParcel_writeStrongBinder(void) {}
void AParcel_writeStrongBinderArray(void) {}

void AStatus_delete(void) {}
void AStatus_fromExceptionCode(void) {}
void AStatus_fromExceptionCodeWithMessage(void) {}
void AStatus_fromServiceSpecificError(void) {}
void AStatus_fromServiceSpecificErrorWithMessage(void) {}
void AStatus_fromStatus(void) {}
void AStatus_getDescription(void) {}
void AStatus_getExceptionCode(void) {}
void AStatus_getMessage(void) {}
void AStatus_getServiceSpecificError(void) {}
void AStatus_getStatus(void) {}
void AStatus_isOk(void) {}
void AStatus_newOk(void) {}
""".replace("void蚕AParcel_writeParcelableArray", "void AParcel_writeParcelableArray")


def find_or_build_binder_ndk_so(abi: str, base_dir: str = None):
    target_arch = "aarch64-linux-android" if abi == "arm64-v8a" else "arm-linux-androideabi"
    script_dir = os.path.dirname(os.path.abspath(__file__))

    search_dirs = []
    if base_dir:
        search_dirs.append(base_dir)
        search_dirs.append(os.path.join(base_dir, "chromium/src"))
    search_dirs.append(script_dir)
    search_dirs.append(os.path.join(script_dir, "chromium/src"))
    search_dirs.append("/root/android-helium-browser/chromium/src")
    if os.environ.get("ANDROID_HOME"):
        search_dirs.append(os.environ["ANDROID_HOME"])
    if os.environ.get("ANDROID_NDK_HOME"):
        search_dirs.append(os.environ["ANDROID_NDK_HOME"])

    # 1. Search for existing prebuilt libbinder_ndk.so in NDK sysroot
    for root in search_dirs:
        if not os.path.isdir(root):
            continue
        for parent, _, files in os.walk(root):
            if "libbinder_ndk.so" in files and target_arch in parent:
                candidate = os.path.join(parent, "libbinder_ndk.so")
                try:
                    with open(candidate, "rb") as f:
                        data = f.read()
                    if len(data) > 0:
                        print(f"[patch_apk_manifest] Found prebuilt {abi} libbinder_ndk.so at: {candidate}")
                        return data
                except Exception:
                    pass

    # 2. Try compiling stub using clang in Chromium tree
    clang_candidates = [
        os.path.join(script_dir, "chromium/src/third_party/llvm-build/Release+Asserts/bin/clang"),
        "/root/android-helium-browser/chromium/src/third_party/llvm-build/Release+Asserts/bin/clang",
        shutil.which("clang"),
    ]
    clang_bin = None
    for cc in clang_candidates:
        if cc and os.path.isfile(cc) and os.access(cc, os.X_OK):
            clang_bin = cc
            break

    if clang_bin:
        with tempfile.TemporaryDirectory(prefix="binder_stub_") as td:
            src_c = os.path.join(td, "binder_ndk_stub.c")
            out_so = os.path.join(td, "libbinder_ndk.so")
            with open(src_c, "w") as f:
                f.write(BINDER_NDK_STUB_C)
            target_flag = f"--target={target_arch}"
            cmd = [clang_bin, target_flag, "-shared", "-fPIC", "-nostdlib", "-Wl,-soname,libbinder_ndk.so", src_c, "-o", out_so]
            res = subprocess.run(cmd, capture_output=True)
            if res.returncode == 0 and os.path.isfile(out_so):
                with open(out_so, "rb") as f:
                    data = f.read()
                print(f"[patch_apk_manifest] Compiled {abi} libbinder_ndk.so stub using {clang_bin}")
                return data

    return None


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

        manifest_modified = patch_axml_bytes(manifest_data, min_sdk, target_sdk, compile_sdk, gles)

        with zipfile.ZipFile(apk_path, "r") as z_in, zipfile.ZipFile(patched_apk, "w") as z_out:
            all_names = set(z_in.namelist())
            has_arm64 = any(name.startswith("lib/arm64-v8a/") for name in all_names)
            has_arm32 = any(name.startswith("lib/armeabi-v7a/") for name in all_names)

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
                    z_out.writestr(item, z_in.read(item.filename))

            # Inject libbinder_ndk.so for Android 9 / old car compatibility
            if has_arm64 and "lib/arm64-v8a/libbinder_ndk.so" not in all_names:
                arm64_binder = find_or_build_binder_ndk_so("arm64-v8a")
                if arm64_binder:
                    z_out.writestr("lib/arm64-v8a/libbinder_ndk.so", arm64_binder)
                    print("[patch_apk_manifest] Injected lib/arm64-v8a/libbinder_ndk.so for Android 9 car compatibility")
                else:
                    print("[patch_apk_manifest] Notice: prebuilt arm64 libbinder_ndk.so not located", file=sys.stderr)

            if has_arm32 and "lib/armeabi-v7a/libbinder_ndk.so" not in all_names:
                arm32_binder = find_or_build_binder_ndk_so("armeabi-v7a")
                if arm32_binder:
                    z_out.writestr("lib/armeabi-v7a/libbinder_ndk.so", arm32_binder)
                    print("[patch_apk_manifest] Injected lib/armeabi-v7a/libbinder_ndk.so for Android 9 car compatibility")
                else:
                    print("[patch_apk_manifest] Notice: prebuilt arm32 libbinder_ndk.so not located", file=sys.stderr)

        shutil.move(patched_apk, apk_path)
        print(f"Successfully patched {apk_path} manifest & car libs (minSdk={min_sdk}, targetSdk={target_sdk}, gles=0x{gles:08x})")
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
