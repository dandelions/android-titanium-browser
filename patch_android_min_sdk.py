#!/usr/bin/env python3
import os
import re
import sys


def patch_file(file_path: str, replacements: list) -> bool:
    if not os.path.isfile(file_path):
        return False

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    new_content = content
    for old_str, new_str in replacements:
        new_content = new_content.replace(old_str, new_str)

    if new_content != content:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Patched: {file_path}")
        return True
    return False


def clean_target_sdk_assignments_in_gn(src_dir: str) -> None:
    # GN 严格检查变量作用域，未使用的 target_sdk_version 会导致 "Assignment had no effect" 报错
    # 清理所有 .gn 和 .gni 文件中错误注入的 target_sdk_version 赋值行
    search_dirs = [
        os.path.join(src_dir, "chrome/android"),
        os.path.join(src_dir, "android_webview"),
        os.path.join(src_dir, "build/config/android"),
        os.path.join(src_dir, "vanadium"),
    ]
    for sdir in search_dirs:
        if not os.path.isdir(sdir):
            continue
        for root, _, files in os.walk(sdir):
            for file_name in files:
                if file_name.endswith((".gn", ".gni")):
                    full_path = os.path.join(root, file_name)
                    try:
                        with open(full_path, "r", encoding="utf-8") as f:
                            c = f.read()
                        if "target_sdk_version" in c:
                            nc = re.sub(r"^[ \t]*target_sdk_version\s*=\s*\d+.*$\n?", "", c, flags=re.MULTILINE)
                            if nc != c:
                                with open(full_path, "w", encoding="utf-8") as f:
                                    f.write(nc)
                                print(f"Cleaned unused target_sdk_version assignment from: {full_path}")
                    except Exception as e:
                        print(f"Warning: could not process {full_path}: {e}", file=sys.stderr)


def patch_min_sdk_in_gni(file_path: str) -> bool:
    # 现已采用 patch_apk_manifest.py 二进制清单注入方案，在 APK 签名阶段直接修改 minSdk 与 targetSdk，
    # 无需改动源码级 .gn/.gni 模板，避免修改构建文件导致 Ninja 编译缓存失效或触发全量重编。
    return False


