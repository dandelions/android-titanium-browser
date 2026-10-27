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
import hashlib
import zlib
import base64

try:
    from prebuilt_shims import EMBEDDED_SHIM_B64
except ImportError:
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from prebuilt_shims import EMBEDDED_SHIM_B64
    except Exception:
        EMBEDDED_SHIM_B64 = {}

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
/* Auto-generated binder_ndk and API 29 compatibility stub for Android 9 / old car units */
#ifndef NULL
#define NULL ((void*)0)
#endif
typedef signed char int8_t;
typedef short int16_t;
typedef int int32_t;
typedef long long int64_t;
typedef unsigned char uint8_t;
typedef unsigned short uint16_t;
typedef unsigned int uint32_t;
typedef unsigned long long uint64_t;
typedef unsigned long size_t;

#define STUB_EXPORT __attribute__((visibility("default")))

// 1. Binder NDK
STUB_EXPORT void AIBinder_associateClass(void) {}
STUB_EXPORT void AIBinder_Class_define(void) {}
STUB_EXPORT void AIBinder_Class_setOnDump(void) {}
STUB_EXPORT void AIBinder_decStrong(void) {}
STUB_EXPORT void AIBinder_dump(void) {}
STUB_EXPORT void AIBinder_fromJavaBinder(void) {}
STUB_EXPORT void AIBinder_getCallingPid(void) {}
STUB_EXPORT void AIBinder_getCallingUid(void) {}
STUB_EXPORT void AIBinder_getClass(void) {}
STUB_EXPORT void AIBinder_getUserData(void) {}
STUB_EXPORT void AIBinder_incStrong(void) {}
STUB_EXPORT void AIBinder_isAlive(void) {}
STUB_EXPORT void AIBinder_isRemote(void) {}
STUB_EXPORT void AIBinder_linkToDeath(void) {}
STUB_EXPORT void AIBinder_new(void) {}
STUB_EXPORT void AIBinder_ping(void) {}
STUB_EXPORT void AIBinder_prepareTransaction(void) {}
STUB_EXPORT void AIBinder_toJavaBinder(void) {}
STUB_EXPORT void AIBinder_transact(void) {}
STUB_EXPORT void AIBinder_unlinkToDeath(void) {}
STUB_EXPORT void AIBinder_DeathRecipient_delete(void) {}
STUB_EXPORT void AIBinder_DeathRecipient_new(void) {}
STUB_EXPORT void AIBinder_Weak_clone(void) {}
STUB_EXPORT void AIBinder_Weak_delete(void) {}
STUB_EXPORT void AIBinder_Weak_new(void) {}
STUB_EXPORT void AIBinder_Weak_promote(void) {}
STUB_EXPORT void AIBinder_setMinSchedulerPolicy(void) {}
STUB_EXPORT void AIBinder_inheritRt(void) {}

