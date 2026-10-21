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
        print(f"Patched SDK version in: {file_path}")
        return True
    return False


def patch_target_sdk_in_gni(file_path: str) -> bool:
    if not os.path.isfile(file_path):
        return False
    # Never inject target_sdk_version into build/config/android to avoid GN scope clobber errors
    norm_path = file_path.replace("\\", "/")
    if "build/config/android" in norm_path:
        return False

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    new_content = content
    # 1. 替换 min_sdk_version = 34 为 29
    new_content = re.sub(r"min_sdk_version\s*=\s*34", "min_sdk_version = 29", new_content)
    new_content = re.sub(
        r"default_min_sdk_version\s*=\s*34", "default_min_sdk_version = 29", new_content
    )

    # 2. 如果存在 min_sdk_version = 29，但未定义 target_sdk_version = 34，则注入 target_sdk_version = 34
    if "target_sdk_version = 34" not in new_content:
        def inject_target_sdk(match):
            indent = match.group(1)
            return f"{indent}min_sdk_version = 29\n{indent}target_sdk_version = 34"

        new_content = re.sub(
            r"([ \t]*)min_sdk_version\s*=\s*29", inject_target_sdk, new_content
        )

    if new_content != content:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Patched and injected target_sdk_version = 34 in: {file_path}")
        return True
    return False


def inject_target_sdk_to_chrome_public_tmpl(src_dir: str) -> None:
    tmpl_path = os.path.join(src_dir, "chrome/android/chrome_public_apk_tmpl.gni")
    if not os.path.isfile(tmpl_path):
        return
    with open(tmpl_path, "r", encoding="utf-8") as f:
        content = f.read()

    new_content = content
    # Unconditionally inject target_sdk_version = 34 at the top of chrome_common_apk_or_module_tmpl
    if 'template("chrome_common_apk_or_module_tmpl")' in new_content and "target_sdk_version = 34" not in new_content:
        new_content = re.sub(
            r'(template\("chrome_common_apk_or_module_tmpl"\)\s*\{)',
            r'\1\n    target_sdk_version = 34',
            new_content,
        )

    if new_content != content:
        with open(tmpl_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Injected target_sdk_version = 34 unconditionally to: {tmpl_path}")


def clean_clobbering_in_build_config(src_dir: str) -> None:
    # Clean up any target_sdk_version that was erroneously injected into global build/config/android files
    check_files = [
        os.path.join(src_dir, "build/config/android/config.gni"),
        os.path.join(src_dir, "build/config/android/rules.gni"),
    ]
    for target_file in check_files:
        if not os.path.isfile(target_file):
            continue
        with open(target_file, "r", encoding="utf-8") as f:
            c = f.read()
        nc = re.sub(r"^[ \t]*target_sdk_version\s*=\s*\d+.*$\n?", "", c, flags=re.MULTILINE)
        if nc != c:
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(nc)
            print(f"Cleaned clobbering target_sdk_version from global file: {target_file}")


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

    new_content = content.replace(
        'android:extractNativeLibs="false"', 'android:extractNativeLibs="true"'
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

        # 1. 显式在 AndroidManifest.xml 中写入或更新 <uses-sdk>
        if "<uses-sdk" in new_content:
            new_content = re.sub(
                r"<uses-sdk[^>]*/>",
                '<uses-sdk android:minSdkVersion="29" android:targetSdkVersion="34" />',
                new_content,
            )
        else:
            # 插入到 <manifest ...> 标签之后
            def insert_uses_sdk(m):
                return m.group(0) + '\n    <uses-sdk android:minSdkVersion="29" android:targetSdkVersion="34" />'
            new_content = re.sub(r"<manifest[^>]*>", insert_uses_sdk, new_content, count=1)

        # 2. 将强制要求的 OpenGL ES 3.0 改为兼容模式 2.0 (或 required="false")，防止车机 GPU 不支持 3.0 导致包解析失败
        new_content = re.sub(
            r'<uses-feature\s+android:glEsVersion="0x00030000"\s*/>',
            '<uses-feature android:glEsVersion="0x00020000" android:required="false" />',
            new_content,
        )

        if new_content != content:
            with open(manifest_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Patched uses-sdk (targetSdk=34) and glEsVersion in: {manifest_path}")


def main() -> None:
    if os.environ.get("CAR_COMPAT", "1").lower() in ("0", "false", "no"):
        print("CAR_COMPAT is disabled (0). Skipping car head-unit patches.")
        return

    src_dir = sys.argv[1] if len(sys.argv) > 1 else "."

    # 1. Clean clobbering variables in build/config/android
    clean_clobbering_in_build_config(src_dir)

    # 2. Inject target_sdk_version = 34 unconditionally into chrome_common_apk_or_module_tmpl
    inject_target_sdk_to_chrome_public_tmpl(src_dir)

    # 3. Inject target_sdk_version = 34 into key templates
    key_gni_targets = [
        os.path.join(src_dir, "chrome/android/chrome_public_apk_tmpl.gni"),
        os.path.join(src_dir, "chrome/android/trichrome.gni"),
        os.path.join(src_dir, "android_webview/system_webview_apk_tmpl.gni"),
        os.path.join(src_dir, "vanadium/chromium_src/chrome/android/BUILD.gn"),
    ]

    for gni_file in key_gni_targets:
        patch_target_sdk_in_gni(gni_file)

    # 4. Patch expectations so expectation checking will not fail the build
    expectations_dirs = [
        os.path.join(src_dir, "chrome/android/expectations"),
        os.path.join(src_dir, "android_webview/expectations"),
    ]
    for exp_dir in expectations_dirs:
        if os.path.isdir(exp_dir):
            for root, _, files in os.walk(exp_dir):
                for file_name in files:
                    if file_name.endswith(".expected"):
                        exp_path = os.path.join(root, file_name)
                        with open(exp_path, "r", encoding="utf-8") as f:
                            c = f.read()
                        nc = re.sub(
                            r'android:minSdkVersion="\d+"',
                            'android:minSdkVersion="29"',
                            c,
                        )
                        nc = re.sub(
                            r'android:targetSdkVersion="\d+"',
                            'android:targetSdkVersion="34"',
                            nc,
                        )
                        if nc != c:
                            with open(exp_path, "w", encoding="utf-8") as f:
                                f.write(nc)
                            print(f"Patched AndroidManifest expectations in: {exp_path}")

    # 5. Scan relevant feature directories (EXCLUDING build/config/android)
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
                    patch_target_sdk_in_gni(full_path)
                elif file_name.endswith(".expected") or file_name == "AndroidManifest.xml":
                    patch_file(
                        full_path,
                        [
                            ('android:minSdkVersion="34"', 'android:minSdkVersion="29"'),
                            ('android:targetSdkVersion="37"', 'android:targetSdkVersion="34"'),
                            ('android:targetSdkVersion="36"', 'android:targetSdkVersion="34"'),
                            ('android:targetSdkVersion="35"', 'android:targetSdkVersion="34"'),
                        ],
                    )

    # 6. Manifest adjustments
    patch_manifest_extract_native_libs(src_dir)
    remove_original_package_from_manifest(src_dir)
    patch_manifest_sdk_and_features(src_dir)

    print("SDK version injection (minSdk: 29 / targetSdk: 34) & extractNativeLibs check complete.")


if __name__ == "__main__":
    main()
