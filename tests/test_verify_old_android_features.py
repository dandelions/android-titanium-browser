import pathlib
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
VERIFY = ROOT / "verify_old_android_features.py"

NEWTAB_FILES = {
    "chrome/browser/extensions/extension_url_overrides.cc": "HeliumNtp: pref list missing",
    "chrome/browser/url_constants/android/java/src/org/chromium/chrome/browser/url_constants/UrlConstantResolver.java": 'Log.i("HeliumNtp",',
    "sandbox/policy/linux/bpf_renderer_policy_linux.cc": "VMOS still performs the executable-memory transition",
    "content/renderer/renderer_main_platform_delegate_android.cc": "std::make_unique<sandbox::policy::RendererProcessPolicy>\nstd::make_unique<sandbox::BaselinePolicyAndroid>",
    "content/app/android/content_main_android.cc": "void HeliumFatalSignalLogger(int sig, siginfo_t* info, void*) {}\n  HeliumInstallFatalSignalLogger();",
    "base/android/linker/linker_jni.h": "static const size_t kAddressSpaceReservationSize = 320 * 1024 * 1024;",
    "base/android/java/src/org/chromium/base/library_loader/Linker.java": "attemptLoadLibraryLocked(library, RelroSharingMode.NO_SHARING);",
    "third_party/libunwindstack/src/libunwindstack/Memory.cpp": "fcntl(helium_fd, F_SETFD, FD_CLOEXEC)",
    "third_party/libunwindstack/src/libprocinfo/include/procinfo/process_map.h": "fcntl(fd, F_SETFD, FD_CLOEXEC)",
    "ui/accessibility/android/java/src/org/chromium/ui/accessibility/AccessibilityStateDelegateImpl.java": "Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q\nint recommendedTimeout = nonA11yTimeout;",
    "content/browser/renderer_host/navigation_request.cc": 'HeliumNavTrace("begin"\nHeliumNavTrace("checks-complete"\nHeliumNavTrace("response"\nHeliumNavTrace("response-body-ready"\nHeliumNavTrace("ready-to-commit"\nHeliumNavTrace("conditions-start"\nHeliumNavTrace("commit-timeout"\nHeliumNavTrace("commit"\nHeliumNavTrace("failed"\nhelium-nav.log',
    "content/browser/renderer_host/commit_deferring_condition_runner.cc": '"Helium commit: condition="\n"Helium commit: condition result="',
    "content/browser/renderer_host/render_frame_host_impl.cc": 'Helium commit: Mojo send url=\nGetCommitNavigationClient()->CommitNavigation(',
    "content/renderer/render_frame_impl.cc": 'HeliumRendererCommitTrace("received")\nHeliumRendererCommitTrace("params")\nHeliumRendererCommitTrace("blink-before")\nHeliumRendererCommitTrace("blink-after")\n/storage/emulated/0/Android/data/io.github.jqssun.helium/files/logs/helium-renderer-commit.log',
    "content/app/content_main.cc": "Helium content main trace revision: 1\nHelium content main: type=\nHelium content main: initialize returned \nHelium content main: run returned ",
    "content/app/content_main_runner_impl.cc": "Helium child main: type=\nHelium child main: matched \nHelium child main: no main function for type=",
    "content/renderer/renderer_main.cc": "Helium renderer lifecycle: main entered\nHelium renderer lifecycle: RenderThreadImpl ready\nHelium renderer lifecycle: message loop entered\nHelium renderer lifecycle: message loop exited",
    "content/child/child_thread_impl.cc": "Helium renderer lifecycle: child channel error",
}