STUB_EXPORT void AParcel_create(void) {}
STUB_EXPORT void AParcel_delete(void) {}
STUB_EXPORT void AParcel_fromJavaParcel(void) {}
STUB_EXPORT void AParcel_getDataPosition(void) {}
STUB_EXPORT void AParcel_getDataSize(void) {}
STUB_EXPORT void AParcel_readBool(void) {}
STUB_EXPORT void AParcel_readBoolArray(void) {}
STUB_EXPORT void AParcel_readByte(void) {}
STUB_EXPORT void AParcel_readByteArray(void) {}
STUB_EXPORT void AParcel_readChar(void) {}
STUB_EXPORT void AParcel_readCharArray(void) {}
STUB_EXPORT void AParcel_readDouble(void) {}
STUB_EXPORT void AParcel_readDoubleArray(void) {}
STUB_EXPORT void AParcel_readFloat(void) {}
STUB_EXPORT void AParcel_readFloatArray(void) {}
STUB_EXPORT void AParcel_readInt32(void) {}
STUB_EXPORT void AParcel_readInt32Array(void) {}
STUB_EXPORT void AParcel_readInt64(void) {}
STUB_EXPORT void AParcel_readInt64Array(void) {}
STUB_EXPORT void AParcel_readParcelFileDescriptor(void) {}
STUB_EXPORT void AParcel_readParcelableArray(void) {}
STUB_EXPORT void AParcel_readStatusHeader(void) {}
STUB_EXPORT void AParcel_readString(void) {}
STUB_EXPORT void AParcel_readStringArray(void) {}
STUB_EXPORT void AParcel_readStrongBinder(void) {}
STUB_EXPORT void AParcel_readStrongBinderArray(void) {}
STUB_EXPORT void AParcel_reset(void) {}
STUB_EXPORT void AParcel_setDataPosition(void) {}
STUB_EXPORT void AParcel_writeBool(void) {}
STUB_EXPORT void AParcel_writeBoolArray(void) {}
STUB_EXPORT void AParcel_writeByte(void) {}
STUB_EXPORT void AParcel_writeByteArray(void) {}
STUB_EXPORT void AParcel_writeChar(void) {}
STUB_EXPORT void AParcel_writeCharArray(void) {}
STUB_EXPORT void AParcel_writeDouble(void) {}
STUB_EXPORT void AParcel_writeDoubleArray(void) {}
STUB_EXPORT void AParcel_writeFloat(void) {}
STUB_EXPORT void AParcel_writeFloatArray(void) {}
STUB_EXPORT void AParcel_writeInt32(void) {}
STUB_EXPORT void AParcel_writeInt32Array(void) {}
STUB_EXPORT void AParcel_writeInt64(void) {}
STUB_EXPORT void AParcel_writeInt64Array(void) {}
STUB_EXPORT void AParcel_writeParcelFileDescriptor(void) {}
STUB_EXPORT void AParcel_writeParcelableArray(void) {}
STUB_EXPORT void AParcel_writeStatusHeader(void) {}
STUB_EXPORT void AParcel_writeString(void) {}
STUB_EXPORT void AParcel_writeStringArray(void) {}
STUB_EXPORT void AParcel_writeStrongBinder(void) {}
STUB_EXPORT void AParcel_writeStrongBinderArray(void) {}

STUB_EXPORT void AStatus_delete(void) {}
STUB_EXPORT void AStatus_fromExceptionCode(void) {}
STUB_EXPORT void AStatus_fromExceptionCodeWithMessage(void) {}
STUB_EXPORT void AStatus_fromServiceSpecificError(void) {}
STUB_EXPORT void AStatus_fromServiceSpecificErrorWithMessage(void) {}
STUB_EXPORT void AStatus_fromStatus(void) {}
STUB_EXPORT void AStatus_getDescription(void) {}
STUB_EXPORT void AStatus_getExceptionCode(void) {}
STUB_EXPORT void AStatus_getMessage(void) {}
STUB_EXPORT void AStatus_getServiceSpecificError(void) {}
STUB_EXPORT void AStatus_getStatus(void) {}
STUB_EXPORT void AStatus_isOk(void) {}
STUB_EXPORT void AStatus_newOk(void) {}

// 2. System Fonts NDK (introduced in API 29, missing in Android 9 /system/lib64/libandroid.so)
STUB_EXPORT void* ASystemFontIterator_open(void) { return NULL; }
STUB_EXPORT void ASystemFontIterator_close(void* it) {}
STUB_EXPORT void* ASystemFontIterator_next(void* it) { return NULL; }
STUB_EXPORT const char* ASystemFont_getFilePath(const void* f) { return NULL; }
STUB_EXPORT uint16_t ASystemFont_getWeight(const void* f) { return 400; }
STUB_EXPORT int ASystemFont_isItalic(const void* f) { return 0; }
STUB_EXPORT size_t ASystemFont_getCollectionIndex(const void* f) { return 0; }
STUB_EXPORT size_t ASystemFont_getAxisCount(const void* f) { return 0; }
STUB_EXPORT uint32_t ASystemFont_getAxisTag(const void* f, uint32_t i) { return 0; }
STUB_EXPORT float ASystemFont_getAxisValue(const void* f, uint32_t i) { return 0.0f; }

