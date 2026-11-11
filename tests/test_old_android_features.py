import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class OldAndroidFeatureConfigurationTest(unittest.TestCase):
    def test_old_android_keeps_api28_and_desktop_extension_support(self):
        args = (ROOT / "args.gn").read_text()
        self.assertIn("default_min_sdk_version = 28", args)
        self.assertIn("is_desktop_android = true", args)
        self.assertIn("v8_enable_drumbrake = false", args)
        self.assertIn("v8_drumbrake_bounds_checks = false", args)

    def test_build_configuration_preserves_desktop_extension_support(self):
        build = (ROOT / "build.sh").read_text()
        self.assertIn(
            'set_gn_arg "$desired_args" is_desktop_android true',
            build,
        )
        self.assertIn(
            'set_gn_arg "$desired_args" default_min_sdk_version 28',
            build,
        )

    def test_hotfixes_require_extension_and_bottom_toolbar_markers(self):
        for name in ("patch.sh", "hotfix_existing_src.sh"):
            with self.subTest(script=name):
                text = (ROOT / name).read_text()
                self.assertIn("patch_ui_mode.py", text)
                self.assertIn("patch_lemur_app_menu.py", text)
                self.assertIn("patch_extension_toolbar.py", text)
                self.assertIn(
                    "Helium: follow the toolbar preference on the NTP and while editing",
                    text,
                )
                self.assertIn(
                    "AddressBarPreference.isToolbarConfiguredToShowOnTop()",
                    text,
                )

    def test_appearance_theme_switch_is_posted_asynchronously(self):
        for name in ("patch.sh", "hotfix_existing_src.sh"):
            with self.subTest(script=name):
                text = (ROOT / name).read_text()
                self.assertIn("mHandler.post(() -> {", text)
                self.assertIn("ChromePreferenceKeys.UI_THEME_SETTING, selectedTheme", text)

    def test_recreation_draw_blocker_has_render_request_and_safety_fallback(self):
        for name in ("patch.sh", "hotfix_existing_src.sh"):
            with self.subTest(script=name):
                text = (ROOT / name).read_text()
                self.assertIn("cvh.requestRender();", text)
                self.assertIn(
                    "mHandler.postDelayed(\n                            mAppLaunchDrawBlocker::onActiveTabAvailableForRecreation, 350);",
                    text,
                )

    def test_patch_bind_isolated_service_compat(self):
        import tempfile
        from patch_android_min_sdk import patch_bind_isolated_service_compat

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = pathlib.Path(tmpdir)
            bind_service_file = (
                tmppath
                / "base/android/java/src/org/chromium/base/process_launcher/BindService.java"
            )
            bind_service_file.parent.mkdir(parents=True, exist_ok=True)
            bind_service_file.write_text(
                """public class BindService {
    static boolean doBindService(Context context, Intent intent, ServiceConnection connection,
            int flags, Handler handler, Executor executor, @Nullable String instanceName) {
        if (sBinderCallCounter != null) {
            sBinderCallCounter.mBindServiceCount++;
        }
        if (instanceName != null) {
            return context.bindIsolatedService(intent, flags, instanceName, executor, connection);
        }
        if (Build.VERSION.SDK_INT <= Build.VERSION_CODES.N) {
            return bindServiceByCall(context, intent, connection, flags);
        }
        try {
            return bindServiceByReflection(context, intent, connection, flags, handler);
        } catch (ReflectiveOperationException reflectionException) {
            try {
                return bindServiceByCall(context, intent, connection, flags);
            } catch (RuntimeException runtimeException) {
                throw new RuntimeException(runtimeException.getMessage(), reflectionException);
            }
        }
    }
    static void doRebindService(Context context, ServiceConnection connection, int flags, boolean urgent) {
        if (sBinderCallCounter != null) {
            sBinderCallCounter.mRebindServiceCount++;
        }
        Context.BindServiceFlags bindServiceFlags =
                Context.BindServiceFlags.of(sanitizeFlagsForBindServiceFlags(flags));
    }
    static void doUpdateServiceGroup(Context context, ServiceConnection connection, int group, int importanceInGroup) {
        if (sBinderCallCounter != null) {
            sBinderCallCounter.mUpdateServiceGroupCount++;
        }
        context.updateServiceGroup(connection, group, importanceInGroup);
    }
}
""",
                encoding="utf-8",
            )

            allocator_file = (
                tmppath
                / "base/android/java/src/org/chromium/base/process_launcher/ChildConnectionAllocator.java"
            )
            allocator_file.parent.mkdir(parents=True, exist_ok=True)
            allocator_file.write_text(
                """public class ChildConnectionAllocator {
    public static ChildConnectionAllocator createVariableSize() {
        boolean disableZygote =
                Build.VERSION.SDK_INT == 29
                        && AndroidInfo.getAndroidBuildFingerprint().startsWith("OnePlus/");
        return null;
    }
}
""",
                encoding="utf-8",
            )

            patch_bind_isolated_service_compat(str(tmppath))

            patched_bind = bind_service_file.read_text(encoding="utf-8")
            self.assertIn("android.os.Build.VERSION.SDK_INT >= 29", patched_bind)
            self.assertIn("context.bindIsolatedService", patched_bind)
            self.assertIn("context.updateServiceGroup", patched_bind)
            self.assertIn("Build.VERSION.SDK_INT < 34", patched_bind)
            self.assertIn("catch (Throwable reflectionException)", patched_bind)

            patched_alloc = allocator_file.read_text(encoding="utf-8")
            self.assertIn("(Build.VERSION.SDK_INT < 29)", patched_alloc)

    def test_patch_zlib_fcntl_cloexec_compat(self):
        import tempfile
        from patch_android_min_sdk import patch_zlib_fcntl_cloexec_compat

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = pathlib.Path(tmpdir)
            zlib_file = tmppath / "third_party/zlib/gzlib.c"
            zlib_file.parent.mkdir(parents=True)
            zlib_file.write_text(
                "#ifdef O_CLOEXEC\n"
                "        if (oflag & O_CLOEXEC)\n"
                "            fcntl(fd, F_SETFD, fcntl(fd, F_GETFD) | O_CLOEXEC);\n"
                "#endif\n",
                encoding="utf-8",
            )

            patch_zlib_fcntl_cloexec_compat(str(tmppath))
            patched = zlib_file.read_text(encoding="utf-8")
            self.assertIn("fcntl(fd, F_SETFD, fcntl(fd, F_GETFD) | FD_CLOEXEC);", patched)
            self.assertNotIn("F_SETFD, fcntl(fd, F_GETFD) | O_CLOEXEC", patched)

            patch_zlib_fcntl_cloexec_compat(str(tmppath))
            self.assertEqual(patched, zlib_file.read_text(encoding="utf-8"))

    def test_patch_advanced_protection_api28_compat(self):
        import tempfile
        from patch_android_min_sdk import patch_advanced_protection_api28_compat

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = pathlib.Path(tmpdir)
            provider_file = (
                tmppath
                / "components/safe_browsing/android/java/src/org/chromium/components/safe_browsing/OsAdditionalSecurityProvider.java"
            )
            provider_file.parent.mkdir(parents=True, exist_ok=True)
            provider_file.write_text(
                """import android.security.advancedprotection.AdvancedProtectionManager;

public class OsAdditionalSecurityProvider {
    public OsAdditionalSecurityProvider() {
        if (!BuildCompat.isAtLeastB()) {
            return;
        }

        Context context = ContextUtils.getApplicationContext();
        if (ContextCompat.checkSelfPermission(
                        context, Manifest.permission.QUERY_ADVANCED_PROTECTION_MODE)
                != PackageManager.PERMISSION_GRANTED) {
            return;
        }
        var manager =
                (AdvancedProtectionManager)
                        context.getSystemService(Context.ADVANCED_PROTECTION_SERVICE);
        if (manager == null) {
            return;
        }

        mIsAdvancedProtectionRequestedByOs = manager.isAdvancedProtectionEnabled();
        manager.registerAdvancedProtectionCallback(
                Runnable::run,
                isAdvancedProtectionEnabled -> {
                    if (isAdvancedProtectionEnabled == mIsAdvancedProtectionRequestedByOs) {
                        return;
                    }

                    ThreadUtils.postOnUiThread(
                            () -> {
                                mIsAdvancedProtectionRequestedByOs = isAdvancedProtectionEnabled;
                                for (Observer observer : mObservers) {
                                    observer.onAdvancedProtectionOsSettingChanged();
                                }
                            });
                });
    }
}
""",
                encoding="utf-8",
            )

            patch_advanced_protection_api28_compat(str(tmppath))
            patched = provider_file.read_text(encoding="utf-8")
            self.assertNotIn("import android.security.advancedprotection.AdvancedProtectionManager;", patched)
            self.assertNotIn("(AdvancedProtectionManager)", patched)
            self.assertIn('Class.forName(', patched)
            self.assertIn('registerAdvancedProtectionCallback', patched)

            first_result = patched
            patch_advanced_protection_api28_compat(str(tmppath))
            self.assertEqual(first_result, provider_file.read_text(encoding="utf-8"))

    def test_patch_motion_event_input_compat(self):
        import tempfile
        from patch_android_min_sdk import patch_motion_event_input_compat

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = pathlib.Path(tmpdir)
            forwarder_file = (
                tmppath / "ui/android/java/src/org/chromium/ui/base/EventForwarder.java"
            )
            forwarder_file.parent.mkdir(parents=True, exist_ok=True)
            forwarder_file.write_text(
                """public class EventForwarder {
    private static boolean validateMotionEvent(MotionEvent event) {
        for (int i = 0; i < event.getPointerCount(); ++i) {
            if (!Float.isFinite(event.getX(i))
                    || !Float.isFinite(event.getY(i))
                    || !Float.isFinite(event.getRawX(i))
                    || !Float.isFinite(event.getRawY(i))) {
                return false;
            }
        }
        return true;
    }

    private boolean sendTouchEvent(MotionEvent event, boolean isTouchHandleEvent) {
        int gestureClassification = event.getClassification();
        return gestureClassification == 0;
    }
}
""",
                encoding="utf-8",
            )

            patch_motion_event_input_compat(str(tmppath))

            patched = forwarder_file.read_text(encoding="utf-8")
            self.assertNotIn("getRawX(i)", patched)
            self.assertNotIn("getRawY(i)", patched)
            self.assertIn("final float rawOffsetX = event.getRawX() - event.getX();", patched)
            self.assertIn("Build.VERSION.SDK_INT >= 29", patched)
            self.assertIn("MotionEvent.CLASSIFICATION_NONE", patched)

            # 重复执行必须保持幂等，否则增量编译会反复叠加补丁文本。
            patch_motion_event_input_compat(str(tmppath))
            self.assertEqual(patched, forwarder_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
