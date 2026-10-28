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


def patch_min_sdk_in_gni(file_path: str, target_min_sdk: int = 28) -> bool:
    if not os.path.isfile(file_path):
        return False
    norm_path = file_path.replace("\\", "/")
    if "build/config/android" in norm_path:
        return False

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    new_content = content
    # 替换任意 min_sdk_version / default_min_sdk_version 为 28 (匹配 Android 9 API 28 车机基线)
    new_content = re.sub(r"min_sdk_version\s*=\s*\d+", f"min_sdk_version = {target_min_sdk}", new_content)
    new_content = re.sub(
        r"default_min_sdk_version\s*=\s*\d+", f"default_min_sdk_version = {target_min_sdk}", new_content
    )
    # 清除 target_sdk_version 赋值以防止 GN "Assignment had no effect"
    new_content = re.sub(r"^[ \t]*target_sdk_version\s*=\s*\d+.*$\n?", "", new_content, flags=re.MULTILINE)

    if new_content != content:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Patched minSdk={target_min_sdk} in: {file_path}")
        return True
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
                    # 将期待的 minSdkVersion 降到 28 (Android 9 车机基线)
                    nc = re.sub(
                        r'android:minSdkVersion="\d+"',
                        'android:minSdkVersion="28"',
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
        # 2. 强制禁用 useAppZygote，避免车机 AMS/Zygote 通信死锁
        new_content = re.sub(r'[ \t]*android:useAppZygote="true"', ' android:useAppZygote="false"', new_content)
        # 3. 移除 memtagMode，避免老旧车机 CPU/libc 内存保护错乱
        new_content = re.sub(r'[ \t]*android:memtagMode="[^"]*"', '', new_content)
        # 4. 移除 enableOnBackInvokedCallback
        new_content = re.sub(r'[ \t]*android:enableOnBackInvokedCallback="[^"]*"', '', new_content)
        # 5. 移除 isolatedSplits，确保车机单体应用无需复杂 split 隔离
        new_content = re.sub(r'[ \t]*android:isolatedSplits="true"', '', new_content)

        if new_content != content:
            with open(manifest_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Cleaned zygotePreload and modern attributes to prevent car head-unit hang in: {manifest_path}")


def patch_gl_software_fallback(src_dir: str) -> None:
    gl_features = os.path.join(src_dir, "ui/gl/gl_features.cc")
    if os.path.isfile(gl_features):
        with open(gl_features, "r", encoding="utf-8") as f:
            c = f.read()
        nc = re.sub(
            r'(bool ShouldFallbackToSWIfGLES3NotSupported\(\)\s*\{[\s\S]*?return\s+)false;',
            r'\1true;',
            c
        )
        if nc != c:
            with open(gl_features, "w", encoding="utf-8") as f:
                f.write(nc)
            print(f"Restored GLES3 software fallback (return true) in: {gl_features}")


def patch_startup_field_trials(src_dir: str) -> None:
    field_trials = os.path.join(src_dir, "chrome/browser/chrome_browser_field_trials.cc")
    if os.path.isfile(field_trials):
        with open(field_trials, "r", encoding="utf-8") as f:
            c = f.read()
        nc = re.sub(r'^[ \t]*feature_overrides\.EnableFeature\(chrome::android::kLoadAllTabsAtStartup\);[ \t]*\n?', '', c, flags=re.MULTILINE)
        if nc != c:
            with open(field_trials, "w", encoding="utf-8") as f:
                f.write(nc)
            print(f"Disabled kLoadAllTabsAtStartup for car head-unit stability in: {field_trials}")


def patch_java_car_sdcard_logger(src_dir: str) -> None:
    helper_code = '''
    // [CAR_SDCARD_LOGGER_START]
    private static volatile boolean sCarLoggerInitialized;
    private static void initCarSdcardLogging(android.content.Context context) {
        if (sCarLoggerInitialized || context == null) return;
        sCarLoggerInitialized = true;
        try {
            final java.io.File carLogDir = context.getExternalFilesDir(null);
            if (carLogDir != null) {
                carLogDir.mkdirs();
                java.io.File bootFile = new java.io.File(carLogDir, "helium_boot.log");
                java.io.FileWriter fw = new java.io.FileWriter(bootFile, true);
                fw.write("Helium process started at " + new java.util.Date() + " PID=" + android.os.Process.myPid() + "\\n");
                fw.close();

                final java.lang.Thread.UncaughtExceptionHandler defaultHandler = java.lang.Thread.getDefaultUncaughtExceptionHandler();
                java.lang.Thread.setDefaultUncaughtExceptionHandler(new java.lang.Thread.UncaughtExceptionHandler() {
                    @Override
                    public void uncaughtException(java.lang.Thread t, java.lang.Throwable e) {
                        try {
                            java.io.File crashFile = new java.io.File(carLogDir, "crash_log.txt");
                            java.io.PrintWriter pw = new java.io.PrintWriter(new java.io.FileWriter(crashFile, true));
                            pw.println("=== FATAL CRASH at " + new java.util.Date() + " Thread: " + t.getName() + " ===");
                            e.printStackTrace(pw);
                            pw.flush();
                            pw.close();
                        } catch (Throwable ignored) {}
                        if (defaultHandler != null) {
                            defaultHandler.uncaughtException(t, e);
                        }
                    }
                });

                new java.lang.Thread(new java.lang.Runnable() {
                    @Override
                    public void run() {
                        try {
                            java.io.File logcatFile = new java.io.File(carLogDir, "helium_logcat.log");
                            java.lang.Runtime.getRuntime().exec(new String[]{"logcat", "-f", logcatFile.getAbsolutePath(), "-v", "time"});
                        } catch (Throwable ignored) {}
                    }
                }).start();
            }
        } catch (Throwable ignored) {}
    }
    // [CAR_SDCARD_LOGGER_END]
'''

    # Target 1: SplitChromeApplication.java
    split_app = os.path.join(src_dir, "chrome/android/java/src/org/chromium/chrome/browser/base/SplitChromeApplication.java")
    if os.path.isfile(split_app):
        with open(split_app, "r", encoding="utf-8") as f:
            c = f.read()
        if "initCarSdcardLogging" not in c:
            if "super.attachBaseContext(context);" in c:
                nc = c.replace(
                    "super.attachBaseContext(context);",
                    "super.attachBaseContext(context);\n        initCarSdcardLogging(context);"
                )
                last_brace_idx = nc.rfind("}")
                if last_brace_idx != -1:
                    nc = nc[:last_brace_idx] + helper_code + "\n}\n"
                    with open(split_app, "w", encoding="utf-8") as f:
                        f.write(nc)
                    print(f"Patched SD card crash logger into: {split_app}")

    # Target 2: ChromeTabbedActivity.java (fallback if SplitChromeApplication wasn't loaded)
    cta = os.path.join(src_dir, "chrome/android/java/src/org/chromium/chrome/browser/ChromeTabbedActivity.java")
    if os.path.isfile(cta):
        with open(cta, "r", encoding="utf-8") as f:
            c = f.read()
        if "initCarSdcardLogging" not in c:
            if "super.onCreate(savedInstanceState);" in c:
                nc = c.replace(
                    "super.onCreate(savedInstanceState);",
                    "super.onCreate(savedInstanceState);\n        initCarSdcardLogging(this);"
                )
                last_brace_idx = nc.rfind("}")
                if last_brace_idx != -1:
                    nc = nc[:last_brace_idx] + helper_code + "\n}\n"
                    with open(cta, "w", encoding="utf-8") as f:
                        f.write(nc)
                    print(f"Patched SD card crash logger fallback into: {cta}")


def patch_activity_lifecycle_callbacks_compat(src_dir: str) -> None:
    target_files = [
        os.path.join(src_dir, "chrome/android/java/src/org/chromium/chrome/browser/ChromeBaseAppCompatActivity.java"),
        os.path.join(src_dir, "chrome/android/java/src/org/chromium/chrome/browser/init/ChromeBaseAppCompatActivity.java"),
        os.path.join(src_dir, "chrome/android/java/src/org/chromium/chrome/browser/ChromeTabbedActivity.java"),
    ]
    helper_code = '''
    // [CAR_ANDROID9_LIFECYCLE_COMPAT_START]
    @Override
    public void registerActivityLifecycleCallbacks(android.app.Application.ActivityLifecycleCallbacks callbacks) {
        if (android.os.Build.VERSION.SDK_INT >= 29) {
            super.registerActivityLifecycleCallbacks(callbacks);
        }
    }

    @Override
    public void unregisterActivityLifecycleCallbacks(android.app.Application.ActivityLifecycleCallbacks callbacks) {
        if (android.os.Build.VERSION.SDK_INT >= 29) {
            super.unregisterActivityLifecycleCallbacks(callbacks);
        }
    }
    // [CAR_ANDROID9_LIFECYCLE_COMPAT_END]
'''
    for target in target_files:
        if not os.path.isfile(target):
            continue
        with open(target, "r", encoding="utf-8") as f:
            c = f.read()
        if "CAR_ANDROID9_LIFECYCLE_COMPAT_START" in c or "registerActivityLifecycleCallbacks(android.app.Application" in c:
            continue
        last_brace = c.rfind("}")
        if last_brace != -1:
            nc = c[:last_brace] + helper_code + "\n}\n"
            with open(target, "w", encoding="utf-8") as f:
                f.write(nc)
            print(f"Patched ActivityLifecycleCallbacks compat into: {target}")


def patch_content_app_aidl_deps(src_dir: str) -> None:
    candidate_paths = [
        os.path.join(src_dir, "content/app/BUILD.gn"),
        os.path.join(src_dir, "chromium/src/content/app/BUILD.gn"),
        os.path.join(src_dir, "src/content/app/BUILD.gn"),
    ]
    for build_gn in candidate_paths:
        if not os.path.isfile(build_gn):
            continue
        with open(build_gn, "r", encoding="utf-8") as f:
            content = f.read()

        new_content = content

        # 1. 确保在 is_android 条件下引入 build/config/android/config.gni (获取 android_ndk_api_level)
        if "build/config/android/config.gni" not in new_content:
            import_marker = 'import("//third_party/tflite/features.gni")\n'
            if import_marker in new_content:
                new_content = new_content.replace(
                    import_marker,
                    import_marker + 'if (is_android) {\n  import("//build/config/android/config.gni")\n}\n',
                )
            else:
                new_content = re.sub(
                    r'(import\(.*?\)\n)',
                    r'\1if (is_android) {\n  import("//build/config/android/config.gni")\n}\n',
                    new_content,
                    count=1,
                )

        # 2. 将仅在 API 29+ NDK 支持的 javaless_child_process_service.cc 与 AIDL native 依赖收敛到 android_ndk_api_level >= 29 判定块内
        if "android_ndk_api_level >= 29" not in new_content:
            # 清除 unguarded 的源码与依赖声明
            new_content = re.sub(r'[ \t]*"android/javaless_child_process_service\.cc",?\n?', '', new_content)
            new_content = re.sub(r'[ \t]*"//base:build_info_aidl_native",?\n?', '', new_content)
            new_content = re.sub(r'[ \t]*"//base:process_launcher_aidl_native",?\n?', '', new_content)

            guard_block = (
                '    if (android_ndk_api_level >= 29) {\n'
                '      sources += [ "android/javaless_child_process_service.cc" ]\n'
                '      deps += [\n'
                '        "//base:build_info_aidl_native",\n'
                '        "//base:process_launcher_aidl_native",\n'
                '      ]\n'
                '    }\n'
            )

            target_pattern = r'([ \t]*"android/library_loader_hooks\.h",\s*\])'
            if re.search(target_pattern, new_content):
                new_content = re.sub(target_pattern, r'\1\n' + guard_block, new_content, count=1)
            else:
                deps_pattern = r'(\s*deps\s*\+=\s*\[\s*"//content/common")'
                if re.search(deps_pattern, new_content):
                    new_content = re.sub(deps_pattern, '\n' + guard_block + r'\1', new_content, count=1)

        if new_content != content:
            with open(build_gn, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Patched content/app/BUILD.gn: guarded AIDL native deps and javaless service for API < 29 in: {build_gn}")


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

    # 5. 扫描相关目录，确保 min_sdk_version 降为 28，并清除 target_sdk_version
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
                    patch_min_sdk_in_gni(full_path, target_min_sdk=28)
                elif "AndroidManifest" in file_name and file_name.endswith(".xml"):
                    with open(full_path, "r", encoding="utf-8") as f:
                        c = f.read()
                    nc = re.sub(r'android:minSdkVersion="\d+"', 'android:minSdkVersion="28"', c)
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
    patch_gl_software_fallback(src_dir)
    patch_startup_field_trials(src_dir)
    patch_java_car_sdcard_logger(src_dir)
    patch_activity_lifecycle_callbacks_compat(src_dir)
    patch_content_app_aidl_deps(src_dir)

    print("SDK version patch (minSdk: 28) & car-compat checks complete.")


if __name__ == "__main__":
    main()