SINGLE_PROCESS_FILES = {
    "content/browser/renderer_host/render_process_host_impl.cc": (
        "if (run_renderer_in_process()) {\n"
        "    // VMOS Android 9 keeps the renderer inside the browser process, so killing\n"
        "    // it would terminate the whole browser. Drop the message instead.\n"
        "    return;\n"
        "}"
    ),
    "extensions/browser/api/messaging/message_service_bindings.cc": (
        "if (!RenderProcessHost::run_renderer_in_process() &&\n"
        "    !ProcessMap::Get(process.GetBrowserContext())\n"
        "        ->Contains(*source_endpoint_extension_id, process.GetID())) {}\n"
        "if (precursor_origin.scheme() == kExtensionScheme &&\n"
        "    !RenderProcessHost::run_renderer_in_process() &&\n"
        "    !ProcessMap::Get(process.GetBrowserContext())\n"
        "        ->Contains(precursor_origin.host(), process.GetID())) {}"
    ),
    "extensions/browser/service_worker/service_worker_host.cc": (
        "if (!content::RenderProcessHost::run_renderer_in_process() &&\n"
        "    (!process_map || !process_map->Contains(extension_id, render_process_id))) {}\n"
        "if (!content::RenderProcessHost::run_renderer_in_process() &&\n"
        "    (!process_map || !process_map->Contains(extension_id, render_process_id))) {}\n"
        "if (!content::RenderProcessHost::run_renderer_in_process() &&\n"
        "    (!process_map || !process_map->Contains(extension_id, render_process_id))) {}"
    ),
    "chrome/browser/net/system_network_context_manager.cc": (
        "// V8 resolver still works there, and PAC proxy rules require it."
    ),
    "chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/"
    "LocationBarPhone.java": (
        "protected @Nullable ImageButton mBackButton;\n"
        + "ImageButton backButton = mBackButton;\n" * 6
    ),
    "chrome/browser/ui/android/omnibox/java/res/layout-sw600dp/location_bar.xml": (
        '<include layout="@layout/omnibox_back_button"/>'
    ),
    "chrome/browser/flags/android/chrome_feature_list.cc": (
        "BASE_FEATURE(kAndroidBottomBar, base::FEATURE_ENABLED_BY_DEFAULT);"
    ),
    "chrome/browser/ui/android/bottombar/java/src/org/chromium/chrome/browser/ui/"
    "bottombar/BottomBarConfigUtils.java": (
        "// Helium: offer the bottom toolbar in desktop mode and on car units too.\n"
        "return ChromeFeatureList.sAndroidBottomBar.isEnabled();"
    ),
}