def remove_original_package_from_manifest(src_dir: str) -> None:
    manifest_paths = [
        os.path.join(src_dir, "chrome/android/java/AndroidManifest.xml"),
    ]
    for manifest_path in manifest_paths:
        if not os.path.isfile(manifest_path):
            continue
        with open(manifest_path, "r", encoding="utf-8") as f:
            content = f.read()
        new_content = re.sub(r"[ \t]*<original-package[^>]*>\s*", "\n", content)
        if new_content != content:
            with open(manifest_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print("Patched AndroidManifest.xml: removed <original-package> to avoid system package signature conflicts.")


def patch_manifest_extract_native_libs(src_dir: str) -> None:
    manifest_path = os.path.join(src_dir, "chrome/android/java/AndroidManifest.xml")
    if not os.path.isfile(manifest_path):
        return
    with open(manifest_path, "r", encoding="utf-8") as f:
        content = f.read()

    new_content = content
    if 'android:extractNativeLibs="false"' in new_content:
        new_content = new_content.replace(
            'android:extractNativeLibs="false"', 'android:extractNativeLibs="true"'
        )
    elif 'android:extractNativeLibs=' not in new_content:
        # 在 Android 10 上，如果 extractNativeLibs="false"，要求所有 SO 零压缩且页对齐，否则 PackageParser 直接报错；
        # 显式在 <application 标签中设置 android:extractNativeLibs="true"，让 Android 10 安装时将 SO 提取到本地目录，规避解析崩溃
        new_content = re.sub(
            r'(<application\b)',
            r'\1 android:extractNativeLibs="true"',
            new_content,
            count=1,
        )

    if new_content != content:
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(
            'Patched AndroidManifest.xml: set android:extractNativeLibs="true" for Android 10 compatibility.'
        )


def patch_manifest_sdk_and_features(src_dir: str) -> None:
    manifest_paths = [
        os.path.join(src_dir, "chrome/android/java/AndroidManifest.xml"),
    ]
    for manifest_path in manifest_paths:
        if not os.path.isfile(manifest_path):
            continue
        with open(manifest_path, "r", encoding="utf-8") as f:
            content = f.read()

        new_content = content

        # 1. 清除 AndroidManifest.xml 中可能存在的硬编码 <uses-sdk>（兼容单行与多行格式）
        # Chromium 构建系统 (manifest_merger / generate_manifest) 会根据 GN 的 min_sdk_version 自动生成合法的 uses-sdk 标签。
        # 如果源 XML 中手动插入了 <uses-sdk>，会导致合并出的二进制清单中存在重复的 <uses-sdk> 标签，
        # 触发 AOSP PackageParser 的 "<manifest> has more than one <uses-sdk>" (INSTALL_PARSE_FAILED_BAD_MANIFEST) 致命解析错误！
        new_content = re.sub(r"[ \t]*<uses-sdk\b.*?(?:/>|</uses-sdk>)\s*", "\n", new_content, flags=re.DOTALL)

        # 2. 将强制要求的 OpenGL ES 3.0 改为兼容模式 2.0 (或 required="false")，防止车机 GPU 不支持 3.0 导致包解析失败
        new_content = re.sub(
            r'<uses-feature\s+android:glEsVersion="0x00030000"\s*/>',
            '<uses-feature android:glEsVersion="0x00020000" android:required="false" />',
            new_content,
        )

        if new_content != content:
            with open(manifest_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Cleaned duplicate uses-sdk and patched glEsVersion in: {manifest_path}")


def restore_default_android_sdk_version(src_dir: str) -> None:
    config_gni = os.path.join(src_dir, "build/config/android/config.gni")
    if not os.path.isfile(config_gni):
        return
    try:
        import subprocess
        subprocess.run(["git", "checkout", "--", "build/config/android/config.gni"], cwd=src_dir, capture_output=True)
        print("Restored default build/config/android/config.gni to avoid breaking native AIDL toolchain.")
    except Exception as e:
        print(f"Warning: could not restore config.gni: {e}", file=sys.stderr)


def patch_expectations(src_dir: str) -> None:
    expectations_dirs = [
        os.path.join(src_dir, "chrome/android/expectations"),
        os.path.join(src_dir, "android_webview/expectations"),
    ]
    for exp_dir in expectations_dirs:
        if not os.path.isdir(exp_dir):
            continue
        for root, _, files in os.walk(exp_dir):
            for file_name in files:
                if file_name.endswith(".expected"):
                    exp_path = os.path.join(root, file_name)
                    with open(exp_path, "r", encoding="utf-8") as f:
                        c = f.read()
                    # 将期待的 minSdkVersion 降到 29 (Android 10 车机基线)
                    nc = re.sub(
                        r'android:minSdkVersion="\d+"',
                        'android:minSdkVersion="29"',
                        c,
                    )
                    # 恢复之前被改成 34 的 targetSdkVersion 回 37（匹配 Chromium 原生输出，防止比对失败）
                    nc = re.sub(
                        r'android:targetSdkVersion="34"',
                        'android:targetSdkVersion="37"',
                        nc,
                    )
                    # 清理 zygotePreload 及现代属性期待项
                    nc = re.sub(r'[ \t]*android:zygotePreloadName="[^"]*"', '', nc)
                    nc = re.sub(r'[ \t]*android:zygotePreloadNativeLib="[^"]*"', '', nc)
                    nc = re.sub(r'[ \t]*android:memtagMode="[^"]*"', '', nc)
                    nc = re.sub(r'[ \t]*android:enableOnBackInvokedCallback="[^"]*"', '', nc)
                    if nc != c:
                        with open(exp_path, "w", encoding="utf-8") as f:
                            f.write(nc)
                        print(f"Patched AndroidManifest expectations in: {exp_path}")


def is_old_android_branch(src_dir: str) -> bool:
    if os.environ.get("CAR_COMPAT") == "1" or os.environ.get("BUILD_OLD_ANDROID") == "1" or os.environ.get("DISABLE_V3_SIGNING") == "1":
        return True
    if os.environ.get("CAR_COMPAT") == "0":
        return False
    try:
        import subprocess
        res = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, cwd=src_dir)
        if "old-android" in res.stdout:
            return True
        res_root = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True)
        if "old-android" in res_root.stdout:
            return True
    except Exception:
        pass
    return True


