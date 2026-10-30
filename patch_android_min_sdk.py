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


def patch_ahardwarebuffer_image_backing_factory(src_dir: str) -> None:
    candidate_paths = [
        os.path.join(src_dir, "gpu/command_buffer/service/shared_image/ahardwarebuffer_image_backing_factory.cc"),
        os.path.join(src_dir, "chromium/src/gpu/command_buffer/service/shared_image/ahardwarebuffer_image_backing_factory.cc"),
        os.path.join(src_dir, "src/gpu/command_buffer/service/shared_image/ahardwarebuffer_image_backing_factory.cc"),
    ]
    for target in candidate_paths:
        if not os.path.isfile(target):
            continue
        with open(target, "r", encoding="utf-8") as f:
            content = f.read()

        new_content = content
        if "<dlfcn.h>" not in new_content:
            new_content = new_content.replace(
                "#include <android/hardware_buffer.h>\n",
                "#include <android/hardware_buffer.h>\n#include <dlfcn.h>\n",
                1,
            )

        # 动态解析 AHardwareBuffer_lockPlanes，避免直接调用引入 API 29+ 符号导致 -Wunguarded-availability
        # 且规避 Android 9 系统 libandroid.so 缺少该符号引发的 dlopen 崩溃
        if "AHardwareBuffer_lockPlanes" in new_content and "pfn_lock_planes" not in new_content:
            old_call = (
                "  int ret = AHardwareBuffer_lockPlanes(hardware_buffer, cpu_read_usage, fence,\n"
                "                                       nullptr, &planes);"
            )
            new_call = (
                "  using PFN_AHardwareBuffer_lockPlanes =\n"
                "      int (*)(AHardwareBuffer*, uint64_t, int32_t, const ARect*,\n"
                "              AHardwareBuffer_Planes*);\n"
                "  static auto pfn_lock_planes = reinterpret_cast<PFN_AHardwareBuffer_lockPlanes>(\n"
                "      dlsym(RTLD_DEFAULT, \"AHardwareBuffer_lockPlanes\"));\n"
                "  if (!pfn_lock_planes) {\n"
                "    return false;\n"
                "  }\n"
                "  int ret = pfn_lock_planes(hardware_buffer, cpu_read_usage, fence, nullptr,\n"
                "                            &planes);"
            )
            if old_call in new_content:
                new_content = new_content.replace(old_call, new_call, 1)
            else:
                new_content = re.sub(
                    r'[ \t]*int\s+ret\s*=\s*AHardwareBuffer_lockPlanes\s*\([^;]+;\s*',
                    new_call + '\n',
                    new_content,
                    count=1,
                )

        if new_content != content:
            with open(target, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Patched AHardwareBuffer_lockPlanes dynamic lookup in: {target}")


def patch_base_hardware_buffer_sources(src_dir: str) -> None:
    candidate_paths = [
        os.path.join(src_dir, "base/BUILD.gn"),
        os.path.join(src_dir, "chromium/src/base/BUILD.gn"),
        os.path.join(src_dir, "src/base/BUILD.gn"),
    ]
    for build_gn in candidate_paths:
        if not os.path.isfile(build_gn):
            continue
        with open(build_gn, "r", encoding="utf-8") as f:
            content = f.read()

        new_content = content
        pattern = (
            r'([ \t]*if\s*\(\s*android_ndk_api_level\s*>=\s*29\s*\)\s*\{[\s\S]*?'
            r'deps\s*\+=\s*\[\s*":build_info_aidl_native"\s*\])\s*\n'
            r'([ \t]*sources\s*\+=\s*\[[\s\S]*?"android/scoped_hardware_buffer_handle\.h",\s*\]\s*\})'
        )
        if re.search(pattern, new_content):
            new_content = re.sub(
                pattern,
                r'\1\n    }\n    if (android_ndk_api_level >= 26) {\n\2',
                new_content,
                count=1,
            )

        if new_content != content:
            with open(build_gn, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Patched base/BUILD.gn: enabled AHardwareBuffer sources for API >= 26 in: {build_gn}")


def patch_ndk_video_encode_accelerator(src_dir: str) -> None:
    candidate_paths = [
        os.path.join(src_dir, "media/gpu/android/ndk_video_encode_accelerator.cc"),
        os.path.join(src_dir, "chromium/src/media/gpu/android/ndk_video_encode_accelerator.cc"),
        os.path.join(src_dir, "src/media/gpu/android/ndk_video_encode_accelerator.cc"),
    ]
    for target in candidate_paths:
        if not os.path.isfile(target):
            continue
        with open(target, "r", encoding="utf-8") as f:
            content = f.read()

        new_content = content

        # 1. 在文件开头抑制 -Wunguarded-availability（防止模板实例化中触发错误）
        diag_suppress = (
            "#pragma clang diagnostic push\n"
            "#pragma clang diagnostic ignored \"-Wunguarded-availability\"\n"
        )
        if "-Wunguarded-availability" not in new_content:
            new_content = diag_suppress + new_content + "\n#pragma clang diagnostic pop\n"

        # 2. 移除 DEFAULT_REQUIRES_ANDROID_API pragma，避免 lambda 闭包被标记 API 29
        # 进而导致 Perfetto TRACE_EVENT 展开时 CallIfEnabled 调用 lambda 触发 -Wunguarded-availability
        pragma_push_pattern = r"#pragma\s+clang\s+attribute\s+push\s+DEFAULT_REQUIRES_ANDROID_API\s*\([\s\\\S]*?NDK_MEDIA_CODEC_MIN_API\s*\)\s*"
        if re.search(pragma_push_pattern, new_content):
            new_content = re.sub(
                pragma_push_pattern,
                "// [CAR-COMPAT] Disabled DEFAULT_REQUIRES_ANDROID_API to avoid attributing Perfetto TRACE_EVENT lambdas with API 29\n",
                new_content,
                count=1,
            )

        pragma_pop_pattern = r"#pragma\s+clang\s+attribute\s+pop\s*"
        if re.search(pragma_pop_pattern, new_content):
            new_content = re.sub(
                pragma_pop_pattern,
                "// [CAR-COMPAT] Pop disabled\n",
                new_content,
                count=1,
            )

        # 3. 动态解析 AHardwareBuffer_lockPlanes，避免直接调用引入 API 29+ 符号导致 -Wunguarded-availability
        # 且规避 Android 9 系统 libandroid.so 缺少该符号引发的运行时崩溃
        if "<dlfcn.h>" not in new_content:
            new_content = new_content.replace(
                "#include <android/hardware_buffer.h>\n",
                "#include <android/hardware_buffer.h>\n#include <dlfcn.h>\n",
                1,
            )

        if "AHardwareBuffer_lockPlanes" in new_content and "pfn_lock_planes" not in new_content:
            old_lock = (
                "      AHardwareBuffer_Planes planes;\n"
                "      int32_t status = AHardwareBuffer_lockPlanes(\n"
                "          ahb, AHARDWAREBUFFER_USAGE_CPU_READ_OFTEN, -1, nullptr, &planes);"
            )
            new_lock = (
                "      AHardwareBuffer_Planes planes;\n"
                "      using PFN_AHardwareBuffer_lockPlanes =\n"
                "          int32_t (*)(AHardwareBuffer*, uint64_t, int32_t, const ARect*,\n"
                "                      AHardwareBuffer_Planes*);\n"
                "      static auto pfn_lock_planes =\n"
                "          reinterpret_cast<PFN_AHardwareBuffer_lockPlanes>(\n"
                "              dlsym(RTLD_DEFAULT, \"AHardwareBuffer_lockPlanes\"));\n"
                "      if (!pfn_lock_planes) {\n"
                "        NotifyErrorStatus({EncoderStatus::Codes::kSystemAPICallError,\n"
                "                           \"AHardwareBuffer_lockPlanes not available on this API level\"});\n"
                "        return nullptr;\n"
                "      }\n"
                "      int32_t status = pfn_lock_planes(\n"
                "          ahb, AHARDWAREBUFFER_USAGE_CPU_READ_OFTEN, -1, nullptr, &planes);"
            )
            if old_lock in new_content:
                new_content = new_content.replace(old_lock, new_lock, 1)
            else:
                new_content = re.sub(
                    r'[ \t]*int32_t\s+status\s*=\s*AHardwareBuffer_lockPlanes\s*\([^;]+;\s*',
                    new_lock + '\n',
                    new_content,
                    count=1,
                )

        if new_content != content:
            with open(target, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Patched ndk_video_encode_accelerator.cc in: {target}")


def patch_gpu_video_encode_accelerator_factory(src_dir: str) -> None:
    candidate_paths = [
        os.path.join(src_dir, "media/gpu/gpu_video_encode_accelerator_factory.cc"),
        os.path.join(src_dir, "chromium/src/media/gpu/gpu_video_encode_accelerator_factory.cc"),
        os.path.join(src_dir, "src/media/gpu/gpu_video_encode_accelerator_factory.cc"),
    ]
    for target in candidate_paths:
        if not os.path.isfile(target):
            continue
        with open(target, "r", encoding="utf-8") as f:
            content = f.read()

        new_content = content
        old_fn = (
            "std::unique_ptr<VideoEncodeAccelerator> CreateAndroidVEA(\n"
            "    const gpu::GpuDriverBugWorkarounds& gpu_workarounds) {\n"
            "  return base::WrapUnique<VideoEncodeAccelerator>(new NdkVideoEncodeAccelerator(\n"
            "      base::SequencedTaskRunner::GetCurrentDefault(), gpu_workarounds));\n"
            "}"
        )
        new_fn = (
            "std::unique_ptr<VideoEncodeAccelerator> CreateAndroidVEA(\n"
            "    const gpu::GpuDriverBugWorkarounds& gpu_workarounds) {\n"
            "  if (__builtin_available(android 29, *)) {\n"
            "    return base::WrapUnique<VideoEncodeAccelerator>(new NdkVideoEncodeAccelerator(\n"
            "        base::SequencedTaskRunner::GetCurrentDefault(), gpu_workarounds));\n"
            "  }\n"
            "  return nullptr;\n"
            "}"
        )
        if old_fn in new_content:
            new_content = new_content.replace(old_fn, new_fn, 1)
        elif "__builtin_available(android 29, *)" not in new_content and "CreateAndroidVEA" in new_content:
            new_content = re.sub(
                r'(std::unique_ptr<VideoEncodeAccelerator>\s+CreateAndroidVEA\s*\([^)]*\)\s*\{)([\s\S]*?return\s+base::WrapUnique[^\;]+;\s*\})',
                r'\1\n  if (__builtin_available(android 29, *)) {\2\n  }\n  return nullptr;\n}',
                new_content,
                count=1,
            )

        if new_content != content:
            with open(target, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Patched gpu_video_encode_accelerator_factory.cc in: {target}")


def patch_ndk_audio_encoder(src_dir: str) -> None:
    candidate_paths = [
        os.path.join(src_dir, "media/gpu/android/ndk_audio_encoder.cc"),
        os.path.join(src_dir, "chromium/src/media/gpu/android/ndk_audio_encoder.cc"),
        os.path.join(src_dir, "src/media/gpu/android/ndk_audio_encoder.cc"),
    ]
    for target in candidate_paths:
        if not os.path.isfile(target):
            continue
        with open(target, "r", encoding="utf-8") as f:
            content = f.read()

        new_content = content
        diag_suppress = (
            "#pragma clang diagnostic push\n"
            "#pragma clang diagnostic ignored \"-Wunguarded-availability\"\n"
        )
        if "-Wunguarded-availability" not in new_content:
            new_content = diag_suppress + new_content + "\n#pragma clang diagnostic pop\n"

        pragma_push_pattern = r"#pragma\s+clang\s+attribute\s+push\s+DEFAULT_REQUIRES_ANDROID_API\s*\([\s\\\S]*?NDK_MEDIA_CODEC_MIN_API\s*\)\s*"
        if re.search(pragma_push_pattern, new_content):
            new_content = re.sub(
                pragma_push_pattern,
                "// [CAR-COMPAT] Disabled DEFAULT_REQUIRES_ANDROID_API for Android 9 baseline\n",
                new_content,
                count=1,
            )

        pragma_pop_pattern = r"#pragma\s+clang\s+attribute\s+pop\s*"
        if re.search(pragma_pop_pattern, new_content):
            new_content = re.sub(
                pragma_pop_pattern,
                "// [CAR-COMPAT] Pop disabled\n",
                new_content,
                count=1,
            )

        if new_content != content:
            with open(target, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Patched ndk_audio_encoder.cc in: {target}")


def patch_strict_mode_credential_protected(src_dir: str) -> None:
    # 扫描并修补所有包含 API 29+ StrictMode 调用的 Java 文件
    # Android 9 (API 28) 缺少 detectCredentialProtectedWhileLocked 与 detectImplicitDirectBoot 方法，
    # 在 Android 9 车机设备上直接调用会引发 java.lang.NoSuchMethodError 致命崩溃。
    target_files = [
        os.path.join(src_dir, "chrome/android/java/src/org/chromium/chrome/browser/ChromeStrictMode.java"),
        os.path.join(src_dir, "chromium/src/chrome/android/java/src/org/chromium/chrome/browser/ChromeStrictMode.java"),
        os.path.join(src_dir, "src/chrome/android/java/src/org/chromium/chrome/browser/ChromeStrictMode.java"),
    ]
    for sub in ["chrome/android", "base/android"]:
        scan_path = os.path.join(src_dir, sub)
        if os.path.isdir(scan_path):
            for root, _, files in os.walk(scan_path):
                for f in files:
                    if f.endswith(".java"):
                        full_f = os.path.join(root, f)
                        if full_f not in target_files:
                            try:
                                with open(full_f, "r", encoding="utf-8") as jf:
                                    snippet = jf.read()
                                if (
                                    "detectCredentialProtectedWhileLocked" in snippet
                                    or "detectImplicitDirectBoot" in snippet
                                ):
                                    target_files.append(full_f)
                            except Exception:
                                pass

    for target in target_files:
        if not os.path.isfile(target):
            continue
        with open(target, "r", encoding="utf-8") as f:
            content = f.read()

        if "detectCredentialProtectedWhileLocked" not in content and "detectImplicitDirectBoot" not in content:
            continue

        if "android.os.Build.VERSION.SDK_INT >= 29" in content:
            continue

        new_content = content
        # Case 1: chained call vmPolicy.detectCredentialProtectedWhileLocked().detectImplicitDirectBoot();
        if "detectCredentialProtectedWhileLocked" in new_content and "detectImplicitDirectBoot" in new_content:
            new_content = re.sub(
                r'([ \t]*)(\w+)\.detectCredentialProtectedWhileLocked\(\)\s*\.\s*detectImplicitDirectBoot\(\);',
                r'\1if (android.os.Build.VERSION.SDK_INT >= 29) {\n\1    try {\n\1        \2.detectCredentialProtectedWhileLocked().detectImplicitDirectBoot();\n\1    } catch (Throwable ignored) {}\n\1}',
                new_content,
            )

        # Case 2: detectCredentialProtectedWhileLocked() standalone
        if "detectCredentialProtectedWhileLocked()" in new_content and "android.os.Build.VERSION.SDK_INT >= 29" not in new_content:
            new_content = re.sub(
                r'([ \t]*)(\w+)\.detectCredentialProtectedWhileLocked\(\);',
                r'\1if (android.os.Build.VERSION.SDK_INT >= 29) {\n\1    try {\n\1        \2.detectCredentialProtectedWhileLocked();\n\1    } catch (Throwable ignored) {}\n\1}',
                new_content,
            )

        # Case 3: detectImplicitDirectBoot() standalone
        if "detectImplicitDirectBoot()" in new_content and "android.os.Build.VERSION.SDK_INT >= 29" not in new_content:
            new_content = re.sub(
                r'([ \t]*)(\w+)\.detectImplicitDirectBoot\(\);',
                r'\1if (android.os.Build.VERSION.SDK_INT >= 29) {\n\1    try {\n\1        \2.detectImplicitDirectBoot();\n\1    } catch (Throwable ignored) {}\n\1}',
                new_content,
            )

        if new_content != content:
            with open(target, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Patched StrictMode API 29+ methods with SDK guard in: {target}")


def patch_url_bar_cursor_handles_compat(src_dir: str) -> None:
    # Android 9 (API 28) 缺少 TextView/EditText 的 getTextCursorDrawable 与 getTextSelectHandle* API 29+ 方法。
    # 在 Android 9 车机设备上直接调用会引发：
    # java.lang.NoSuchMethodError: No virtual method getTextCursorDrawable()Landroid/graphics/drawable/Drawable; in class Landroid/widget/EditText;
    # 导致应用启动/创建 Omnibox 阶段直接闪退。
    target_files = [
        os.path.join(src_dir, "chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/UrlBarViewBinder.java"),
        os.path.join(src_dir, "chromium/src/chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/UrlBarViewBinder.java"),
        os.path.join(src_dir, "src/chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/UrlBarViewBinder.java"),
    ]
    for sub in ["chrome/browser/ui/android", "chrome/android", "chrome"]:
        scan_path = os.path.join(src_dir, sub)
        if os.path.isdir(scan_path):
            for root, _, files in os.walk(scan_path):
                for f in files:
                    if f.endswith(".java"):
                        full_f = os.path.join(root, f)
                        if full_f not in target_files:
                            try:
                                with open(full_f, "r", encoding="utf-8") as jf:
                                    snippet = jf.read()
                                if "getTextCursorDrawable" in snippet or "updateCursorAndSelectHandleColor" in snippet:
                                    target_files.append(full_f)
                            except Exception:
                                pass

    for target in target_files:
        if not os.path.isfile(target):
            continue
        with open(target, "r", encoding="utf-8") as f:
            content = f.read()

        if "getTextCursorDrawable" not in content and "updateCursorAndSelectHandleColor" not in content:
            continue

        new_content = content

        # 1. 守卫 bind() 中对 updateCursorAndSelectHandleColor 的无条件调用
        if "Build.VERSION_CODES.Q" not in new_content and "Build.VERSION.SDK_INT >= 29" not in new_content:
            new_content = re.sub(
                r'([ \t]*)updateCursorAndSelectHandleColor\(([^)]+)\);',
                r'\1if (android.os.Build.VERSION.SDK_INT >= 29) {\n\1    updateCursorAndSelectHandleColor(\2);\n\1}',
                new_content,
            )

        # 2. 方法体内增加 API 28 快速返回，防止反射或异常触发执行
        if "android.os.Build.VERSION.SDK_INT < 29" not in new_content:
            new_content = re.sub(
                r'((?:private|protected|public)?\s*static\s+void\s+updateCursorAndSelectHandleColor\s*\([^)]*\)\s*\{)',
                r'\1\n        if (android.os.Build.VERSION.SDK_INT < 29) {\n            return;\n        }',
                new_content,
            )

        # 3. 针对 getTextCursorDrawable / getTextSelectHandle* 的调用增加 try-catch 保护，规避魔改车机固件异常
        drawables_pattern = (
            r"([ \t]*)final\s+Drawable\s+textCursor\s*=\s*view\.getTextCursorDrawable\(\);\s*\n"
            r"[ \t]*final\s+Drawable\s+textSelectHandle\s*=\s*view\.getTextSelectHandle\(\);\s*\n"
            r"[ \t]*final\s+Drawable\s+textSelectHandleLeft\s*=\s*view\.getTextSelectHandleLeft\(\);\s*\n"
            r"[ \t]*final\s+Drawable\s+textSelectHandleRight\s*=\s*view\.getTextSelectHandleRight\(\);"
        )

        def replace_drawables(m):
            indent = m.group(1)
            return (
                f"{indent}Drawable textCursor = null;\n"
                f"{indent}Drawable textSelectHandle = null;\n"
                f"{indent}Drawable textSelectHandleLeft = null;\n"
                f"{indent}Drawable textSelectHandleRight = null;\n"
                f"{indent}try {{\n"
                f"{indent}    textCursor = view.getTextCursorDrawable();\n"
                f"{indent}    textSelectHandle = view.getTextSelectHandle();\n"
                f"{indent}    textSelectHandleLeft = view.getTextSelectHandleLeft();\n"
                f"{indent}    textSelectHandleRight = view.getTextSelectHandleRight();\n"
                f"{indent}}} catch (Throwable ignored) {{\n"
                f"{indent}    return;\n"
                f"{indent}}}"
            )

        if "catch (Throwable ignored)" not in new_content:
            new_content = re.sub(drawables_pattern, replace_drawables, new_content)

        if new_content != content:
            with open(target, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Patched UrlBar cursor/select handle drawables for API 28 compat in: {target}")


def patch_url_bar_multiline_scroll_compat(src_dir: str) -> None:
    # Android 9 (API 28) 缺少 TextView.isHorizontallyScrollable() API 29+ 方法。
    # 在 UrlBar.java 中 updateUrlBarForMultilineInput() 调用了 isHorizontallyScrollable()，
    # 在 Android 9 车机设备上直接引发 NoSuchMethodError 导致 Omnibox 初始化/输入时崩溃。
    target_files = [
        os.path.join(src_dir, "chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/UrlBar.java"),
        os.path.join(src_dir, "chromium/src/chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/UrlBar.java"),
        os.path.join(src_dir, "src/chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/UrlBar.java"),
    ]
    for sub in ["chrome/browser/ui/android", "chrome/android", "chrome"]:
        scan_path = os.path.join(src_dir, sub)
        if os.path.isdir(scan_path):
            for root, _, files in os.walk(scan_path):
                for f in files:
                    if f == "UrlBar.java" or (f.endswith(".java") and "UrlBar" in f):
                        full_f = os.path.join(root, f)
                        if full_f not in target_files:
                            try:
                                with open(full_f, "r", encoding="utf-8", errors="ignore") as jf:
                                    snippet = jf.read()
                                if "isHorizontallyScrollable" in snippet:
                                    target_files.append(full_f)
                            except Exception:
                                pass

    for target in target_files:
        if not os.path.isfile(target):
            continue
        with open(target, "r", encoding="utf-8") as f:
            content = f.read()

        if "isHorizontallyScrollable" not in content:
            continue

        new_content = content

        # Check if isHorizontallyScrollable() is already guarded by SDK check
        if re.search(r'SDK_INT\s*>=\s*29[\s\S]{1,100}isHorizontallyScrollable\(\)', new_content):
            continue

        # 守卫 updateUrlBarForMultilineInput 中对 isHorizontallyScrollable() 的无条件调用
        new_content = re.sub(
            r'([ \t]*)if\s*\(\s*wantWrap\s*==\s*!isHorizontallyScrollable\(\)\s*\)\s*(?:return;|\{\s*return;\s*\})',
            r'\1if (android.os.Build.VERSION.SDK_INT >= 29) {\n\1    try {\n\1        if (wantWrap == !isHorizontallyScrollable()) return;\n\1    } catch (Throwable ignored) {}\n\1}',
            new_content,
        )

        if new_content != content:
            with open(target, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Patched UrlBar multiline scroll for API 28 compat in: {target}")


def patch_gesture_exclusion_rects_compat(src_dir: str) -> None:
    # Android 9 (API 28) 缺少 View.setSystemGestureExclusionRects(List<Rect>) API 29+ 方法。
    # ToolbarControlContainer 重写了该方法并在 updateSystemGestureExclusions() 等处无条件调用
    # super.setSystemGestureExclusionRects(...)，在 Android 9 车机设备上直接引发：
    # java.lang.NoSuchMethodError: No super method setSystemGestureExclusionRects(Ljava/util/List;)V in class Landroid/widget/FrameLayout;
    # 导致启动进入 ChromeTabbedActivity 时致命闪退。
    target_files = [
        os.path.join(src_dir, "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/top/ToolbarControlContainer.java"),
        os.path.join(src_dir, "chromium/src/chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/top/ToolbarControlContainer.java"),
        os.path.join(src_dir, "src/chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/top/ToolbarControlContainer.java"),
    ]

    for sub in ["chrome/browser/ui/android", "chrome/android", "chrome", "components"]:
        scan_path = os.path.join(src_dir, sub)
        if os.path.isdir(scan_path):
            for root, _, files in os.walk(scan_path):
                for f in files:
                    if f == "ToolbarControlContainer.java":
                        target_files.append(os.path.join(root, f))
                    elif f.endswith(".java"):
                        try:
                            fp = os.path.join(root, f)
                            with open(fp, "r", encoding="utf-8", errors="ignore") as jf:
                                c = jf.read()
                                if "setSystemGestureExclusionRects" in c or "updateSystemGestureExclusions" in c:
                                    target_files.append(fp)
                        except Exception:
                            pass

    seen = set()
    for target in target_files:
        if not os.path.isfile(target):
            continue
        real_path = os.path.realpath(target)
        if real_path in seen:
            continue
        seen.add(real_path)

        with open(target, "r", encoding="utf-8") as f:
            content = f.read()

        if "setSystemGestureExclusionRects" not in content and "updateSystemGestureExclusions" not in content:
            continue

        new_content = content

        # 1. 在 updateSystemGestureExclusions() 方法体入口加入 API 28 快速返回
        if "updateSystemGestureExclusions" in new_content:
            if not re.search(r"updateSystemGestureExclusions\s*\([^)]*\)\s*\{[^}]*SDK_INT", new_content):
                new_content = re.sub(
                    r"((?:private|protected|public)?\s*void\s+updateSystemGestureExclusions\s*\([^)]*\)\s*\{)",
                    r"\1\n        if (android.os.Build.VERSION.SDK_INT < 29) {\n            return;\n        }",
                    new_content,
                )

        # 2. 在 setSystemGestureExclusionRects(...) 方法体入口加入 API 28 快速返回
        if "setSystemGestureExclusionRects" in new_content:
            if not re.search(r"public\s+void\s+setSystemGestureExclusionRects\s*\([^)]*\)\s*\{[^}]*SDK_INT", new_content):
                new_content = re.sub(
                    r"((?:@Override\s*\n\s*)?public\s+void\s+setSystemGestureExclusionRects\s*\([^)]*\)\s*\{)",
                    r"\1\n        if (android.os.Build.VERSION.SDK_INT < 29) {\n            return;\n        }",
                    new_content,
                )

        # 3. 逐行扫描守卫 super.setSystemGestureExclusionRects 和外部调用
        lines = new_content.split("\n")
        patched_lines = []
        i = 0
        while i < len(lines):
            line = lines[i]
            # 守卫 super.setSystemGestureExclusionRects(...)
            if "super.setSystemGestureExclusionRects" in line:
                has_guard = False
                for k in range(max(0, i - 4), i):
                    if any(kw in lines[k] for kw in ("SDK_INT >= 29", "VERSION_CODES.Q", "SDK_INT < 29")):
                        has_guard = True
                        break
                if not has_guard:
                    m = re.match(r"^(\s*)super\.setSystemGestureExclusionRects\((.*)\);", line)
                    if m:
                        indent = m.group(1)
                        arg = m.group(2)
                        patched_lines.append(f"{indent}if (android.os.Build.VERSION.SDK_INT >= 29) {{")
                        patched_lines.append(f"{indent}    super.setSystemGestureExclusionRects({arg});")
                        patched_lines.append(f"{indent}}}")
                        i += 1
                        continue
            # 守卫外部调用 target.setSystemGestureExclusionRects(...)
            elif ".setSystemGestureExclusionRects(" in line:
                has_guard = False
                for k in range(max(0, i - 4), i):
                    if any(kw in lines[k] for kw in ("SDK_INT >= 29", "VERSION_CODES.Q", "SDK_INT < 29")):
                        has_guard = True
                        break
                if not has_guard:
                    m = re.match(r"^(\s*)([a-zA-Z0-9_$.]+)\.setSystemGestureExclusionRects\((.*)\);", line)
                    if m and m.group(2) != "super":
                        indent = m.group(1)
                        obj = m.group(2)
                        arg = m.group(3)
                        patched_lines.append(f"{indent}if (android.os.Build.VERSION.SDK_INT >= 29) {{")
                        patched_lines.append(f"{indent}    {obj}.setSystemGestureExclusionRects({arg});")
                        patched_lines.append(f"{indent}}}")
                        i += 1
                        continue
            patched_lines.append(line)
            i += 1

        new_content = "\n".join(patched_lines)

        if new_content != content:
            with open(target, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Patched View.setSystemGestureExclusionRects for API 28 compat in: {target}")


def patch_system_bar_contrast_enforced_compat(src_dir: str) -> None:
    # Android 9 (API 28) 缺少 Window.setNavigationBarContrastEnforced(boolean) 与
    # Window.setStatusBarContrastEnforced(boolean) API 29+ 方法。
    # EdgeToEdgeSystemBarColorHelper 与 WindowSystemBarColorHelper 无条件调用该方法，
    # 在 Android 9 车机设备上直接引发：
    # java.lang.NoSuchMethodError: No virtual method setNavigationBarContrastEnforced(Z)V in class Landroid/view/Window;
    # 导致应用启动进入 ChromeTabbedActivity.onCreate 时致命闪退。
    target_files = [
        os.path.join(src_dir, "ui/edge_to_edge/android/java/src/org/chromium/ui/edge_to_edge/WindowSystemBarColorHelper.java"),
        os.path.join(src_dir, "chromium/src/ui/edge_to_edge/android/java/src/org/chromium/ui/edge_to_edge/WindowSystemBarColorHelper.java"),
        os.path.join(src_dir, "src/ui/edge_to_edge/android/java/src/org/chromium/ui/edge_to_edge/WindowSystemBarColorHelper.java"),
        os.path.join(src_dir, "ui/edge_to_edge/android/java/src/org/chromium/ui/edge_to_edge/EdgeToEdgeSystemBarColorHelper.java"),
        os.path.join(src_dir, "chromium/src/ui/edge_to_edge/android/java/src/org/chromium/ui/edge_to_edge/EdgeToEdgeSystemBarColorHelper.java"),
        os.path.join(src_dir, "src/ui/edge_to_edge/android/java/src/org/chromium/ui/edge_to_edge/EdgeToEdgeSystemBarColorHelper.java"),
    ]

    for sub in ["ui", "chrome", "components", "android_webview"]:
        scan_path = os.path.join(src_dir, sub)
        if os.path.isdir(scan_path):
            for root, _, files in os.walk(scan_path):
                for f in files:
                    if f.endswith(".java"):
                        try:
                            fp = os.path.join(root, f)
                            with open(fp, "r", encoding="utf-8", errors="ignore") as jf:
                                c = jf.read()
                                if "setNavigationBarContrastEnforced" in c or "setStatusBarContrastEnforced" in c:
                                    target_files.append(fp)
                        except Exception:
                            pass

    seen = set()
    for target in target_files:
        if not os.path.isfile(target):
            continue
        real_path = os.path.realpath(target)
        if real_path in seen:
            continue
        seen.add(real_path)

        with open(target, "r", encoding="utf-8") as f:
            content = f.read()

        if "setNavigationBarContrastEnforced" not in content and "setStatusBarContrastEnforced" not in content:
            continue

        new_content = content

        # 1. 在 WindowSystemBarColorHelper 等直接操作 mWindow 的方法定义中加入 API 28 快速返回
        if "setNavigationBarContrastEnforced" in new_content:
            if not re.search(r"void\s+setNavigationBarContrastEnforced\s*\([^)]*\)\s*\{[^}]*SDK_INT", new_content):
                new_content = re.sub(
                    r"((?:@Override\s*\n\s*)?(?:public|protected|private)?\s*void\s+setNavigationBarContrastEnforced\s*\([^)]*\)\s*\{)",
                    r"\1\n        if (android.os.Build.VERSION.SDK_INT < 29) {\n            return;\n        }",
                    new_content,
                )

        if "setStatusBarContrastEnforced" in new_content:
            if not re.search(r"void\s+setStatusBarContrastEnforced\s*\([^)]*\)\s*\{[^}]*SDK_INT", new_content):
                new_content = re.sub(
                    r"((?:@Override\s*\n\s*)?(?:public|protected|private)?\s*void\s+setStatusBarContrastEnforced\s*\([^)]*\)\s*\{)",
                    r"\1\n        if (android.os.Build.VERSION.SDK_INT < 29) {\n            return;\n        }",
                    new_content,
                )

        # 2. 守卫 mWindow.set*ContrastEnforced 直接调用（针对 WindowSystemBarColorHelper）
        new_content = re.sub(
            r'([ \t]*)mWindow\.setNavigationBarContrastEnforced\s*\(\s*(\w+)\s*\)\s*;',
            r'\1if (android.os.Build.VERSION.SDK_INT >= 29) {\n\1    try {\n\1        mWindow.setNavigationBarContrastEnforced(\2);\n\1    } catch (Throwable ignored) {}\n\1}',
            new_content
        )
        new_content = re.sub(
            r'([ \t]*)mWindow\.setStatusBarContrastEnforced\s*\(\s*(\w+)\s*\)\s*;',
            r'\1if (android.os.Build.VERSION.SDK_INT >= 29) {\n\1    try {\n\1        mWindow.setStatusBarContrastEnforced(\2);\n\1    } catch (Throwable ignored) {}\n\1}',
            new_content
        )

        # 3. 逐行扫描守卫其它调用（如 EdgeToEdgeSystemBarColorHelper 或外部组件调用）
        lines = new_content.split("\n")
        patched_lines = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if (
                (".setNavigationBarContrastEnforced(" in line or ".setStatusBarContrastEnforced(" in line)
                and "void set" not in line
                and "abstract" not in line
            ):
                has_guard = False
                for k in range(max(0, i - 4), i):
                    if any(kw in lines[k] for kw in ("SDK_INT >= 29", "VERSION_CODES.Q", "SDK_INT < 29", "SDK_INT >= Build.VERSION_CODES.Q")):
                        has_guard = True
                        break
                if not has_guard:
                    stmt_lines = [line]
                    while ";" not in stmt_lines[-1] and i + 1 < len(lines):
                        i += 1
                        stmt_lines.append(lines[i])
                    indent = stmt_lines[0][: len(stmt_lines[0]) - len(stmt_lines[0].lstrip())]
                    patched_lines.append(f"{indent}if (android.os.Build.VERSION.SDK_INT >= 29) {{")
                    patched_lines.append(f"{indent}    try {{")
                    for s in stmt_lines:
                        patched_lines.append(f"    {s}")
                    patched_lines.append(f"{indent}    }} catch (Throwable ignored) {{}}")
                    patched_lines.append(f"{indent}}}")
                    i += 1
                    continue
            patched_lines.append(line)
            i += 1

        new_content = "\n".join(patched_lines)

        if new_content != content:
            with open(target, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Patched SystemBar contrast enforced methods for API 28 compat in: {target}")


def patch_power_monitor_compat(src_dir: str) -> None:
    # Android 9 (API 28) 缺少 PowerManager.addThermalStatusListener 与
    # PowerManager.getCurrentThermalStatus API 29+ 方法及 OnThermalStatusChangedListener 接口。
    # Chromium 156 将 minSdk 提高至 29 后，移除了版本守卫，导致 Android 9 车机上抛出：
    # java.lang.NoSuchMethodError: No virtual method addThermalStatusListener(...)
    # java.lang.NoSuchMethodError: No virtual method getCurrentThermalStatus()I
    target_files = [
        os.path.join(src_dir, "base/android/java/src/org/chromium/base/PowerMonitor.java"),
        os.path.join(src_dir, "chromium/src/base/android/java/src/org/chromium/base/PowerMonitor.java"),
        os.path.join(src_dir, "src/base/android/java/src/org/chromium/base/PowerMonitor.java"),
        os.path.join(src_dir, "base/android/java/src/org/chromium/base/PowerMonitorForQ.java"),
        os.path.join(src_dir, "chromium/src/base/android/java/src/org/chromium/base/PowerMonitorForQ.java"),
        os.path.join(src_dir, "src/base/android/java/src/org/chromium/base/PowerMonitorForQ.java"),
    ]

    for sub in ["base", "chrome", "components", "android_webview", "content", "services"]:
        scan_path = os.path.join(src_dir, sub)
        if os.path.isdir(scan_path):
            for root, _, files in os.walk(scan_path):
                for f in files:
                    if f.endswith(".java"):
                        try:
                            fp = os.path.join(root, f)
                            with open(fp, "r", encoding="utf-8", errors="ignore") as jf:
                                c = jf.read()
                                if (
                                    "addThermalStatusListener" in c
                                    or "getCurrentThermalStatus" in c
                                    or "removeThermalStatusListener" in c
                                    or "OnThermalStatusChangedListener" in c
                                ):
                                    target_files.append(fp)
                        except Exception:
                            pass

    seen = set()
    for target in target_files:
        if not os.path.isfile(target):
            continue
        real_path = os.path.realpath(target)
        if real_path in seen:
            continue
        seen.add(real_path)

        with open(target, "r", encoding="utf-8") as f:
            content = f.read()

        if (
            "addThermalStatusListener" not in content
            and "getCurrentThermalStatus" not in content
            and "removeThermalStatusListener" not in content
        ):
            continue

        new_content = content

        # 1. getCurrentThermalStatus() 方法入口守卫：API 28 下直接返回 -1 (kUnknown)
        if "getCurrentThermalStatus" in new_content:
            if not re.search(r"int\s+getCurrentThermalStatus\s*\([^)]*\)\s*\{[^}]*SDK_INT", new_content):
                new_content = re.sub(
                    r"((?:@Override\s*\n\s*)?(?:public|protected|private)?\s*(?:static\s+)?int\s+getCurrentThermalStatus\s*\([^)]*\)\s*\{)",
                    r"\1\n        if (android.os.Build.VERSION.SDK_INT < 29) {\n            return -1;\n        }",
                    new_content,
                )

        # 2. 守卫 return powerManager.getCurrentThermalStatus();
        new_content = re.sub(
            r'([ \t]*)return\s+(\w+)\.getCurrentThermalStatus\s*\(\s*\)\s*;',
            r'\1if (android.os.Build.VERSION.SDK_INT >= 29) {\n\1    try {\n\1        return \2.getCurrentThermalStatus();\n\1    } catch (Throwable ignored) {}\n\1}\n\1return -1;',
            new_content,
        )

        # 3. 守卫 return ApiHelperForQ.getCurrentThermalStatus(powerManager);
        new_content = re.sub(
            r'([ \t]*)return\s+ApiHelperForQ\.getCurrentThermalStatus\s*\(\s*(\w+)\s*\)\s*;',
            r'\1if (android.os.Build.VERSION.SDK_INT >= 29) {\n\1    try {\n\1        return ApiHelperForQ.getCurrentThermalStatus(\2);\n\1    } catch (Throwable ignored) {}\n\1}\n\1return -1;',
            new_content,
        )

        # 4. 守卫赋值调用 status = powerManager.getCurrentThermalStatus();
        new_content = re.sub(
            r'([ \t]*)(\w+)\s*=\s*(\w+)\.getCurrentThermalStatus\s*\(\s*\)\s*;',
            r'\1if (android.os.Build.VERSION.SDK_INT >= 29) {\n\1    try {\n\1        \2 = \3.getCurrentThermalStatus();\n\1    } catch (Throwable ignored) {}\n\1}',
            new_content,
        )

        # 5. 逐行多行扫描守卫 addThermalStatusListener / removeThermalStatusListener
        lines = new_content.split("\n")
        patched_lines = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if (
                (".addThermalStatusListener(" in line or ".removeThermalStatusListener(" in line)
                and "void " not in line
                and "abstract " not in line
            ):
                has_guard = False
                for k in range(max(0, i - 4), i):
                    if any(kw in lines[k] for kw in ("SDK_INT >= 29", "VERSION_CODES.Q", "SDK_INT < 29", "SDK_INT >= Build.VERSION_CODES.Q")):
                        has_guard = True
                        break
                if not has_guard:
                    stmt_lines = [line]
                    depth = line.count("(") - line.count(")")
                    while (depth > 0 or ";" not in stmt_lines[-1]) and i + 1 < len(lines):
                        i += 1
                        stmt_lines.append(lines[i])
                        depth += lines[i].count("(") - lines[i].count(")")
                    indent = stmt_lines[0][: len(stmt_lines[0]) - len(stmt_lines[0].lstrip())]
                    patched_lines.append(f"{indent}if (android.os.Build.VERSION.SDK_INT >= 29) {{")
                    patched_lines.append(f"{indent}    try {{")
                    for s in stmt_lines:
                        patched_lines.append(f"{indent}        {s.lstrip()}")
                    patched_lines.append(f"{indent}    }} catch (Throwable ignored) {{}}")
                    patched_lines.append(f"{indent}}}")
                    i += 1
                    continue
            patched_lines.append(line)
            i += 1

        new_content = "\n".join(patched_lines)

        # 6. 将外部 if (powerManager != null) 扩展为 API 29 守卫
        new_content = re.sub(
            r'if\s*\(\s*(\w+)\s*!=\s*null\s*\)\s*\{\s*\n(\s*)if\s*\(\s*android\.os\.Build\.VERSION\.SDK_INT\s*>=\s*29\s*\)',
            r'if (\1 != null && android.os.Build.VERSION.SDK_INT >= 29) {\n\2if (android.os.Build.VERSION.SDK_INT >= 29)',
            new_content,
        )

        if new_content != content:
            with open(target, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Patched PowerMonitor thermal methods for API 28 compat in: {target}")


def patch_path_utils_compat(src_dir: str) -> None:
    # Android 9 缺少 MediaStore.getExternalVolumeNames(Context) 与
    # StorageManager.getStorageVolume(Uri) API 29+ 方法。
    target_files = [
        os.path.join(src_dir, "base/android/java/src/org/chromium/base/PathUtils.java"),
        os.path.join(src_dir, "chromium/src/base/android/java/src/org/chromium/base/PathUtils.java"),
        os.path.join(src_dir, "src/base/android/java/src/org/chromium/base/PathUtils.java"),
    ]

    for sub in ["base", "chrome", "components", "android_webview"]:
        scan_path = os.path.join(src_dir, sub)
        if os.path.isdir(scan_path):
            for root, _, files in os.walk(scan_path):
                for f in files:
                    if f.endswith(".java"):
                        fp = os.path.join(root, f)
                        try:
                            with open(fp, "r", encoding="utf-8", errors="ignore") as jf:
                                c = jf.read()
                                if "getExternalDownloadVolumesNames" in c:
                                    target_files.append(fp)
                        except Exception:
                            pass

    seen = set()
    for target in target_files:
        if not os.path.isfile(target):
            continue
        real_path = os.path.realpath(target)
        if real_path in seen:
            continue
        seen.add(real_path)

        with open(target, "r", encoding="utf-8") as f:
            content = f.read()

        if "getExternalDownloadVolumesNames" not in content:
            continue

        new_content = content
        if not re.search(r"String\[\]\s+getExternalDownloadVolumesNames\s*\([^)]*\)\s*\{[^}]*SDK_INT", new_content):
            new_content = re.sub(
                r"((?:@Override\s*\n\s*)?(?:public|protected|private)?\s*(?:static\s+)?(?:@\w+\s+)?String\[\]\s+getExternalDownloadVolumesNames\s*\([^)]*\)\s*\{)",
                r"\1\n        if (android.os.Build.VERSION.SDK_INT < 29) {\n            return new String[0];\n        }",
                new_content,
            )

        if new_content != content:
            with open(target, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Patched PathUtils for API 28 compat in: {target}")


def patch_intent_identifier_compat(src_dir: str) -> None:
    # Android 9 (API 28) 缺少 Intent.setIdentifier(String) API 29+ 方法。
    target_files = [
        os.path.join(src_dir, "chrome/android/java/src/org/chromium/chrome/browser/notifications/NotificationIntentInterceptor.java"),
        os.path.join(src_dir, "chromium/src/chrome/android/java/src/org/chromium/chrome/browser/notifications/NotificationIntentInterceptor.java"),
        os.path.join(src_dir, "src/chrome/android/java/src/org/chromium/chrome/browser/notifications/NotificationIntentInterceptor.java"),
    ]

    for sub in ["chrome", "base", "components"]:
        scan_path = os.path.join(src_dir, sub)
        if os.path.isdir(scan_path):
            for root, _, files in os.walk(scan_path):
                for f in files:
                    if f.endswith(".java"):
                        fp = os.path.join(root, f)
                        try:
                            with open(fp, "r", encoding="utf-8", errors="ignore") as jf:
                                c = jf.read()
                                if ".setIdentifier(" in c:
                                    target_files.append(fp)
                        except Exception:
                            pass

    seen = set()
    for target in target_files:
        if not os.path.isfile(target):
            continue
        real_path = os.path.realpath(target)
        if real_path in seen:
            continue
        seen.add(real_path)

        with open(target, "r", encoding="utf-8") as f:
            content = f.read()

        if ".setIdentifier(" not in content:
            continue

        # 1. 自动回滚错误包裹了链式调用（例如以点开头的 builder 模式）的代码
        revert_pattern = (
            r"[ \t]*if\s*\(\s*android\.os\.Build\.VERSION\.SDK_INT\s*>=\s*29\s*\)\s*\{\s*\n"
            r"[ \t]*try\s*\{\s*\n"
            r"([ \t]*\.[^}]+?)[ \t]*\}\s*catch\s*\(Throwable\s+\w+\)\s*\{\}\s*\n[ \t]*\}"
        )
        unwrapped_content = re.sub(revert_pattern, lambda m: m.group(1).rstrip(), content)
        if unwrapped_content != content:
            content = unwrapped_content
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Restored corrupted chained setIdentifier calls in: {target}")

        # 2. 只有明确包含 Intent 且存在真正的 intent.setIdentifier 调用时才进行兼容守卫
        intent_caller_pattern = r"(?:^|[^\w.])(\w*[iI]ntent\w*(?:\(\))?)\.setIdentifier\s*\("
        if not ("Intent" in content and re.search(intent_caller_pattern, content)):
            continue

        lines = content.split("\n")
        patched_lines = []
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.lstrip()

            # 严格排除以点号开头的链式调用、方法定义或非 Intent 调用
            if (
                stripped.startswith(".")
                or "abstract " in line
                or "void " in line
                or re.search(r"(?:public|protected|private)\s+.*\bsetIdentifier\s*\(", line)
            ):
                patched_lines.append(line)
                i += 1
                continue

            match = re.search(intent_caller_pattern, line)
            if match:
                has_guard = False
                for k in range(max(0, i - 4), i):
                    if any(kw in lines[k] for kw in ("SDK_INT >= 29", "VERSION_CODES.Q", "SDK_INT < 29")):
                        has_guard = True
                        break
                if not has_guard:
                    stmt_lines = [line]
                    while ";" not in stmt_lines[-1] and i + 1 < len(lines):
                        i += 1
                        stmt_lines.append(lines[i])

                    indent = stmt_lines[0][: len(stmt_lines[0]) - len(stmt_lines[0].lstrip())]
                    stripped_head = stmt_lines[0].lstrip()
                    intent_var = match.group(1)

                    if stripped_head.startswith("return "):
                        call_stmt = stmt_lines[:]
                        call_stmt[0] = indent + stripped_head[len("return "):]
                        patched_lines.append(f"{indent}if (android.os.Build.VERSION.SDK_INT >= 29) {{")
                        patched_lines.append(f"{indent}    try {{")
                        for s in call_stmt:
                            patched_lines.append(f"{indent}        {s.lstrip()}")
                        patched_lines.append(f"{indent}    }} catch (Throwable ignored) {{}}")
                        patched_lines.append(f"{indent}}}")
                        patched_lines.append(f"{indent}return {intent_var};")
                    else:
                        patched_lines.append(f"{indent}if (android.os.Build.VERSION.SDK_INT >= 29) {{")
                        patched_lines.append(f"{indent}    try {{")
                        for s in stmt_lines:
                            patched_lines.append(f"{indent}        {s.lstrip()}")
                        patched_lines.append(f"{indent}    }} catch (Throwable ignored) {{}}")
                        patched_lines.append(f"{indent}}}")
                    i += 1
                    continue

            patched_lines.append(line)
            i += 1

        new_content = "\n".join(patched_lines)
        if new_content != content:
            with open(target, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Patched Intent.setIdentifier for API 28 compat in: {target}")


def patch_media_codec_info_compat(src_dir: str) -> None:
    # Android 9 (API 28) 缺少 MediaCodecInfo 的 API 29+ 方法：
    # - info.isHardwareAccelerated()
    # - info.isSoftwareOnly()
    # - info.isAlias()
    # 在 MediaCodecUtil.java 和 VideoAcceleratorUtil.java 中直接调用这些方法会导致
    # java.lang.NoSuchMethodError 致命闪退，特别是在 GPU 进程查询编解码器与视频播放/录制初始化阶段。
    target_files = [
        os.path.join(src_dir, "media/base/android/java/src/org/chromium/media/MediaCodecUtil.java"),
        os.path.join(src_dir, "media/base/android/java/src/org/chromium/media/VideoAcceleratorUtil.java"),
        os.path.join(src_dir, "chromium/src/media/base/android/java/src/org/chromium/media/MediaCodecUtil.java"),
        os.path.join(src_dir, "chromium/src/media/base/android/java/src/org/chromium/media/VideoAcceleratorUtil.java"),
        os.path.join(src_dir, "src/media/base/android/java/src/org/chromium/media/MediaCodecUtil.java"),
        os.path.join(src_dir, "src/media/base/android/java/src/org/chromium/media/VideoAcceleratorUtil.java"),
    ]

    for sub in ["media/base/android", "media"]:
        scan_path = os.path.join(src_dir, sub)
        if os.path.isdir(scan_path):
            for root, _, files in os.walk(scan_path):
                for f in files:
                    if f in ("MediaCodecUtil.java", "VideoAcceleratorUtil.java") or f.endswith(".java"):
                        full_f = os.path.join(root, f)
                        if full_f not in target_files:
                            try:
                                with open(full_f, "r", encoding="utf-8", errors="ignore") as jf:
                                    snippet = jf.read()
                                if any(kw in snippet for kw in ("isHardwareAccelerated", "isSoftwareOnly", "isAlias")):
                                    target_files.append(full_f)
                            except Exception:
                                pass

    for target in target_files:
        if not os.path.isfile(target):
            continue
        with open(target, "r", encoding="utf-8") as f:
            content = f.read()

        new_content = content

        # 1. Patch MediaCodecUtil.java:
        # public static boolean isSoftwareCodec(MediaCodecInfo info)
        if ("isHardwareAccelerated()" in new_content or "isSoftwareOnly()" in new_content) and not re.search(
            r'SDK_INT\s*>=\s*29[\s\S]{1,100}isHardwareAccelerated\(\)', new_content
        ):
            new_content = re.sub(
                r'([ \t]*)if\s*\(\s*!info\.isHardwareAccelerated\(\)\s*\|\|\s*info\.isSoftwareOnly\(\)\s*\)\s*(?:\n[ \t]*)?return\s+true;',
                r'\1if (android.os.Build.VERSION.SDK_INT >= 29) {\n\1    try {\n\1        if (!info.isHardwareAccelerated() || info.isSoftwareOnly()) return true;\n\1    } catch (Throwable ignored) {}\n\1}',
                new_content,
            )

        # 2. Patch VideoAcceleratorUtil.java:
        if "isCodecAlias" not in new_content and re.search(r'class\s+VideoAcceleratorUtil\b', new_content):
            helpers = (
                "\n"
                "    private static boolean isCodecAlias(MediaCodecInfo codecInfo) {\n"
                "        if (android.os.Build.VERSION.SDK_INT >= 29) {\n"
                "            try {\n"
                "                return codecInfo.isAlias();\n"
                "            } catch (Throwable ignored) {}\n"
                "        }\n"
                "        return false;\n"
                "    }\n"
                "\n"
                "    private static boolean isCodecHardwareAccelerated(MediaCodecInfo codecInfo) {\n"
                "        if (android.os.Build.VERSION.SDK_INT >= 29) {\n"
                "            try {\n"
                "                return codecInfo.isHardwareAccelerated();\n"
                "            } catch (Throwable ignored) {}\n"
                "        }\n"
                "        return !MediaCodecUtil.isSoftwareCodec(codecInfo);\n"
                "    }\n"
                "\n"
                "    private static boolean isCodecSoftwareOnly(MediaCodecInfo codecInfo) {\n"
                "        if (android.os.Build.VERSION.SDK_INT >= 29) {\n"
                "            try {\n"
                "                return codecInfo.isSoftwareOnly();\n"
                "            } catch (Throwable ignored) {}\n"
                "        }\n"
                "        return MediaCodecUtil.isSoftwareCodec(codecInfo);\n"
                "    }\n"
            )

            # Replace call sites first (using codecInfo in helpers guarantees no recursion)
            new_content = re.sub(r'isAtLeastQ\s*&&\s*info\.isAlias\(\)', 'isCodecAlias(info)', new_content)
            new_content = re.sub(r'\binfo\.isAlias\(\)', 'isCodecAlias(info)', new_content)
            new_content = re.sub(r'\binfo\.isHardwareAccelerated\(\)', 'isCodecHardwareAccelerated(info)', new_content)
            new_content = re.sub(r'\binfo\.isSoftwareOnly\(\)', 'isCodecSoftwareOnly(info)', new_content)

            # Insert helpers after class declaration
            new_content = re.sub(
                r'((?:public\s+|protected\s+|private\s+)?class\s+VideoAcceleratorUtil\b[^{]*\{)',
                r'\1' + helpers,
                new_content,
                count=1,
            )

        if new_content != content:
            with open(target, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Patched MediaCodec API 29+ methods for API 28 compat in: {target}")


def patch_default_browser_promo_compat(src_dir: str) -> None:
    # Android 9 (API 28) 缺少 RoleManager (Context.ROLE_SERVICE / android.app.role.RoleManager) API 29+。
    # Chromium 156 在 DefaultBrowserPromoUtils 与 DefaultBrowserPromoManager 中直接使用 RoleManager，
    # 在 Android 9 车机设备上启动或切换标签页时会导致：
    # java.lang.NoClassDefFoundError: Failed resolution of: Landroid/app/role/RoleManager;
    #   at DefaultBrowserPromoUtils.isRoleAvailableButNotHeld(...)
    # 引发闪退。
    target_files = [
        os.path.join(
            src_dir,
            "chrome/browser/ui/android/default_browser_promo/java/src/org/chromium/chrome/browser/ui/default_browser_promo/DefaultBrowserPromoUtils.java",
        ),
        os.path.join(
            src_dir,
            "chromium/src/chrome/browser/ui/android/default_browser_promo/java/src/org/chromium/chrome/browser/ui/default_browser_promo/DefaultBrowserPromoUtils.java",
        ),
        os.path.join(
            src_dir,
            "src/chrome/browser/ui/android/default_browser_promo/java/src/org/chromium/chrome/browser/ui/default_browser_promo/DefaultBrowserPromoUtils.java",
        ),
        os.path.join(
            src_dir,
            "chrome/browser/ui/android/default_browser_promo/java/src/org/chromium/chrome/browser/ui/default_browser_promo/DefaultBrowserPromoManager.java",
        ),
        os.path.join(
            src_dir,
            "chromium/src/chrome/browser/ui/android/default_browser_promo/java/src/org/chromium/chrome/browser/ui/default_browser_promo/DefaultBrowserPromoManager.java",
        ),
        os.path.join(
            src_dir,
            "src/chrome/browser/ui/android/default_browser_promo/java/src/org/chromium/chrome/browser/ui/default_browser_promo/DefaultBrowserPromoManager.java",
        ),
    ]

    for sub in ["chrome/browser/ui/android", "chrome/android", "chrome"]:
        scan_path = os.path.join(src_dir, sub)
        if os.path.isdir(scan_path):
            for root, _, files in os.walk(scan_path):
                for f in files:
                    if f.endswith(".java"):
                        full_f = os.path.join(root, f)
                        if full_f not in target_files:
                            try:
                                with open(full_f, "r", encoding="utf-8", errors="ignore") as jf:
                                    snippet = jf.read()
                                if "isRoleAvailableButNotHeld" in snippet or "promoByRoleManager" in snippet:
                                    target_files.append(full_f)
                            except Exception:
                                pass

    seen = set()
    for target in target_files:
        if not os.path.isfile(target):
            continue
        real_path = os.path.realpath(target)
        if real_path in seen:
            continue
        seen.add(real_path)

        with open(target, "r", encoding="utf-8") as f:
            content = f.read()

        new_content = content

        # 1. Patch DefaultBrowserPromoUtils.java: isRoleAvailableButNotHeld
        if "isRoleAvailableButNotHeld" in new_content:
            pattern_utils = r"private\s+boolean\s+isRoleAvailableButNotHeld\s*\(\s*Context\s+context\s*\)\s*\{[\s\S]*?return\s+isRoleAvailable\s*&&\s*!isRoleHeld\s*;\s*\}"
            replacement_utils = (
                "private boolean isRoleAvailableButNotHeld(Context context) {\n"
                "        if (android.os.Build.VERSION.SDK_INT < 29) {\n"
                "            return false;\n"
                "        }\n"
                "        try {\n"
                '            Object roleManager = context.getSystemService("role");\n'
                "            if (roleManager == null) return false;\n"
                "            java.lang.reflect.Method isAvailableMethod =\n"
                '                    roleManager.getClass().getMethod("isRoleAvailable", String.class);\n'
                "            java.lang.reflect.Method isHeldMethod =\n"
                '                    roleManager.getClass().getMethod("isRoleHeld", String.class);\n'
                "            boolean isRoleAvailable =\n"
                '                    (Boolean) isAvailableMethod.invoke(roleManager, "android.app.role.BROWSER");\n'
                "            boolean isRoleHeld =\n"
                '                    (Boolean) isHeldMethod.invoke(roleManager, "android.app.role.BROWSER");\n'
                "            return isRoleAvailable && !isRoleHeld;\n"
                "        } catch (Throwable t) {\n"
                "            return false;\n"
                "        }\n"
                "    }"
            )
            if "android.os.Build.VERSION.SDK_INT < 29" not in new_content:
                new_content = re.sub(pattern_utils, replacement_utils, new_content)

        # 2. Patch DefaultBrowserPromoManager.java: promoByRoleManager
        if "void promoByRoleManager" in new_content:
            if "android.os.Build.VERSION.SDK_INT < 29" not in new_content:
                new_content = re.sub(
                    r'(void\s+promoByRoleManager\s*\(\s*\)\s*\{)',
                    r'\1\n        if (android.os.Build.VERSION.SDK_INT < 29) {\n            return;\n        }',
                    new_content,
                )

        if new_content != content:
            with open(target, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Patched RoleManager compat for API 28 in: {target}")


def patch_compositor_view_compat(src_dir: str) -> None:
    # Android 9 (API 28) 缺少 SurfaceControl.TransactionCommittedListener 接口 (API 33+)。
    # CompositorView.java 中使用 lambda 直接实现 TransactionCommittedListener 会导致 D8 生成
    # implements SurfaceControl$TransactionCommittedListener 的合成类。
    # 在 Android 9 车机设备上类验证阶段抛出：
    # java.lang.NoClassDefFoundError: Failed resolution of: Landroid/view/SurfaceControl$TransactionCommittedListener;
    # 导致 CompositorViewHolder 构造或类初始化失败。
    target_files = [
        os.path.join(
            src_dir,
            "chrome/android/java/src/org/chromium/chrome/browser/compositor/CompositorView.java",
        ),
        os.path.join(
            src_dir,
            "chromium/src/chrome/android/java/src/org/chromium/chrome/browser/compositor/CompositorView.java",
        ),
        os.path.join(
            src_dir,
            "src/chrome/android/java/src/org/chromium/chrome/browser/compositor/CompositorView.java",
        ),
    ]

    for sub in ["chrome/android", "chrome", "content"]:
        scan_path = os.path.join(src_dir, sub)
        if os.path.isdir(scan_path):
            for root, _, files in os.walk(scan_path):
                for f in files:
                    if f.endswith(".java"):
                        full_f = os.path.join(root, f)
                        if full_f not in target_files:
                            try:
                                with open(full_f, "r", encoding="utf-8", errors="ignore") as jf:
                                    snippet = jf.read()
                                if "addTransactionCommittedListener" in snippet:
                                    target_files.append(full_f)
                            except Exception:
                                pass

    seen = set()
    for target in target_files:
        if not os.path.isfile(target):
            continue
        real_path = os.path.realpath(target)
        if real_path in seen:
            continue
        seen.add(real_path)

        with open(target, "r", encoding="utf-8") as f:
            content = f.read()

        if "addTransactionCommittedListener" not in content:
            continue

        new_content = content

        # 将直接实现 TransactionCommittedListener 的 lambda 改为运行时动态代理 Proxy，
        # 避免在 API 28 平台生成包含不可解析接口的外部合成类（避免 NoClassDefFoundError）。
        pattern_comp = (
            r"Transaction\s+t\s*=\s*new\s+Transaction\(\s*\)\s*;\s*\n"
            r"\s*t\.addTransactionCommittedListener\s*\(\s*\n"
            r"\s*ThreadUtils::postOnUiThread\s*,\s*\n"
            r"\s*\(\s*\)\s*->\s*\{[\s\S]*?\}\s*\)\s*;\s*\n"
            r"\s*rootSurfaceControl\.applyTransactionOnDraw\s*\(\s*t\s*\)\s*;"
        )

        replacement_comp = (
            "Transaction t = new Transaction();\n"
            "            try {\n"
            "                Class<?> listenerClass =\n"
            '                        Class.forName("android.view.SurfaceControl$TransactionCommittedListener");\n'
            "                Object listener =\n"
            "                        java.lang.reflect.Proxy.newProxyInstance(\n"
            "                                CompositorView.class.getClassLoader(),\n"
            "                                new Class<?>[] {listenerClass},\n"
            "                                (proxy, method, args) -> {\n"
            '                                    if ("onTransactionCommitted".equals(method.getName())) {\n'
            "                                        if (seqNo == mResizeSeqNo) {\n"
            "                                            unpauseDraw();\n"
            "                                        }\n"
            "                                    }\n"
            "                                    return null;\n"
            "                                });\n"
            "                java.lang.reflect.Method addListenerMethod =\n"
            "                        t.getClass()\n"
            "                                .getMethod(\n"
            '                                        "addTransactionCommittedListener",\n'
            "                                        java.util.concurrent.Executor.class,\n"
            "                                        listenerClass);\n"
            "                addListenerMethod.invoke(\n"
            "                        t,\n"
            "                        (java.util.concurrent.Executor) ThreadUtils::postOnUiThread,\n"
            "                        listener);\n"
            "            } catch (Throwable ignored) {\n"
            "                unpauseDraw();\n"
            "            }\n"
            "            rootSurfaceControl.applyTransactionOnDraw(t);"
        )

        if "Proxy.newProxyInstance" not in new_content:
            new_content = re.sub(pattern_comp, replacement_comp, new_content)

        if new_content != content:
            with open(target, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Patched CompositorView TransactionCommittedListener for API 28 in: {target}")


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
    patch_strict_mode_credential_protected(src_dir)
    patch_url_bar_cursor_handles_compat(src_dir)
    patch_url_bar_multiline_scroll_compat(src_dir)
    patch_gesture_exclusion_rects_compat(src_dir)
    patch_system_bar_contrast_enforced_compat(src_dir)
    patch_power_monitor_compat(src_dir)
    patch_path_utils_compat(src_dir)
    patch_intent_identifier_compat(src_dir)
    patch_content_app_aidl_deps(src_dir)
    patch_ahardwarebuffer_image_backing_factory(src_dir)
    patch_base_hardware_buffer_sources(src_dir)
    patch_ndk_video_encode_accelerator(src_dir)
    patch_gpu_video_encode_accelerator_factory(src_dir)
    patch_ndk_audio_encoder(src_dir)
    patch_media_codec_info_compat(src_dir)
    patch_default_browser_promo_compat(src_dir)
    patch_compositor_view_compat(src_dir)

    print("SDK version patch (minSdk: 28) & car-compat checks complete.")


if __name__ == "__main__":
    main()