class VerifyOldAndroidFeaturesTest(unittest.TestCase):
    def test_accepts_required_feature_markers(self):
        files = {
            "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionsToolbarCoordinatorImpl.java": "return !mIsWebApp && mCanShowMenuIcon;",
            "chrome/android/java/src/org/chromium/chrome/browser/app/appmenu/AppMenuPropertiesDelegateImpl.java": "boolean shouldShowExtensionsItem() {\n        return true;\n    }",
            "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/ToolbarPositionController.java": "Helium: follow the toolbar preference on the NTP and while editing",
            "chrome/android/java/src/org/chromium/chrome/browser/ntp/NewTabPageCoordinator.java": "AddressBarPreference.isToolbarConfiguredToShowOnTop()",
            "chrome/browser/ui/android/toolbar/java/res/layout/toolbar_phone.xml": '<ViewStub android:id="@+id/extensions_toolbar_container_stub"/>',
            "chrome/android/java/src/org/chromium/chrome/browser/toolbar/ToolbarManager.java": (
                "ExtensionsToolbarCoordinator.maybeCreate(mToolbarLayout,\n"
                "if (mToolbarLayout instanceof ToolbarTablet) {\n"
                "    return ((ToolbarTablet) mToolbarLayout).areAnyToolbarComponentsMissingForWidth();\n"
                "}"
            ),
        }
        files.update(NEWTAB_FILES)
        files.update(SINGLE_PROCESS_FILES)
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            for relative, content in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            subprocess.run([sys.executable, str(VERIFY), str(root)], check=True)

    def test_rejects_missing_bottom_address_bar_marker(self):
        files = {
            "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionsToolbarCoordinatorImpl.java": "return !mIsWebApp && mCanShowMenuIcon;",
            "chrome/android/java/src/org/chromium/chrome/browser/app/appmenu/AppMenuPropertiesDelegateImpl.java": "boolean shouldShowExtensionsItem() {\n        return true;\n    }",
            "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/ToolbarPositionController.java": "Helium: follow the toolbar preference on the NTP and while editing",
            "chrome/android/java/src/org/chromium/chrome/browser/ntp/NewTabPageCoordinator.java": "no bottom toolbar patch",
            "chrome/browser/ui/android/toolbar/java/res/layout/toolbar_phone.xml": '<ViewStub android:id="@+id/extensions_toolbar_container_stub"/>',
            "chrome/android/java/src/org/chromium/chrome/browser/toolbar/ToolbarManager.java": "mToolbarLayout,",
        }
        files.update(NEWTAB_FILES)
        files.update(SINGLE_PROCESS_FILES)
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            for relative, content in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            result = subprocess.run([sys.executable, str(VERIFY), str(root)])
            self.assertNotEqual(result.returncode, 0)

    def test_rejects_missing_toolbar_phone_extension_stub(self):
        files = {
            "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionsToolbarCoordinatorImpl.java": "return !mIsWebApp && mCanShowMenuIcon;",
            "chrome/android/java/src/org/chromium/chrome/browser/app/appmenu/AppMenuPropertiesDelegateImpl.java": "boolean shouldShowExtensionsItem() {\n        return true;\n    }",
            "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/ToolbarPositionController.java": "Helium: follow the toolbar preference on the NTP and while editing",
            "chrome/android/java/src/org/chromium/chrome/browser/ntp/NewTabPageCoordinator.java": "AddressBarPreference.isToolbarConfiguredToShowOnTop()",
            "chrome/browser/ui/android/toolbar/java/res/layout/toolbar_phone.xml": "<LinearLayout/>",
            "chrome/android/java/src/org/chromium/chrome/browser/toolbar/ToolbarManager.java": "mToolbarLayout,",
        }
        files.update(NEWTAB_FILES)
        files.update(SINGLE_PROCESS_FILES)
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            for relative, content in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            result = subprocess.run([sys.executable, str(VERIFY), str(root)])
            self.assertNotEqual(result.returncode, 0)

    def test_rejects_unguarded_toolbar_tablet_cast(self):
        files = {
            "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionsToolbarCoordinatorImpl.java": "return !mIsWebApp;",
            "chrome/android/java/src/org/chromium/chrome/browser/app/appmenu/AppMenuPropertiesDelegateImpl.java": "boolean shouldShowExtensionsItem() {\n        return true;\n    }",
            "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/ToolbarPositionController.java": "Helium: follow the toolbar preference on the NTP and while editing",
            "chrome/android/java/src/org/chromium/chrome/browser/ntp/NewTabPageCoordinator.java": "AddressBarPreference.isToolbarConfiguredToShowOnTop()",
            "chrome/browser/ui/android/toolbar/java/res/layout/toolbar_phone.xml": '<ViewStub android:id="@+id/extensions_toolbar_container_stub"/>',
            "chrome/android/java/src/org/chromium/chrome/browser/toolbar/ToolbarManager.java": "ExtensionsToolbarCoordinator.maybeCreate((ToolbarTablet) mToolbarLayout,",
        }
        files.update(NEWTAB_FILES)
        files.update(SINGLE_PROCESS_FILES)
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            for relative, content in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            result = subprocess.run([sys.executable, str(VERIFY), str(root)])
            self.assertNotEqual(result.returncode, 0)

    def test_rejects_corrupted_device_form_factor(self):
        files = {
            "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionsToolbarCoordinatorImpl.java": "return !mIsWebApp;",
            "chrome/android/java/src/org/chromium/chrome/browser/app/appmenu/AppMenuPropertiesDelegateImpl.java": "boolean shouldShowExtensionsItem() {\n        return true;\n    }",
            "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/ToolbarPositionController.java": "Helium: follow the toolbar preference on the NTP and while editing",
            "chrome/android/java/src/org/chromium/chrome/browser/ntp/NewTabPageCoordinator.java": "AddressBarPreference.isToolbarConfiguredToShowOnTop()",
            "chrome/browser/ui/android/toolbar/java/res/layout/toolbar_phone.xml": '<ViewStub android:id="@+id/extensions_toolbar_container_stub"/>',
            "chrome/android/java/src/org/chromium/chrome/browser/toolbar/ToolbarManager.java": "mToolbarLayout,",
            "ui/android/java/src/org/chromium/ui/base/DeviceFormFactor.java": (
                "public class DeviceFormFactor {\n"
                "  public static int getMinimumTabletWidthPx(DisplayAndroid d) {\n"
                "    return DisplayUtil.dpToPx(d, DeviceFormFactor.MINIMUM_TABLET_WIDTH_DP);\n"
                "  }\n"
                "}"
            ),
        }
        files.update(NEWTAB_FILES)
        files.update(SINGLE_PROCESS_FILES)
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            for relative, content in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            result = subprocess.run([sys.executable, str(VERIFY), str(root)])
            self.assertNotEqual(result.returncode, 0)

    def test_rejects_unguarded_motion_event_api(self):
        files = {
            "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionsToolbarCoordinatorImpl.java": "return !mIsWebApp;",
            "chrome/android/java/src/org/chromium/chrome/browser/app/appmenu/AppMenuPropertiesDelegateImpl.java": "boolean shouldShowExtensionsItem() {\n        return true;\n    }",
            "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/ToolbarPositionController.java": "Helium: follow the toolbar preference on the NTP and while editing",
            "chrome/android/java/src/org/chromium/chrome/browser/ntp/NewTabPageCoordinator.java": "AddressBarPreference.isToolbarConfiguredToShowOnTop()",
            "chrome/browser/ui/android/toolbar/java/res/layout/toolbar_phone.xml": '<ViewStub android:id="@+id/extensions_toolbar_container_stub"/>',
            "chrome/android/java/src/org/chromium/chrome/browser/toolbar/ToolbarManager.java": "mToolbarLayout,",
            "ui/android/java/src/org/chromium/ui/base/EventForwarder.java": (
                "class EventForwarder {\n"
                "    private static boolean validateMotionEvent(MotionEvent event) {\n"
                "        return !Float.isFinite(event.getRawX(0));\n"
                "    }\n"
                "}"
            ),
        }
        files.update(NEWTAB_FILES)
        files.update(SINGLE_PROCESS_FILES)
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            for relative, content in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            result = subprocess.run([sys.executable, str(VERIFY), str(root)])
            self.assertNotEqual(result.returncode, 0)

    def test_rejects_missing_newtab_override_fallback(self):
        files = {
            "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionsToolbarCoordinatorImpl.java": "return !mIsWebApp;",
            "chrome/android/java/src/org/chromium/chrome/browser/app/appmenu/AppMenuPropertiesDelegateImpl.java": "boolean shouldShowExtensionsItem() {\n        return true;\n    }",
            "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/ToolbarPositionController.java": "Helium: follow the toolbar preference on the NTP and while editing",
            "chrome/android/java/src/org/chromium/chrome/browser/ntp/NewTabPageCoordinator.java": "AddressBarPreference.isToolbarConfiguredToShowOnTop()",
            "chrome/browser/ui/android/toolbar/java/res/layout/toolbar_phone.xml": '<ViewStub android:id="@+id/extensions_toolbar_container_stub"/>',
            "chrome/android/java/src/org/chromium/chrome/browser/toolbar/ToolbarManager.java": "mToolbarLayout,",
        }
        files.update(NEWTAB_FILES)
        files.update(SINGLE_PROCESS_FILES)
        files["chrome/browser/extensions/extension_url_overrides.cc"] = "no fallback"
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            for relative, content in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            result = subprocess.run([sys.executable, str(VERIFY), str(root)])
            self.assertNotEqual(result.returncode, 0)


    def test_rejects_missing_single_process_bad_message_guard(self):
        files = {
            "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionsToolbarCoordinatorImpl.java": "return !mIsWebApp && mCanShowMenuIcon;",
            "chrome/android/java/src/org/chromium/chrome/browser/app/appmenu/AppMenuPropertiesDelegateImpl.java": "boolean shouldShowExtensionsItem() {\n        return true;\n    }",
            "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/ToolbarPositionController.java": "Helium: follow the toolbar preference on the NTP and while editing",
            "chrome/android/java/src/org/chromium/chrome/browser/ntp/NewTabPageCoordinator.java": "AddressBarPreference.isToolbarConfiguredToShowOnTop()",
            "chrome/browser/ui/android/toolbar/java/res/layout/toolbar_phone.xml": '<ViewStub android:id="@+id/extensions_toolbar_container_stub"/>',
            "chrome/android/java/src/org/chromium/chrome/browser/toolbar/ToolbarManager.java": (
                "ExtensionsToolbarCoordinator.maybeCreate(mToolbarLayout,\n"
                "if (mToolbarLayout instanceof ToolbarTablet) {\n"
                "    return ((ToolbarTablet) mToolbarLayout).areAnyToolbarComponentsMissingForWidth();\n"
                "}"
            ),
        }
        files.update(NEWTAB_FILES)
        files.update(SINGLE_PROCESS_FILES)
        files["content/browser/renderer_host/render_process_host_impl.cc"] = "NOTREACHED();"
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            for relative, content in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            result = subprocess.run([sys.executable, str(VERIFY), str(root)])
            self.assertNotEqual(result.returncode, 0)

    def test_rejects_restricted_bottom_toolbar_eligibility(self):
        files = {
            "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionsToolbarCoordinatorImpl.java": "return !mIsWebApp && mCanShowMenuIcon;",
            "chrome/android/java/src/org/chromium/chrome/browser/app/appmenu/AppMenuPropertiesDelegateImpl.java": "boolean shouldShowExtensionsItem() {\n        return true;\n    }",
            "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/ToolbarPositionController.java": "Helium: follow the toolbar preference on the NTP and while editing",
            "chrome/android/java/src/org/chromium/chrome/browser/ntp/NewTabPageCoordinator.java": "AddressBarPreference.isToolbarConfiguredToShowOnTop()",
            "chrome/browser/ui/android/toolbar/java/res/layout/toolbar_phone.xml": '<ViewStub android:id="@+id/extensions_toolbar_container_stub"/>',
            "chrome/android/java/src/org/chromium/chrome/browser/toolbar/ToolbarManager.java": (
                "ExtensionsToolbarCoordinator.maybeCreate(mToolbarLayout,\n"
                "if (mToolbarLayout instanceof ToolbarTablet) {\n"
                "    return ((ToolbarTablet) mToolbarLayout).areAnyToolbarComponentsMissingForWidth();\n"
                "}"
            ),
        }
        files.update(NEWTAB_FILES)
        files.update(SINGLE_PROCESS_FILES)
        files[
            "chrome/browser/ui/android/bottombar/java/src/org/chromium/chrome/browser/ui/"
            "bottombar/BottomBarConfigUtils.java"
        ] = "return !DeviceInfo.isAutomotive() && ChromeFeatureList.sAndroidBottomBar.isEnabled();"
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            for relative, content in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            result = subprocess.run([sys.executable, str(VERIFY), str(root)])
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