def clean_manifest_zygote_and_modern_attributes(src_dir: str) -> None:
    manifest_paths = [
        os.path.join(src_dir, "chrome/android/java/AndroidManifest.xml"),
    ]
    # 额外扫描 chrome/android 与 android_webview 下可能存在的所有 AndroidManifest 文件
    for sub in ["chrome/android", "android_webview"]:
        target_dir = os.path.join(src_dir, sub)
        if os.path.isdir(target_dir):
            for root, _, files in os.walk(target_dir):
                for file_name in files:
                    if "AndroidManifest" in file_name and file_name.endswith(".xml"):
                        p = os.path.join(root, file_name)
                        if p not in manifest_paths:
                            manifest_paths.append(p)

    for manifest_path in manifest_paths:
        if not os.path.isfile(manifest_path):
            continue
        with open(manifest_path, "r", encoding="utf-8") as f:
            content = f.read()

        new_content = content
        # 1. 移除 zygotePreloadName 与 zygotePreloadNativeLib，避免车机 App Zygote 阻塞卡死
        new_content = re.sub(r'[ \t]*android:zygotePreloadName="[^"]*"', '', new_content)
        new_content = re.sub(r'[ \t]*android:zygotePreloadNativeLib="[^"]*"', '', new_content)
        # 2. 移除 memtagMode，避免老旧车机 CPU/libc 内存保护错乱
        new_content = re.sub(r'[ \t]*android:memtagMode="[^"]*"', '', new_content)
        # 3. 移除 enableOnBackInvokedCallback
        new_content = re.sub(r'[ \t]*android:enableOnBackInvokedCallback="[^"]*"', '', new_content)

        if new_content != content:
            with open(manifest_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Cleaned zygotePreload and modern attributes to prevent car head-unit hang in: {manifest_path}")


def main() -> None:
    src_dir = sys.argv[1] if len(sys.argv) > 1 else "."

    if not is_old_android_branch(src_dir):
        print("Not old-android branch and CAR_COMPAT is disabled. Skipping car head-unit patches.")
        return

    # 1. 清理所有 .gn / .gni 中未被使用的 target_sdk_version 赋值（避免 GN Assignment had no effect 致命错误）
    clean_target_sdk_assignments_in_gn(src_dir)

    # 2. 恢复 build/config/android/config.gni 的默认 SDK 版本，避免破坏原生 AIDL 编译工具链
    restore_default_android_sdk_version(src_dir)

    # 3. 修改关键 GN 模板的 min_sdk_version
    key_gni_targets = [
        os.path.join(src_dir, "chrome/android/chrome_public_apk_tmpl.gni"),
        os.path.join(src_dir, "chrome/android/trichrome.gni"),
        os.path.join(src_dir, "android_webview/system_webview_apk_tmpl.gni"),
        os.path.join(src_dir, "vanadium/chromium_src/chrome/android/BUILD.gn"),
    ]

    for gni_file in key_gni_targets:
        patch_min_sdk_in_gni(gni_file)

    # 4. 修正 expectations 以免检查比对失败
    patch_expectations(src_dir)

    # 5. 扫描相关目录，确保 min_sdk_version 降为 29，并清除 target_sdk_version
    scan_dirs = [
        os.path.join(src_dir, "chrome/android"),
        os.path.join(src_dir, "android_webview"),
        os.path.join(src_dir, "vanadium"),
    ]

    for scan_dir in scan_dirs:
        if not os.path.isdir(scan_dir):
            continue
        for root, _, files in os.walk(scan_dir):
            for file_name in files:
                full_path = os.path.join(root, file_name)
                if file_name.endswith((".gni", ".gn")):
                    patch_min_sdk_in_gni(full_path)
                elif "AndroidManifest" in file_name and file_name.endswith(".xml"):
                    with open(full_path, "r", encoding="utf-8") as f:
                        c = f.read()
                    nc = re.sub(r'android:minSdkVersion="\d+"', 'android:minSdkVersion="29"', c)
                    nc = re.sub(
                        r'<uses-feature\s+android:glEsVersion="0x00030000"\s*/>',
                        '<uses-feature android:glEsVersion="0x00020000" android:required="false" />',
                        nc,
                    )
                    if nc != c:
                        with open(full_path, "w", encoding="utf-8") as f:
                            f.write(nc)
                        print(f"Patched AndroidManifest.xml: {full_path}")

    # 6. Manifest 属性调整
    patch_manifest_extract_native_libs(src_dir)
    remove_original_package_from_manifest(src_dir)
    patch_manifest_sdk_and_features(src_dir)
    clean_manifest_zygote_and_modern_attributes(src_dir)

    print("SDK version patch (minSdk: 29) & extractNativeLibs check complete.")


if __name__ == "__main__":
    main()