// 3. Font and FontMatcher NDK (API 29)
STUB_EXPORT const char* AFont_getFilePath(const void* f) { return NULL; }
STUB_EXPORT uint16_t AFont_getWeight(const void* f) { return 400; }
STUB_EXPORT int AFont_isItalic(const void* f) { return 0; }
STUB_EXPORT const char* AFont_getLocale(const void* f) { return NULL; }
STUB_EXPORT size_t AFont_getCollectionIndex(const void* f) { return 0; }
STUB_EXPORT size_t AFont_getAxisCount(const void* f) { return 0; }
STUB_EXPORT uint32_t AFont_getAxisTag(const void* f, uint32_t i) { return 0; }
STUB_EXPORT float AFont_getAxisValue(const void* f, uint32_t i) { return 0.0f; }
STUB_EXPORT void AFont_close(void* f) {}
STUB_EXPORT void* AFontMatcher_create(void) { return NULL; }
STUB_EXPORT void AFontMatcher_destroy(void* m) {}
STUB_EXPORT void AFontMatcher_setStyle(void* m, uint16_t w, int it) {}
STUB_EXPORT void AFontMatcher_setLocales(void* m, const char* l) {}
STUB_EXPORT void* AFontMatcher_match(const void* m, const char* f, const uint16_t* t, uint32_t len, void* run) { return NULL; }

// 4. Trace NDK (API 29 additions)
STUB_EXPORT void ATrace_beginAsyncSection(const char* n, int32_t c) {}
STUB_EXPORT void ATrace_endAsyncSection(const char* n, int32_t c) {}
STUB_EXPORT void ATrace_setCounter(const char* n, int64_t v) {}
STUB_EXPORT int ATrace_isEnabled(void) { return 0; }

// 5. Thermal NDK (API 29)
STUB_EXPORT void* AThermal_acquireManager(void) { return NULL; }
STUB_EXPORT void AThermal_releaseManager(void* m) {}
STUB_EXPORT int AThermal_getCurrentThermalStatus(void* m) { return 0; }
STUB_EXPORT int AThermal_registerThermalStatusListener(void* m, void* l, void* d) { return -1; }
STUB_EXPORT int AThermal_unregisterThermalStatusListener(void* m, void* l, void* d) { return -1; }

// 6. Choreographer NDK (API 29 additions)
STUB_EXPORT void AChoreographer_postFrameCallback64(void* c, void* cb, void* d) {}
STUB_EXPORT void AChoreographer_postFrameCallbackDelayed64(void* c, void* cb, void* d, int64_t ms) {}
STUB_EXPORT int AChoreographer_registerRefreshRateCallback(void* c, void* cb, void* d) { return -1; }
STUB_EXPORT int AChoreographer_unregisterRefreshRateCallback(void* c, void* cb, void* d) { return -1; }

// 7. HardwareBuffer NDK (API 29 additions)
STUB_EXPORT int AHardwareBuffer_isSupported(const void* d) { return 0; }
STUB_EXPORT int AHardwareBuffer_getId(const void* b, uint64_t* id) { return -1; }

// 8. SurfaceControl NDK (API 29)
STUB_EXPORT void* ASurfaceControl_createFromWindow(void* p, const char* n) { return NULL; }
STUB_EXPORT void* ASurfaceControl_create(void* p, const char* n) { return NULL; }
STUB_EXPORT void ASurfaceControl_release(void* sc) {}
STUB_EXPORT void* ASurfaceTransaction_create(void) { return NULL; }
STUB_EXPORT void ASurfaceTransaction_delete(void* t) {}
STUB_EXPORT void ASurfaceTransaction_apply(void* t) {}
STUB_EXPORT void ASurfaceTransaction_setVisibility(void* t, void* sc, int8_t v) {}
STUB_EXPORT void ASurfaceTransaction_setZOrder(void* t, void* sc, int32_t z) {}
STUB_EXPORT void ASurfaceTransaction_setBuffer(void* t, void* sc, void* b, int fd) {}
STUB_EXPORT void ASurfaceTransaction_setGeometry(void* t, void* sc, const void* s, const void* d, int32_t tr) {}
STUB_EXPORT void ASurfaceTransaction_setBufferAlpha(void* t, void* sc, float a) {}
STUB_EXPORT void ASurfaceTransaction_setBufferDataSpace(void* t, void* sc, int32_t ds) {}
STUB_EXPORT void ASurfaceTransaction_setHdrMetadata_cta861_3(void* t, void* sc, const void* m, size_t b) {}
STUB_EXPORT void ASurfaceTransaction_setHdrMetadata_smpte2086(void* t, void* sc, const void* m, size_t b) {}
STUB_EXPORT void ASurfaceTransaction_setDamageRegion(void* t, void* sc, const void* r, size_t c) {}
STUB_EXPORT void ASurfaceTransaction_setDesiredPresentTime(void* t, int64_t time) {}
STUB_EXPORT void ASurfaceTransaction_setColor(void* t, void* sc, float r, float g, float b, float a, int32_t ds) {}
STUB_EXPORT void ASurfaceTransaction_setOnComplete(void* t, void* ctx, void* cb) {}
"""


def find_or_build_binder_ndk_so(abi: str, base_dir: str = None):
    # 0. Prioritize prebuilt embedded freestanding shim (zero toolchain dependencies, guaranteed full API 29 coverage)
    if abi in EMBEDDED_SHIM_B64 and EMBEDDED_SHIM_B64[abi]:
        try:
            raw = base64.b64decode(EMBEDDED_SHIM_B64[abi])
            try:
                raw = zlib.decompress(raw)
            except Exception:
                pass
            if len(raw) > 0 and raw.startswith(b"\x7fELF"):
                print(f"[patch_apk_manifest] Using prebuilt embedded {abi} libbinder_ndk.so shim ({len(raw)} bytes)")
                return raw
        except Exception as e:
            print(f"[patch_apk_manifest] Warning: failed to decode embedded shim for {abi}: {e}")

    target_arch = "aarch64-linux-android" if abi == "arm64-v8a" else "arm-linux-androideabi"
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # 1. Prioritize compiling custom stub with clang/gcc to include all API 29 missing symbols (such as ASystemFontIterator_open)
    clang_candidates = [
        os.path.join(script_dir, "chromium/src/third_party/llvm-build/Release+Asserts/bin/clang"),
        os.path.join(script_dir, "third_party/llvm-build/Release+Asserts/bin/clang"),
        "/root/android-helium-browser/chromium/src/third_party/llvm-build/Release+Asserts/bin/clang",
    ]
    if base_dir:
        clang_candidates.append(os.path.join(base_dir, "chromium/src/third_party/llvm-build/Release+Asserts/bin/clang"))
        clang_candidates.append(os.path.join(base_dir, "third_party/llvm-build/Release+Asserts/bin/clang"))
    if os.environ.get("ANDROID_NDK_HOME"):
        clang_candidates.append(os.path.join(os.environ["ANDROID_NDK_HOME"], "toolchains/llvm/prebuilt/linux-x86_64/bin/clang"))
    if os.environ.get("ANDROID_HOME"):
        ah = os.environ["ANDROID_HOME"]
        for cand_ndk in [os.path.join(ah, "ndk"), os.path.join(ah, "ndk-bundle")]:
            if os.path.isdir(cand_ndk):
                try:
                    for sub in os.listdir(cand_ndk):
                        c = os.path.join(cand_ndk, sub, "toolchains/llvm/prebuilt/linux-x86_64/bin/clang")
                        if os.path.isfile(c):
                            clang_candidates.append(c)
                except Exception:
                    pass
    clang_candidates.append(shutil.which("clang"))

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
            for extra_flags in [["-fuse-ld=lld"], []]:
                cmd = [clang_bin, target_flag] + extra_flags + ["-shared", "-fPIC", "-nostdlib", "-Wl,-soname,libbinder_ndk.so", src_c, "-o", out_so]
                res = subprocess.run(cmd, capture_output=True)
                if res.returncode == 0 and os.path.isfile(out_so):
                    with open(out_so, "rb") as f:
                        data = f.read()
                    if len(data) > 0:
                        print(f"[patch_apk_manifest] Compiled {abi} libbinder_ndk.so stub using {clang_bin}")
                        return data

    gcc_candidates = ["aarch64-linux-gnu-gcc", "aarch64-linux-android-gcc"] if abi == "arm64-v8a" else ["arm-linux-gnueabihf-gcc", "arm-linux-gnueabi-gcc", "arm-linux-androideabi-gcc"]
    for gcc in gcc_candidates:
        gcc_bin = shutil.which(gcc)
        if gcc_bin:
            with tempfile.TemporaryDirectory(prefix="binder_gcc_stub_") as td:
                src_c = os.path.join(td, "binder_ndk_stub.c")
                out_so = os.path.join(td, "libbinder_ndk.so")
                with open(src_c, "w") as f:
                    f.write(BINDER_NDK_STUB_C)
                cmd = [gcc_bin, "-shared", "-fPIC", "-nostdlib", "-Wl,-soname,libbinder_ndk.so", src_c, "-o", out_so]
                res = subprocess.run(cmd, capture_output=True)
                if res.returncode == 0 and os.path.isfile(out_so):
                    with open(out_so, "rb") as f:
                        data = f.read()
                    if len(data) > 0:
                        print(f"[patch_apk_manifest] Compiled {abi} libbinder_ndk.so stub using {gcc_bin}")
                        return data

    # 2. Fallback: search for existing prebuilt libbinder_ndk.so in NDK sysroot
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

    return None


def read_uleb128(data: bytearray, offset: int):
    result = 0
    shift = 0
    pos = offset
    while True:
        b = data[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if (b & 0x80) == 0:
            break
        shift += 7
    return result, pos


def read_dex_string(data: bytearray, string_ids_off: int, idx: int) -> str:
    off = struct.unpack_from("<I", data, string_ids_off + idx * 4)[0]
    pos = off
    while (data[pos] & 0x80) != 0:
        pos += 1
    pos += 1
    end = data.find(b"\x00", pos)
    return data[pos:end].decode("utf-8", errors="replace")


DALVIK_OP_WIDTHS = [
    1, 1, 2, 3, 1, 2, 3, 1, 2, 3, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 2, 3, 2, 2, 3, 5, 2, 2, 3, 2, 1, 1, 2,
    2, 1, 2, 2, 3, 3, 3, 1, 1, 2, 3, 3, 3, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    1, 1, 1, 1, 1, 1, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 3,
    3, 3, 3, 1, 3, 3, 3, 3, 3, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1
]


def patch_dex_bytes(dex_bytes: bytearray) -> tuple[bytearray, bool]:
    """
    Scans a DEX file and patches calls to API 29+ methods that crash Android 9 (API 28):
    1. Activity.registerActivityLifecycleCallbacks / unregisterActivityLifecycleCallbacks
    2. View.saveAttributeDataForStyleable (causes InflateException in AlertDialogLayout/AppCompat on Android 9)
    3. View.setSystemGestureExclusionRects (causes NoSuchMethodError on gesture handling)
    with NOPs to prevent NoSuchMethodError crash on Android 9 (API 28).
    All patched methods must return void (V) so NOPing them does not leave unconsumed results.
    """
    if not dex_bytes.startswith(b"dex\n"):
        return dex_bytes, False

    target_defs = [
        (b"Landroid/app/Activity;", b"registerActivityLifecycleCallbacks", "Landroid/app/Activity;", "registerActivityLifecycleCallbacks"),
        (b"Landroid/app/Activity;", b"unregisterActivityLifecycleCallbacks", "Landroid/app/Activity;", "unregisterActivityLifecycleCallbacks"),
        (b"Landroid/view/View;", b"saveAttributeDataForStyleable", "Landroid/view/View;", "saveAttributeDataForStyleable"),
        (b"Landroid/view/View;", b"setSystemGestureExclusionRects", "Landroid/view/View;", "setSystemGestureExclusionRects"),
        (b"Landroid/view/View;", b"setForceDarkAllowed", "Landroid/view/View;", "setForceDarkAllowed"),
        (b"Landroid/view/Window;", b"setStatusBarContrastEnforced", "Landroid/view/Window;", "setStatusBarContrastEnforced"),
        (b"Landroid/view/Window;", b"setNavigationBarContrastEnforced", "Landroid/view/Window;", "setNavigationBarContrastEnforced"),
    ]

    active_targets = [t for t in target_defs if t[0] in dex_bytes and t[1] in dex_bytes]
    if not active_targets:
        return dex_bytes, False

    string_ids_size, string_ids_off = struct.unpack_from("<II", dex_bytes, 0x38)
    type_ids_size, type_ids_off = struct.unpack_from("<II", dex_bytes, 0x40)
    method_ids_size, method_ids_off = struct.unpack_from("<II", dex_bytes, 0x58)
    class_defs_size, class_defs_off = struct.unpack_from("<II", dex_bytes, 0x60)

    needed_strings = set()
    for _, _, cls_str, m_str in active_targets:
        needed_strings.add(cls_str)
        needed_strings.add(m_str)

    # 1. Identify target string indices
    str_to_idx = {}
    for s_idx in range(string_ids_size):
        try:
            s_val = read_dex_string(dex_bytes, string_ids_off, s_idx)
            if s_val in needed_strings:
                str_to_idx[s_val] = s_idx
        except Exception:
            continue

    if not str_to_idx:
        return dex_bytes, False

    # 2. Identify type indices for target classes
    class_to_type_indices = {}
    for _, _, cls_str, _ in active_targets:
        if cls_str in str_to_idx and cls_str not in class_to_type_indices:
            cls_s_idx = str_to_idx[cls_str]
            type_set = set()
            for t_idx in range(type_ids_size):
                desc_idx = struct.unpack_from("<I", dex_bytes, type_ids_off + t_idx * 4)[0]
                if desc_idx == cls_s_idx:
                    type_set.add(t_idx)
            class_to_type_indices[cls_str] = type_set

    # 3. Identify target method indices
    target_method_indices = set()
    for _, _, cls_str, m_str in active_targets:
        if cls_str not in class_to_type_indices or m_str not in str_to_idx:
            continue
        c_types = class_to_type_indices[cls_str]
        m_s_idx = str_to_idx[m_str]
        for m_idx in range(method_ids_size):
            class_idx = struct.unpack_from("<H", dex_bytes, method_ids_off + m_idx * 8)[0]
            name_idx = struct.unpack_from("<I", dex_bytes, method_ids_off + m_idx * 8 + 4)[0]
            if class_idx in c_types and name_idx == m_s_idx:
                target_method_indices.add(m_idx)

    if not target_method_indices:
        return dex_bytes, False

    # 4. Scan class_defs for method bytecode
    total_patched = 0
    for c_idx in range(class_defs_size):
        class_data_off = struct.unpack_from("<I", dex_bytes, class_defs_off + c_idx * 32 + 24)[0]
        if class_data_off == 0:
            continue
        try:
            pos = class_data_off
            static_fields_size, pos = read_uleb128(dex_bytes, pos)
            instance_fields_size, pos = read_uleb128(dex_bytes, pos)
            direct_methods_size, pos = read_uleb128(dex_bytes, pos)
            virtual_methods_size, pos = read_uleb128(dex_bytes, pos)

            for _ in range(static_fields_size):
                _, pos = read_uleb128(dex_bytes, pos)
                _, pos = read_uleb128(dex_bytes, pos)
            for _ in range(instance_fields_size):
                _, pos = read_uleb128(dex_bytes, pos)
                _, pos = read_uleb128(dex_bytes, pos)

            for _ in range(direct_methods_size + virtual_methods_size):
                _, pos = read_uleb128(dex_bytes, pos)
                _, pos = read_uleb128(dex_bytes, pos)
                code_off, pos = read_uleb128(dex_bytes, pos)
                if code_off == 0:
                    continue

                insns_size = struct.unpack_from("<I", dex_bytes, code_off + 12)[0]
                insns_start = code_off + 16
                insns = list(struct.unpack_from(f"<{insns_size}H", dex_bytes, insns_start))

                pc = 0
                method_modified = False
                while pc < insns_size:
                    inst = insns[pc]
                    op = inst & 0xFF
                    if inst == 0x0100:
                        count = insns[pc + 1]
                        width = 4 + count * 2
                    elif inst == 0x0200:
                        count = insns[pc + 1]
                        width = 2 + count * 4
                    elif inst == 0x0300:
                        elem_w = insns[pc + 1]
                        elem_c = insns[pc + 2] | (insns[pc + 3] << 16)
                        width = 4 + (elem_w * elem_c + 1) // 2
                    else:
                        width = DALVIK_OP_WIDTHS[op]
                        if op in (0x6E, 0x6F, 0x74, 0x75) and pc + 1 < insns_size:
                            m_idx = insns[pc + 1]
                            if m_idx in target_method_indices:
                                # Replace invoke instruction (3 code units = 6 bytes) with NOPs
                                insns[pc] = 0x0000
                                insns[pc + 1] = 0x0000
                                insns[pc + 2] = 0x0000
                                method_modified = True
                                total_patched += 1
                    if width <= 0:
                        break
                    pc += width

                if method_modified:
                    struct.pack_into(f"<{insns_size}H", dex_bytes, insns_start, *insns)
        except Exception:
            continue

    if total_patched > 0:
        sha1 = hashlib.sha1(dex_bytes[32:]).digest()
        dex_bytes[12:32] = sha1
        checksum = zlib.adler32(dex_bytes[12:]) & 0xFFFFFFFF
        struct.pack_into("<I", dex_bytes, 8, checksum)
        print(f"[patch_apk_manifest] Patched {total_patched} API 29+ calls (Activity callbacks / View styleable) with NOP in DEX")
        return dex_bytes, True

    return dex_bytes, False


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

            arm64_binder = find_or_build_binder_ndk_so("arm64-v8a") if has_arm64 else None
            arm32_binder = find_or_build_binder_ndk_so("armeabi-v7a") if has_arm32 else None

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
                elif item.filename.endswith(".dex"):
                    dex_data = bytearray(z_in.read(item.filename))
                    patched_dex, did_patch = patch_dex_bytes(dex_data)
                    if did_patch:
                        z_out.writestr(item, bytes(patched_dex))
                        print(f"[patch_apk_manifest] Injected DEX compatibility patch into {item.filename}")
                    else:
                        z_out.writestr(item, z_in.read(item.filename))
                elif item.filename == "lib/arm64-v8a/libbinder_ndk.so":
                    if arm64_binder:
                        z_out.writestr(item, arm64_binder)
                        arm64_binder = None  # marked as injected/replaced
                        print("[patch_apk_manifest] Replaced lib/arm64-v8a/libbinder_ndk.so with comprehensive API 29 compatibility shim")
                    else:
                        z_out.writestr(item, z_in.read(item.filename))
                elif item.filename == "lib/armeabi-v7a/libbinder_ndk.so":
                    if arm32_binder:
                        z_out.writestr(item, arm32_binder)
                        arm32_binder = None  # marked as injected/replaced
                        print("[patch_apk_manifest] Replaced lib/armeabi-v7a/libbinder_ndk.so with comprehensive API 29 compatibility shim")
                    else:
                        z_out.writestr(item, z_in.read(item.filename))
                else:
                    z_out.writestr(item, z_in.read(item.filename))

            # Inject libbinder_ndk.so if not already present in the source APK
            if has_arm64 and arm64_binder:
                z_out.writestr("lib/arm64-v8a/libbinder_ndk.so", arm64_binder)
                print("[patch_apk_manifest] Injected lib/arm64-v8a/libbinder_ndk.so for Android 9 car compatibility")

            if has_arm32 and arm32_binder:
                z_out.writestr("lib/armeabi-v7a/libbinder_ndk.so", arm32_binder)
                print("[patch_apk_manifest] Injected lib/armeabi-v7a/libbinder_ndk.so for Android 9 car compatibility")

        shutil.move(patched_apk, apk_path)
        print(f"Successfully patched {apk_path} manifest, dex & car libs (minSdk={min_sdk}, targetSdk={target_sdk}, gles=0x{gles:08x})")
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
