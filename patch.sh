#!/bin/bash

SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"

mkdir -p chrome/android/java/res_helium_base
for icon in $(find chrome/android/java/res_helium_base -type f -name '*.png'); do convert $icon -fill navy -tint 36 $icon; done
sed -i 's|<application |<application android:extractNativeLibs="false" |' chrome/android/java/AndroidManifest.xml
sed -i 's|<data android:mimeType="message/rfc822"/>|<data android:mimeType="message/rfc822"/><data android:mimeType="application/pdf"/>|' chrome/android/java/AndroidManifest.xml
sed -i '/com.google.ar.core.min_apk_version/d' third_party/arcore-android-sdk-client/AndroidManifest_basesplit.xml
# sed -i 's|Google LLC|jqssun, Google LLC|' chrome/browser/ui/android/strings/android_chrome_strings.grd

sed -i '/safelyRemovePreference(prefFragment/d' helium/chromium_src/chrome/browser/language/android/java/src/org/chromium/chrome/browser/language/settings/LanguageSettingsExt.java
sed -i '/removeEntryForKey(fragmentName, "translate_switch")/d' chrome/android/java/src/org/chromium/chrome/browser/settings/search/SettingsSearchCoordinator.java
sed -i '/feature_overrides.EnableFeature(::features::kSkipVulkanBlocklist);/d' chrome/browser/chrome_browser_field_trials.cc
sed -i '/feature_overrides.EnableFeature(::features::kDefaultANGLEVulkan);/d' chrome/browser/chrome_browser_field_trials.cc
sed -i '/feature_overrides.EnableFeature(::features::kVulkanFromANGLE);/d' chrome/browser/chrome_browser_field_trials.cc
sed -i '/feature_overrides.EnableFeature(::features::kDefaultPassthroughCommandDecoder);/d' chrome/browser/chrome_browser_field_trials.cc
# Chromium 152 moves desktop-Android feature enablement into field trials.
sed -i '/#if BUILDFLAG(IS_DESKTOP_ANDROID)/{
a\
feature_overrides.EnableFeature(chrome::android::kSubmenusInAppMenu);\
feature_overrides.EnableFeature(features::kAndroidDevToolsFrontend);\
feature_overrides.EnableFeature(kAndroidMediaPicker);\
feature_overrides.EnableFeature(features::kUserMediaScreenCapturing);\
feature_overrides.EnableFeature(media::kAndroidEnableBackgroundMediaCapturing);\
feature_overrides.EnableFeature(media::kAutoPictureInPictureAndroid);\
feature_overrides.EnableFeature(media::kContextMenuPictureInPictureAndroid);\
feature_overrides.EnableFeature(chrome::android::kLoadAllTabsAtStartup);\
#if 0
d}' chrome/browser/chrome_browser_field_trials.cc
sed -i '/^bool ShouldFallbackToSWIfGLES3NotSupported() {$/,/^}$/ s|^  return true;$|  return false;|' ui/gl/gl_features.cc # virt

# sed -i 's|int ExpirationMilestoneForFlag(const char\* flag) {|int ExpirationMilestoneForFlag(const char* flag) { if ((true)) return -1;|' chrome/browser/unexpire_flags.cc
for flag in "align-wakeups" "android-bottom-bar" "cct-open-in-browser-button-if-allowed-by-embedder" "darken-websites-checkbox-in-themes-setting" "enable-accessibility-sequential-focus" "enforce-incognito-isolation" "inline-pdf-v2" "jump-start-omnibox" "offline-auto-fetch" "use-fullscreen-insets-api"; do
    sed -i "/\"name\": \"$flag\"/,/}/ s/\"expiry_milestone\": [0-9]\+/\"expiry_milestone\": -1/" chrome/browser/flag-metadata.json
done

# dev
sed -i 's/BASE_FEATURE(kSubmenusInAppMenu, base::FEATURE_DISABLED_BY_DEFAULT);/BASE_FEATURE(kSubmenusInAppMenu, base::FEATURE_ENABLED_BY_DEFAULT);/' chrome/browser/flags/android/chrome_feature_list.cc
sed -i '/BASE_FEATURE(kTaskManagerClank,/,/);/ s/base::FEATURE_DISABLED_BY_DEFAULT/base::FEATURE_ENABLED_BY_DEFAULT/' chrome/browser/task_manager/common/task_manager_features.cc
sed -i 's/BASE_FEATURE(kAndroidDevToolsFrontend, base::FEATURE_DISABLED_BY_DEFAULT);/BASE_FEATURE(kAndroidDevToolsFrontend, base::FEATURE_ENABLED_BY_DEFAULT);/' content/public/common/content_features.cc
sed -i 's|if (!DeviceFormFactor.isNonMultiDisplayContextOnTablet(mContext)) {|if (false) {|' chrome/android/java/src/org/chromium/chrome/browser/tabbed_mode/TabbedAppMenuPropertiesDelegate.java
sed -i 's|boolean shouldShowDeveloperMenu() {|boolean shouldShowDeveloperMenu() { if (true) return DevToolsWindowAndroid.isDevToolsAllowedFor(getProfile(), mItemDelegate.getWebContents());|' chrome/android/java/src/org/chromium/chrome/browser/contextmenu/ChromeContextMenuPopulator.java
sed -i 's|TabUtils.isUsingDesktopUserAgent(mItemDelegate.getWebContents())|(true \|\| TabUtils.isUsingDesktopUserAgent(mItemDelegate.getWebContents()))|' chrome/android/java/src/org/chromium/chrome/browser/contextmenu/ChromeContextMenuPopulator.java
perl -0pi -e 's|(<activity\n            android:name="org\.chromium\.chrome\.browser\.devtools\.DevToolsActivity"\n            android:theme="\@style/Theme\.Chromium\.Activity"\n            android:exported="false"\n)(?!            android:resizeableActivity="true"\n)|$1            android:resizeableActivity="true"\n|' chrome/android/java/AndroidManifest.xml
perl -0pi -e 's|(<activity\n            android:name="org\.chromium\.chrome\.browser\.devtools\.DevToolsActivity"(?:(?!</activity>).)*?            android:resizeableActivity="true"\n)(?!            android:supportsPictureInPicture="true"\n)|$1            android:supportsPictureInPicture="true"\n|s' chrome/android/java/AndroidManifest.xml
perl -0pi -e 's|(<activity\n            android:name="org\.chromium\.chrome\.browser\.devtools\.DevToolsActivity"(?:(?!</activity>).)*?            \{\{ self\.extra_web_rendering_activity_definitions\(\) \}\}\n)(?!            <property android:name="android\.window\.PROPERTY_SUPPORTS_MULTI_INSTANCE_SYSTEM_UI")|$1            <property android:name="android.window.PROPERTY_SUPPORTS_MULTI_INSTANCE_SYSTEM_UI"\n                android:value="true" />\n|s' chrome/android/java/AndroidManifest.xml
grep -q 'org.chromium.chrome.browser.flags.ActivityType' chrome/android/java/src/org/chromium/chrome/browser/customtabs/features/minimizedcustomtab/CustomTabMinimizationManager.java || sed -i '/import org.chromium.chrome.browser.customtabs.CustomTabsConnection;/a\import org.chromium.chrome.browser.flags.ActivityType;' chrome/android/java/src/org/chromium/chrome/browser/customtabs/features/minimizedcustomtab/CustomTabMinimizationManager.java
grep -q 'mIntentData.getActivityType() == ActivityType.DEV_TOOLS' chrome/android/java/src/org/chromium/chrome/browser/customtabs/features/minimizedcustomtab/CustomTabMinimizationManager.java || sed -i '/if (!(mTabProvider.get() != null)) return;/a\
        if (mIntentData.getActivityType() == ActivityType.DEV_TOOLS) {\
            mActivity.moveTaskToBack(true);\
            return;\
        }' chrome/android/java/src/org/chromium/chrome/browser/customtabs/features/minimizedcustomtab/CustomTabMinimizationManager.java
grep -q 'org.chromium.chrome.browser.flags.ActivityType' chrome/android/java/src/org/chromium/chrome/browser/customtabs/features/minimizedcustomtab/MinimizedFeatureUtils.java || sed -i '/import org.chromium.chrome.browser.flags.ChromeFeatureList;/a\import org.chromium.chrome.browser.flags.ActivityType;' chrome/android/java/src/org/chromium/chrome/browser/customtabs/features/minimizedcustomtab/MinimizedFeatureUtils.java
grep -q 'intentDataProvider.getActivityType() == ActivityType.DEV_TOOLS' chrome/android/java/src/org/chromium/chrome/browser/customtabs/features/minimizedcustomtab/MinimizedFeatureUtils.java || sed -i '/public static boolean shouldEnableMinimizedCustomTabs(/,/if (intentDataProvider.hasTargetNetwork()) return false;/ s|if (intentDataProvider.hasTargetNetwork()) return false;|if (intentDataProvider.getActivityType() == ActivityType.DEV_TOOLS) return false;\n        if (intentDataProvider.hasTargetNetwork()) return false;|' chrome/android/java/src/org/chromium/chrome/browser/customtabs/features/minimizedcustomtab/MinimizedFeatureUtils.java
sed -i '/public @TitleVisibility int getTitleVisibilityState()/,/^    }/ s|return TitleVisibility.VISIBLE;|return TitleVisibility.HIDDEN;|' chrome/android/java/src/org/chromium/chrome/browser/devtools/DevToolsIntentDataProvider.java
sed -i '/public boolean isCloseButtonEnabled()/,/^    }/ s|return false;|return true;|' chrome/android/java/src/org/chromium/chrome/browser/devtools/DevToolsIntentDataProvider.java
sed -i 's#connection.shouldEnableOmniboxForIntent(mIntentDataProvider.get());#connection.shouldEnableOmniboxForIntent(mIntentDataProvider.get())\n                        || mIntentDataProvider.get().getActivityType() == ActivityType.DEV_TOOLS;#' chrome/android/java/src/org/chromium/chrome/browser/customtabs/BaseCustomTabRootUiCoordinator.java
grep -q 'org.chromium.cc.input.BrowserControlsState' chrome/android/java/src/org/chromium/chrome/browser/devtools/DevToolsActivity.java || sed -i '/import org.chromium.base.ContextUtils;/a\import org.chromium.cc.input.BrowserControlsState;' chrome/android/java/src/org/chromium/chrome/browser/devtools/DevToolsActivity.java
grep -q 'android.view.Gravity' chrome/android/java/src/org/chromium/chrome/browser/devtools/DevToolsActivity.java || sed -i '/import android.content.Intent;/a\import android.view.Gravity;' chrome/android/java/src/org/chromium/chrome/browser/devtools/DevToolsActivity.java
grep -q 'android.view.ViewGroup' chrome/android/java/src/org/chromium/chrome/browser/devtools/DevToolsActivity.java || sed -i '/import android.view.Gravity;/a\import android.view.ViewGroup;' chrome/android/java/src/org/chromium/chrome/browser/devtools/DevToolsActivity.java
grep -q 'android.widget.Button' chrome/android/java/src/org/chromium/chrome/browser/devtools/DevToolsActivity.java || sed -i '/import android.view.ViewGroup;/a\import android.widget.Button;' chrome/android/java/src/org/chromium/chrome/browser/devtools/DevToolsActivity.java
grep -q 'android.widget.FrameLayout' chrome/android/java/src/org/chromium/chrome/browser/devtools/DevToolsActivity.java || sed -i '/import android.widget.Button;/a\import android.widget.FrameLayout;' chrome/android/java/src/org/chromium/chrome/browser/devtools/DevToolsActivity.java
grep -q 'addInspectedPageSwitcher(WebContents devToolsWebContents)' chrome/android/java/src/org/chromium/chrome/browser/devtools/DevToolsActivity.java || perl -0pi -e 's~(\n    \@Override\n    public void finishNativeInitialization\(\) \{)~\n    private void addInspectedPageSwitcher(WebContents devToolsWebContents) {\n        Button switchButton = new Button(this);\n        switchButton.setText("Page");\n        switchButton.setAllCaps(false);\n        switchButton.setOnClickListener(\n                v -> DevToolsWindowAndroid.activateInspectedPage(devToolsWebContents));\n        FrameLayout.LayoutParams params =\n                new FrameLayout.LayoutParams(\n                        ViewGroup.LayoutParams.WRAP_CONTENT,\n                        ViewGroup.LayoutParams.WRAP_CONTENT,\n                        Gravity.TOP | Gravity.END);\n        int margin = (int) (8 * getResources().getDisplayMetrics().density);\n        params.setMargins(margin, margin, margin, margin);\n        addContentView(switchButton, params);\n    }\n$1~' chrome/android/java/src/org/chromium/chrome/browser/devtools/DevToolsActivity.java
grep -q 'addInspectedPageSwitcher(webContents)' chrome/android/java/src/org/chromium/chrome/browser/devtools/DevToolsActivity.java || perl -0pi -e 's~(DevToolsWindowAndroid\.attachToBrowser\(\n                    webContents, task\.getOrCreateNativeBrowserWindowPtr\(profile\)\);\n)~$1            addInspectedPageSwitcher(webContents);\n~' chrome/android/java/src/org/chromium/chrome/browser/devtools/DevToolsActivity.java
grep -q 'setBrowserControlsState(BrowserControlsState.SHOWN)' chrome/android/java/src/org/chromium/chrome/browser/devtools/DevToolsActivity.java || sed -i '/super.finishNativeInitialization();/a\        getCustomTabToolbarCoordinator().setBrowserControlsState(BrowserControlsState.SHOWN);' chrome/android/java/src/org/chromium/chrome/browser/devtools/DevToolsActivity.java
grep -q 'public static void activateInspectedPage' chrome/browser/devtools/android/java/src/org/chromium/chrome/browser/devtools/DevToolsWindowAndroid.java || perl -0pi -e 's~(\n    /\*\*\n     \* Attaches the DevTools frontend web contents to the browser window\.)~\n    public static void activateInspectedPage(WebContents webContents) {\n        DevToolsWindowAndroidJni.get().activateInspectedPage(webContents);\n    }\n$1~' chrome/browser/devtools/android/java/src/org/chromium/chrome/browser/devtools/DevToolsWindowAndroid.java
grep -q '^        void activateInspectedPage(WebContents webContents);' chrome/browser/devtools/android/java/src/org/chromium/chrome/browser/devtools/DevToolsWindowAndroid.java || sed -i '/void attachToBrowser(WebContents webContents, long nativeBrowserWindowPtr);/i\        void activateInspectedPage(WebContents webContents);\n' chrome/browser/devtools/android/java/src/org/chromium/chrome/browser/devtools/DevToolsWindowAndroid.java
grep -q 'web_contents_delegate.h' chrome/browser/devtools/android/devtools_window_android.cc || sed -i '/#include "content\/public\/browser\/web_contents.h"/a\#include "content/public/browser/web_contents_delegate.h"' chrome/browser/devtools/android/devtools_window_android.cc
grep -q 'JNI_DevToolsWindowAndroid_ActivateInspectedPage' chrome/browser/devtools/android/devtools_window_android.cc || perl -0pi -e 's~(\nstatic void JNI_DevToolsWindowAndroid_AttachToBrowser\()~\nstatic void JNI_DevToolsWindowAndroid_ActivateInspectedPage(\n    JNIEnv* env,\n    const jni_zero::JavaRef<jobject>& java_web_contents) {\n#if BUILDFLAG(ENABLE_DEVTOOLS_FRONTEND)\n  content::WebContents* web_contents =\n      content::WebContents::FromJavaWebContents(java_web_contents);\n  DevToolsWindow* window = DevToolsWindow::AsDevToolsWindow(web_contents);\n  if (!window) {\n    return;\n  }\n  content::WebContents* inspected_web_contents =\n      window->GetInspectedWebContents();\n  if (!inspected_web_contents || !inspected_web_contents->GetDelegate()) {\n    return;\n  }\n  inspected_web_contents->GetDelegate()->ActivateContents(\n      inspected_web_contents);\n  inspected_web_contents->Focus();\n#endif\n}\n$1~' chrome/browser/devtools/android/devtools_window_android.cc
grep -q 'components/tabs/public/tab_interface.h' chrome/browser/devtools/devtools_window.cc || sed -i '/#include "components\/strings\/grit\/components_strings.h"/a\#include "components/tabs/public/tab_interface.h"' chrome/browser/devtools/devtools_window.cc
grep -q 'HeliumAndroidDevToolsSameWindow' chrome/browser/devtools/devtools_window.cc || perl -0pi -e 's~#if BUILDFLAG\(IS_ANDROID\)\n  if \(!owned_main_web_contents_ \|\| launched_activity_\) \{\n    return;\n  \}\n  JNIEnv\* env = base::android::AttachCurrentThread\(\);\n  Java_DevToolsActivity_launchDevToolsActivity\(\n      env, main_web_contents_->GetJavaWebContents\(\)\);\n\n  launched_activity_ = true;\n\n  OverrideAndSyncDevToolsRendererPrefs\(\);~#if BUILDFLAG(IS_ANDROID)\n  if (!owned_main_web_contents_ || launched_activity_) {\n    return;\n  }\n  content::WebContents* inspected_web_contents = GetInspectedWebContents();\n  tabs::TabInterface* inspected_tab =\n      inspected_web_contents\n          ? tabs::TabInterface::MaybeGetFromContents(inspected_web_contents)\n          : nullptr;\n  BrowserWindowInterface* inspected_browser =\n      inspected_tab ? inspected_tab->GetBrowserWindowInterface() : nullptr;\n  TabListInterface* inspected_tab_list =\n      inspected_browser ? TabListInterface::From(inspected_browser) : nullptr;\n  if (inspected_tab_list) {\n    // HeliumAndroidDevToolsSameWindow: put DevTools in the inspected page window.\n    AttachToBrowser(inspected_browser);\n  } else {\n    JNIEnv* env = base::android::AttachCurrentThread();\n    Java_DevToolsActivity_launchDevToolsActivity(\n        env, main_web_contents_->GetJavaWebContents());\n  }\n\n  launched_activity_ = true;\n\n  OverrideAndSyncDevToolsRendererPrefs();~' chrome/browser/devtools/devtools_window.cc
perl -0pi -e 's~(#if BUILDFLAG\(IS_ANDROID\)\n)    NOTIMPLEMENTED\(\);\n(#else\n    if \(browser_\) \{)~$1    WebContents* inspected_tab = GetInspectedWebContents();\n    if (inspected_tab && inspected_tab->GetDelegate()) {\n      inspected_tab->GetDelegate()->ActivateContents(inspected_tab);\n      inspected_tab->Focus();\n    }\n$2~' chrome/browser/devtools/devtools_window.cc
perl -0pi -e 's~(#if BUILDFLAG\(IS_ANDROID\)\n)  NOTIMPLEMENTED\(\);\n(#else\n  if \(is_docked_ && GetInspectedBrowserWindow\(\)\) \{)~$1  tabs::TabInterface* devtools_tab =\n      tabs::TabInterface::MaybeGetFromContents(main_web_contents_);\n  BrowserWindowInterface* devtools_browser =\n      devtools_tab ? devtools_tab->GetBrowserWindowInterface() : nullptr;\n  TabListInterface* tab_list =\n      devtools_browser ? TabListInterface::From(devtools_browser) : nullptr;\n  if (tab_list && devtools_tab) {\n    tab_list->ActivateTab(devtools_tab->GetHandle());\n    main_web_contents_->Focus();\n  }\n$2~' chrome/browser/devtools/devtools_window.cc
grep -q 'InspectElementCompleted.AndroidActivateWindow' chrome/browser/devtools/devtools_window.cc || perl -0pi -e 's~void DevToolsWindow::InspectElementCompleted\(\) \{\n  if \(!inspect_element_start_time_\.is_null\(\)\) \{\n    UMA_HISTOGRAM_TIMES\("DevTools\.InspectElement",\n                        base::TimeTicks::Now\(\) - inspect_element_start_time_\);\n    inspect_element_start_time_ = base::TimeTicks\(\);\n  \}\n\}~void DevToolsWindow::InspectElementCompleted() {\n  if (!inspect_element_start_time_.is_null()) {\n    UMA_HISTOGRAM_TIMES("DevTools.InspectElement",\n                        base::TimeTicks::Now() - inspect_element_start_time_);\n    inspect_element_start_time_ = base::TimeTicks();\n  }\n#if BUILDFLAG(IS_ANDROID)\n  // InspectElementCompleted.AndroidActivateWindow: return to DevTools after picking an element.\n  ActivateWindow();\n#endif\n}~' chrome/browser/devtools/devtools_window.cc
grep -q 'tab_list->ActivateTab(tab->GetHandle())' chrome/browser/devtools/devtools_window.cc || perl -0pi -e 's~  auto\* tab_list = TabListInterface::From\(browser\);\n  if \(!tab_list\) \{\n    return;\n  \}\n  tab_list->InsertWebContentsAt\(0, std::move\(owned_web_contents\), false,\n                                std::nullopt\);~  auto* tab_list = TabListInterface::From(browser);\n  if (!tab_list) {\n    return;\n  }\n  browser_ = browser;\n  tabs::TabInterface* tab = tab_list->InsertWebContentsAt(\n      0, std::move(owned_web_contents), false, std::nullopt);\n  if (tab) {\n    tab_list->ActivateTab(tab->GetHandle());\n  }~' chrome/browser/devtools/devtools_window.cc

# ext: app menu
sed -i 's|return ExtensionUi.isEnabled(getProfileFromTabModel());|return true;|' chrome/android/java/src/org/chromium/chrome/browser/tabbed_mode/TabbedAppMenuPropertiesDelegate.java
# The toolbar icon toggles the menu, so the duplicate close button is not needed.
perl -0pi -e 's|\n        android:padding="12dp"||g; s|(android:id="\@\+id/extensions_menu_close_button"\n)(?!        android:visibility="gone"\n)|$1        android:visibility="gone"\n|' chrome/browser/ui/android/extensions/java/res/layout/extensions_menu_header.xml
sed -i '/coordinator.showExtensionsMenu();/c\            if (coordinator != null) {\
                coordinator.showExtensionsMenu();\
            } else {\
                LoadUrlParams params = new LoadUrlParams(UrlConstants.CHROME_EXTENSIONS_URL, PageTransition.AUTO_TOPLEVEL);\
                if (currentTab == null) {\
                    getTabCreator(getCurrentTabModel().isIncognito()).createNewTab(params, TabLaunchType.FROM_CHROME_UI, /* parent= */ null);\
                } else {\
                    currentTab.loadUrl(params);\
                }\
            }' chrome/android/java/src/org/chromium/chrome/browser/ChromeTabbedActivity.java
grep -q 'org.chromium.chrome.browser.ui.toolbar.InvocationSource' chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionsMenuMediator.java || sed -i '/import org.chromium.chrome.browser.ui.extensions.ExtensionsToolbarBridge;/a\import org.chromium.chrome.browser.ui.toolbar.InvocationSource;' chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionsMenuMediator.java
grep -q 'ExtensionsToolbarBridge mToolbarBridge;' chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionsMenuMediator.java || sed -i '/private final ExtensionsMenuBridge mMenuBridge;/a\    private ExtensionsToolbarBridge mToolbarBridge;' chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionsMenuMediator.java
sed -i 's|private final ExtensionsToolbarBridge mToolbarBridge;|private ExtensionsToolbarBridge mToolbarBridge;|' chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionsMenuMediator.java
grep -q 'mToolbarBridge = toolbarBridge;' chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionsMenuMediator.java || perl -0pi -e 's|(\n[ \t]*)(mMenuBridge[ \t]*=)|$1mToolbarBridge = toolbarBridge;\n$1$2|' chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionsMenuMediator.java
sed -i 's|(view) -> openExtensionFromMenu(entry.id))|(view) -> mMenuBridge.executeAction(entry.id))|' chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionsMenuMediator.java
sed -i 's|(view) -> openUrlFromMenu(UrlConstants.CHROME_EXTENSIONS_ID_URL + entry.id))|(view) -> mMenuBridge.executeAction(entry.id))|' chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionsMenuMediator.java
sed -i 's|(view) -> mToolbarBridge.executeUserAction(entry.id, InvocationSource.TOOLBAR_BUTTON))|(view) -> mMenuBridge.executeAction(entry.id))|' chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionsMenuMediator.java
sed -i 's|(view) -> openExtensionOptionsFromMenu(entry.id))|(view) -> mMenuBridge.executeAction(entry.id))|' chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionsMenuMediator.java
perl -0pi -e 's|if \(hasPoppedOutAction\(\) && itemWidth <= availableWidth\) \{\n            mCanShowPoppedOutAction = true;\n            return itemWidth;\n        \} else \{\n            mCanShowPoppedOutAction = false;\n            return 0;\n        \}|if (hasPoppedOutAction()) {\n            mCanShowPoppedOutAction = true;\n            return itemWidth;\n        } else {\n            mCanShowPoppedOutAction = false;\n            return 0;\n        }|' chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionActionListMediator.java
perl -0pi -e 's|if \(findIndexForId\(actionId\) == -1\) \{\n            mPoppedOutActionId = actionId;\n        \}|if (findIndexForId(actionId) == -1) {\n            mPoppedOutActionId = actionId;\n            mCanShowPoppedOutAction = true;\n            reconcileActionItems();\n        }|' chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionActionListMediator.java
grep -q 'private void openExtensionOptionsFromMenu' chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionsMenuMediator.java || sed -i '/private void openUrlFromMenu(String url) {/i\
    private void openExtensionOptionsFromMenu(String extensionId) {\
        String optionsUrl = mMenuBridge.getOptionsPageUrl(extensionId);\
        if (optionsUrl != null && !optionsUrl.isEmpty()) {\
            openUrlFromMenu(optionsUrl);\
            return;\
        }\
        if (mToolbarBridge != null) {\
            mToolbarBridge.executeUserAction(extensionId, InvocationSource.TOOLBAR_BUTTON);\
            return;\
        }\
        mMenuBridge.executeAction(extensionId);\
    }\
' chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionsMenuMediator.java
grep -q 'getOptionsPageUrl(String extensionId)' chrome/browser/ui/android/extensions/java/src/org/chromium/chrome/browser/ui/extensions/ExtensionsMenuBridge.java || sed -i '/public void executeAction(String extensionId) {/i\
    public String getOptionsPageUrl(String extensionId) {\
        return ExtensionsMenuBridgeJni.get()\
                .getOptionsPageUrl(mNativeExtensionsMenuDelegateAndroid, extensionId);\
    }\
' chrome/browser/ui/android/extensions/java/src/org/chromium/chrome/browser/ui/extensions/ExtensionsMenuBridge.java
grep -q '^        String getOptionsPageUrl(' chrome/browser/ui/android/extensions/java/src/org/chromium/chrome/browser/ui/extensions/ExtensionsMenuBridge.java || perl -0pi -e 's|(\n\s*\@NativeMethods\n\s*public interface Natives \{\n)|$1        \@JniType("std::string")\n        String getOptionsPageUrl(\n                long nativeExtensionsMenuDelegateAndroid,\n                \@JniType("std::string") String extensionId);\n\n|' chrome/browser/ui/android/extensions/java/src/org/chromium/chrome/browser/ui/extensions/ExtensionsMenuBridge.java
grep -q '#include <string>' chrome/browser/ui/android/extensions/extensions_menu_delegate_android.h || sed -i '/^#include "base\/android\/jni_android.h"/i\#include <string>' chrome/browser/ui/android/extensions/extensions_menu_delegate_android.h
grep -q 'GetOptionsPageUrl(JNIEnv' chrome/browser/ui/android/extensions/extensions_menu_delegate_android.h || sed -i '/void ExecuteAction(JNIEnv\* env, const extensions::ExtensionId& extension_id);/a\  std::string GetOptionsPageUrl(JNIEnv* env, const std::string& extension_id);' chrome/browser/ui/android/extensions/extensions_menu_delegate_android.h
grep -q 'extensions/common/manifest_handlers/options_page_info.h' chrome/browser/ui/android/extensions/extensions_menu_delegate_android.cc || sed -i '/#include "chrome\/browser\/ui\/android\/extensions\/extension_action_delegate_android.h"/a\#include "chrome/browser/profiles/profile.h"\n#include "extensions/browser/extension_registry.h"\n#include "extensions/common/manifest_handlers/options_page_info.h"' chrome/browser/ui/android/extensions/extensions_menu_delegate_android.cc
grep -q 'ExtensionsMenuDelegateAndroid::GetOptionsPageUrl' chrome/browser/ui/android/extensions/extensions_menu_delegate_android.cc || sed -i '/void ExtensionsMenuDelegateAndroid::ExecuteAction(/i\
std::string ExtensionsMenuDelegateAndroid::GetOptionsPageUrl(\
    JNIEnv* env,\
    const std::string& extension_id) {\
  extensions::ExtensionRegistry* registry =\
      extensions::ExtensionRegistry::Get(browser_->GetProfile());\
  if (!registry) {\
    return std::string();\
  }\
  const extensions::Extension* extension =\
      registry->enabled_extensions().GetByID(extension_id);\
  if (!extension || !extensions::OptionsPageInfo::HasOptionsPage(extension)) {\
    return std::string();\
  }\
  const GURL& options_url =\
      extensions::OptionsPageInfo::GetOptionsPage(extension);\
  return options_url.is_valid() ? options_url.spec() : std::string();\
}\
' chrome/browser/ui/android/extensions/extensions_menu_delegate_android.cc
sed -i '/#include "chrome\/browser\/extensions\/extension_view_host_factory.h"/a\#include "chrome/browser/extensions/extension_tab_util.h"\n#include "chrome/browser/profiles/profile.h"\n#include "chrome/browser/ui/browser_window/public/browser_window_interface.h"\n#include "extensions/browser/extension_registry.h"' chrome/browser/ui/android/extensions/extension_action_delegate_android.cc
perl -0pi -e 's|void ExtensionActionDelegateAndroid::ShowContextMenuAsFallback\(\) \{\n  const extensions::Extension\* extension =\n      extensions::ExtensionRegistry::Get\(browser_->GetProfile\(\)\)\n          ->enabled_extensions\(\)\n          \.GetByID\(action_id_\);\n  if \(extension &&\n      extensions::ExtensionTabUtil::OpenOptionsPage\(extension, browser_\)\) \{\n    return;\n  \}\n\n  toolbar_android_->ShowContextMenu\(action_id_\);\n\}|void ExtensionActionDelegateAndroid::ShowContextMenuAsFallback() {\n  toolbar_android_->ShowContextMenu(action_id_);\n}|' chrome/browser/ui/android/extensions/extension_action_delegate_android.cc

# Menu action popups should be anchored to the clicked menu row, not by
# temporarily popping the extension action into the toolbar.
BRIDGE=chrome/browser/ui/android/extensions/java/src/org/chromium/chrome/browser/ui/extensions/ExtensionsMenuBridge.java
TOOLBAR_BRIDGE=chrome/browser/ui/android/extensions/java/src/org/chromium/chrome/browser/ui/extensions/ExtensionsToolbarBridge.java
MENU_MEDIATOR=chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionsMenuMediator.java
MENU_COORDINATOR=chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionsMenuCoordinator.java
TOOLBAR=chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionsToolbarCoordinatorImpl.java
MENU_DELEGATE_CC=chrome/browser/ui/android/extensions/extensions_menu_delegate_android.cc
MENU_DELEGATE_H=chrome/browser/ui/android/extensions/extensions_menu_delegate_android.h
TOOLBAR_ANDROID_CC=chrome/browser/ui/android/extensions/extensions_toolbar_android.cc
TOOLBAR_ANDROID_H=chrome/browser/ui/android/extensions/extensions_toolbar_android.h
ACTION_DELEGATE_CC=chrome/browser/ui/android/extensions/extension_action_delegate_android.cc
ACTION_DELEGATE_H=chrome/browser/ui/android/extensions/extension_action_delegate_android.h
ACTION_LIST_MEDIATOR=chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionActionListMediator.java
EXTENSION_ACTION_POPUP=chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionActionPopup.java
EXTENSION_POPUP_CONTENTS=chrome/browser/ui/android/extensions/java/src/org/chromium/chrome/browser/ui/extensions/ExtensionActionPopupContents.java
EXTENSION_POPUP_CONTENTS_CC=chrome/browser/ui/android/extensions/extension_action_popup_contents.cc
EXTENSION_POPUP_CONTENTS_H=chrome/browser/ui/android/extensions/extension_action_popup_contents.h
EXTENSION_ACTION_VIEW_MODEL=chrome/browser/ui/extensions/extension_action_view_model.cc
TABS_API_CC=chrome/browser/extensions/api/tabs/tabs_api.cc
TABS_EVENT_ROUTER_CC=chrome/browser/extensions/api/tabs/tabs_event_router.cc
CHROME_EXTENSIONS_BROWSER_CLIENT=chrome/browser/extensions/chrome_extensions_browser_client.cc
EXTENSION_TAB_UTIL_CC=chrome/browser/extensions/extension_tab_util.cc
# Treat the toolbar extensions icon as a menu toggle.
sed -i '/private long mLastMenuDismissedAtMs;/d' "$MENU_COORDINATOR"
perl -0pi -e 's|\n                    if \(android\.os\.SystemClock\.uptimeMillis\(\) - mLastMenuDismissedAtMs\n                            < android\.view\.ViewConfiguration\.getDoubleTapTimeout\(\)\) \{\n                        return;\n                    \}||; s|\n                        mLastMenuDismissedAtMs = android\.os\.SystemClock\.uptimeMillis\(\);||' "$MENU_COORDINATOR"
grep -q 'private boolean mMenuWasShowing;' "$MENU_COORDINATOR" || sed -i '/ExtensionsMenuMediator mMediator;/a\    private boolean mMenuWasShowing;' "$MENU_COORDINATOR"
grep -q 'private boolean mConsumeMenuButtonTouch;' "$MENU_COORDINATOR" || sed -i '/private boolean mMenuWasShowing;/a\    private boolean mConsumeMenuButtonTouch;' "$MENU_COORDINATOR"
perl -0pi -e 's|(if \(mMediator != null\) \{\n                        mExtensionsMenuButton\.dismiss\(\);\n                        destroyMediator\(\);)\n                        mExtensionModels\.clear\(\);|$1|; s|(mExtensionsMenuButton\.setOnClickListener\(\n                \(view\) -> \{\n)(?!                    if \(mMediator != null\))|$1                    if (mMediator != null) {\n                        mExtensionsMenuButton.dismiss();\n                        destroyMediator();\n                        return;\n                    }\n|' "$MENU_COORDINATOR"
grep -q 'mExtensionsMenuButton.setOnTouchListener(' "$MENU_COORDINATOR" || perl -0pi -e 's~(\n        mExtensionsMenuButton\.addPopupListener\()~\n        mExtensionsMenuButton.setOnTouchListener(\n                (view, event) -> {\n                    int action = event.getActionMasked();\n                    if (action == android.view.MotionEvent.ACTION_DOWN && mMenuWasShowing) {\n                        mConsumeMenuButtonTouch = true;\n                        mExtensionsMenuButton.dismiss();\n                    }\n                    if (!mConsumeMenuButtonTouch) {\n                        return false;\n                    }\n                    if (action == android.view.MotionEvent.ACTION_UP\n                            || action == android.view.MotionEvent.ACTION_CANCEL) {\n                        mConsumeMenuButtonTouch = false;\n                    }\n                    return true;\n                });\n$1~' "$MENU_COORDINATOR"
perl -0pi -e 's|public void onPopupMenuShown\(\) \{\}|public void onPopupMenuShown() {\n                        mMenuWasShowing = true;\n                    }|; s|(public void onPopupMenuDismissed\(\) \{\n)(?!                        mExtensionsMenuButton\.post)|$1                        mExtensionsMenuButton.post(() -> mMenuWasShowing = false);\n|' "$MENU_COORDINATOR"
grep -q 'mExtensionsMenuButton.setOnTouchListener(null);' "$MENU_COORDINATOR" || sed -i '/mExtensionsMenuButton.setOnClickListener(null);/a\        mExtensionsMenuButton.setOnTouchListener(null);' "$MENU_COORDINATOR"
perl -0pi -e 's|if \(hasPoppedOutAction\(\)\) \{\n            mCanShowPoppedOutAction = true;\n            return itemWidth;\n        \} else \{\n            mCanShowPoppedOutAction = false;\n            return 0;\n        \}|if (hasPoppedOutAction() && itemWidth <= availableWidth) {\n            mCanShowPoppedOutAction = true;\n            return itemWidth;\n        } else {\n            mCanShowPoppedOutAction = false;\n            return 0;\n        }|' "$ACTION_LIST_MEDIATOR"
perl -0pi -e 's|if \(findIndexForId\(actionId\) == -1\) \{\n            mPoppedOutActionId = actionId;\n            mCanShowPoppedOutAction = true;\n            reconcileActionItems\(\);\n        \}|if (findIndexForId(actionId) == -1) {\n            mPoppedOutActionId = actionId;\n        }|' "$ACTION_LIST_MEDIATOR"
grep -q 'org.chromium.chrome.browser.tabmodel.TabModelSelector' "$MENU_COORDINATOR" || sed -i '/import org.chromium.chrome.browser.tabmodel.TabCreator;/a\import org.chromium.chrome.browser.tabmodel.TabModelSelector;' "$MENU_COORDINATOR"
grep -q 'org.chromium.components.embedder_support.contextmenu.ContextMenuPopulatorFactory' "$MENU_COORDINATOR" || sed -i '/import org.chromium.chrome.browser.user_education.UserEducationHelper;/a\import org.chromium.components.embedder_support.contextmenu.ContextMenuPopulatorFactory;' "$MENU_COORDINATOR"
grep -q 'org.chromium.content_public.browser.selection.SelectionDropdownMenuDelegate' "$MENU_COORDINATOR" || sed -i '/import org.chromium.content_public.browser.WebContents;/a\import org.chromium.content_public.browser.selection.SelectionDropdownMenuDelegate;' "$MENU_COORDINATOR"
grep -q 'org.chromium.ui.base.WindowAndroid' "$MENU_COORDINATOR" || sed -i '/import org.chromium.content_public.browser.selection.SelectionDropdownMenuDelegate;/a\import org.chromium.ui.base.WindowAndroid;' "$MENU_COORDINATOR"
grep -q 'private final WindowAndroid mWindowAndroid;' "$MENU_COORDINATOR" || sed -i '/private final TabCreator mTabCreator;/a\    private final WindowAndroid mWindowAndroid;' "$MENU_COORDINATOR"
grep -q 'mContextMenuPopulatorFactory' "$MENU_COORDINATOR" || sed -i '/private final TabCreator mTabCreator;/a\    private final @Nullable ContextMenuPopulatorFactory mContextMenuPopulatorFactory;\n    private final @Nullable SelectionDropdownMenuDelegate mSelectionDropdownMenuDelegate;\n    private final TabModelSelector mTabModelSelector;' "$MENU_COORDINATOR"
perl -0pi -e 's|(\n            WindowAndroid windowAndroid,){2,}|\n            WindowAndroid windowAndroid,|g' "$MENU_COORDINATOR"
grep -q 'WindowAndroid windowAndroid,' "$MENU_COORDINATOR" || perl -0pi -e 's|(\n            ExtensionsToolbarBridge extensionsToolbarBridge,)|$1\n            WindowAndroid windowAndroid,|' "$MENU_COORDINATOR"
perl -0pi -e 's|(\n            \@Nullable ContextMenuPopulatorFactory contextMenuPopulatorFactory,\n            \@Nullable SelectionDropdownMenuDelegate selectionDropdownMenuDelegate,\n            TabModelSelector tabModelSelector,){2,}|\n            \@Nullable ContextMenuPopulatorFactory contextMenuPopulatorFactory,\n            \@Nullable SelectionDropdownMenuDelegate selectionDropdownMenuDelegate,\n            TabModelSelector tabModelSelector,|g' "$MENU_COORDINATOR"
perl -0pi -e 's|(\n            ExtensionsToolbarBridge extensionsToolbarBridge,\n)            WindowAndroid windowAndroid,\n(\s*\@Nullable ContextMenuPopulatorFactory contextMenuPopulatorFactory,)|$1$2|g' "$MENU_COORDINATOR"
grep -q 'ContextMenuPopulatorFactory contextMenuPopulatorFactory,' "$MENU_COORDINATOR" || perl -0pi -e 's|(\n            ExtensionsToolbarBridge extensionsToolbarBridge,)|$1\n            \@Nullable ContextMenuPopulatorFactory contextMenuPopulatorFactory,\n            \@Nullable SelectionDropdownMenuDelegate selectionDropdownMenuDelegate,\n            TabModelSelector tabModelSelector,|' "$MENU_COORDINATOR"
perl -0pi -e 's|(\n        mContextMenuPopulatorFactory = contextMenuPopulatorFactory;\n        mSelectionDropdownMenuDelegate = selectionDropdownMenuDelegate;\n        mTabModelSelector = tabModelSelector;){2,}|\n        mContextMenuPopulatorFactory = contextMenuPopulatorFactory;\n        mSelectionDropdownMenuDelegate = selectionDropdownMenuDelegate;\n        mTabModelSelector = tabModelSelector;|g' "$MENU_COORDINATOR"
grep -q 'mContextMenuPopulatorFactory = contextMenuPopulatorFactory;' "$MENU_COORDINATOR" || perl -0pi -e 's|(\n        mTabCreator = tabCreator;\n        mTask = task;\n        mProfile = profile;\n)|        mContextMenuPopulatorFactory = contextMenuPopulatorFactory;\n        mSelectionDropdownMenuDelegate = selectionDropdownMenuDelegate;\n        mTabModelSelector = tabModelSelector;\n$1|' "$MENU_COORDINATOR"
grep -q 'mContextMenuPopulatorFactory = contextMenuPopulatorFactory;' "$MENU_COORDINATOR" || sed -i '/mExtensionsToolbarBridge = extensionsToolbarBridge;/a\        mContextMenuPopulatorFactory = contextMenuPopulatorFactory;\n        mSelectionDropdownMenuDelegate = selectionDropdownMenuDelegate;\n        mTabModelSelector = tabModelSelector;' "$MENU_COORDINATOR"
grep -q 'mWindowAndroid = windowAndroid;' "$MENU_COORDINATOR" || sed -i '/mExtensionsToolbarBridge = extensionsToolbarBridge;/a\        mWindowAndroid = windowAndroid;' "$MENU_COORDINATOR"
perl -0pi -e 's|(\n                        mContextMenuPopulatorFactory,\n                        mSelectionDropdownMenuDelegate,\n                        mTabModelSelector,){2,}|\n                        mContextMenuPopulatorFactory,\n                        mSelectionDropdownMenuDelegate,\n                        mTabModelSelector,|g' "$MENU_COORDINATOR"
perl -0pi -e 's|(\n                        mWindowAndroid,){2,}|\n                        mWindowAndroid,|g' "$MENU_COORDINATOR"
perl -0pi -e 's~(\n                        (?:mExtensionsToolbarBridge|extensionsToolbarBridge),)(?!\n                        mWindowAndroid,)~$1\n                        mWindowAndroid,~' "$MENU_COORDINATOR"
perl -0pi -e 's~(\n                        mWindowAndroid,)(?!\n                        mContextMenuPopulatorFactory,)~$1\n                        mContextMenuPopulatorFactory,\n                        mSelectionDropdownMenuDelegate,\n                        mTabModelSelector,~' "$MENU_COORDINATOR"
perl -0pi -e 's|(\n                        contextMenuPopulatorFactory,\n                        selectionDropdownMenuDelegate,\n                        tabModelSelector,){2,}|\n                        contextMenuPopulatorFactory,\n                        selectionDropdownMenuDelegate,\n                        tabModelSelector,|g' "$TOOLBAR"
perl -0pi -e 's~(\n                        windowAndroid,\n)                        contextMenuPopulatorFactory,\n                        selectionDropdownMenuDelegate,\n                        tabModelSelector,\n(\s*(?:task|mTask),)~$1$2~g' "$TOOLBAR"
perl -0pi -e 's|(\n                        mExtensionsToolbarBridge,\n)                        windowAndroid,\n(\s*contextMenuPopulatorFactory,)|$1$2|g' "$TOOLBAR"
perl -0pi -e 's~(\n                        currentTabSupplier,\n                        tabCreator,\n                        mExtensionsToolbarBridge,)(?!\n                        contextMenuPopulatorFactory,)~$1\n                        contextMenuPopulatorFactory,\n                        selectionDropdownMenuDelegate,\n                        tabModelSelector,~' "$TOOLBAR"
perl -0pi -e 's|mExtensionsToolbarBridge,\n                        mMenuButtonPinningDelegate,\n                        contextMenuPopulatorFactory,\n                        selectionDropdownMenuDelegate,\n                        tabModelSelector,|mExtensionsToolbarBridge,\n                        contextMenuPopulatorFactory,\n                        selectionDropdownMenuDelegate,\n                        tabModelSelector,\n                        mMenuButtonPinningDelegate,|' "$TOOLBAR"
grep -q 'import android.app.Activity;' "$MENU_MEDIATOR" || sed -i '/import android.content.Context;/i\import android.app.Activity;' "$MENU_MEDIATOR"
grep -q 'import android.view.View;' "$MENU_MEDIATOR" || sed -i '/import android.graphics.Bitmap;/a\import android.view.View;' "$MENU_MEDIATOR"
grep -q 'org.chromium.build.annotations.Nullable' "$MENU_MEDIATOR" || sed -i '/import org.chromium.build.annotations.NullMarked;/a\import org.chromium.build.annotations.Nullable;' "$MENU_MEDIATOR"
grep -q 'org.chromium.chrome.browser.tabmodel.TabModelSelector' "$MENU_MEDIATOR" || sed -i '/import org.chromium.chrome.browser.tab.TabLaunchType;/a\import org.chromium.chrome.browser.tabmodel.TabModelSelector;' "$MENU_MEDIATOR"
grep -q 'org.chromium.chrome.browser.ui.extensions.ExtensionActionPopupContents' "$MENU_MEDIATOR" || sed -i '/import org.chromium.chrome.browser.ui.extensions.ExtensionActionContextMenuBridge;/a\import org.chromium.chrome.browser.ui.extensions.ExtensionActionPopupContents;' "$MENU_MEDIATOR"
grep -q 'org.chromium.components.embedder_support.contextmenu.ContextMenuPopulatorFactory' "$MENU_MEDIATOR" || sed -i '/import org.chromium.components.embedder_support.util.UrlConstants;/i\import org.chromium.components.embedder_support.contextmenu.ContextMenuPopulatorFactory;' "$MENU_MEDIATOR"
grep -q 'org.chromium.content_public.browser.selection.SelectionDropdownMenuDelegate' "$MENU_MEDIATOR" || sed -i '/import org.chromium.content_public.browser.LoadUrlParams;/a\import org.chromium.content_public.browser.selection.SelectionDropdownMenuDelegate;' "$MENU_MEDIATOR"
grep -q 'org.chromium.ui.base.WindowAndroid' "$MENU_MEDIATOR" || sed -i '/import org.chromium.ui.base.PageTransition;/a\import org.chromium.ui.base.WindowAndroid;' "$MENU_MEDIATOR"
grep -q 'private final WindowAndroid mWindowAndroid;' "$MENU_MEDIATOR" || sed -i '/private final Context mContext;/a\    private final WindowAndroid mWindowAndroid;\n    private final TabModelSelector mTabModelSelector;\n    private final @Nullable ContextMenuPopulatorFactory mContextMenuPopulatorFactory;\n    private final @Nullable SelectionDropdownMenuDelegate mSelectionDropdownMenuDelegate;' "$MENU_MEDIATOR"
grep -q 'mPendingActionAnchorView' "$MENU_MEDIATOR" || sed -i '/private final TabCreator mTabCreator;/a\\n    private @Nullable View mPendingActionAnchorView;\n    private @Nullable ExtensionActionPopup mActivePopup;\n    private @Nullable String mActivePopupActionId;' "$MENU_MEDIATOR"
perl -0pi -e 's|(\n            WindowAndroid windowAndroid,\n            \@Nullable ContextMenuPopulatorFactory contextMenuPopulatorFactory,\n            \@Nullable SelectionDropdownMenuDelegate selectionDropdownMenuDelegate,\n            TabModelSelector tabModelSelector,){2,}|\n            WindowAndroid windowAndroid,\n            \@Nullable ContextMenuPopulatorFactory contextMenuPopulatorFactory,\n            \@Nullable SelectionDropdownMenuDelegate selectionDropdownMenuDelegate,\n            TabModelSelector tabModelSelector,|g' "$MENU_MEDIATOR"
grep -q 'WindowAndroid windowAndroid,' "$MENU_MEDIATOR" || perl -0pi -e 's|(\n            TabCreator tabCreator,\n            ExtensionsToolbarBridge toolbarBridge,)|$1\n            WindowAndroid windowAndroid,\n            \@Nullable ContextMenuPopulatorFactory contextMenuPopulatorFactory,\n            \@Nullable SelectionDropdownMenuDelegate selectionDropdownMenuDelegate,\n            TabModelSelector tabModelSelector,|' "$MENU_MEDIATOR"
perl -0pi -e 's|(\n        mWindowAndroid = windowAndroid;\n        mContextMenuPopulatorFactory = contextMenuPopulatorFactory;\n        mSelectionDropdownMenuDelegate = selectionDropdownMenuDelegate;\n        mTabModelSelector = tabModelSelector;){2,}|\n        mWindowAndroid = windowAndroid;\n        mContextMenuPopulatorFactory = contextMenuPopulatorFactory;\n        mSelectionDropdownMenuDelegate = selectionDropdownMenuDelegate;\n        mTabModelSelector = tabModelSelector;|g' "$MENU_MEDIATOR"
grep -q 'mWindowAndroid = windowAndroid;' "$MENU_MEDIATOR" || perl -0pi -e 's|(\n        mActionModels = actionModels;\n        mContext = context;\n)|$1        mWindowAndroid = windowAndroid;\n        mContextMenuPopulatorFactory = contextMenuPopulatorFactory;\n        mSelectionDropdownMenuDelegate = selectionDropdownMenuDelegate;\n        mTabModelSelector = tabModelSelector;\n|' "$MENU_MEDIATOR"
perl -0pi -e 's|(mMenuBridge\.destroy\(\);\n    \})|closeActivePopup();\n        $1|' "$MENU_MEDIATOR"
perl -0pi -e 's|(?:\s*closeActivePopup\(\);\n)+(\s*mMenuBridge\.destroy\(\);)|\n        closeActivePopup();\n$1|' "$MENU_MEDIATOR"
sed -i 's|(view) -> mMenuBridge.executeAction(entry.id))|(view) -> onPrimaryActionClicked(view, entry.id))|' "$MENU_MEDIATOR"
sed -i 's|(view) -> openExtensionFromMenu(entry.id))|(view) -> onPrimaryActionClicked(view, entry.id))|' "$MENU_MEDIATOR"
sed -i 's|(view) -> openUrlFromMenu(UrlConstants.CHROME_EXTENSIONS_ID_URL + entry.id))|(view) -> onPrimaryActionClicked(view, entry.id))|' "$MENU_MEDIATOR"
sed -i 's|(view) -> openExtensionOptionsFromMenu(entry.id))|(view) -> onPrimaryActionClicked(view, entry.id))|' "$MENU_MEDIATOR"
perl -0pi -e 's|(\n  const raw_ptr<ExtensionsToolbarAndroid> toolbar_android_;\n)\n  // The platform-agnostic menu view model\.\n  std::unique_ptr<ExtensionsMenuViewModel> menu_model_;\n  base::ScopedObservation<ExtensionsMenuViewModel,\n                          ExtensionsMenuViewModel::Observer>\n      menu_model_observation_\{this\};\n\n  const base::android::ScopedJavaGlobalRef<jobject> java_object_;|$1\n  const base::android::ScopedJavaGlobalRef<jobject> java_object_;\n\n  // The platform-agnostic menu view model.\n  std::unique_ptr<ExtensionsMenuViewModel> menu_model_;\n  base::ScopedObservation<ExtensionsMenuViewModel,\n                          ExtensionsMenuViewModel::Observer>\n      menu_model_observation_{this};|' "$MENU_DELEGATE_H"
perl -0pi -e 's|: browser_\(browser\),\n      toolbar_android_\(toolbar_android\),\n      menu_model_\(std::make_unique<ExtensionsMenuViewModel>\(browser,\n                                                            /\*delegate=\*/this\)\),\n      java_object_\(java_object\) \{|: browser_(browser),\n      toolbar_android_(toolbar_android),\n      java_object_(java_object),\n      menu_model_(std::make_unique<ExtensionsMenuViewModel>(browser,\n                                                            /*delegate=*/this)) {|' "$MENU_DELEGATE_CC"
if ! grep -q 'private void onPrimaryActionClicked' "$MENU_MEDIATOR"; then
    sed -i '/private void openUrlFromMenu(String url) {/i\
    private void onPrimaryActionClicked(View anchorView, String extensionId) {\
        if (mActivePopup != null) {\
            boolean closeOnly = extensionId.equals(mActivePopupActionId);\
            closeActivePopup();\
            if (closeOnly) {\
                return;\
            }\
        }\
        mPendingActionAnchorView = anchorView;\
        mMenuBridge.executeAction(extensionId);\
    }\
\
    private void showActionPopup(String actionId, long nativeHostPtr) {\
        ExtensionActionPopupContents contents = ExtensionActionPopupContents.create(nativeHostPtr);\
        View anchorView = mPendingActionAnchorView;\
        mPendingActionAnchorView = null;\
        if (anchorView == null || !anchorView.isShown()) {\
            contents.destroy();\
            return;\
        }\
        Activity activity = mWindowAndroid.getActivity().get();\
        if (activity == null) {\
            contents.destroy();\
            return;\
        }\
        closeActivePopup();\
        mActivePopup =\
                new ExtensionActionPopup(\
                        activity,\
                        mWindowAndroid,\
                        anchorView,\
                        actionId,\
                        contents,\
                        mContextMenuPopulatorFactory,\
                        mSelectionDropdownMenuDelegate,\
                        mTabModelSelector);\
        mActivePopupActionId = actionId;\
        mActivePopup.loadInitialPage();\
        mActivePopup.addOnDismissListener(this::closeActivePopup);\
    }\
\
    private void showActionContextMenu(String actionId) {\
        ListMenuButton buttonView = findContextMenuButtonForPendingAction();\
        mPendingActionAnchorView = null;\
        if (buttonView != null) {\
            onContextMenuButtonClicked(buttonView, actionId);\
        }\
    }\
\
    private @Nullable ListMenuButton findContextMenuButtonForPendingAction() {\
        View current = mPendingActionAnchorView;\
        while (current != null) {\
            View button = current.findViewById(R.id.extensions_menu_item_context_menu);\
            if (button instanceof ListMenuButton) {\
                return (ListMenuButton) button;\
            }\
            if (!(current.getParent() instanceof View)) {\
                return null;\
            }\
            current = (View) current.getParent();\
        }\
        return null;\
    }\
\
    private void closeActivePopup() {\
        if (mActivePopup == null) {\
            return;\
        }\
        ExtensionActionPopup popup = mActivePopup;\
        mActivePopup = null;\
        mActivePopupActionId = null;\
        popup.destroy();\
    }\
\
' "$MENU_MEDIATOR"
fi
perl -0pi -e 's|\@Override\n    \@Override\n    public void onActionPopupRequested|@Override\n    public void onActionPopupRequested|' "$MENU_MEDIATOR"
grep -q 'public void onActionPopupRequested(String actionId, long nativeHostPtr)' "$MENU_MEDIATOR" || perl -0pi -e 's|(\n    \@Override\n    public void onReady\(\) \{)|\n    \@Override\n    public void onActionPopupRequested(String actionId, long nativeHostPtr) {\n        showActionPopup(actionId, nativeHostPtr);\n    }\n\n    \@Override\n    public void onActionContextMenuRequested(String actionId) {\n        showActionContextMenu(actionId);\n    }\n\n    \@Override\n    public void hideActivePopup() {\n        closeActivePopup();\n    }\n\n    \@Override\n    public boolean hasActivePopup() {\n        return mActivePopup != null;\n    }\n$1|' "$MENU_MEDIATOR"
grep -q 'public void triggerPopup' "$BRIDGE" || perl -0pi -e 's|(    public void onActionUpdated\(int actionIndex\) \{\n        mObserver\.onActionUpdated\(actionIndex\);\n    \}\n)|$1\n    \@CalledByNative\n    public void triggerPopup(\@JniType("std::string") String actionId, long nativeHostPtr) {\n        mObserver.onActionPopupRequested(actionId, nativeHostPtr);\n    }\n\n    \@CalledByNative\n    public void showContextMenu(\@JniType("std::string") String actionId) {\n        mObserver.onActionContextMenuRequested(actionId);\n    }\n\n    \@CalledByNative\n    public void hideActivePopup() {\n        mObserver.hideActivePopup();\n    }\n\n    \@CalledByNative\n    public boolean hasActivePopup() {\n        return mObserver.hasActivePopup();\n    }\n\n|' "$BRIDGE"
perl -0pi -e 's|    /\*\*\n    \@CalledByNative\n    public void triggerPopup\(\@JniType\("std::string"\) String actionId, long nativeHostPtr\) \{\n        mObserver\.onActionPopupRequested\(actionId, nativeHostPtr\);\n    \}\n\n    \@CalledByNative\n    public void showContextMenu\(\@JniType\("std::string"\) String actionId\) \{\n        mObserver\.onActionContextMenuRequested\(actionId\);\n    \}\n\n    \@CalledByNative\n    public void hideActivePopup\(\) \{\n        mObserver\.hideActivePopup\(\);\n    \}\n\n    \@CalledByNative\n    public boolean hasActivePopup\(\) \{\n        return mObserver\.hasActivePopup\(\);\n    \}\n\n\n     \* Callback from native indicating that an extension has been updated\.|    /**\n     * Callback from native indicating that an extension has been updated.|' "$BRIDGE"
perl -0pi -e 's|\@CalledByNative\n    \@CalledByNative\n    public void triggerPopup|@CalledByNative\n    public void triggerPopup|' "$BRIDGE"
grep -q 'void onActionPopupRequested(String actionId, long nativeHostPtr);' "$BRIDGE" || sed -i '/void onActionUpdated(int actionIndex);/a\\n        /** Called when native created a popup host for a menu action. */\n        void onActionPopupRequested(String actionId, long nativeHostPtr);\n\n        /** Called when native wants to show fallback context menu for a menu action. */\n        void onActionContextMenuRequested(String actionId);\n\n        /** Called when active popup should be hidden. */\n        void hideActivePopup();\n\n        /** Returns whether there is an active popup. */\n        boolean hasActivePopup();' "$BRIDGE"
grep -q 'base/android/scoped_java_ref.h' "$ACTION_DELEGATE_H" || sed -i '/#include "base\/memory\/raw_ptr.h"/i\#include "base/android/scoped_java_ref.h"' "$ACTION_DELEGATE_H"
grep -q 'java_menu_object' "$ACTION_DELEGATE_H" || sed -i '/extensions::ExtensionsToolbarAndroid\* toolbar_android);/a\  ExtensionActionDelegateAndroid(\n      BrowserWindowInterface* browser,\n      const ToolbarActionsModel::ActionId& action_id,\n      extensions::ExtensionsToolbarAndroid* toolbar_android,\n      const base::android::JavaRef<jobject>& java_menu_object);' "$ACTION_DELEGATE_H"
grep -q 'java_menu_object_' "$ACTION_DELEGATE_H" || sed -i '/const raw_ptr<extensions::ExtensionsToolbarAndroid> toolbar_android_;/a\\n  // Optional Java menu bridge used when a popup was requested from the extensions menu.\n  const base::android::ScopedJavaGlobalRef<jobject> java_menu_object_;' "$ACTION_DELEGATE_H"
grep -q '#include "base/android/jni_android.h"' "$ACTION_DELEGATE_CC" || sed -i '/#include <utility>/a\\n#include "base/android/jni_android.h"' "$ACTION_DELEGATE_CC"
grep -q '#include <cstdint>' "$ACTION_DELEGATE_CC" || sed -i '/#include "chrome\/browser\/ui\/android\/extensions\/extension_action_delegate_android.h"/a\\n#include <cstdint>' "$ACTION_DELEGATE_CC"
perl -0pi -e 's~#pragma clang diagnostic push\n#pragma clang diagnostic ignored "-Wunused-function"\n#include "chrome/browser/ui/android/extensions/jni_headers/ExtensionsMenuBridge_jni.h"\n#pragma clang diagnostic pop~#include "chrome/browser/ui/android/extensions/jni_headers/ExtensionsMenuBridge_jni.h"~g; s~\n?DEFINE_JNI_ExtensionsMenuBridge\(\);?\n~\n~g' "$ACTION_DELEGATE_CC"
grep -q 'ExtensionsMenuBridge_jni.h' "$ACTION_DELEGATE_CC" || perl -0pi -e 's~(#include "chrome/browser/ui/extensions/extension_action_view_model.h"\n)~$1\n#include "chrome/browser/ui/android/extensions/jni_headers/ExtensionsMenuBridge_jni.h"\n~' "$ACTION_DELEGATE_CC"
perl -0pi -e 's~(?:#pragma clang diagnostic ignored "-Wunused-function"\n)*(#include "chrome/browser/ui/android/extensions/jni_headers/ExtensionsMenuBridge_jni.h"\n)~#pragma clang diagnostic ignored "-Wunused-function"\n$1~g' "$ACTION_DELEGATE_CC"
perl -0pi -e 's|(ExtensionActionDelegateAndroid::ExtensionActionDelegateAndroid\(\n    BrowserWindowInterface\* browser,\n    const ToolbarActionsModel::ActionId& action_id,\n    extensions::ExtensionsToolbarAndroid\* toolbar_android,\n    const base::android::JavaRef<jobject>& java_menu_object\)\n    : browser_\(browser\),\n      action_id_\(action_id\),\n      toolbar_android_\(toolbar_android\),\n      java_menu_object_\(java_menu_object\) \{\}\n\n){2,}|$1|g' "$ACTION_DELEGATE_CC"
grep -q 'const base::android::JavaRef<jobject>& java_menu_object)' "$ACTION_DELEGATE_CC" || perl -0pi -e 's|ExtensionActionDelegateAndroid::ExtensionActionDelegateAndroid\(\n    BrowserWindowInterface\* browser,\n    const ToolbarActionsModel::ActionId& action_id,\n    extensions::ExtensionsToolbarAndroid\* toolbar_android\)\n    : browser_\(browser\),\n      action_id_\(action_id\),\n      toolbar_android_\(toolbar_android\) \{\}|ExtensionActionDelegateAndroid::ExtensionActionDelegateAndroid(\n    BrowserWindowInterface* browser,\n    const ToolbarActionsModel::ActionId& action_id,\n    extensions::ExtensionsToolbarAndroid* toolbar_android)\n    : browser_(browser),\n      action_id_(action_id),\n      toolbar_android_(toolbar_android) {}\n\nExtensionActionDelegateAndroid::ExtensionActionDelegateAndroid(\n    BrowserWindowInterface* browser,\n    const ToolbarActionsModel::ActionId& action_id,\n    extensions::ExtensionsToolbarAndroid* toolbar_android,\n    const base::android::JavaRef<jobject>& java_menu_object)\n    : browser_(browser),\n      action_id_(action_id),\n      toolbar_android_(toolbar_android),\n      java_menu_object_(java_menu_object) {}|' "$ACTION_DELEGATE_CC"
perl -0pi -e 's|bool ExtensionActionDelegateAndroid::IsShowingPopup\(\) const \{\n  return toolbar_android_->HasActivePopup\(\);\n\}|bool ExtensionActionDelegateAndroid::IsShowingPopup() const {\n  if (!java_menu_object_.is_null()) {\n    return extensions::Java_ExtensionsMenuBridge_hasActivePopup(\n        base::android::AttachCurrentThread(), java_menu_object_);\n  }\n  return toolbar_android_->HasActivePopup();\n}|' "$ACTION_DELEGATE_CC"
perl -0pi -e 's|void ExtensionActionDelegateAndroid::HidePopup\(\) \{\n  toolbar_android_->HideActivePopup\(\);\n\}|void ExtensionActionDelegateAndroid::HidePopup() {\n  if (!java_menu_object_.is_null()) {\n    extensions::Java_ExtensionsMenuBridge_hideActivePopup(\n        base::android::AttachCurrentThread(), java_menu_object_);\n    return;\n  }\n  toolbar_android_->HideActivePopup();\n}|' "$ACTION_DELEGATE_CC"
perl -0pi -e 's|void ExtensionActionDelegateAndroid::TriggerPopup\(\n    std::unique_ptr<extensions::ExtensionViewHost> host,\n    PopupShowAction show_action,\n    bool by_user,\n    ShowPopupCallback callback\) \{\n  toolbar_android_->TriggerPopup\(action_id_, std::move\(host\)\);\n\}|void ExtensionActionDelegateAndroid::TriggerPopup(\n    std::unique_ptr<extensions::ExtensionViewHost> host,\n    PopupShowAction show_action,\n    bool by_user,\n    ShowPopupCallback callback) {\n  if (!java_menu_object_.is_null()) {\n    extensions::Java_ExtensionsMenuBridge_triggerPopup(\n        base::android::AttachCurrentThread(), java_menu_object_, action_id_,\n        reinterpret_cast<int64_t>(host.release()));\n    return;\n  }\n  toolbar_android_->TriggerPopup(action_id_, std::move(host));\n}|' "$ACTION_DELEGATE_CC"
perl -0pi -e 's|void ExtensionActionDelegateAndroid::ShowContextMenuAsFallback\(\) \{\n  toolbar_android_->ShowContextMenu\(action_id_\);\n\}|void ExtensionActionDelegateAndroid::ShowContextMenuAsFallback() {\n  if (!java_menu_object_.is_null()) {\n    extensions::Java_ExtensionsMenuBridge_showContextMenu(\n        base::android::AttachCurrentThread(), java_menu_object_, action_id_);\n    return;\n  }\n  toolbar_android_->ShowContextMenu(action_id_);\n}|' "$ACTION_DELEGATE_CC"
perl -0pi -e 's~\bJava_ExtensionsMenuBridge_(hasActivePopup|hideActivePopup|triggerPopup|showContextMenu)\b~extensions::Java_ExtensionsMenuBridge_$1~g; s~extensions::extensions::Java_ExtensionsMenuBridge_~extensions::Java_ExtensionsMenuBridge_~g' "$ACTION_DELEGATE_CC"
perl -0pi -e 's|void ExtensionActionDelegateAndroid::CloseExtensionsMenuIfOpen\(\) \{\n  toolbar_android_->CloseExtensionsMenuIfOpen\(\);\n\}|void ExtensionActionDelegateAndroid::CloseExtensionsMenuIfOpen() {\n  if (!java_menu_object_.is_null()) {\n    return;\n  }\n  toolbar_android_->CloseExtensionsMenuIfOpen();\n}|' "$ACTION_DELEGATE_CC"
perl -0pi -e 's|std::make_unique<ExtensionActionDelegateAndroid>\(browser_, extension_id,\n                                                       toolbar_android_\)|std::make_unique<ExtensionActionDelegateAndroid>(browser_, extension_id,\n                                                       toolbar_android_,\n                                                       java_object_)|' "$MENU_DELEGATE_CC"

# search
sed -i 's|BASE_FEATURE(kOmniboxSiteSearch, DISABLED);|BASE_FEATURE(kOmniboxSiteSearch, ENABLED);|' components/omnibox/common/omnibox_features.cc

# playback
sed -i 's|#if BUILDFLAG(IS_ANDROID)|#if 0|' content/public/renderer/render_frame_media_playback_options.cc

# Proportionally scale extension popups to the space outside the toolbar.
python3 "$SCRIPT_DIR/patch_extension_popup_width.py" \
    "$EXTENSION_ACTION_POPUP" \
    "$EXTENSION_POPUP_CONTENTS" \
    "$EXTENSION_POPUP_CONTENTS_CC" \
    "$EXTENSION_POPUP_CONTENTS_H"

# viewport
sed -i 's|<meta name="color-scheme" content="light dark">|&\n<meta name="viewport" content="width=device-width">|' chrome/browser/resources/extensions/extensions.html
sed -i 's|height: calc(var(--md-toolbar-height) + 58px);|height: calc(var(--md-toolbar-height) + 104px);|' chrome/browser/resources/extensions/extensions.html
sed -i 's|--extensions-card-width: 400px;|--extensions-card-width: 96%;|' chrome/browser/resources/extensions/item_list.css # card width
sed -i 's|--cr-toolbar-field-width: 680px;|--cr-toolbar-field-width: 96%;|' chrome/browser/resources/extensions/shared_vars.css # page content
sed -i 's|padding: 24px 60px 64px;|padding: 24px 0 64px;|' chrome/browser/resources/extensions/item_list.css # content wrapper
perl -0pi -e 's/#devDrawer\[expanded\] #buttonStrip \{\n  top: 0;\n\}/#devDrawer[expanded] #buttonStrip {\n  top: auto;\n}/' chrome/browser/resources/extensions/toolbar.css
perl -0pi -e 's/#devDrawer\[expanded\] \{\n  height: calc\(var\(--button-row-height\) \+ var\(--border-bottom-height\)\);\n\}/#devDrawer[expanded] {\n  height: auto;\n  min-height: calc(var(--button-row-height) + var(--border-bottom-height));\n}/' chrome/browser/resources/extensions/toolbar.css
perl -0pi -e 's/#buttonStrip \{\n  margin-inline-end: auto;\n  margin-inline-start: 24px;\n  padding: var\(--padding-top-bottom\) 0;\n  position: absolute;\n  top: calc\(var\(--button-row-height\) \* -1\);\n  transition: top var\(--drawer-transition\);\n  \/\* Prevent selection of the blank space between buttons\. \*\/\n  user-select: none;\n  width: 100%;\n\}/#buttonStrip {\n  box-sizing: border-box;\n  display: flex;\n  flex-wrap: wrap;\n  gap: 8px 12px;\n  margin-inline-end: auto;\n  margin-inline-start: 0;\n  padding: var(--padding-top-bottom) 24px;\n  position: static;\n  transition: top var(--drawer-transition);\n  user-select: none;\n  width: 100%;\n}/' chrome/browser/resources/extensions/toolbar.css
perl -0pi -e 's/#buttonStrip cr-button \{\n  margin-inline-end: 16px;\n\}/#buttonStrip cr-button {\n  margin-inline-end: 0;\n  max-width: 100%;\n}/' chrome/browser/resources/extensions/toolbar.css

# ext: install local zip/crx from developer mode
sed -i '/info.can_load_unpacked =/,/->HasAllowlistedExtension();/c\  info.can_load_unpacked = true;' chrome/browser/extensions/api/developer_private/profile_info_generator.cc
perl -0pi -e 's|  file_path = \*vp;\n#endif  // BUILDFLAG\(IS_ANDROID\)|  file_path = *vp;\n\n  base::FilePath local_unpacked_dir =\n      Profile::FromBrowserContext(browser_context())\n          ->GetPath()\n          .Append(FILE_PATH_LITERAL("Local Extension Install Files"))\n          .Append(FILE_PATH_LITERAL("Unpacked Folders"));\n  base::FilePath stable_file_path =\n      local_unpacked_dir.Append(file_path.BaseName());\n  if (base::CreateDirectory(local_unpacked_dir)) {\n    if (base::PathExists(stable_file_path)) {\n      base::DeletePathRecursively(stable_file_path);\n    }\n    if (base::CopyDirectory(file_path, stable_file_path, true)) {\n      file_path = stable_file_path;\n    }\n  }\n#endif  // BUILDFLAG(IS_ANDROID)|' chrome/browser/extensions/api/developer_private/developer_private_functions.cc
# ZIP installs become unpacked extensions. Keep their extracted files under
# the profile on Chromium branches that still gate this behind a feature flag.
sed -i 's/BASE_FEATURE(kExtensionsZipFileInstalledInProfileDir, base::FEATURE_DISABLED_BY_DEFAULT);/BASE_FEATURE(kExtensionsZipFileInstalledInProfileDir, base::FEATURE_ENABLED_BY_DEFAULT);/' extensions/common/extension_features.cc
sed -i 's/BASE_FEATURE(kExtensionsZipFileInstalledInProfileDir, "ExtensionsZipFileInstalledInProfileDir", base::FEATURE_DISABLED_BY_DEFAULT);/BASE_FEATURE(kExtensionsZipFileInstalledInProfileDir, "ExtensionsZipFileInstalledInProfileDir", base::FEATURE_ENABLED_BY_DEFAULT);/' extensions/common/extension_features.cc
sed -i '/#include "base\/functional\/callback_helpers.h"/a\#include "base/hash/sha1.h"\n#include "base/strings/string_number_conversions.h"' extensions/browser/zipfile_installer.cc
perl -0pi -e 's|  // Create the root of the unique directory for the \.zip file\.\n  base::FilePath::StringType dir_name =\n      zip_file\.RemoveExtension\(\)\.BaseName\(\)\.value\(\) \+ FILE_PATH_LITERAL\("_"\);\n\n  // Creates the full unique directory path as unzip_dir\.\n  base::FilePath unzip_dir;\n  if \(!base::CreateTemporaryDirInDir\(root_unzip_dir, dir_name, &unzip_dir\)\) \{\n    return ZipResultVariant\{ErrorUtils::FormatErrorMessage\(\n        kExtensionHandlerZippedDirError,\n        base::UTF16ToUTF8\(unzip_dir\.LossyDisplayName\(\)\)\)\};\n  \}|  std::string zip_contents;\n  if (!base::ReadFileToString(zip_file, \&zip_contents)) {\n    return ZipResultVariant{std::string(kExtensionHandlerFileUnzipError)};\n  }\n\n  std::string zip_hash =\n      base::HexEncodeLower(base::SHA1HashString(zip_contents)).substr(0, 12);\n  base::FilePath unzip_dir = root_unzip_dir.Append(\n      zip_file.RemoveExtension().BaseName().value() + FILE_PATH_LITERAL("_") +\n      base::FilePath::FromASCII(zip_hash).value());\n  if (base::PathExists(unzip_dir) \&\&\n      !base::DeletePathRecursively(unzip_dir)) {\n    return ZipResultVariant{ErrorUtils::FormatErrorMessage(\n        kExtensionHandlerZippedDirError,\n        base::UTF16ToUTF8(unzip_dir.LossyDisplayName()))};\n  }\n  if (!base::CreateDirectory(unzip_dir)) {\n    return ZipResultVariant{ErrorUtils::FormatErrorMessage(\n        kExtensionHandlerZippedDirError,\n        base::UTF16ToUTF8(unzip_dir.LossyDisplayName()))};\n  }|' extensions/browser/zipfile_installer.cc
sed -i '/loadUnpacked(): Promise<boolean>;/a\
  /** Opens a file picker to install a local zip, crx, or user script. */\
  installLocalExtensionFile(): Promise<boolean>;' chrome/browser/resources/extensions/toolbar.ts
sed -i '/loadUnpacked() {/i\
  installLocalExtensionFile() {\
    return Promise.resolve(false);\
  }' chrome/browser/resources/extensions/toolbar.ts
sed -i '/loadUnpacked: HTMLElement,/a\
    loadExtensionFile: HTMLElement,' chrome/browser/resources/extensions/toolbar.ts
sed -i '/protected onLoadUnpackedClick_()/i\
  protected onLoadExtensionFileClick_() {\
    this.delegate.installLocalExtensionFile()\
        .then((success) => {\
          if (success) {\
            const toastManager = getToastManager();\
            toastManager.duration = TOAST_DURATION_MS;\
            toastManager.show(this.i18n("toolbarLoadUnpackedDone"));\
          }\
        })\
        .catch(loadError => {\
          this.fire("load-error", loadError);\
        });\
    chrome.metricsPrivate.recordUserAction("Options_LoadLocalExtensionFile");\
  }\
' chrome/browser/resources/extensions/toolbar.ts
sed -i '/<cr-button ?hidden="${!this.canLoadUnpacked_()}" id="loadUnpacked"/i\
    <cr-button id="loadExtensionFile"\
        @click="${this.onLoadExtensionFileClick_}">\
      Load ZIP/CRX\
    </cr-button>' chrome/browser/resources/extensions/toolbar.html.ts
sed -i 's|<cr-button ?hidden="${!this.canLoadUnpacked_()}" id="loadUnpacked"|<cr-button id="loadUnpacked"|' chrome/browser/resources/extensions/toolbar.html.ts
sed -i '/protected canLoadUnpacked_()/,/^  }/c\
  protected canLoadUnpacked_() {\
    return true;\
  }' chrome/browser/resources/extensions/toolbar.ts
sed -i '/loadUnpacked(): Promise<boolean> {/i\
  installLocalExtensionFile(): Promise<boolean> {\
    return this.chooseFilePath_(\
        chrome.developerPrivate.SelectType.FILE,\
        chrome.developerPrivate.FileType.LOAD)\
        .then(path => {\
          if (!path) {\
            return false;\
          }\
          return Promise.resolve(chrome.developerPrivate.installDroppedFile())\
              .then(() => true);\
        });\
  }\
' chrome/browser/resources/extensions/service.ts
sed -i '/if (params->file_type == developer::FileType::kLoad) {/a\
    if (params->select_type == developer::SelectType::kFile) {\
      file_type_info.extensions.push_back({FILE_PATH_LITERAL("zip"),\
                                           FILE_PATH_LITERAL("crx"),\
                                           FILE_PATH_LITERAL("user.js")});\
      file_type_info.include_all_files = true;\
      file_type_index = 1;\
    }' chrome/browser/extensions/api/developer_private/developer_private_functions.cc
sed -i '/Respond(WithArguments(file.path().LossyDisplayName()));/i\
  base::FilePath selected_path = file.path();\
  ui::FileInfo display_file(selected_path, base::FilePath(file.display_name));\
  if (MatchesExtension(display_file, FILE_PATH_LITERAL(".zip")) ||\
      MatchesExtension(display_file, FILE_PATH_LITERAL(".crx")) ||\
      MatchesExtension(display_file, FILE_PATH_LITERAL(".user.js"))) {\
    base::FilePath selected_name = file.display_name.empty()\
        ? selected_path.BaseName()\
        : base::FilePath(file.display_name).BaseName();\
    base::FilePath dragged_path = selected_path;\
    base::FilePath persisted_dir;\
    base::FilePath local_extension_dir =\
        Profile::FromBrowserContext(browser_context())\
            ->GetPath()\
            .Append(FILE_PATH_LITERAL("Local Extension Install Files"));\
    if (base::CreateDirectory(local_extension_dir) &&\
        base::CreateTemporaryDirInDir(\
            local_extension_dir, FILE_PATH_LITERAL("install-"), &persisted_dir)) {\
      base::FilePath persisted_path = persisted_dir.Append(selected_name);\
      if (base::CopyFile(selected_path, persisted_path)) {\
        dragged_path = persisted_path;\
      } else {\
        base::DeletePathRecursively(persisted_dir);\
      }\
    }\
    ui::FileInfo selected_file(dragged_path, selected_name);\
    if (content::WebContents* web_contents = GetSenderWebContents()) {\
      DeveloperPrivateAPI::Get(browser_context())->SetDraggedFile(\
          web_contents, selected_file);\
    }\
  }' chrome/browser/extensions/api/developer_private/developer_private_functions.cc
perl -0pi -e 's|#if BUILDFLAG\(IS_ANDROID\)\n  base::expected<void, std::string> result =\n      SetDroppedPath\(web_contents, browser_context\(\)\);\n  if \(!result\.has_value\(\)\) \{\n    return RespondNow\(Error\(result\.error\(\)\)\);\n  \}\n#endif  // BUILDFLAG\(IS_ANDROID\)|#if BUILDFLAG(IS_ANDROID)\n  {\n    DeveloperPrivateAPI* api = DeveloperPrivateAPI::Get(browser_context());\n    ui::FileInfo file = api->GetDraggedFile(web_contents);\n    if (file.path.empty()) {\n      base::expected<void, std::string> result =\n          SetDroppedPath(web_contents, browser_context());\n      if (!result.has_value()) {\n        return RespondNow(Error(result.error()));\n      }\n    }\n  }\n#endif  // BUILDFLAG(IS_ANDROID)|' chrome/browser/extensions/api/developer_private/developer_private_functions.cc
perl -0pi -e 's|  if \(MatchesExtension\(file, FILE_PATH_LITERAL\("\.zip"\)\)\) \{\n    ExtensionRegistrar\* registrar = ExtensionRegistrar::Get\(browser_context\(\)\);\n    ZipFileInstaller::Create\(\n        GetExtensionFileTaskRunner\(\),\n        MakeRegisterInExtensionServiceCallback\(browser_context\(\)\)\)\n        ->InstallZipFileToUnpackedExtensionsDir\(\n            file\.path, registrar->unpacked_install_directory\(\)\);\n  \} else \{|  if (MatchesExtension(file, FILE_PATH_LITERAL(".zip"))) {\n    base::FilePath local_zip_unpacked_dir =\n        Profile::FromBrowserContext(browser_context())\n            ->GetPath()\n            .Append(FILE_PATH_LITERAL("Local Extension Install Files"))\n            .Append(FILE_PATH_LITERAL("Unpacked Extensions"));\n    ZipFileInstaller::Create(\n        GetExtensionFileTaskRunner(),\n        MakeRegisterInExtensionServiceCallback(browser_context()))\n        ->InstallZipFileToUnpackedExtensionsDir(file.path,\n                                                local_zip_unpacked_dir);\n  } else {|' chrome/browser/extensions/api/developer_private/developer_private_functions.cc

# ext: mv2
sed -i '/^bool OffStoreInstallAllowedByPrefs(/a\  for (const char* d : {"addons.opera.com", "operacdn.com", "microsoftedge.microsoft.com", "edge.microsoft.com", "delivery.mp.microsoft.com"}) if (item.GetURL().DomainIs(d) || item.GetReferrerUrl().DomainIs(d)) return true;' chrome/browser/download/download_crx_util.cc
sed -i 's/BASE_FEATURE(kExtensionManifestV2Unsupported, base::FEATURE_ENABLED_BY_DEFAULT);/BASE_FEATURE(kExtensionManifestV2Unsupported, base::FEATURE_DISABLED_BY_DEFAULT);/' extensions/common/extension_features.cc
sed -i 's/BASE_FEATURE(kExtensionManifestV2Disabled, base::FEATURE_ENABLED_BY_DEFAULT);/BASE_FEATURE(kExtensionManifestV2Disabled, base::FEATURE_DISABLED_BY_DEFAULT);/' extensions/common/extension_features.cc
perl -0pi -e 's|bool ExtensionManagement::IsAllowedByUnpackedDeveloperModePolicy\(\n    const Extension& extension\) \{\n.*?\n\}\n\nbool ExtensionManagement::IsGreylistedForceInstalledInLowTrustEnvironment|bool ExtensionManagement::IsAllowedByUnpackedDeveloperModePolicy(\n    const Extension& extension) {\n  return true;\n}\n\nbool ExtensionManagement::IsGreylistedForceInstalledInLowTrustEnvironment|s' chrome/browser/extensions/extension_management.cc
sed -i 's|return IsFromStore(extension, context) && CanUseExtensionApis(extension);|return extension.from_webstore() \&\& CanUseExtensionApis(extension);|' extensions/browser/install_verifier.cc
perl -0pi -e 's|  if \(AllowedByEnterprisePolicy\(extension->id\(\)\) &&\n      !ExtensionsBrowserClient::Get\(\)\n           ->GetExtensionManagementClient\(context_\)\n           ->IsForceInstalledInLowTrustEnvironment\(\*extension\)\) \{\n    return false;\n  \}\n\n  bool verified = true;|  if (AllowedByEnterprisePolicy(extension->id()) &&\n      !ExtensionsBrowserClient::Get()\n           ->GetExtensionManagementClient(context_)\n           ->IsForceInstalledInLowTrustEnvironment(*extension)) {\n    return false;\n  }\n  if (!extension->from_webstore()) {\n    return false;\n  }\n\n  bool verified = true;|' extensions/browser/install_verifier.cc
sed -i 's|if (!InstallVerifier::IsFromStore(extension, context_)) {|if (!extension.from_webstore()) {|' chrome/browser/extensions/chrome_content_verifier_delegate.cc
perl -0pi -e 's/^\s+"proxy\.json",\n//mg; s/^(schema_sources_ = \[\n)/$1  "proxy.json",\n/' chrome/common/extensions/api/api_sources.gni
perl -0pi -e 's/^\s+"browser_action\.json",\n//mg; s/^\s+"page_action\.json",\n//mg; s/^(uncompiled_sources_ = \[\n)/$1  "browser_action.json",\n  "page_action.json",\n/' chrome/common/extensions/api/api_sources.gni
WEBSTORE_PRIVATE_API=extensions/browser/api/webstore_private/webstore_private_api.cc
if [ ! -f "$WEBSTORE_PRIVATE_API" ]; then
    WEBSTORE_PRIVATE_API=chrome/browser/extensions/api/webstore_private/webstore_private_api.cc
fi
sed -i 's/api::webstore_private::MV2DeprecationStatus::kHardDisable)));/api::webstore_private::MV2DeprecationStatus::kNone)));/' "$WEBSTORE_PRIVATE_API"
sed -i 's/bool g_allow_mv2_for_testing = false;/bool g_allow_mv2_for_testing = true;/' extensions/browser/manifest_v2_handler.cc

# android: require explicit user confirmation before launching external apps
perl -0pi -e 's|            if \(debug\(\)\) Log\.i\(TAG, "startActivity"\);\n            context\.startActivity\(intent\);\n            recordExternalNavigationDispatched\(intent\);\n            mDelegate\.reportIntentToSafeBrowsing\(intent\);|            if (debug()) Log.i(TAG, "startActivity");\n            Intent launchIntent = intent;\n            if (!Intent.ACTION_CHOOSER.equals(intent.getAction())\n                    \&\& !Intent.ACTION_PICK_ACTIVITY.equals(intent.getAction())) {\n                launchIntent = Intent.createChooser(intent, null);\n            }\n            context.startActivity(launchIntent);\n            recordExternalNavigationDispatched(intent);\n            mDelegate.reportIntentToSafeBrowsing(intent);|' components/external_intents/android/java/src/org/chromium/components/external_intents/ExternalNavigationHandler.java
# android: offer installed third-party download handlers before using Chromium's
# internal downloader. The handler gets the public URL and filename; Chromium
# remains the fallback when no external handler is installed or launch fails.
python3 - "chrome/android/java/src/org/chromium/chrome/browser/download/DownloadController.java" <<'PYCODE'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
marker = '    static void enqueueDownloadManagerRequest(final DownloadInfo info) {\n'
imports = '''import android.content.ActivityNotFoundException;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.net.Uri;
import android.os.Build;

import java.util.ArrayList;
import java.util.List;

'''
chromium_import = 'import org.chromium.build.annotations.NullMarked;\n'
context_import = 'import org.chromium.base.ContextUtils;\n'
method = '''    // HeliumExternalDownloadHandler: offer non-browser handlers for downloads.
    private static boolean launchExternalDownloadHandler(DownloadInfo info) {
        Context context = ContextUtils.getApplicationContext();
        Intent downloadIntent = new Intent(Intent.ACTION_VIEW, Uri.parse(info.getUrl().getSpec()));
        // Do not require CATEGORY_BROWSABLE: many download managers expose only
        // ACTION_VIEW/DEFAULT handlers for direct HTTP(S) downloads.
        downloadIntent.putExtra(Intent.EXTRA_TITLE, info.getFileName());
        downloadIntent.putExtra(Intent.EXTRA_TEXT, info.getUrl().getSpec());

        List<ResolveInfo> handlers =
                context.getPackageManager()
                        .queryIntentActivities(downloadIntent, PackageManager.MATCH_DEFAULT_ONLY);
        ArrayList<ComponentName> ownComponents = new ArrayList<>();
        boolean hasExternalHandler = false;
        for (ResolveInfo handler : handlers) {
            if (handler.activityInfo == null) {
                continue;
            }
            ComponentName component =
                    new ComponentName(handler.activityInfo.packageName, handler.activityInfo.name);
            if (context.getPackageName().equals(handler.activityInfo.packageName)) {
                ownComponents.add(component);
            } else {
                hasExternalHandler = true;
            }
        }
        if (!hasExternalHandler) {
            return false;
        }

        Intent chooser = Intent.createChooser(downloadIntent, "Download with");
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N && !ownComponents.isEmpty()) {
            chooser.putExtra(
                    Intent.EXTRA_EXCLUDE_COMPONENTS,
                    ownComponents.toArray(new ComponentName[0]));
        }
        chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try {
            context.startActivity(chooser);
            return true;
        } catch (ActivityNotFoundException e) {
            return false;
        }
    }

'''
if imports not in text:
    if chromium_import not in text:
        raise SystemExit(f'import anchor not found in {path}')
    text = text.replace(chromium_import, imports + chromium_import, 1)
if context_import not in text:
    text = text.replace(chromium_import, chromium_import + context_import, 1)
if 'HeliumExternalDownloadHandler' not in text:
    if marker not in text:
        raise SystemExit(f'download enqueue anchor not found in {path}')
    text = text.replace(marker, method + marker, 1)
old = '''    static void enqueueDownloadManagerRequest(final DownloadInfo info) {
        DownloadManagerService.getDownloadManagerService()
'''
new = '''    static void enqueueDownloadManagerRequest(final DownloadInfo info) {
        if (launchExternalDownloadHandler(info)) {
            return;
        }
        DownloadManagerService.getDownloadManagerService()
'''
if old in text:
    text = text.replace(old, new, 1)
elif 'if (launchExternalDownloadHandler(info))' not in text:
    raise SystemExit(f'download enqueue body not found in {path}')
path.write_text(text)
PYCODE

# Add a direct Appearance entry to every Android three-dot menu mode.
python3 - "chrome/android/java/src/org/chromium/chrome/browser/tabbed_mode/TabbedAppMenuPropertiesDelegate.java" <<'PYCODE'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text()
method = """    private ListItem buildAppearanceItem() {
        return new ListItem(
                AppMenuHandler.AppMenuItemType.STANDARD,
                AppMenuItemUtils.buildModelForStandardMenuItem(
                        mContext,
                        getAppMenuItemTheme(),
                        R.id.appearance_menu_id,
                        R.string.menu_appearance,
                        Resources.ID_NULL,
                        isMenuIconAtStart()));
    }

"""
if "private ListItem buildAppearanceItem()" not in text:
    anchor = "    private ListItem buildSettingsItem() {\n"
    if anchor not in text:
        raise SystemExit("appearance menu method anchor not found")
    text = text.replace(anchor, method + anchor, 1)
if "modelList.add(buildAppearanceItem());" not in text:
    text = text.replace(
        "        modelList.add(buildSettingsItem());",
        "        modelList.add(buildAppearanceItem());\n        modelList.add(buildSettingsItem());")
path.write_text(text)
PYCODE

# Add the Appearance menu resource and route it to the existing settings fragment.
sed -i '/<item type="id" name="preferences_id" \/>/i\    <item type="id" name="appearance_menu_id" />' chrome/android/java/res/values/ids.xml
python3 - "chrome/browser/ui/android/strings/android_chrome_strings.grd" <<'PYCODE'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text()
entry = """      <message name=\"IDS_MENU_APPEARANCE\" desc=\"Menu item for opening appearance settings. [CHAR_LIMIT=27]\">\n        Appearance\n      </message>\n"""
if 'name="IDS_MENU_APPEARANCE"' not in text:
    anchor = '      <message name="IDS_MENU_SETTINGS"'
    if anchor not in text:
        raise SystemExit("menu settings string anchor not found")
    text = text.replace(anchor, entry + anchor, 1)
path.write_text(text)
PYCODE
python3 - "chrome/android/java/src/org/chromium/chrome/browser/app/ChromeActivity.java" <<'PYCODE'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text()
imp = 'import org.chromium.chrome.browser.about_settings.AboutChromeSettings;\n'
new_imp = 'import org.chromium.chrome.browser.appearance.settings.AppearanceSettingsFragment;\n'
if new_imp not in text:
    if imp not in text:
        raise SystemExit("ChromeActivity import anchor not found")
    text = text.replace(imp, imp + new_imp, 1)
handler = """        if (id == R.id.appearance_menu_id) {
            SettingsNavigationFactory.createSettingsNavigation()
                    .startSettings(this, AppearanceSettingsFragment.class);
            RecordUserAction.record(\"MobileMenuAppearance\");
            return true;
        }

"""
anchor = '        if (id == R.id.preferences_id) {\n'
if 'id == R.id.appearance_menu_id' not in text:
    if anchor not in text:
        raise SystemExit("ChromeActivity settings handler anchor not found")
    text = text.replace(anchor, handler + anchor, 1)
path.write_text(text)
PYCODE

# android: expose third-party downloader selection under Downloads settings.
# Default off: Chromium's internal download manager remains the normal path.
python3 - "chrome/android/java/src/org/chromium/chrome/browser/download/DownloadController.java" "chrome/browser/download/android/java/src/org/chromium/chrome/browser/download/settings/DownloadSettings.java" "chrome/browser/download/android/java/res/xml/download_preferences.xml" <<'PYCODE'
from pathlib import Path
import sys

controller = Path(sys.argv[1])
settings = Path(sys.argv[2])
preferences = Path(sys.argv[3])

text = controller.read_text()
class_anchor = 'public class DownloadController {\n'
class_replacement = '''public class DownloadController {
    private static final String EXTERNAL_DOWNLOAD_HANDLER_PREF =
            "external_download_handler";
'''
if 'EXTERNAL_DOWNLOAD_HANDLER_PREF' not in text:
    if class_anchor not in text:
        raise SystemExit(f'DownloadController class anchor missing: {controller}')
    text = text.replace(class_anchor, class_replacement, 1)
shared_import = 'import org.chromium.chrome.browser.preferences.ChromeSharedPreferences;\n'
nullmarked_import = 'import org.chromium.build.annotations.NullMarked;\n'
if shared_import not in text:
    if nullmarked_import not in text:
        raise SystemExit(f'DownloadController import anchor missing: {controller}')
    text = text.replace(nullmarked_import, nullmarked_import + shared_import, 1)
method_anchor = '    private static boolean launchExternalDownloadHandler(DownloadInfo info) {\n'
method_replacement = '''    private static boolean launchExternalDownloadHandler(DownloadInfo info) {
        if (!ChromeSharedPreferences.getInstance()
                .readBoolean(EXTERNAL_DOWNLOAD_HANDLER_PREF, false)) {
            return false;
        }
'''
if 'readBoolean(EXTERNAL_DOWNLOAD_HANDLER_PREF, false)' not in text:
    if method_anchor not in text:
        raise SystemExit(f'DownloadController handler anchor missing: {controller}')
    text = text.replace(method_anchor, method_replacement, 1)
controller.write_text(text)

text = settings.read_text()
shared_import = 'import org.chromium.chrome.browser.preferences.ChromeSharedPreferences;\n'
pref_import = 'import org.chromium.chrome.browser.preferences.Pref;\n'
if shared_import not in text:
    if pref_import not in text:
        raise SystemExit(f'DownloadSettings import anchor missing: {settings}')
    text = text.replace(pref_import, pref_import + shared_import, 1)
constant_anchor = '    public static final String PREF_AUTO_OPEN_PDF_ENABLED = "auto_open_pdf_enabled";\n'
constant_replacement = constant_anchor + '    public static final String PREF_EXTERNAL_DOWNLOAD_HANDLER = "external_download_handler";\n'
if 'PREF_EXTERNAL_DOWNLOAD_HANDLER' not in text:
    if constant_anchor not in text:
        raise SystemExit(f'DownloadSettings constant anchor missing: {settings}')
    text = text.replace(constant_anchor, constant_replacement, 1)
field_anchor = '    private ChromeSwitchPreference mAutoOpenPdfEnabledPref;\n'
field_replacement = field_anchor + '    private ChromeSwitchPreference mExternalDownloadHandlerPref;\n'
if 'mExternalDownloadHandlerPref' not in text:
    if field_anchor not in text:
        raise SystemExit(f'DownloadSettings field anchor missing: {settings}')
    text = text.replace(field_anchor, field_replacement, 1)
create_anchor = '''        mLocationChangePref = (DownloadLocationPreference) findPreference(PREF_LOCATION_CHANGE);
        mLocationChangePref.setDownloadLocationHelper(new DownloadLocationHelperImpl(getProfile()));

'''
create_replacement = create_anchor + '''        mExternalDownloadHandlerPref =
                (ChromeSwitchPreference) findPreference(PREF_EXTERNAL_DOWNLOAD_HANDLER);
        mExternalDownloadHandlerPref.setOnPreferenceChangeListener(this);

'''
if 'findPreference(PREF_EXTERNAL_DOWNLOAD_HANDLER)' not in text:
    if create_anchor not in text:
        raise SystemExit(f'DownloadSettings create anchor missing: {settings}')
    text = text.replace(create_anchor, create_replacement, 1)
update_anchor = '''    private void updateDownloadSettings() {
        mLocationChangePref.updateSummary();

'''
update_replacement = update_anchor + '''        mExternalDownloadHandlerPref.setChecked(
                ChromeSharedPreferences.getInstance()
                        .readBoolean(PREF_EXTERNAL_DOWNLOAD_HANDLER, false));
        mExternalDownloadHandlerPref.setEnabled(true);

'''
if 'mExternalDownloadHandlerPref.setChecked' not in text:
    if update_anchor not in text:
        raise SystemExit(f'DownloadSettings update anchor missing: {settings}')
    text = text.replace(update_anchor, update_replacement, 1)
change_anchor = '''        } else if (PREF_AUTO_OPEN_PDF_ENABLED.equals(preference.getKey())) {
            UserPrefs.get(getProfile()).setBoolean(Pref.AUTO_OPEN_PDF_ENABLED, (boolean) newValue);
        }
'''
change_replacement = '''        } else if (PREF_AUTO_OPEN_PDF_ENABLED.equals(preference.getKey())) {
            UserPrefs.get(getProfile()).setBoolean(Pref.AUTO_OPEN_PDF_ENABLED, (boolean) newValue);
        } else if (PREF_EXTERNAL_DOWNLOAD_HANDLER.equals(preference.getKey())) {
            ChromeSharedPreferences.getInstance()
                    .writeBoolean(PREF_EXTERNAL_DOWNLOAD_HANDLER, (boolean) newValue);
        }
'''
if 'writeBoolean(PREF_EXTERNAL_DOWNLOAD_HANDLER' not in text:
    if change_anchor not in text:
        raise SystemExit(f'DownloadSettings change anchor missing: {settings}')
    text = text.replace(change_anchor, change_replacement, 1)
settings.write_text(text)

text = preferences.read_text()
entry = '''
    <org.chromium.components.browser_ui.settings.ChromeSwitchPreference
        android:key="external_download_handler"
        android:title="Use third-party download tool"
        android:summaryOn="Show a chooser before downloading"
        android:summaryOff="Use the browser download manager"
        android:defaultValue="false" />
'''
closing_tag = '</PreferenceScreen>\n'
if 'android:key="external_download_handler"' not in text:
    if closing_tag not in text:
        raise SystemExit(f'download_preferences.xml closing tag missing: {preferences}')
    text = text.replace(closing_tag, entry + closing_tag, 1)
preferences.write_text(text)
PYCODE

# ext: isolate top-level navigations from extension blockers
sed -i '/case DNRRequestAction::Type::BLOCK:/,/case DNRRequestAction::Type::ALLOW:/ s|ClearPendingCallbacks(browser_context, \*request);|if (request->web_request_type == WebRequestResourceType::MAIN_FRAME) { break; }\n          ClearPendingCallbacks(browser_context, *request);|' extensions/browser/api/web_request/extension_web_request_event_router.cc
sed -i '/case DNRRequestAction::Type::REDIRECT:/,/case DNRRequestAction::Type::MODIFY_HEADERS:/ s|ClearPendingCallbacks(browser_context, \*request);|if (request->web_request_type == WebRequestResourceType::MAIN_FRAME) { break; }\n          ClearPendingCallbacks(browser_context, *request);|' extensions/browser/api/web_request/extension_web_request_event_router.cc
grep -q 'Helium: ignore extension main-frame cancel/redirect' extensions/browser/api/web_request/extension_web_request_event_router.cc || sed -i '/  const bool redirected =/i\
  // Helium: ignore extension main-frame cancel/redirect results. Ad blockers\
  // can otherwise leave a restored startup tab with an empty WebContents.\
  if (request->web_request_type == WebRequestResourceType::MAIN_FRAME) {\
    canceled_by_extension.reset();\
    if (blocked_request.new_url \&\& !blocked_request.new_url->is_empty()) {\
      *blocked_request.new_url = GURL();\
    }\
  }\
' extensions/browser/api/web_request/extension_web_request_event_router.cc

# ext: keep early content-script injection from breaking page startup
sed -i '/extensions_features::kExtensionsBackgroundCompilation));/a\
  if (host_id_.type == mojom::HostID::HostType::kExtensions &&\
      web_frame->IsOutermostMainFrame() &&\
      !document_url.SchemeIs("chrome-extension")) {\
    return;\
  }' extensions/renderer/user_script_set.cc
sed -i '/  bool inject_css = !script->css_scripts().empty() &&/,/      !script->js_scripts().empty() && script->run_location() == run_location;/c\
  // Delay extension main-frame work until the page is idle. Dark-mode/style\
  // and filtering extensions can otherwise alter CSS or script state before\
  // the page initializes, leaving some sites blank. Keep\
  // extension pages at their declared timing so new-tab/homepage extensions\
  // such as iTabs can initialize normally.\
  const bool delay_main_frame_extension_scripts =\
      host_id_.type == mojom::HostID::HostType::kExtensions &&\
      web_frame->IsOutermostMainFrame() &&\
      !document_url.SchemeIs("chrome-extension");\
\
  mojom::RunLocation script_run_location = script->run_location();\
  if (delay_main_frame_extension_scripts &&\
      (script_run_location == mojom::RunLocation::kDocumentStart ||\
       script_run_location == mojom::RunLocation::kDocumentEnd)) {\
    script_run_location = mojom::RunLocation::kDocumentIdle;\
  }\
\
  const mojom::RunLocation css_run_location =\
      delay_main_frame_extension_scripts ? mojom::RunLocation::kDocumentIdle\
                                         : mojom::RunLocation::kDocumentStart;\
  bool inject_css =\
      !script->css_scripts().empty() && run_location == css_run_location;\
  bool inject_js =\
      !script->js_scripts().empty() && script_run_location == run_location;' extensions/renderer/user_script_set.cc

# ext: toolbar
sed -i '/<ViewStub/{N;N;N;N;N;N; /optional_button_stub/a\
        <ViewStub\
            android:id="@+id/extensions_toolbar_container_stub"\
            android:inflatedId="@+id/extensions_toolbar_container"\
            android:layout_width="wrap_content"\
            android:layout_height="match_parent" />
}' chrome/browser/ui/android/toolbar/java/res/layout/toolbar_phone.xml
sed -i 's|(ToolbarTablet) mToolbarLayout,|mToolbarLayout,|' chrome/android/java/src/org/chromium/chrome/browser/toolbar/ToolbarManager.java
sed -i '/\/\/ Draw the signin button if visible./i\        { View extContainer = findViewById(R.id.extensions_toolbar_container); if (extContainer != null \&\& extContainer.getVisibility() != View.GONE \&\& extContainer.getWidth() != 0) { canvas.save(); ViewUtils.translateCanvasToView(mToolbarButtonsContainer, extContainer, canvas); extContainer.draw(canvas); canvas.restore(); } }' chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/top/ToolbarPhone.java

# ext: popup
sed -i '/public class RecyclerViewDelegate {$/a\public View getContainerView() { return mContainer; }' chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionActionListCoordinator.java
sed -i '/private void showPopupOnAnchor() {/,/private void closePopup() {/ s|if (buttonView == null) {|if (false) {|' chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionActionListMediator.java
sed -i 's|buttonView.setIsPressed(true);|if (buttonView != null) buttonView.setIsPressed(true);|' chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionActionListMediator.java
sed -i '/[[:space:]]mWindowAndroid,/!b;n;s|[[:space:]]buttonView,|buttonView != null ? buttonView : mRecyclerViewDelegate.getContainerView(),|' chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionActionListMediator.java
sed -i 's|private boolean handleKeyboardEvent(WebContents webContents, KeyEvent event) {|private boolean handleKeyboardEvent(WebContents webContents, KeyEvent event) { if (event == null) return false;|' chrome/browser/ui/android/extensions/java/src/org/chromium/chrome/browser/ui/extensions/ExtensionActionPopupContents.java

# ext: pin
perl -0pi -e 'if (!/setHeliumMenuButtonVisibility/) { s|    private void showIphInternal\(\) \{|    private void setHeliumMenuButtonVisibility(boolean visible) {\n        if (mContainer == null) return;\n        View menuButton = mContainer.findViewById(R.id.extensions_menu_button);\n        if (menuButton == null) return;\n        menuButton.setVisibility(visible ? View.VISIBLE : View.GONE);\n    }\n\n    private void showIphInternal() {| }' chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionsToolbarCoordinatorImpl.java
sed -i 's|if (mPrefService.getBoolean(Pref.PIN_EXTENSIONS_MENU_BUTTON)) { mContainer.findViewById(R.id.extensions_menu_button).setVisibility(View.VISIBLE); } else { mContainer.findViewById(R.id.extensions_menu_button).setVisibility(View.GONE); }|        setHeliumMenuButtonVisibility(mPrefService.getBoolean(Pref.PIN_EXTENSIONS_MENU_BUTTON));|' chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionsToolbarCoordinatorImpl.java
sed -i 's|mContainer.findViewById(R.id.extensions_menu_button).setVisibility(isMenuButtonPinned() ? View.VISIBLE : View.GONE);|                setHeliumMenuButtonVisibility(isMenuButtonPinned());|' chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionsToolbarCoordinatorImpl.java
sed -i '/Pref.PIN_EXTENSIONS_MENU_BUTTON, this::updateMenuButtonPinState);$/a\        setHeliumMenuButtonVisibility(mPrefService.getBoolean(Pref.PIN_EXTENSIONS_MENU_BUTTON));' chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionsToolbarCoordinatorImpl.java
sed -i '/"ExtensionsToolbarCoordinatorImpl.requestLayoutWithViewUtils()");$/a\                setHeliumMenuButtonVisibility(isMenuButtonPinned());' chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionsToolbarCoordinatorImpl.java
perl -0pi -e 's|        mContainer\.findViewById\(R\.id\.extensions_menu_button\)\.setVisibility\(visibility\);|        View menuButton = mContainer.findViewById(R.id.extensions_menu_button);\n        if (menuButton != null) {\n            menuButton.setVisibility(visibility);\n        }|' chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionsToolbarCoordinatorImpl.java

# ext: incognito
grep -q 'build/build_config.h' chrome/browser/ui/extensions/extensions_menu_view_model.cc || sed -i '/#include "base\/metrics\/user_metrics_action.h"/a\#include "build/build_config.h"' chrome/browser/ui/extensions/extensions_menu_view_model.cc
perl -0pi -e 's|  ExtensionsMenuViewModel::ControlState button_state;\n  button_state\.text = action_model->GetActionName\(\);|  ExtensionsMenuViewModel::ControlState button_state;\n#if BUILDFLAG(IS_ANDROID)\n  std::u16string action_title =\n      web_contents ? action_model->GetActionTitle(web_contents)\n                   : std::u16string();\n  button_state.text = action_title.empty() ? action_model->GetActionName()\n                                           : action_title;\n#else\n  button_state.text = action_model->GetActionName();\n#endif|' chrome/browser/ui/extensions/extensions_menu_view_model.cc

# Use the current Java tab when the Android extensions menu asks native for
# action state. The platform-agnostic menu model can otherwise resolve the
# active WebContents from the regular browser window while the visible tab is
# incognito, which makes per-tab action titles/icons (SwitchyOmega status) show
# the normal tab instead of the current incognito page.
grep -q 'org.chromium.content_public.browser.WebContents;' "$BRIDGE" || sed -i '/import org.chromium.chrome.browser.ui.browser_window.ChromeAndroidTask;/a\import org.chromium.content_public.browser.WebContents;' "$BRIDGE"
perl -0pi -e 's|public void executeAction\(String extensionId\) \{\n        ExtensionsMenuBridgeJni\.get\(\)\n                \.executeAction\(mNativeExtensionsMenuDelegateAndroid, extensionId\);\n    \}|public void executeAction(String extensionId) {\n        executeAction(extensionId, null);\n    }\n\n    public void executeAction(String extensionId, \@Nullable WebContents webContents) {\n        ExtensionsMenuBridgeJni.get()\n                .executeAction(mNativeExtensionsMenuDelegateAndroid, extensionId, webContents);\n    }|' "$BRIDGE"
perl -0pi -e 's|public \@Nullable Bitmap getActionIcon\(int actionIndex\) \{\n        return ExtensionsMenuBridgeJni\.get\(\)\n                \.getActionIcon\(mNativeExtensionsMenuDelegateAndroid, actionIndex\);\n    \}|public \@Nullable Bitmap getActionIcon(int actionIndex) {\n        return getActionIcon(actionIndex, null);\n    }\n\n    public \@Nullable Bitmap getActionIcon(int actionIndex, \@Nullable WebContents webContents) {\n        return ExtensionsMenuBridgeJni.get()\n                .getActionIcon(mNativeExtensionsMenuDelegateAndroid, actionIndex, webContents);\n    }|' "$BRIDGE"
perl -0pi -e 's|public List<ExtensionsMenuTypes\.MenuEntryState> getMenuEntries\(\) \{\n        return ExtensionsMenuBridgeJni\.get\(\)\.getMenuEntries\(mNativeExtensionsMenuDelegateAndroid\);\n    \}|public List<ExtensionsMenuTypes.MenuEntryState> getMenuEntries() {\n        return getMenuEntries(null);\n    }\n\n    public List<ExtensionsMenuTypes.MenuEntryState> getMenuEntries(\n            \@Nullable WebContents webContents) {\n        return ExtensionsMenuBridgeJni.get()\n                .getMenuEntries(mNativeExtensionsMenuDelegateAndroid, webContents);\n    }|' "$BRIDGE"
perl -0pi -e 's|public ExtensionsMenuTypes\.MenuEntryState getMenuEntry\(int actionIndex\) \{\n        return ExtensionsMenuBridgeJni\.get\(\)\n                \.getMenuEntry\(mNativeExtensionsMenuDelegateAndroid, actionIndex\);\n    \}|public ExtensionsMenuTypes.MenuEntryState getMenuEntry(int actionIndex) {\n        return getMenuEntry(actionIndex, null);\n    }\n\n    public ExtensionsMenuTypes.MenuEntryState getMenuEntry(\n            int actionIndex, \@Nullable WebContents webContents) {\n        return ExtensionsMenuBridgeJni.get()\n                .getMenuEntry(mNativeExtensionsMenuDelegateAndroid, actionIndex, webContents);\n    }|' "$BRIDGE"
perl -0pi -e 's|\@Nullable Bitmap getActionIcon\(long nativeExtensionsMenuDelegateAndroid, int actionIndex\);|\@Nullable Bitmap getActionIcon(\n                long nativeExtensionsMenuDelegateAndroid,\n                int actionIndex,\n                \@Nullable \@JniType("content::WebContents*") WebContents webContents);|' "$BRIDGE"
perl -0pi -e 's|void executeAction\(\n                long nativeExtensionsMenuDelegateAndroid,\n                \@JniType\("std::string"\) String extensionId\);|void executeAction(\n                long nativeExtensionsMenuDelegateAndroid,\n                \@JniType("std::string") String extensionId,\n                \@Nullable \@JniType("content::WebContents*") WebContents webContents);|' "$BRIDGE"
perl -0pi -e 's|List<ExtensionsMenuTypes\.MenuEntryState> getMenuEntries\(\n                long nativeExtensionsMenuDelegateAndroid\);|List<ExtensionsMenuTypes.MenuEntryState> getMenuEntries(\n                long nativeExtensionsMenuDelegateAndroid,\n                \@Nullable \@JniType("content::WebContents*") WebContents webContents);|' "$BRIDGE"
perl -0pi -e 's|ExtensionsMenuTypes\.MenuEntryState getMenuEntry\(\n                long nativeExtensionsMenuDelegateAndroid, int actionIndex\);|ExtensionsMenuTypes.MenuEntryState getMenuEntry(\n                long nativeExtensionsMenuDelegateAndroid,\n                int actionIndex,\n                \@Nullable \@JniType("content::WebContents*") WebContents webContents);|' "$BRIDGE"

grep -q 'org.chromium.build.annotations.Nullable' "$MENU_MEDIATOR" || sed -i '/import org.chromium.build.annotations.NullMarked;/a\import org.chromium.build.annotations.Nullable;' "$MENU_MEDIATOR"
# Clean stale getCurrentWebContents helpers before inserting the morning-version helper.
python3 - "$MENU_MEDIATOR" <<'PYCODE'
from pathlib import Path
import sys
import re

path = Path(sys.argv[1])
text = path.read_text()
needle = "private @Nullable WebContents getCurrentWebContents() {"
while True:
    pos = text.find(needle)
    if pos < 0:
        break
    start = text.rfind("\n", 0, pos)
    start = 0 if start < 0 else start
    brace = text.find("{", pos)
    depth = 0
    end = None
    for idx in range(brace, len(text)):
        if text[idx] == "{":
            depth += 1
        elif text[idx] == "}":
            depth -= 1
            if depth <= 0:
                end = idx + 1
                while end < len(text) and text[end] in " \t\r\n":
                    end += 1
                break
    if end is None:
        break
    text = text[:start].rstrip() + "\n\n" + text[end:]
path.write_text(text)
PYCODE
grep -q 'private @Nullable WebContents getCurrentWebContents()' "$MENU_MEDIATOR" || sed -i '/private @ExtensionsMenuProperties.Page int getCurrentPage()/i\
    private @Nullable WebContents getCurrentWebContents() {\
        Tab incognitoTab = mTabModelSelector.getModel(true).getCurrentTabSupplier().get();\
        if (incognitoTab != null\
                && incognitoTab.getWebContents() != null\
                && (mTabModelSelector.isOffTheRecordModelSelected()\
                        || incognitoTab.isUserInteractable()\
                        || incognitoTab.isActivated())) {\
            return incognitoTab.getWebContents();\
        }\
        Tab currentTab = mTabModelSelector.getCurrentTab();\
        if (currentTab != null && currentTab.getWebContents() != null) {\
            return currentTab.getWebContents();\
        }\
        Tab suppliedTab = mCurrentTabSupplier.get();\
        if (suppliedTab != null && suppliedTab.getWebContents() != null) {\
            return suppliedTab.getWebContents();\
        }\
        return incognitoTab != null ? incognitoTab.getWebContents() : null;\
    }\
\
' "$MENU_MEDIATOR"
sed -i 's|mMenuBridge.getMenuEntry(actionIndex)|mMenuBridge.getMenuEntry(actionIndex, getCurrentWebContents())|g' "$MENU_MEDIATOR"
sed -i 's|mMenuBridge.getMenuEntry(newIndex)|mMenuBridge.getMenuEntry(newIndex, getCurrentWebContents())|g' "$MENU_MEDIATOR"
sed -i 's|mMenuBridge.getActionIcon(actionIndex)|mMenuBridge.getActionIcon(actionIndex, getCurrentWebContents())|g' "$MENU_MEDIATOR"
sed -i 's|mMenuBridge.getMenuEntries()|mMenuBridge.getMenuEntries(getCurrentWebContents())|g' "$MENU_MEDIATOR"
perl -0pi -e 's|mMenuBridge\.executeAction\(extensionId\);|mMenuBridge.executeAction(extensionId, getCurrentWebContents());|g' "$MENU_MEDIATOR"
perl -0pi -e 's|mMenuBridge\.executeAction\(entry\.id\)(?!,)|mMenuBridge.executeAction(entry.id, getCurrentWebContents())|g' "$MENU_MEDIATOR"

grep -q 'namespace content {' "$MENU_DELEGATE_H" || sed -i '/namespace extensions {/i\
namespace content {\
class WebContents;\
}  // namespace content\
\
' "$MENU_DELEGATE_H"
grep -q 'GetLastAndroidExtensionActionTabId' "$MENU_DELEGATE_H" || sed -i '/namespace extensions {/a\
int GetLastAndroidExtensionActionTabId();\
\
' "$MENU_DELEGATE_H"
grep -q 'GetLastAndroidExtensionActionWebContents' "$MENU_DELEGATE_H" || sed -i '/namespace extensions {/a\
content::WebContents* GetLastAndroidExtensionActionWebContents();\
\
' "$MENU_DELEGATE_H"
grep -q 'SetLastAndroidExtensionActionWebContents' "$MENU_DELEGATE_H" || sed -i '/namespace extensions {/a\
void SetLastAndroidExtensionActionWebContents(content::WebContents* web_contents);\
\
' "$MENU_DELEGATE_H"
perl -0pi -e 's|void ExecuteAction\(JNIEnv\* env, const extensions::ExtensionId& extension_id\);|void ExecuteAction(JNIEnv* env,\n                     const extensions::ExtensionId& extension_id,\n                     content::WebContents* web_contents);|' "$MENU_DELEGATE_H"
perl -0pi -e 's|base::android::ScopedJavaLocalRef<jobject> GetActionIcon\(JNIEnv\* env,\n                                                           int action_index\);|base::android::ScopedJavaLocalRef<jobject> GetActionIcon(\n      JNIEnv* env,\n      int action_index,\n      content::WebContents* web_contents);|' "$MENU_DELEGATE_H"
perl -0pi -e 's|base::android::ScopedJavaLocalRef<jobject> GetMenuEntry\(JNIEnv\* env,\n                                                          int action_index\);|base::android::ScopedJavaLocalRef<jobject> GetMenuEntry(\n      JNIEnv* env,\n      int action_index,\n      content::WebContents* web_contents);|' "$MENU_DELEGATE_H"
perl -0pi -e 's|std::vector<base::android::ScopedJavaLocalRef<jobject>> GetMenuEntries\(\n      JNIEnv\* env\);|std::vector<base::android::ScopedJavaLocalRef<jobject>> GetMenuEntries(\n      JNIEnv* env,\n      content::WebContents* web_contents);|' "$MENU_DELEGATE_H"

grep -q 'chrome/browser/extensions/extension_tab_util.h' "$MENU_DELEGATE_CC" || sed -i '/#include "chrome\/browser\/ui\/android\/extensions\/extension_action_delegate_android.h"/a\#include "chrome/browser/extensions/extension_tab_util.h"' "$MENU_DELEGATE_CC"
grep -q 'chrome/browser/android/tab_android.h' "$MENU_DELEGATE_CC" || sed -i '/#include "chrome\/browser\/ui\/android\/extensions\/extension_action_delegate_android.h"/a\#include "chrome/browser/android/tab_android.h"' "$MENU_DELEGATE_CC"
grep -q 'chrome/browser/ui/android/tab_model/tab_model.h' "$MENU_DELEGATE_CC" || sed -i '/#include "chrome\/browser\/ui\/android\/extensions\/extension_action_delegate_android.h"/a\#include "chrome/browser/ui/android/tab_model/tab_model.h"' "$MENU_DELEGATE_CC"
grep -q 'chrome/browser/ui/android/tab_model/tab_model_list.h' "$MENU_DELEGATE_CC" || sed -i '/#include "chrome\/browser\/ui\/android\/extensions\/extension_action_delegate_android.h"/a\#include "chrome/browser/ui/android/tab_model/tab_model_list.h"' "$MENU_DELEGATE_CC"
grep -q 'chrome/browser/tab_list/tab_list_interface.h' "$MENU_DELEGATE_CC" || sed -i '/#include "chrome\/browser\/ui\/android\/extensions\/extension_action_delegate_android.h"/a\#include "chrome/browser/tab_list/tab_list_interface.h"' "$MENU_DELEGATE_CC"
grep -q 'chrome/browser/ui/toolbar/toolbar_action_view_model.h' "$MENU_DELEGATE_CC" || sed -i '/#include "chrome\/browser\/ui\/extensions\/extensions_menu_view_model.h"/a\#include "chrome/browser/ui/toolbar/toolbar_action_view_model.h"' "$MENU_DELEGATE_CC"
grep -q 'components/tabs/public/tab_interface.h' "$MENU_DELEGATE_CC" || sed -i '/#include "chrome\/browser\/ui\/extensions\/extensions_menu_view_model.h"/a\#include "components/tabs/public/tab_interface.h"' "$MENU_DELEGATE_CC"
grep -q 'extensions/browser/extension_registry.h' "$MENU_DELEGATE_CC" || sed -i '/#include "components\/tabs\/public\/tab_interface.h"/a\#include "extensions/browser/extension_registry.h"' "$MENU_DELEGATE_CC"
grep -q 'base/no_destructor.h' "$MENU_DELEGATE_CC" || sed -i '/#include "chrome\/browser\/ui\/android\/extensions\/extension_action_delegate_android.h"/a\#include "base/no_destructor.h"' "$MENU_DELEGATE_CC"
grep -q 'base/memory/weak_ptr.h' "$MENU_DELEGATE_CC" || sed -i '/#include "chrome\/browser\/ui\/android\/extensions\/extension_action_delegate_android.h"/a\#include "base/memory/weak_ptr.h"' "$MENU_DELEGATE_CC"
grep -q 'g_last_android_extension_action_tab_id' "$MENU_DELEGATE_CC" || sed -i '/constexpr gfx::Size kActionIconSize = gfx::Size(24, 24);/a\
int g_last_android_extension_action_tab_id = -1;\
base::WeakPtr<content::WebContents>&\
GetLastAndroidExtensionActionWebContentsStorage() {\
  static base::NoDestructor<base::WeakPtr<content::WebContents>> storage;\
  return *storage;\
}\
' "$MENU_DELEGATE_CC"
grep -qE 'GetLastAndroidExtensionActionWebContentsStorage|g_last_android_extension_action_web_contents' "$MENU_DELEGATE_CC" || sed -i '/int g_last_android_extension_action_tab_id = -1;/a\
base::WeakPtr<content::WebContents>&\
GetLastAndroidExtensionActionWebContentsStorage() {\
  static base::NoDestructor<base::WeakPtr<content::WebContents>> storage;\
  return *storage;\
}\
' "$MENU_DELEGATE_CC"
grep -q 'int GetLastAndroidExtensionActionTabId()' "$MENU_DELEGATE_CC" || sed -i '/using PermissionsManager = extensions::PermissionsManager;/a\
int GetLastAndroidExtensionActionTabId() {\
  return g_last_android_extension_action_tab_id;\
}\
\
' "$MENU_DELEGATE_CC"
grep -q 'content::WebContents\* GetLastAndroidExtensionActionWebContents()' "$MENU_DELEGATE_CC" || sed -i '/using PermissionsManager = extensions::PermissionsManager;/a\
content::WebContents* GetLastAndroidExtensionActionWebContents() {\
  content::WebContents* cached_contents =\
      GetLastAndroidExtensionActionWebContentsStorage().get();\
  for (TabModel* tab_model : TabModelList::models()) {\
    if (!tab_model || !tab_model->IsOffTheRecord()) {\
      continue;\
    }\
    content::WebContents* contents = tab_model->GetActiveWebContents();\
    if (!contents) {\
      continue;\
    }\
    TabAndroid* tab = TabAndroid::FromWebContents(contents);\
    if ((tab && (tab->IsUserInteractable() || tab->IsActivated())) ||\
        contents == cached_contents) {\
      return contents;\
    }\
  }\
  return cached_contents;\
}\
\
' "$MENU_DELEGATE_CC"
grep -q 'void SetLastAndroidExtensionActionWebContents' "$MENU_DELEGATE_CC" || sed -i '/using PermissionsManager = extensions::PermissionsManager;/a\
void SetLastAndroidExtensionActionWebContents(content::WebContents* web_contents) {\
  GetLastAndroidExtensionActionWebContentsStorage() =\
      web_contents ? web_contents->GetWeakPtr()\
                   : base::WeakPtr<content::WebContents>();\
  g_last_android_extension_action_tab_id =\
      web_contents ? ExtensionTabUtil::GetTabId(web_contents) : -1;\
}\
\
' "$MENU_DELEGATE_CC"
grep -q 'web_contents ? web_contents->GetWeakPtr()' "$MENU_DELEGATE_CC" || perl -0pi -e 's|(void SetLastAndroidExtensionActionWebContents\(content::WebContents\* web_contents\) \{\n)|$1  GetLastAndroidExtensionActionWebContentsStorage() =\n      web_contents ? web_contents->GetWeakPtr()\n                   : base::WeakPtr<content::WebContents>();\n|' "$MENU_DELEGATE_CC"
perl -0pi -e 's|base::WeakPtr<content::WebContents> g_last_android_extension_action_web_contents;|base::WeakPtr<content::WebContents>\&\nGetLastAndroidExtensionActionWebContentsStorage() {\n  static base::NoDestructor<base::WeakPtr<content::WebContents>> storage;\n  return *storage;\n}|g; s|base::NoDestructor<base::WeakPtr<content::WebContents>>\n    g_last_android_extension_action_web_contents;|base::WeakPtr<content::WebContents>\&\nGetLastAndroidExtensionActionWebContentsStorage() {\n  static base::NoDestructor<base::WeakPtr<content::WebContents>> storage;\n  return *storage;\n}|g; s|return g_last_android_extension_action_web_contents\.get\(\);|return GetLastAndroidExtensionActionWebContentsStorage().get();|g; s|return g_last_android_extension_action_web_contents->get\(\);|return GetLastAndroidExtensionActionWebContentsStorage().get();|g; s|(?m)^\s*\*?g_last_android_extension_action_web_contents =|  GetLastAndroidExtensionActionWebContentsStorage() =|g' "$MENU_DELEGATE_CC"
python3 - "$MENU_DELEGATE_CC" <<'PYCODE'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
marker = "content::WebContents* GetLastAndroidExtensionActionWebContents() {"
start = text.find(marker)
if start < 0:
    raise SystemExit(f"action WebContents getter not found in {path}")
brace = text.find("{", start)
depth = 0
end = None
for idx in range(brace, len(text)):
    if text[idx] == "{":
        depth += 1
    elif text[idx] == "}":
        depth -= 1
        if depth == 0:
            end = idx + 1
            break
if end is None:
    raise SystemExit(f"action WebContents getter end not found in {path}")
replacement = """content::WebContents* GetLastAndroidExtensionActionWebContents() {
  content::WebContents* cached_contents =
      GetLastAndroidExtensionActionWebContentsStorage().get();
  for (TabModel* tab_model : TabModelList::models()) {
    if (!tab_model || !tab_model->IsOffTheRecord()) {
      continue;
    }
    content::WebContents* contents = tab_model->GetActiveWebContents();
    if (!contents) {
      continue;
    }
    TabAndroid* tab = TabAndroid::FromWebContents(contents);
    if ((tab && (tab->IsUserInteractable() || tab->IsActivated())) ||
        contents == cached_contents) {
      return contents;
    }
  }
  return cached_contents;
}"""
text = text[:start] + replacement + text[end:]
path.write_text(text)
PYCODE
perl -0pi -e 's|void ExtensionsMenuDelegateAndroid::ExecuteAction\(\n    JNIEnv\* env,\n    const extensions::ExtensionId& extension_id\) \{\n  menu_model_->ExecuteAction\(extension_id\);\n\}|void ExtensionsMenuDelegateAndroid::ExecuteAction(\n    JNIEnv* env,\n    const extensions::ExtensionId& extension_id,\n    content::WebContents* web_contents) {\n  if (web_contents) {\n    tabs::TabInterface* tab =\n        tabs::TabInterface::MaybeGetFromContents(web_contents);\n    BrowserWindowInterface* action_browser =\n        tab ? tab->GetBrowserWindowInterface() : nullptr;\n    TabListInterface* tab_list =\n        action_browser ? TabListInterface::From(action_browser) : nullptr;\n    extensions::ExtensionRegistry* registry =\n        action_browser\n            ? extensions::ExtensionRegistry::Get(action_browser->GetProfile())\n            : nullptr;\n    if (tab_list \&\& registry \&\&\n        registry->enabled_extensions().Contains(extension_id)) {\n      tab_list->ActivateTab(tab->GetHandle());\n      auto action_model = ExtensionActionViewModel::Create(\n          extension_id, action_browser,\n          std::make_unique<ExtensionActionDelegateAndroid>(\n              action_browser, extension_id, toolbar_android_, java_object_));\n      action_model->ExecuteUserAction(\n          ToolbarActionViewModel::InvocationSource::kMenuEntry);\n      return;\n    }\n  }\n\n  menu_model_->ExecuteAction(extension_id);\n}|' "$MENU_DELEGATE_CC"
perl -0pi -e 's|if \(web_contents\) \{\n    g_last_android_extension_action_tab_id = ExtensionTabUtil::GetTabId\(web_contents\);\n  \}|SetLastAndroidExtensionActionWebContents(web_contents);|g' "$MENU_DELEGATE_CC"
grep -q 'SetLastAndroidExtensionActionWebContents(web_contents);' "$MENU_DELEGATE_CC" || perl -0pi -e 's|(void ExtensionsMenuDelegateAndroid::ExecuteAction\(\n    JNIEnv\* env,\n    const extensions::ExtensionId& extension_id,\n    content::WebContents\* web_contents\) \{\n)|$1  SetLastAndroidExtensionActionWebContents(web_contents);\n|' "$MENU_DELEGATE_CC"
perl -0pi -e 's|ScopedJavaLocalRef<jobject> ExtensionsMenuDelegateAndroid::GetActionIcon\(\n    JNIEnv\* env,\n    int action_index\) \{\n  ui::ImageModel icon_model =\n      menu_model_->GetActionIcon\(action_index, kActionIconSize\);\n  return ConvertToJavaBitmap\(icon_model\);\n\}|ScopedJavaLocalRef<jobject> ExtensionsMenuDelegateAndroid::GetActionIcon(\n    JNIEnv* env,\n    int action_index,\n    content::WebContents* web_contents) {\n  if (web_contents) {\n    const auto\& action_models = menu_model_->action_models();\n    CHECK_GE(action_index, 0);\n    CHECK_LT(static_cast<size_t>(action_index), action_models.size());\n    return ConvertToJavaBitmap(\n        action_models[action_index]->GetIcon(web_contents, kActionIconSize));\n  }\n\n  ui::ImageModel icon_model =\n      menu_model_->GetActionIcon(action_index, kActionIconSize);\n  return ConvertToJavaBitmap(icon_model);\n}|' "$MENU_DELEGATE_CC"
perl -0pi -e 's|ScopedJavaLocalRef<jobject> ExtensionsMenuDelegateAndroid::GetMenuEntry\(\n    JNIEnv\* env,\n    int action_index\) \{|ScopedJavaLocalRef<jobject> ExtensionsMenuDelegateAndroid::GetMenuEntry(\n    JNIEnv* env,\n    int action_index,\n    content::WebContents* web_contents) {|' "$MENU_DELEGATE_CC"
grep -q 'action_model->GetActionTitle(web_contents)' "$MENU_DELEGATE_CC" || perl -0pi -e 's|  ExtensionsMenuViewModel::MenuEntryState state =\n      menu_model_->GetMenuEntryState\(id, kActionIconSize\);\n|  ExtensionsMenuViewModel::MenuEntryState state =\n      menu_model_->GetMenuEntryState(id, kActionIconSize);\n  if (web_contents) {\n    std::u16string action_title = action_model->GetActionTitle(web_contents);\n    if (!action_title.empty()) {\n      state.action_button.text = action_title;\n    }\n    state.action_button.tooltip_text = action_model->GetTooltip(web_contents);\n    state.action_button.status =\n        action_model->IsEnabled(web_contents)\n            ? ExtensionsMenuViewModel::ControlState::Status::kEnabled\n            : ExtensionsMenuViewModel::ControlState::Status::kDisabled;\n    state.action_button.icon =\n        action_model->GetIcon(web_contents, kActionIconSize);\n    state.origin = web_contents->GetPrimaryMainFrame()->GetLastCommittedOrigin();\n  }\n|' "$MENU_DELEGATE_CC"
perl -0pi -e 's|std::u16string action_title = action_model->GetActionTitle\(web_contents\);\n    state\.action_button\.text = action_title\.empty\(\)\n                                   \? action_model->GetActionName\(\)\n                                   : action_title;|std::u16string action_title = action_model->GetActionTitle(web_contents);\n    if (!action_title.empty()) {\n      state.action_button.text = action_title;\n    }|' "$MENU_DELEGATE_CC"
perl -0pi -e 's|ExtensionsMenuDelegateAndroid::GetMenuEntries\(JNIEnv\* env\) \{|ExtensionsMenuDelegateAndroid::GetMenuEntries(\n    JNIEnv* env,\n    content::WebContents* web_contents) {|' "$MENU_DELEGATE_CC"
sed -i 's|GetMenuEntry(env, i)|GetMenuEntry(env, i, web_contents)|g' "$MENU_DELEGATE_CC"
python3 - "$MENU_DELEGATE_CC" <<'PYCODE'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()

def replace_function(text, name, replacement):
    marker = f"ExtensionsMenuDelegateAndroid::{name}("
    name_pos = text.find(marker)
    if name_pos < 0:
        raise SystemExit(f"{name} not found in {path}")
    start = text.rfind("\n", 0, name_pos)
    start = 0 if start < 0 else start + 1
    brace = text.find("{", name_pos)
    if brace < 0:
        raise SystemExit(f"{name} body not found in {path}")
    depth = 0
    end = None
    for idx in range(brace, len(text)):
        if text[idx] == "{":
            depth += 1
        elif text[idx] == "}":
            depth -= 1
            if depth == 0:
                end = idx + 1
                break
    if end is None:
        raise SystemExit(f"{name} body end not found in {path}")
    return text[:start] + replacement + text[end:]

get_action_icon = """ScopedJavaLocalRef<jobject> ExtensionsMenuDelegateAndroid::GetActionIcon(
    JNIEnv* env,
    int action_index,
    content::WebContents* web_contents) {
  // Prefer the visible tab supplied by the Android UI. The cached action
  // WebContents is only a fallback for callers that have no current tab.
  if (!web_contents) {
    if (content::WebContents* active_contents =
            GetLastAndroidExtensionActionWebContents()) {
      Profile* active_profile =
          Profile::FromBrowserContext(active_contents->GetBrowserContext());
      if (browser_->GetProfile()->IsSameOrParent(active_profile)) {
        web_contents = active_contents;
      }
    }
  }
  const auto& action_models = menu_model_->action_models();
  CHECK_GE(action_index, 0);
  CHECK_LT(static_cast<size_t>(action_index), action_models.size());
  if (web_contents) {
    return ConvertToJavaBitmap(
        action_models[action_index]->GetIcon(web_contents, kActionIconSize));
  }

  ui::ImageModel icon_model =
      menu_model_->GetActionIcon(action_index, kActionIconSize);
  return ConvertToJavaBitmap(icon_model);
}

"""

get_menu_entry = """ScopedJavaLocalRef<jobject> ExtensionsMenuDelegateAndroid::GetMenuEntry(
    JNIEnv* env,
    int action_index,
    content::WebContents* web_contents) {
  // Prefer the visible tab supplied by the Android UI. The cached action
  // WebContents is only a fallback for callers that have no current tab.
  if (!web_contents) {
    if (content::WebContents* active_contents =
            GetLastAndroidExtensionActionWebContents()) {
      Profile* active_profile =
          Profile::FromBrowserContext(active_contents->GetBrowserContext());
      if (browser_->GetProfile()->IsSameOrParent(active_profile)) {
        web_contents = active_contents;
      }
    }
  }
  const auto& action_models = menu_model_->action_models();
  CHECK_GE(action_index, 0);
  CHECK_LT(static_cast<size_t>(action_index), action_models.size());

  const auto& action_model = action_models[action_index];
  extensions::ExtensionId id = action_model->GetId();
  ExtensionsMenuViewModel::MenuEntryState state =
      menu_model_->GetMenuEntryState(id, kActionIconSize);
  if (web_contents) {
    std::u16string action_title = action_model->GetActionTitle(web_contents);
    if (!action_title.empty()) {
      state.action_button.text = action_title;
    }
    state.action_button.accessible_name =
        action_model->GetAccessibleName(web_contents);
    state.action_button.tooltip_text = action_model->GetTooltip(web_contents);
    state.action_button.status =
        action_model->IsEnabled(web_contents)
            ? ExtensionsMenuViewModel::ControlState::Status::kEnabled
            : ExtensionsMenuViewModel::ControlState::Status::kDisabled;
    state.action_button.icon =
        action_model->GetIcon(web_contents, kActionIconSize);
    state.origin = web_contents->GetPrimaryMainFrame()->GetLastCommittedOrigin();
  }

  return Java_MenuEntryState_Constructor(
      env, id, CreateJavaControlState(env, state.action_button),
      CreateJavaControlState(env, state.context_menu_button),
      CreateJavaControlState(env, state.site_access_toggle),
      CreateJavaControlState(env, state.site_permissions_button),
      state.is_enterprise, state.origin.Serialize());
}

"""

text = replace_function(text, "GetActionIcon", get_action_icon)
text = replace_function(text, "GetMenuEntry", get_menu_entry)
path.write_text(text)
PYCODE

grep -q 'public void setActiveWebContents' "$TOOLBAR_BRIDGE" || perl -0pi -e 's|(\n    public void executeUserAction\(String actionId, \@InvocationSource int source\) \{\n)|\n    public void setActiveWebContents(\@Nullable WebContents webContents) {\n        assert mNativeExtensionsToolbarAndroid != 0;\n        ExtensionsToolbarBridgeJni.get()\n                .setActiveWebContents(mNativeExtensionsToolbarAndroid, webContents);\n    }\n$1|' "$TOOLBAR_BRIDGE"
perl -0pi -e 's|\n        if \(mProfile\.shutdownStarted\(\)\) \{\n            return;\n        \}(\n        ExtensionsToolbarBridgeJni\.get\(\)\n                \.setActiveWebContents)|$1|' "$TOOLBAR_BRIDGE"
perl -0pi -e 'if (!/void setActiveWebContents\(\n\s+long nativeExtensionsToolbarAndroid,/) { s|(\n        void executeUserAction\(\n                long nativeExtensionsToolbarAndroid,)|\n        void setActiveWebContents(\n                long nativeExtensionsToolbarAndroid,\n                \@Nullable \@JniType("content::WebContents*") WebContents webContents);\n$1| }' "$TOOLBAR_BRIDGE"
python3 - "$ACTION_LIST_MEDIATOR" <<'PYCODE'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
text = path.read_text()
signature = re.compile(
    r"(?m)^[ \t]*(?:private[ \t]+)?@Nullable[ \t]+WebContents[ \t]+"
    r"getCurrentWebContents\(\)[ \t]*\{"
)
while True:
    match = signature.search(text)
    if match is None:
        break
    start = text.rfind("\n", 0, match.start()) + 1
    brace = text.find("{", match.start(), match.end())
    depth = 0
    end = None
    for idx in range(brace, len(text)):
        if text[idx] == "{":
            depth += 1
        elif text[idx] == "}":
            depth -= 1
            if depth <= 0:
                end = idx + 1
                while end < len(text) and text[end] in "\r\n":
                    end += 1
                break
    if end is None:
        raise SystemExit(f"unterminated getCurrentWebContents helper in {path}")
    text = text[:start] + text[end:]

helper = """    private @Nullable WebContents getCurrentWebContents() {
        Tab incognitoTab = mTabModelSelector.getModel(true).getCurrentTabSupplier().get();
        if (incognitoTab != null
                && incognitoTab.getWebContents() != null
                && (mTabModelSelector.isOffTheRecordModelSelected()
                        || incognitoTab.isUserInteractable()
                        || incognitoTab.isActivated())) {
            return incognitoTab.getWebContents();
        }
        Tab currentTab = mTabModelSelector.getCurrentTab();
        if (currentTab != null && currentTab.getWebContents() != null) {
            return currentTab.getWebContents();
        }
        Tab suppliedTab = mCurrentTabSupplier.get();
        if (suppliedTab != null && suppliedTab.getWebContents() != null) {
            return suppliedTab.getWebContents();
        }
        return incognitoTab != null ? incognitoTab.getWebContents() : null;
    }

"""
anchor = re.search(
    r"(?m)^    (?:private )?void updateActionPropertiesForAll\(WebContents webContents\) \{$",
    text,
)
if anchor is None:
    raise SystemExit(f"updateActionPropertiesForAll insertion anchor not found in {path}")
text = text[:anchor.start()] + helper + text[anchor.start():]
if len(signature.findall(text)) != 1:
    raise SystemExit(f"expected exactly one getCurrentWebContents helper in {path}")
path.write_text(text)
PYCODE
perl -0pi -e 's|Tab currentTab = mCurrentTabSupplier\.get\(\);\n        WebContents webContents = currentTab != null \? currentTab\.getWebContents\(\) : null;|WebContents webContents = getCurrentWebContents();|g' "$ACTION_LIST_MEDIATOR"
grep -q 'mExtensionsToolbarBridge.setActiveWebContents(getCurrentWebContents());' "$ACTION_LIST_MEDIATOR" || perl -0pi -e 's|(\n    public void executeUserAction\(String actionId, \@InvocationSource int source\) \{\n)|$1        mExtensionsToolbarBridge.setActiveWebContents(getCurrentWebContents());\n|' "$ACTION_LIST_MEDIATOR"
grep -q 'SetActiveWebContents' "$TOOLBAR_ANDROID_H" || perl -0pi -e 's|(  void ExecuteUserAction\(const ToolbarActionsModel::ActionId& action_id,\n                         ToolbarActionViewModel::InvocationSource source\);\n)|  void SetActiveWebContents(JNIEnv* env, content::WebContents* web_contents);\n$1|' "$TOOLBAR_ANDROID_H"
grep -q 'extensions_menu_delegate_android.h' "$TOOLBAR_ANDROID_CC" || sed -i '/#include "chrome\/browser\/ui\/android\/extensions\/extension_action_delegate_android.h"/a\#include "chrome/browser/ui/android/extensions/extensions_menu_delegate_android.h"' "$TOOLBAR_ANDROID_CC"
python3 - "$TOOLBAR_ANDROID_CC" <<'PYCODE'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
marker = "void ExtensionsToolbarAndroid::OnActiveWebContentsChanged("
start = text.find(marker)
if start < 0:
    raise SystemExit(f"OnActiveWebContentsChanged not found in {path}")
brace = text.find("{", start)
if brace < 0:
    raise SystemExit(f"OnActiveWebContentsChanged body not found in {path}")
body_end = text.find("\n}", brace)
if body_end < 0:
    raise SystemExit(f"OnActiveWebContentsChanged end not found in {path}")
setter = "  SetLastAndroidExtensionActionWebContents(web_contents);\n"
if setter not in text[brace:body_end]:
    text = text[:brace + 2] + setter + text[brace + 2:]
path.write_text(text)
PYCODE
python3 - "$TOOLBAR_ANDROID_CC" <<'PYCODE'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
resolver = """  // Prefer the visible tab supplied by the Android UI. The cached action
  // WebContents is only a fallback for callers that have no current tab.
  if (!web_contents) {
    if (content::WebContents* active_contents =
            GetLastAndroidExtensionActionWebContents()) {
      Profile* active_profile =
          Profile::FromBrowserContext(active_contents->GetBrowserContext());
      if (browser_->GetProfile()->IsSameOrParent(active_profile)) {
        web_contents = active_contents;
      }
    }
  }
"""

for name in ("GetAction", "GetIcon"):
    marker = f"ExtensionsToolbarAndroid::{name}("
    start = text.find(marker)
    if start < 0:
        raise SystemExit(f"{name} not found in {path}")
    brace = text.find("{", start)
    if brace < 0:
        raise SystemExit(f"{name} body not found in {path}")
    depth = 0
    end = None
    for idx in range(brace, len(text)):
        if text[idx] == "{":
            depth += 1
        elif text[idx] == "}":
            depth -= 1
            if depth == 0:
                end = idx + 1
                break
    if end is None:
        raise SystemExit(f"{name} end not found in {path}")
    if "GetLastAndroidExtensionActionWebContents()" not in text[brace:end]:
        text = text[:brace + 2] + resolver + text[brace + 2:]

path.write_text(text)
PYCODE
grep -q 'ExtensionsToolbarAndroid::SetActiveWebContents' "$TOOLBAR_ANDROID_CC" || sed -i '/void ExtensionsToolbarAndroid::ExecuteUserAction(/i\
void ExtensionsToolbarAndroid::SetActiveWebContents(\
    JNIEnv* env,\
    content::WebContents* web_contents) {\
  SetLastAndroidExtensionActionWebContents(web_contents);\
}\
\
' "$TOOLBAR_ANDROID_CC"

perl -0pi -e 's|bool ExtensionPrefs::IsIncognitoEnabled\(const ExtensionId& extension_id\) const \{\n  return ReadPrefAsBooleanAndReturn\(extension_id, kPrefIncognitoEnabled\);\n\}|bool ExtensionPrefs::IsIncognitoEnabled(const ExtensionId& extension_id) const {\n#if BUILDFLAG(IS_ANDROID)\n  return true;\n#else\n  return ReadPrefAsBooleanAndReturn(extension_id, kPrefIncognitoEnabled);\n#endif\n}|' extensions/browser/extension_prefs.cc
perl -0pi -e 's|void ExtensionPrefs::SetIsIncognitoEnabled\(const ExtensionId& extension_id,\n                                           bool enabled\) \{\n  UpdateExtensionPref\(extension_id, kPrefIncognitoEnabled,\n                      base::Value\(enabled\)\);\n  extension_pref_value_map_->SetExtensionIncognitoState\(extension_id, enabled\);\n\}|void ExtensionPrefs::SetIsIncognitoEnabled(const ExtensionId& extension_id,\n                                           bool enabled) {\n#if BUILDFLAG(IS_ANDROID)\n  enabled = true;\n#endif\n  UpdateExtensionPref(extension_id, kPrefIncognitoEnabled,\n                      base::Value(enabled));\n  extension_pref_value_map_->SetExtensionIncognitoState(extension_id, enabled);\n}|' extensions/browser/extension_prefs.cc

grep -q 'build/build_config.h' "$CHROME_EXTENSIONS_BROWSER_CLIENT" || sed -i '/#include "base\/containers\/contains.h"/a\#include "build/build_config.h"' "$CHROME_EXTENSIONS_BROWSER_CLIENT"
grep -q 'chrome/browser/android/tab_android.h' "$CHROME_EXTENSIONS_BROWSER_CLIENT" || sed -i '/#include "build\/build_config.h"/a\
#if BUILDFLAG(IS_ANDROID)\
#include "chrome/browser/android/tab_android.h"\
#endif' "$CHROME_EXTENSIONS_BROWSER_CLIENT"
python3 - "$CHROME_EXTENSIONS_BROWSER_CLIENT" <<'PYCODE'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
marker = "HeliumAndroidTabIdFallback"
if marker not in text:
    old = """void ChromeExtensionsBrowserClient::GetTabAndWindowIdForWebContents(
    content::WebContents* web_contents,
    int* tab_id,
    int* window_id) {
  sessions::SessionTabHelper* session_tab_helper =
      sessions::SessionTabHelper::FromWebContents(web_contents);
  if (session_tab_helper) {
    *tab_id = session_tab_helper->session_id().id();
    *window_id = session_tab_helper->window_id().id();
  } else {
    *tab_id = -1;
    *window_id = -1;
  }
}
"""
    new = """void ChromeExtensionsBrowserClient::GetTabAndWindowIdForWebContents(
    content::WebContents* web_contents,
    int* tab_id,
    int* window_id) {
  sessions::SessionTabHelper* session_tab_helper =
      sessions::SessionTabHelper::FromWebContents(web_contents);
  if (session_tab_helper) {
    *tab_id = session_tab_helper->session_id().id();
    *window_id = session_tab_helper->window_id().id();
  } else {
    *tab_id = -1;
    *window_id = -1;
  }

#if BUILDFLAG(IS_ANDROID)
  // HeliumAndroidTabIdFallback: Android incognito WebContents may not have a
  // SessionTabHelper when extension webRequest details are built.
  if ((*tab_id == -1 || *window_id == -1) && web_contents) {
    TabAndroid* tab = TabAndroid::FromWebContents(web_contents);
    if (tab) {
      if (*tab_id == -1) {
        *tab_id = tab->GetAndroidId();
      }
      if (*window_id == -1 && tab->GetWindowId().is_valid()) {
        *window_id = tab->GetWindowId().id();
      }
    }
  }
#endif
}
"""
    if old not in text:
        raise SystemExit(f"GetTabAndWindowIdForWebContents pattern not found in {path}")
    text = text.replace(old, new, 1)
path.write_text(text)
PYCODE

grep -q 'build/build_config.h' "$EXTENSION_TAB_UTIL_CC" || sed -i '/#include "base\/strings\/utf_string_conversions.h"/a\#include "build/build_config.h"' "$EXTENSION_TAB_UTIL_CC"
grep -q 'chrome/browser/android/tab_android.h' "$EXTENSION_TAB_UTIL_CC" || sed -i '/#include "chrome\/browser\/ui\/android\/tab_model\/tab_model.h"/i\
#include "chrome/browser/android/tab_android.h"' "$EXTENSION_TAB_UTIL_CC"
python3 - "$EXTENSION_TAB_UTIL_CC" <<'PYCODE'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
if "HeliumAndroidExtensionTabIdFallback" not in text:
    old = """int GetTabIdForExtensions(WebContents& web_contents) {
  BrowserWindowInterface* browser =
      browser_window_util::GetBrowserForTabContents(web_contents);
  if (browser && !ExtensionTabUtil::BrowserSupportsTabs(browser)) {
    return -1;
  }
  return sessions::SessionTabHelper::IdForTab(&web_contents).id();
}
"""
    new = """int GetTabIdForExtensions(WebContents& web_contents) {
  BrowserWindowInterface* browser =
      browser_window_util::GetBrowserForTabContents(web_contents);
  if (browser && !ExtensionTabUtil::BrowserSupportsTabs(browser)) {
    return -1;
  }
  int tab_id = sessions::SessionTabHelper::IdForTab(&web_contents).id();
#if BUILDFLAG(IS_ANDROID)
  // HeliumAndroidExtensionTabIdFallback: keep Android incognito extension
  // tabs/webRequest/action state keyed by a valid TabAndroid id.
  if (tab_id == -1) {
    TabAndroid* tab = TabAndroid::FromWebContents(&web_contents);
    if (tab) {
      tab_id = tab->GetAndroidId();
    }
  }
#endif
  return tab_id;
}
"""
    if old not in text:
        raise SystemExit(f"GetTabIdForExtensions pattern not found in {path}")
    text = text.replace(old, new, 1)

    old = """int ExtensionTabUtil::GetTabId(const WebContents* web_contents) {
  return sessions::SessionTabHelper::IdForTab(web_contents).id();
}
"""
    new = """int ExtensionTabUtil::GetTabId(const WebContents* web_contents) {
  int tab_id = sessions::SessionTabHelper::IdForTab(web_contents).id();
#if BUILDFLAG(IS_ANDROID)
  if (tab_id == -1) {
    const TabAndroid* tab = TabAndroid::FromWebContents(web_contents);
    if (tab) {
      tab_id = tab->GetAndroidId();
    }
  }
#endif
  return tab_id;
}
"""
    if old not in text:
        raise SystemExit(f"GetTabId pattern not found in {path}")
    text = text.replace(old, new, 1)

    old = """int ExtensionTabUtil::GetWindowIdOfTab(const WebContents* web_contents) {
  return sessions::SessionTabHelper::IdForWindowContainingTab(web_contents)
      .id();
}
"""
    new = """int ExtensionTabUtil::GetWindowIdOfTab(const WebContents* web_contents) {
  int window_id =
      sessions::SessionTabHelper::IdForWindowContainingTab(web_contents).id();
#if BUILDFLAG(IS_ANDROID)
  if (window_id == -1) {
    const TabAndroid* tab = TabAndroid::FromWebContents(web_contents);
    if (tab && tab->GetWindowId().is_valid()) {
      window_id = tab->GetWindowId().id();
    }
  }
#endif
  return window_id;
}
"""
    if old not in text:
        raise SystemExit(f"GetWindowIdOfTab pattern not found in {path}")
    text = text.replace(old, new, 1)
    text = text.replace(
        """      if (sessions::SessionTabHelper::IdForTab(target_contents).id() ==
          tab_id) {
""",
        """      int target_tab_id = sessions::SessionTabHelper::IdForTab(target_contents).id();
#if BUILDFLAG(IS_ANDROID)
      if (target_tab_id == -1) {
        const TabAndroid* target_tab =
            TabAndroid::FromWebContents(target_contents);
        if (target_tab) {
          target_tab_id = target_tab->GetAndroidId();
        }
      }
#endif
      if (target_tab_id == tab_id) {
""",
        1,
    )
    text = text.replace(
        """      if (sessions::SessionTabHelper::IdForTab(web_contents).id() != tab_id) {
        return;
      }
""",
        """      int prerender_tab_id = sessions::SessionTabHelper::IdForTab(web_contents).id();
#if BUILDFLAG(IS_ANDROID)
      if (prerender_tab_id == -1) {
        const TabAndroid* prerender_tab =
            TabAndroid::FromWebContents(web_contents);
        if (prerender_tab) {
          prerender_tab_id = prerender_tab->GetAndroidId();
        }
      }
#endif
      if (prerender_tab_id != tab_id) {
        return;
      }
""",
        1,
    )
path.write_text(text)
PYCODE

perl -0pi -e 's|#include "chrome/browser/extensions/extension_tab_util\.h"\n||g' "$EXTENSION_ACTION_VIEW_MODEL"
if grep -q '#include "chrome/browser/extensions/chrome_extension_function_details.h"' "$EXTENSION_ACTION_VIEW_MODEL"; then
  sed -i '/#include "chrome\/browser\/extensions\/chrome_extension_function_details.h"/a\#include "chrome/browser/extensions/extension_tab_util.h"' "$EXTENSION_ACTION_VIEW_MODEL"
else
  sed -i '/#include "base\/strings\/utf_string_conversions.h"/a\#include "chrome/browser/extensions/extension_tab_util.h"' "$EXTENSION_ACTION_VIEW_MODEL"
fi
perl -0pi -e 's|sessions::SessionTabHelper::IdForTab\(web_contents\)\.id\(\)|extensions::ExtensionTabUtil::GetTabId(web_contents)|g; s|(?<!extensions::)ExtensionTabUtil::GetTabId\(web_contents\)|extensions::ExtensionTabUtil::GetTabId(web_contents)|g; s|extensions::extensions::ExtensionTabUtil::GetTabId\(web_contents\)|extensions::ExtensionTabUtil::GetTabId(web_contents)|g' "$EXTENSION_ACTION_VIEW_MODEL"

# ext: priority
sed -i 's|host_contents_->SetColorProviderSource(NoOpColorProviderSource::Get());|&\nhost_contents_->SetPrimaryPageImportance(content::ChildProcessImportance::IMPORTANT, content::ChildProcessImportance::NORMAL);|' extensions/browser/extension_host.cc

# ext: perms prompt
sed -i '/content::WebContents\* web_contents = show_params->GetParentWebContents();/,/DCHECK(view_android);/{/GetParentWebContents/!d}' chrome/browser/ui/android/extensions/extension_install_dialog_view_android.cc
sed -i 's|view_android->GetWindowAndroid();|show_params->GetParentWindow();|' chrome/browser/ui/android/extensions/extension_install_dialog_view_android.cc
sed -i 's|"platforms": \["win", "mac"\]|"platforms": ["win", "mac", "desktop_android"]|' chrome/common/extensions/api/_manifest_features.json

# ext: dialog and unpacked locale handling
sed -i 's|.with(ModalDialogProperties.FILTER_TOUCH_FOR_SECURITY, true)|.with(ModalDialogProperties.FILTER_TOUCH_FOR_SECURITY, false)|' chrome/browser/ui/android/extensions/java/src/org/chromium/chrome/browser/ui/extensions/ExtensionInstallDialogBridge.java
sed -i 's|while (!(locale_path = locales.Next()).empty()) {|&if (locale_path.IsContentUri()) { locale_path = path.Append(locales.GetInfo().GetName()); }|' extensions/common/manifest_handlers/default_locale_handler.cc
sed -i 's|while (!(locale_folder = locales.Next()).empty()) {|&if (locale_folder.IsContentUri()) { locale_folder = locale_path.Append(locales.GetInfo().GetName()); }|' extensions/common/extension_l10n_util.cc
sed -i '/extension_l10n_util::ValidateExtensionLocales($/,/error) &&$/{s|extension_l10n_util::ValidateExtensionLocales(|(extension_path_.IsVirtualDocumentPath() \|\| &|;s|error) &&|error)) \&\&|}' extensions/browser/unpacked_installer.cc

# ext: ntp
if version_lt "$VERSION" "152.0.7969.0"; then
sed -i 's|import org.chromium.chrome.browser.url_constants.UrlConstantResolverFactory;|&\nimport org.chromium.chrome.browser.url_constants.UrlOverrideUtils;|' chrome/android/java/src/org/chromium/chrome/browser/ChromeTabbedActivity.java
sed -i 's|if (isTabNtp \&\& !currentTab.isNativePage()) {|if (isTabNtp \&\& !currentTab.isNativePage() \&\& !UrlOverrideUtils.isNtpOverrideEnabled() \&\& !UrlOverrideUtils.isWebUiNtpOverrideEnabled()) {|' chrome/android/java/src/org/chromium/chrome/browser/ChromeTabbedActivity.java
else
sed -i 's|if (isTabNtp \&\& !currentTab.isNativePage() \&\& !isTabWebUiNtp) {|if (isTabNtp \&\& !currentTab.isNativePage() \&\& !isTabWebUiNtp \&\& !UrlOverrideUtils.isNtpOverrideEnabled()) {|' chrome/android/java/src/org/chromium/chrome/browser/ChromeTabbedActivity.java
fi

# desktop: omnibox
sed -i 's/is_desktop_android = !!BUILDFLAG(IS_DESKTOP_ANDROID);/is_desktop_android = false;/' components/omnibox/browser/zero_suggest_verbatim_match_provider.cc
sed -i 's/is_android_mobile = is_android_any \&\& !is_android_desktop;/is_android_mobile = is_android_any \&\& is_android_desktop;/' components/omnibox/browser/autocomplete_result.cc
# sed -i 's|OmniboxCapabilities.hasDesktopExperience(context)|true|g' chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/FuseboxSessionState.java

# tmp: config info
sed -i 's|if (!_omit_dex) {|if (_is_base_module \&\& !_omit_dex) {|' build/config/android/rules.gni

# tmp
sed -i 's|if (!IncognitoUtils.shouldOpenIncognitoAsWindow() \|\| isIncognitoShowing()) {|if (true) {|' chrome/android/java/src/org/chromium/chrome/browser/tabbed_mode/TabbedAppMenuPropertiesDelegate.java
sed -i 's|if (!separateIncognitoWindow \|\| isIncognito) {|if (true) {|' chrome/android/java/src/org/chromium/chrome/browser/tabbed_mode/TabbedAppMenuPropertiesDelegate.java
sed -i 's/BASE_FEATURE(kAndroidSearchInSettings,"SearchInSettings", base::FEATURE_DISABLED_BY_DEFAULT);/BASE_FEATURE(kAndroidSearchInSettings,"SearchInSettings", base::FEATURE_ENABLED_BY_DEFAULT);/' chrome/browser/flags/android/chrome_feature_list.cc
perl -0pi -e 's|current_toolchain == default_toolchain,|current_toolchain == default_toolchain \|\|\n        current_toolchain == "//build/toolchain/android:android_clang_arm64_webview",|' build/timestamp.gni

# crbug.com/406136787: load unpacked
sed -i 's|assert treeId.equals(documentId);|&\n if ("com.android.externalstorage.documents".equals(mAuthority)) { String fastId = mRelativePath.isEmpty() ? treeId : (treeId.endsWith(":") ? treeId + mRelativePath : treeId + "/" + mRelativePath); Uri fast = DocumentsContract.buildDocumentUriUsingTree(tree, fastId); return contentUriExists(fast) ? fast : null; }|' base/android/java/src/org/chromium/base/VirtualDocumentPath.java

# crbug.com/40831291: bottom address bar
sed -i 's@(idealFitsBelow && spaceBelowAnchor >= spaceAboveAnchor) || !idealFitsAbove;@(idealFitsBelow == idealFitsAbove) ? (spaceBelowAnchor >= spaceAboveAnchor) : idealFitsBelow;@' ui/android/java/src/org/chromium/ui/widget/PopupSpecCalculator.java

# On the NTP and while editing, follow the user's toolbar preference. Chromium's
# dropdown embedder places history and suggestions above a bottom toolbar.
TOOLBAR_POSITION_CONTROLLER=chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/ToolbarPositionController.java
if ! grep -q 'Helium: follow the toolbar preference on the NTP and while editing' "$TOOLBAR_POSITION_CONTROLLER"; then
perl -0pi -e 's~        // Helium: keep the focused omnibox at the bottom\.
        if \(isOmniboxFocused\) \{
            newControlsPosition = ControlsPosition\.BOTTOM;
        \} else if \(ntpShowing
                \|\| tabSwitcherShowing
                \|\| isFindInPageShowing
                \|\| doesUserPreferTopToolbar\) \{
            newControlsPosition = ControlsPosition\.TOP;
        \} else \{
            newControlsPosition = ControlsPosition\.BOTTOM;
        \}~        // Helium: follow the toolbar preference on the NTP and while editing.
        if (tabSwitcherShowing || isFindInPageShowing || doesUserPreferTopToolbar) {
            newControlsPosition = ControlsPosition.TOP;
        } else {
            newControlsPosition = ControlsPosition.BOTTOM;
        }~' "$TOOLBAR_POSITION_CONTROLLER"
perl -0pi -e 's~        if \(ntpShowing
                \|\| tabSwitcherShowing
                \|\| isOmniboxFocused
                \|\| isFindInPageShowing
                \|\| doesUserPreferTopToolbar\) \{
            newControlsPosition = ControlsPosition\.TOP;
        \} else \{
            newControlsPosition = ControlsPosition\.BOTTOM;
        \}~        // Helium: follow the toolbar preference on the NTP and while editing.
        if (tabSwitcherShowing || isFindInPageShowing || doesUserPreferTopToolbar) {
            newControlsPosition = ControlsPosition.TOP;
        } else {
            newControlsPosition = ControlsPosition.BOTTOM;
        }~' "$TOOLBAR_POSITION_CONTROLLER"
fi
if ! grep -q 'Helium: follow the toolbar preference on the NTP and while editing' "$TOOLBAR_POSITION_CONTROLLER"; then
echo "NTP and omnibox toolbar position patch did not apply: $TOOLBAR_POSITION_CONTROLLER" >&2
exit 1
fi

# In bottom-toolbar mode, use the real omnibox on the NTP instead of leaving a
# second fake search box at the top. Keep short suggestion lists adjacent to it.
NEW_TAB_PAGE=chrome/android/java/src/org/chromium/chrome/browser/ntp/NewTabPage.java
NEW_TAB_PAGE_COORDINATOR=chrome/android/java/src/org/chromium/chrome/browser/ntp/NewTabPageCoordinator.java
OMNIBOX_SUGGESTIONS_DROPDOWN=chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/suggestions/OmniboxSuggestionsDropdown.java
OMNIBOX_SUGGESTIONS_CONTAINER=chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/suggestions/OmniboxSuggestionsContainer.java
OMNIBOX_DROPDOWN_EMBEDDER=chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/OmniboxSuggestionsDropdownEmbedderImpl.java
OMNIBOX_DROPDOWN_EMBEDDER_INTERFACE=chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/suggestions/OmniboxSuggestionsDropdownEmbedder.java
FEED_SURFACE_COORDINATOR=chrome/android/feed/core/java/src/org/chromium/chrome/browser/feed/FeedSurfaceCoordinator.java
python3 - "$NEW_TAB_PAGE" "$NEW_TAB_PAGE_COORDINATOR" "$OMNIBOX_SUGGESTIONS_DROPDOWN" "$OMNIBOX_SUGGESTIONS_CONTAINER" "$OMNIBOX_DROPDOWN_EMBEDDER" "$OMNIBOX_DROPDOWN_EMBEDDER_INTERFACE" "$FEED_SURFACE_COORDINATOR" <<'PYCODE'
from pathlib import Path
import sys


def replace_if_missing(path, marker, old, new):
    text = path.read_text()
    if marker in text:
        return
    if old not in text:
        raise SystemExit(f"NTP bottom toolbar pattern not found in {path}: {marker}")
    path.write_text(text.replace(old, new, 1))


def replace_if_present(path, old, new):
    text = path.read_text()
    if old in text:
        path.write_text(text.replace(old, new, 1))


ntp = Path(sys.argv[1])
coordinator = Path(sys.argv[2])
dropdown = Path(sys.argv[3])
container = Path(sys.argv[4])
embedder = Path(sys.argv[5])
embedder_interface = Path(sys.argv[6])
feed_surface_coordinator = Path(sys.argv[7])

replace_if_missing(
    ntp,
    "import org.chromium.chrome.browser.toolbar.settings.AddressBarPreference;",
    "import org.chromium.chrome.browser.toolbar.top.Toolbar;\n",
    "import org.chromium.chrome.browser.toolbar.settings.AddressBarPreference;\n"
    "import org.chromium.chrome.browser.toolbar.top.Toolbar;\n",
)
replace_if_missing(
    ntp,
    "&& AddressBarPreference.isToolbarConfiguredToShowOnTop()",
    """            return isInSingleUrlBarMode() && !mNewTabPageCoordinator.urlFocusAnimationsDisabled();
""",
    """            return isInSingleUrlBarMode()
                    && AddressBarPreference.isToolbarConfiguredToShowOnTop()
                    && !mNewTabPageCoordinator.urlFocusAnimationsDisabled();
""",
)

replace_if_missing(
    coordinator,
    "import org.chromium.chrome.browser.toolbar.settings.AddressBarPreference;",
    "import org.chromium.chrome.browser.tasks.ReturnToChromeUtil;\n",
    "import org.chromium.chrome.browser.tasks.ReturnToChromeUtil;\n"
    "import org.chromium.chrome.browser.toolbar.settings.AddressBarPreference;\n",
)
replace_if_missing(
    coordinator,
    "private @Nullable Boolean mShowFakeSearchBoxForToolbarPosition;",
    "    private @Nullable Boolean mIsWhiteBackgroundOnSearchBoxApplied;\n",
    "    private @Nullable Boolean mIsWhiteBackgroundOnSearchBoxApplied;\n"
    "    private @Nullable Boolean mShowFakeSearchBoxForToolbarPosition;\n"
    "    private int mToolbarPositionTopInset = Integer.MIN_VALUE;\n",
)
replace_if_missing(
    coordinator,
    "mModel.set(NewTabPageLayoutProperties.SEARCH_BOX_VIEW, mNtpSearchBox.getView());\n"
    "        updateSearchBoxVisibilityForToolbarPosition();",
    "        mModel.set(NewTabPageLayoutProperties.SEARCH_BOX_VIEW, mNtpSearchBox.getView());\n",
    "        mModel.set(NewTabPageLayoutProperties.SEARCH_BOX_VIEW, mNtpSearchBox.getView());\n"
    "        updateSearchBoxVisibilityForToolbarPosition();\n",
)
replace_if_missing(
    coordinator,
    "private void updateSearchBoxVisibilityForToolbarPosition()",
    """    /**
     * @return The fake search box view.
     */
""",
    """    // Helium: the real omnibox is the NTP search entry when the toolbar is at the bottom.
    private void updateSearchBoxVisibilityForToolbarPosition() {
        boolean showFakeSearchBox =
                mIsTablet || AddressBarPreference.isToolbarConfiguredToShowOnTop();
        if (mShowFakeSearchBoxForToolbarPosition != null
                && mShowFakeSearchBoxForToolbarPosition == showFakeSearchBox
                && mToolbarPositionTopInset == mTopInset) {
            return;
        }
        mShowFakeSearchBoxForToolbarPosition = showFakeSearchBox;
        mToolbarPositionTopInset = mTopInset;
        if (mNtpSearchBox != null) {
            mNtpSearchBox
                    .getView()
                    .setVisibility(showFakeSearchBox ? View.VISIBLE : View.GONE);
        }
        int toolbarTopPadding =
                showFakeSearchBox
                        ? mActivity
                                .getResources()
                                .getDimensionPixelSize(R.dimen.toolbar_height_no_shadow)
                        : 0;
        mModel.set(NewTabPageLayoutProperties.TOP_INSET_PX, toolbarTopPadding + mTopInset);
    }

    /**
     * @return The fake search box view.
     */
    """,
)
coordinator_text = coordinator.read_text()
measure_marker = (
    "public void onMeasure(int width) {\n"
    "        updateSearchBoxVisibilityForToolbarPosition();"
)
if measure_marker not in coordinator_text:
    old_measure = """    public void onMeasure(int width) {
        if (mIsTablet && mMostVisitedTilesCoordinator != null) {
"""
    new_measure = """    public void onMeasure(int width) {
        updateSearchBoxVisibilityForToolbarPosition();
        if (mIsTablet && mMostVisitedTilesCoordinator != null) {
"""
    if old_measure not in coordinator_text:
        old_measure = """    public void onMeasure(int width) {
        unifyElementWidths(width);
"""
        new_measure = """    public void onMeasure(int width) {
        updateSearchBoxVisibilityForToolbarPosition();
        unifyElementWidths(width);
"""
    if old_measure not in coordinator_text:
        raise SystemExit(f"NTP onMeasure pattern not found in {coordinator}")
    coordinator.write_text(coordinator_text.replace(old_measure, new_measure, 1))

coordinator_text = coordinator.read_text()
if "private final boolean mIsLff;" in coordinator_text:
    coordinator_text = coordinator_text.replace(
        "mIsTablet || AddressBarPreference.isToolbarConfiguredToShowOnTop()",
        "mIsLff || AddressBarPreference.isToolbarConfiguredToShowOnTop()",
    )
    coordinator.write_text(coordinator_text)
replace_if_missing(
    coordinator,
    "public void onSwitchToForeground() {\n        updateSearchBoxVisibilityForToolbarPosition();",
    """    public void onSwitchToForeground() {
        if (mMostVisitedTilesCoordinator != null) {
""",
    """    public void onSwitchToForeground() {
        updateSearchBoxVisibilityForToolbarPosition();
        if (mMostVisitedTilesCoordinator != null) {
""",
)
replace_if_missing(
    coordinator,
    "mCurrentNtpFakeSearchBoxTransitionStartOffset =\n"
    "                getNtpSearchBoxTransitionStartOffset(!mSearchProviderHasLogo) + mTopInset;\n"
    "        updateSearchBoxVisibilityForToolbarPosition();",
    """        mCurrentNtpFakeSearchBoxTransitionStartOffset =
                getNtpSearchBoxTransitionStartOffset(!mSearchProviderHasLogo) + mTopInset;

        int toolbarHeightNoShadow =
                mActivity.getResources().getDimensionPixelSize(R.dimen.toolbar_height_no_shadow);
        // Top padding is applied to the NTP layout, ensuring all UI components remain in their
        // original positions after Status bar is hidden.
        mModel.set(NewTabPageLayoutProperties.TOP_INSET_PX, toolbarHeightNoShadow + mTopInset);
""",
    """        mCurrentNtpFakeSearchBoxTransitionStartOffset =
                getNtpSearchBoxTransitionStartOffset(!mSearchProviderHasLogo) + mTopInset;
        updateSearchBoxVisibilityForToolbarPosition();
""",
)

replace_if_missing(
    dropdown,
    "private boolean mAlignToBottom;",
    """        private boolean mCurrentGestureAffectedKeyboardState;
""",
    """        private boolean mCurrentGestureAffectedKeyboardState;
        private boolean mAlignToBottom;
""",
)
replace_if_present(
    dropdown,
    """            super.onLayoutChildren(recycler, state);
            // Helium: keep short bottom-omnibox suggestion lists next to the omnibox.
            if (mAlignToBottom && state.getItemCount() > 0) {
                View first = findViewByPosition(0);
                View last = findViewByPosition(state.getItemCount() - 1);
                if (first != null && last != null) {
                    int gap = getHeight() - getPaddingBottom() - getDecoratedBottom(last);
                    if (gap > 0) offsetChildrenVertical(gap);
                }
            }
        }
""",
    """            super.onLayoutChildren(recycler, state);
        }
""",
)
replace_if_present(
    dropdown,
    "if (mAlignToBottom || OmniboxFeatures.sResetSuggestionsScroll.isEnabled()) {",
    "if (OmniboxFeatures.sResetSuggestionsScroll.isEnabled()) {",
)
replace_if_present(
    dropdown,
    """        void setAlignToBottom(boolean alignToBottom) {
            if (mAlignToBottom == alignToBottom) return;
            mAlignToBottom = alignToBottom;
            requestLayout();
        }
""",
    """        void setAlignToBottom(boolean alignToBottom) {
            if (mAlignToBottom == alignToBottom) return;
            mAlignToBottom = alignToBottom;
            setReverseLayout(false);
            requestLayout();
        }
""",
)
replace_if_present(
    dropdown,
    """        void setAlignToBottom(boolean alignToBottom) {
            if (mAlignToBottom == alignToBottom) return;
            mAlignToBottom = alignToBottom;
            setReverseLayout(false);
            requestLayout();
        }
""",
    """        void setAlignToBottom(boolean alignToBottom) {
            if (mAlignToBottom == alignToBottom) return;
            mAlignToBottom = alignToBottom;
            setReverseLayout(false);
            requestLayout();
        }
""",
)
replace_if_present(
    dropdown,
    """        void setAlignToBottom(boolean alignToBottom) {
            if (mAlignToBottom == alignToBottom) return;
            mAlignToBottom = alignToBottom;
            setReverseLayout(alignToBottom);
            scrollToPositionWithOffset(0, 0);
            requestLayout();
        }
""",
    """        void setAlignToBottom(boolean alignToBottom) {
            if (mAlignToBottom == alignToBottom) return;
            mAlignToBottom = alignToBottom;
            setReverseLayout(false);
            requestLayout();
        }
""",
)
replace_if_present(
    dropdown,
    """        void setAlignToBottom(boolean alignToBottom) {
            if (mAlignToBottom == alignToBottom) return;
            mAlignToBottom = alignToBottom;
            setReverseLayout(alignToBottom);
            requestLayout();
        }
""",
    """        void setAlignToBottom(boolean alignToBottom) {
            if (mAlignToBottom == alignToBottom) return;
            mAlignToBottom = alignToBottom;
            setReverseLayout(false);
            requestLayout();
        }
""",
)
replace_if_missing(
    dropdown,
    "if (!mAlignToBottom && OmniboxFeatures.sResetSuggestionsScroll.isEnabled())",
    "if (OmniboxFeatures.sResetSuggestionsScroll.isEnabled()) {\n"
    "                scrollToPositionWithOffset(0, 0);\n"
    "            }\n"
    "            super.onLayoutChildren(recycler, state);",
    "if (!mAlignToBottom && OmniboxFeatures.sResetSuggestionsScroll.isEnabled()) {\n"
    "                scrollToPositionWithOffset(0, 0);\n"
    "            }\n"
    "            super.onLayoutChildren(recycler, state);",
)
replace_if_missing(
    dropdown,
    "void setAlignToBottom(boolean alignToBottom)",
    """        /**
         * Reset the internal scroll tracker. This needs to be called either when the
""",
    """        void setAlignToBottom(boolean alignToBottom) {
            if (mAlignToBottom == alignToBottom) return;
            mAlignToBottom = alignToBottom;
            setReverseLayout(false);
            requestLayout();
        }

        /**
         * Reset the internal scroll tracker. This needs to be called either when the
""",
)
replace_if_present(
    container,
    "setAlignToBottom(omniboxAlignment.top == 0);",
    "setAlignToBottom(omniboxAlignment.isBottomToolbar);",
)
replace_if_missing(
    container,
    "setAlignToBottom(omniboxAlignment.isBottomToolbar);",
    """        mOmniboxAlignment = omniboxAlignment;
        mDropdown.setPaddingRelative(
""",
    """        mOmniboxAlignment = omniboxAlignment;
        mDropdown.getLayoutScrollListener().setAlignToBottom(omniboxAlignment.isBottomToolbar);
        mDropdown.setPaddingRelative(
""",
)
replace_if_present(
    embedder,
    ".getInsets(WindowInsetsCompat.Type.statusBars())",
    ".getInsetsIgnoringVisibility(WindowInsetsCompat.Type.statusBars())",
)
replace_if_missing(
    embedder,
    "// Helium: keep bottom-toolbar suggestions below the status bar.",
    """        // TODO(pnoland@, https://crbug.com/40257117): avoid pushing changes that are identical to
        // the previous alignment value.
        OmniboxAlignment omniboxAlignment =
""",
    """        // Helium: keep bottom-toolbar suggestions below the status bar.
        int paddingTop = mTopPaddingForEdgeToEdge;
        if (controlsPosition == ControlsPosition.BOTTOM
                && contentView != null
                && contentView.getRootWindowInsets() != null) {
            int statusBarInset =
                    WindowInsetsCompat.toWindowInsetsCompat(
                                    contentView.getRootWindowInsets(), contentView)
                            .getInsetsIgnoringVisibility(WindowInsetsCompat.Type.statusBars())
                            .top;
            paddingTop = Math.max(paddingTop, statusBarInset);
        }

        // TODO(pnoland@, https://crbug.com/40257117): avoid pushing changes that are identical to
        // the previous alignment value.
        OmniboxAlignment omniboxAlignment =
""",
)
replace_if_present(
    embedder,
    "                        paddingTop,\n                        paddingBottom);",
    "                        paddingTop,\n"
    "                        paddingBottom,\n"
    "                        controlsPosition == ControlsPosition.BOTTOM);",
)
replace_if_missing(
    embedder,
    "paddingBottom,\n                        controlsPosition == ControlsPosition.BOTTOM);",
    """                        mTopPaddingForEdgeToEdge,
                        paddingBottom);
""",
    """                        paddingTop,
                        paddingBottom,
                        controlsPosition == ControlsPosition.BOTTOM);
""",
)

# The previous revisions inferred bottom mode from top == 0 and only reversed
# item traversal. Normalize them to an explicit alignment flag and anchor the
# list from the end so adapter position 0 stays next to the bottom omnibox.
replace_if_present(
    dropdown,
    """            super.onLayoutChildren(recycler, state);
            // Helium: anchor short bottom-toolbar suggestion lists above the omnibox.
            if (mAlignToBottom && getChildCount() > 0) {
                View bottomChild = getChildAt(getChildCount() - 1);
                int availableBottom = getHeight() - getPaddingBottom();
                int gap = availableBottom - getDecoratedBottom(bottomChild);
                if (gap > 0) offsetChildrenVertical(gap);
            }
""",
    """            super.onLayoutChildren(recycler, state);
""",
)
replace_if_present(
    dropdown,
    """            if (OmniboxFeatures.sResetSuggestionsScroll.isEnabled()) {
                scrollToPositionWithOffset(0, 0);
            }
""",
    """            if (!mAlignToBottom && OmniboxFeatures.sResetSuggestionsScroll.isEnabled()) {
                scrollToPositionWithOffset(0, 0);
            }
""",
)
replace_if_present(
    embedder,
    """        int paddingTop = mTopPaddingForEdgeToEdge;
        if (controlsPosition == ControlsPosition.BOTTOM
                && contentView != null
                && contentView.getRootWindowInsets() != null) {
            int statusBarInset =
                    WindowInsetsCompat.toWindowInsetsCompat(
                                    contentView.getRootWindowInsets(), contentView)
                            .getInsetsIgnoringVisibility(WindowInsetsCompat.Type.statusBars())
                            .top;
            paddingTop = Math.max(paddingTop, statusBarInset);
        }
""",
    """        int paddingTop = mTopPaddingForEdgeToEdge;
""",
)
replace_if_present(
    dropdown,
    """            setStackFromEnd(alignToBottom);
            scrollToPositionWithOffset(0, 0);
            requestLayout();
""",
    """            setStackFromEnd(alignToBottom);
            if (!alignToBottom) scrollToPositionWithOffset(0, 0);
            requestLayout();
""",
)
replace_if_missing(
    dropdown,
    "if (!mAlignToBottom) {\n                postOnAnimation(() -> scrollToPositionWithOffset(0, 0));",
    """            postOnAnimation(() -> scrollToPositionWithOffset(0, 0));
""",
    """            if (!mAlignToBottom) {
                postOnAnimation(() -> scrollToPositionWithOffset(0, 0));
            }
""",
)
replace_if_present(
    dropdown,
    """        mLayoutScrollListener.scrollToPositionWithOffset(0, 0);
        mSelectionController.reset();
""",
    """        if (!mLayoutScrollListener.mAlignToBottom) {
            mLayoutScrollListener.scrollToPositionWithOffset(0, 0);
        }
        mSelectionController.reset();
""",
)
replace_if_present(
    dropdown,
    """            setReverseLayout(false);
            requestLayout();
""",
    """            setReverseLayout(alignToBottom);
            setStackFromEnd(alignToBottom);
            if (!alignToBottom) scrollToPositionWithOffset(0, 0);
            requestLayout();
""",
)
if "setStackFromEnd(alignToBottom);" not in dropdown.read_text():
    raise SystemExit(f"Bottom suggestion stack-from-end patch did not apply: {dropdown}")

replace_if_missing(
    embedder_interface,
    "public final boolean isBottomToolbar;",
    "        public final int paddingBottom;\n",
    "        public final int paddingBottom;\n"
    "        public final boolean isBottomToolbar;\n",
)
replace_if_missing(
    embedder_interface,
    "int paddingBottom,\n                boolean isBottomToolbar)",
    """                int paddingTop,
                int paddingBottom) {
            this.left = left;
""",
    """                int paddingTop,
                int paddingBottom) {
            this(
                    left,
                    top,
                    width,
                    height,
                    paddingLeft,
                    paddingRight,
                    paddingTop,
                    paddingBottom,
                    false);
        }

        public OmniboxAlignment(
                int left,
                int top,
                int width,
                int height,
                int paddingLeft,
                int paddingRight,
                int paddingTop,
                int paddingBottom,
                boolean isBottomToolbar) {
            this.left = left;
""",
)
replace_if_missing(
    embedder_interface,
    "this.isBottomToolbar = isBottomToolbar;",
    "            this.paddingBottom = paddingBottom;\n",
    "            this.paddingBottom = paddingBottom;\n"
    "            this.isBottomToolbar = isBottomToolbar;\n",
)
replace_if_missing(
    embedder_interface,
    "&& other.isBottomToolbar == this.isBottomToolbar",
    "                    && other.height == this.height\n",
    "                    && other.height == this.height\n"
    "                    && other.isBottomToolbar == this.isBottomToolbar\n",
)

replace_if_present(
    container,
    "setAlignToBottom(omniboxAlignment.top == 0);",
    "setAlignToBottom(omniboxAlignment.isBottomToolbar);",
)
replace_if_missing(
    embedder,
    "// Helium: reserve the status-bar region in the dropdown geometry.",
    """        int top;
        int left;
        int width;
        int paddingLeft = 0;
        int paddingRight = 0;

        @ControlsPosition int controlsPosition = mControlsPositionSupplier.get();
        if (controlsPosition == ControlsPosition.BOTTOM) {
            top = 0;
""",
    """        @ControlsPosition int controlsPosition = mControlsPositionSupplier.get();
        // Helium: reserve the status-bar region in the dropdown geometry.
        int statusBarInset = 0;
        if (controlsPosition == ControlsPosition.BOTTOM
                && contentView != null
                && contentView.getRootWindowInsets() != null) {
            statusBarInset =
                    WindowInsetsCompat.toWindowInsetsCompat(
                                    contentView.getRootWindowInsets(), contentView)
                            .getInsetsIgnoringVisibility(WindowInsetsCompat.Type.statusBars())
                            .top;
        }

        int top;
        int left;
        int width;
        int paddingLeft = 0;
        int paddingRight = 0;

        if (controlsPosition == ControlsPosition.BOTTOM) {
            top = statusBarInset;
""",
)
replace_if_missing(
    embedder,
    "- navBarHeight\n                            - statusBarInset;",
    "- navBarHeight;",
    "- navBarHeight\n                            - statusBarInset;",
)
replace_if_missing(
    embedder,
    "paddingBottom,\n                        controlsPosition == ControlsPosition.BOTTOM);",
    """                        paddingTop,
                        paddingBottom);
""",
    """                        paddingTop,
                        paddingBottom,
                        controlsPosition == ControlsPosition.BOTTOM);
""",
)

# NewTabPageLayout is a RecyclerView header, so MATCH_PARENT on the header is
# measured as content height. Insert a real adapter spacer before the NTP header
# to place the tiles immediately above a bottom toolbar.
replace_if_missing(
    feed_surface_coordinator,
    "import org.chromium.chrome.browser.toolbar.settings.AddressBarPreference;",
    "import org.chromium.chrome.browser.toolbar.top.Toolbar;\n",
    "import org.chromium.chrome.browser.toolbar.settings.AddressBarPreference;\n"
    "import org.chromium.chrome.browser.toolbar.top.Toolbar;\n",
)
replace_if_missing(
    feed_surface_coordinator,
    "private final View mBottomToolbarNtpSpacer;",
    "    private final View mHeaderView;\n",
    "    private final View mHeaderView;\n"
    "    private final View mBottomToolbarNtpSpacer;\n",
)
replace_if_missing(
    feed_surface_coordinator,
    "mBottomToolbarNtpSpacer = new View(mActivity);",
    "        mNtpHeader = ntpHeader;\n",
    """        mNtpHeader = ntpHeader;
        mBottomToolbarNtpSpacer = new View(mActivity);
        mBottomToolbarNtpSpacer.setLayoutParams(
                new ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0));
        if (mNtpHeader != null) {
            mNtpHeader.addOnLayoutChangeListener(
                    (view, left, top, right, bottom, oldLeft, oldTop, oldRight, oldBottom) ->
                            updateBottomToolbarNtpSpacerHeight());
        }
""",
)
replace_if_missing(
    feed_surface_coordinator,
    "// Helium: update the spacer when the Feed viewport changes.",
    """            super.onSizeChanged(width, height, oldWidth, oldHeight);
""",
    """            super.onSizeChanged(width, height, oldWidth, oldHeight);
            // Helium: update the spacer when the Feed viewport changes.
            updateBottomToolbarNtpSpacerHeight();
""",
)
replace_if_missing(
    feed_surface_coordinator,
    "private void addNtpHeaderViews(List<View> headers)",
    """    /**
     * Configures header views and properties for feed: Adds the feed headers, creates the feed
""",
    """    private boolean shouldPlaceNtpHeaderAboveBottomToolbar() {
        return mNtpHeader != null
                && !AddressBarPreference.isToolbarConfiguredToShowOnTop();
    }

    private void updateBottomToolbarNtpSpacerHeight() {
        ViewGroup.LayoutParams params = mBottomToolbarNtpSpacer.getLayoutParams();
        if (params == null) return;

        int spacerHeight = 0;
        if (shouldPlaceNtpHeaderAboveBottomToolbar()) {
            int toolbarHeight =
                    mActivity
                            .getResources()
                            .getDimensionPixelSize(R.dimen.toolbar_height_no_shadow);
            int headerHeight = mNtpHeader == null ? 0 : mNtpHeader.getMeasuredHeight();
            spacerHeight =
                    Math.max(
                            mRootView.getHeight()
                                    - mRootView.getPaddingTop()
                                    - toolbarHeight
                                    - headerHeight,
                            0);
        }
        if (params.height == spacerHeight) return;
        params.height = spacerHeight;
        mBottomToolbarNtpSpacer.setLayoutParams(params);
    }

    private void addNtpHeaderViews(List<View> headers) {
        if (mNtpHeader == null) return;
        if (shouldPlaceNtpHeaderAboveBottomToolbar()) {
            updateBottomToolbarNtpSpacerHeight();
            headers.add(mBottomToolbarNtpSpacer);
        }
        headers.add(mNtpHeader);
    }

    /**
     * Configures header views and properties for feed: Adds the feed headers, creates the feed
""",
)
replace_if_missing(
    feed_surface_coordinator,
    "addNtpHeaderViews(headerList);",
    """        if (mNtpHeader != null) {
            headerList.add(mNtpHeader);
        }
""",
    """        addNtpHeaderViews(headerList);
""",
)
replace_if_missing(
    feed_surface_coordinator,
    "addNtpHeaderViews(headers);",
    """        if (mNtpHeader != null) {
            headers.add(mNtpHeader);
        }
""",
    """        addNtpHeaderViews(headers);
""",
)

# Remove the ineffective header-local gravity workaround from sources patched
# by 13386a9. The adapter spacer above is the authoritative positioning logic.
coordinator_text = coordinator.read_text()
helper_start = coordinator_text.find(
    "    // Helium: the NTP tiles belong above a bottom toolbar, not below the status bar.\n"
)
if helper_start >= 0:
    helper_end = coordinator_text.find(
        "    /**\n     * @return The fake search box view.\n", helper_start
    )
    if helper_end < 0:
        raise SystemExit(f"NTP tile workaround end marker not found in {coordinator}")
    coordinator_text = coordinator_text[:helper_start] + coordinator_text[helper_end:]
coordinator_text = coordinator_text.replace(
    "        updateNtpTilesPositionForToolbar();\n", ""
)
coordinator_text = coordinator_text.replace("import android.view.Gravity;\n", "")
coordinator.write_text(coordinator_text)
PYCODE

# crbug.com/525294822: overscroll
if version_lt "$VERSION" "151.0.7922.0"; then
sed -i 's|if (mContainerView != null) mSwipeRefreshLayout.setEnabled(true);|if (mTab.getContentView() != null) mSwipeRefreshLayout.setEnabled(true);|' chrome/android/java/src/org/chromium/chrome/browser/SwipeRefreshHandler.java
sed -i 's|assumeNonNull(mContainerView).addView(mSwipeRefreshLayout);|assumeNonNull(mTab.getContentView()).addView(mSwipeRefreshLayout);|' chrome/android/java/src/org/chromium/chrome/browser/SwipeRefreshHandler.java
sed -i 's|assumeNonNull(mContainerView).removeView(mSwipeRefreshLayout);|((ViewGroup) mSwipeRefreshLayout.getParent()).removeView(mSwipeRefreshLayout);|' chrome/android/java/src/org/chromium/chrome/browser/SwipeRefreshHandler.java
fi
# crbug.com/445475304: incognito back
sed -i 's|private void onTabChanged(@Nullable Tab tab) {|private void onTabChanged(@Nullable Tab tab) { if (tab != null \&\& tab.isIncognitoBranded()) { mSystemBackPressSupplier.set(true); return; }|' chrome/browser/back_press/android/java/src/org/chromium/chrome/browser/back_press/MinimizeAppAndCloseTabBackPressHandler.java

# crbug.com/helium: place the Hub/tab switcher toolbar at the bottom.
HUB_LAYOUT=chrome/browser/hub/internal/android/res/layout/hub_layout.xml
if [ -f "$HUB_LAYOUT" ]; then
sed -i 's|android:layout_marginTop="@dimen/toolbar_height_no_shadow"|android:layout_marginBottom="@dimen/toolbar_height_no_shadow"|' "$HUB_LAYOUT"
sed -i 's|<include layout="@layout/hub_toolbar_layout" />|<include layout="@layout/hub_toolbar_layout" android:layout_gravity="bottom" />|' "$HUB_LAYOUT"
perl -0pi -e 's|<include layout="\@layout/hub_toolbar_layout"(?: android:layout_gravity="bottom")? />|<include\n        layout="\@layout/hub_toolbar_layout"\n        android:layout_width="match_parent"\n        android:layout_height="wrap_content"\n        android:layout_gravity="bottom" />|' "$HUB_LAYOUT"
fi

# crbug.com/404069963: ntp override
sed -i 's/BASE_FEATURE(kChromeNativeUrlOverriding, base::FEATURE_DISABLED_BY_DEFAULT);/BASE_FEATURE(kChromeNativeUrlOverriding, base::FEATURE_ENABLED_BY_DEFAULT);/' chrome/browser/flags/android/chrome_feature_list.cc
sed -i 's|newCachedFlag(CHROME_NATIVE_URL_OVERRIDING, BuildConfig.IS_DESKTOP_ANDROID)|newCachedFlag(CHROME_NATIVE_URL_OVERRIDING, true)|' chrome/browser/flags/android/java/src/org/chromium/chrome/browser/flags/ChromeFeatureList.java

# crbug.com/helium: expose per-site forced dark mode in the app menu
perl -0pi -e 's/BASE_FEATURE\(kDarkenWebsitesCheckboxInThemesSetting,\n\s*base::FEATURE_DISABLED_BY_DEFAULT\);/BASE_FEATURE(kDarkenWebsitesCheckboxInThemesSetting,\n             base::FEATURE_ENABLED_BY_DEFAULT);/' components/content_settings/core/common/features.cc
perl -0pi -e 's/^[ \t]*return currentTab != null && !isNativePage && isFlagEnabled && isFeatureEnabled;\n/        return currentTab != null && !isNativePage;\n/m; s/^[ \t]*return currentTab != null[^\n]*isFeatureEnabled[^\n]*!isNativePage;\n/        return currentTab != null && !isNativePage;\n/m' chrome/android/java/src/org/chromium/chrome/browser/app/appmenu/AppMenuPropertiesDelegateImpl.java

# crbug.com/helium: do not let pages block tab close/navigation with beforeunload
grep -q 'Helium: beforeunload dialogs are disabled by default' components/javascript_dialogs/app_modal_dialog_manager.cc || sed -i '/void AppModalDialogManager::RunBeforeUnloadDialog(/,/^[}]$/ { /ChromeJavaScriptDialogExtraData\* extra_data =/i\
  // Helium: beforeunload dialogs are disabled by default.\
  std::move(callback).Run(true, std::u16string());\
  return;\

}' components/javascript_dialogs/app_modal_dialog_manager.cc

# crbug.com/helium: allow forcing site-requested new tabs/windows into current tab
if [ -f chrome/browser/ungoogled_flag_entries.h ] && ! grep -q '"open-new-links-in-current-tab"' chrome/browser/ungoogled_flag_entries.h; then
sed -i '/SINGLE_VALUE_TYPE("popups-to-tabs")},/a\
    {"open-new-links-in-current-tab",\
     "Open new links in current tab",\
     "Forces site-requested new tabs and windows to navigate in the current tab. ungoogled-chromium flag",\
     kOsAll, SINGLE_VALUE_TYPE("open-new-links-in-current-tab")},' chrome/browser/ungoogled_flag_entries.h
elif [ ! -f chrome/browser/ungoogled_flag_entries.h ] && ! grep -q '"open-new-links-in-current-tab"' chrome/browser/about_flags.cc; then
sed -i '/#include "chrome\/browser\/unexpire_flags_gen.inc"/a\
    {"open-new-links-in-current-tab",\
     "Open new links in current tab",\
     "Forces site-requested new tabs and windows to navigate in the current tab.",\
     kOsAndroid, SINGLE_VALUE_TYPE("open-new-links-in-current-tab")},' chrome/browser/about_flags.cc
fi
grep -q '#include "base/command_line.h"' content/renderer/render_frame_impl.cc || sed -i '0,/^#include /s|^#include |#include "base/command_line.h"\n#include |' content/renderer/render_frame_impl.cc
if ! grep -q 'open-new-links-in-current-tab' content/renderer/render_frame_impl.cc; then
sed -i '/case blink::kWebNavigationPolicyNewBackgroundTab:/,/return WindowOpenDisposition::NEW_BACKGROUND_TAB;/ s|return WindowOpenDisposition::NEW_BACKGROUND_TAB;|if (base::CommandLine::ForCurrentProcess()->HasSwitch("open-new-links-in-current-tab"))\n        return WindowOpenDisposition::CURRENT_TAB;\n      return WindowOpenDisposition::NEW_BACKGROUND_TAB;|' content/renderer/render_frame_impl.cc
sed -i '/case blink::kWebNavigationPolicyNewForegroundTab:/,/return WindowOpenDisposition::NEW_FOREGROUND_TAB;/ s|return WindowOpenDisposition::NEW_FOREGROUND_TAB;|if (base::CommandLine::ForCurrentProcess()->HasSwitch("open-new-links-in-current-tab"))\n        return WindowOpenDisposition::CURRENT_TAB;\n      return WindowOpenDisposition::NEW_FOREGROUND_TAB;|' content/renderer/render_frame_impl.cc
sed -i '/case blink::kWebNavigationPolicyNewWindow:/,/return WindowOpenDisposition::NEW_WINDOW;/ s|return WindowOpenDisposition::NEW_WINDOW;|if (base::CommandLine::ForCurrentProcess()->HasSwitch("open-new-links-in-current-tab"))\n        return WindowOpenDisposition::CURRENT_TAB;\n      return WindowOpenDisposition::NEW_WINDOW;|' content/renderer/render_frame_impl.cc
sed -i '/case blink::kWebNavigationPolicyNewPopup:/,/return WindowOpenDisposition::NEW_POPUP;/ s|return WindowOpenDisposition::NEW_POPUP;|if (base::CommandLine::ForCurrentProcess()->HasSwitch("open-new-links-in-current-tab"))\n        return WindowOpenDisposition::CURRENT_TAB;\n      return WindowOpenDisposition::NEW_POPUP;|' content/renderer/render_frame_impl.cc
fi
grep -q '#include "base/command_line.h"' ui/base/mojom/window_open_disposition_mojom_traits.h || sed -i '0,/^#include /s|^#include |#include "base/command_line.h"\n#include |' ui/base/mojom/window_open_disposition_mojom_traits.h
if ! grep -q 'open-new-links-in-current-tab' ui/base/mojom/window_open_disposition_mojom_traits.h; then
sed -i '/case WindowOpenDisposition::NEW_FOREGROUND_TAB:/,/return ui::mojom::WindowOpenDisposition::NEW_FOREGROUND_TAB;/ s|return ui::mojom::WindowOpenDisposition::NEW_FOREGROUND_TAB;|if (base::CommandLine::ForCurrentProcess()->HasSwitch("open-new-links-in-current-tab"))\n          return ui::mojom::WindowOpenDisposition::CURRENT_TAB;\n        return ui::mojom::WindowOpenDisposition::NEW_FOREGROUND_TAB;|' ui/base/mojom/window_open_disposition_mojom_traits.h
sed -i '/case WindowOpenDisposition::NEW_BACKGROUND_TAB:/,/return ui::mojom::WindowOpenDisposition::NEW_BACKGROUND_TAB;/ s|return ui::mojom::WindowOpenDisposition::NEW_BACKGROUND_TAB;|if (base::CommandLine::ForCurrentProcess()->HasSwitch("open-new-links-in-current-tab"))\n          return ui::mojom::WindowOpenDisposition::CURRENT_TAB;\n        return ui::mojom::WindowOpenDisposition::NEW_BACKGROUND_TAB;|' ui/base/mojom/window_open_disposition_mojom_traits.h
sed -i '/case WindowOpenDisposition::NEW_POPUP:/,/return ui::mojom::WindowOpenDisposition::NEW_POPUP;/ s|return ui::mojom::WindowOpenDisposition::NEW_POPUP;|if (base::CommandLine::ForCurrentProcess()->HasSwitch("open-new-links-in-current-tab"))\n          return ui::mojom::WindowOpenDisposition::CURRENT_TAB;\n        return ui::mojom::WindowOpenDisposition::NEW_POPUP;|' ui/base/mojom/window_open_disposition_mojom_traits.h
sed -i '/case WindowOpenDisposition::NEW_WINDOW:/,/return ui::mojom::WindowOpenDisposition::NEW_WINDOW;/ s|return ui::mojom::WindowOpenDisposition::NEW_WINDOW;|if (base::CommandLine::ForCurrentProcess()->HasSwitch("open-new-links-in-current-tab"))\n          return ui::mojom::WindowOpenDisposition::CURRENT_TAB;\n        return ui::mojom::WindowOpenDisposition::NEW_WINDOW;|' ui/base/mojom/window_open_disposition_mojom_traits.h
sed -i '/case ui::mojom::WindowOpenDisposition::NEW_FOREGROUND_TAB:/,/return WindowOpenDisposition::NEW_FOREGROUND_TAB;/ s|return WindowOpenDisposition::NEW_FOREGROUND_TAB;|if (base::CommandLine::ForCurrentProcess()->HasSwitch("open-new-links-in-current-tab"))\n          return WindowOpenDisposition::CURRENT_TAB;\n        return WindowOpenDisposition::NEW_FOREGROUND_TAB;|' ui/base/mojom/window_open_disposition_mojom_traits.h
sed -i '/case ui::mojom::WindowOpenDisposition::NEW_BACKGROUND_TAB:/,/return WindowOpenDisposition::NEW_BACKGROUND_TAB;/ s|return WindowOpenDisposition::NEW_BACKGROUND_TAB;|if (base::CommandLine::ForCurrentProcess()->HasSwitch("open-new-links-in-current-tab"))\n          return WindowOpenDisposition::CURRENT_TAB;\n        return WindowOpenDisposition::NEW_BACKGROUND_TAB;|' ui/base/mojom/window_open_disposition_mojom_traits.h
sed -i '/case ui::mojom::WindowOpenDisposition::NEW_POPUP:/,/return WindowOpenDisposition::NEW_POPUP;/ s|return WindowOpenDisposition::NEW_POPUP;|if (base::CommandLine::ForCurrentProcess()->HasSwitch("open-new-links-in-current-tab"))\n          return WindowOpenDisposition::CURRENT_TAB;\n        return WindowOpenDisposition::NEW_POPUP;|' ui/base/mojom/window_open_disposition_mojom_traits.h
sed -i '/case ui::mojom::WindowOpenDisposition::NEW_WINDOW:/,/return WindowOpenDisposition::NEW_WINDOW;/ s|return WindowOpenDisposition::NEW_WINDOW;|if (base::CommandLine::ForCurrentProcess()->HasSwitch("open-new-links-in-current-tab"))\n          return WindowOpenDisposition::CURRENT_TAB;\n        return WindowOpenDisposition::NEW_WINDOW;|' ui/base/mojom/window_open_disposition_mojom_traits.h
sed -i '/case ui::mojom::WindowOpenDisposition::NEW_FOREGROUND_TAB:/,/return true;/ s|return true;|if (base::CommandLine::ForCurrentProcess()->HasSwitch("open-new-links-in-current-tab"))\n          *out = WindowOpenDisposition::CURRENT_TAB;\n        return true;|' ui/base/mojom/window_open_disposition_mojom_traits.h
sed -i '/case ui::mojom::WindowOpenDisposition::NEW_BACKGROUND_TAB:/,/return true;/ s|return true;|if (base::CommandLine::ForCurrentProcess()->HasSwitch("open-new-links-in-current-tab"))\n          *out = WindowOpenDisposition::CURRENT_TAB;\n        return true;|' ui/base/mojom/window_open_disposition_mojom_traits.h
sed -i '/case ui::mojom::WindowOpenDisposition::NEW_POPUP:/,/return true;/ s|return true;|if (base::CommandLine::ForCurrentProcess()->HasSwitch("open-new-links-in-current-tab"))\n          *out = WindowOpenDisposition::CURRENT_TAB;\n        return true;|' ui/base/mojom/window_open_disposition_mojom_traits.h
sed -i '/case ui::mojom::WindowOpenDisposition::NEW_WINDOW:/,/return true;/ s|return true;|if (base::CommandLine::ForCurrentProcess()->HasSwitch("open-new-links-in-current-tab"))\n          *out = WindowOpenDisposition::CURRENT_TAB;\n        return true;|' ui/base/mojom/window_open_disposition_mojom_traits.h
fi
grep -q '#include "base/command_line.h"' content/browser/web_contents/web_contents_impl.cc || sed -i '0,/^#include /s|^#include |#include "base/command_line.h"\n#include |' content/browser/web_contents/web_contents_impl.cc
if ! grep -q 'Helium: force new-tab OpenURL dispositions into current tab' content/browser/web_contents/web_contents_impl.cc; then
sed -i '/WebContents\* WebContentsImpl::OpenURL(/,/^#if DCHECK_IS_ON()/ { /^#if DCHECK_IS_ON()/i\
  // Helium: force new-tab OpenURL dispositions into current tab.\
  if (base::CommandLine::ForCurrentProcess()->HasSwitch(\
          "open-new-links-in-current-tab") \&\&\
      (params.disposition == WindowOpenDisposition::NEW_FOREGROUND_TAB ||\
       params.disposition == WindowOpenDisposition::NEW_BACKGROUND_TAB ||\
       params.disposition == WindowOpenDisposition::NEW_POPUP ||\
       params.disposition == WindowOpenDisposition::NEW_WINDOW)) {\
    OpenURLParams current_tab_params(params);\
    current_tab_params.disposition = WindowOpenDisposition::CURRENT_TAB;\
    return OpenURL(current_tab_params, std::move(navigation_handle_callback));\
  }\

}' content/browser/web_contents/web_contents_impl.cc
fi

# crbug.com/helium: disable tab close undo snackbar
grep -q 'Helium: disable tab close undo snackbar' chrome/android/java/src/org/chromium/chrome/browser/undo_tab_close_snackbar/UndoBarController.java || sed -i '/if (closedTabs.isEmpty() && savedTabGroupSyncIds.isEmpty()) return;/a\
        if (shouldDisableUndoSnackbar()) {\
            for (Tab closedTab : closedTabs) {\
                commitTabClosure(closedTab.getId());\
            }\
            return;\
        }' chrome/android/java/src/org/chromium/chrome/browser/undo_tab_close_snackbar/UndoBarController.java
grep -q 'private static boolean shouldDisableUndoSnackbar' chrome/android/java/src/org/chromium/chrome/browser/undo_tab_close_snackbar/UndoBarController.java || sed -i '/private void showUndoBar(/i\
    private static boolean shouldDisableUndoSnackbar() {\
        // Helium: disable tab close undo snackbar.\
        return true;\
    }\
' chrome/android/java/src/org/chromium/chrome/browser/undo_tab_close_snackbar/UndoBarController.java

# crbug.com/helium: startup blank-screen recovery guards
sed -i '/import org.chromium.components.embedder_support.util.UrlUtilities;/i\
import org.chromium.components.embedder_support.util.UrlConstants;' chrome/android/java/src/org/chromium/chrome/browser/tabmodel/TabPersistentStoreImpl.java
sed -i '/private static boolean sDeferredStartupComplete;/a\
\
    private static boolean shouldReplaceUrlForRestore(@Nullable String url) {\
        return TextUtils.isEmpty(url)\
                || url.startsWith("chrome-extension://")\
                || url.equals("about:blank")\
                || url.startsWith("chrome://newtab")\
                || url.startsWith("chrome://new-tab-page")\
                || url.startsWith("chrome-native://newtab");\
    }\
\
    private static String safeUrlForRestore(@Nullable String url) {\
        return shouldReplaceUrlForRestore(url) ? UrlConstants.NTP_URL : assumeNonNull(url);\
    }' chrome/android/java/src/org/chromium/chrome/browser/tabmodel/TabPersistentStoreImpl.java
sed -i '/boolean isIncognito = isIncognitoTabBeingRestored(tabToRestore, tabState);/a\
        if (shouldReplaceUrlForRestore(tabToRestore.url)) {\
            tabState = null;\
            tabToRestore =\
                    new TabRestoreDetails(\
                            tabToRestore.id,\
                            tabToRestore.originalIndex,\
                            tabToRestore.isIncognito,\
                            safeUrlForRestore(tabToRestore.url),\
                            tabToRestore.fromMerge);\
        }' chrome/android/java/src/org/chromium/chrome/browser/tabmodel/TabPersistentStoreImpl.java
perl -0pi -e 's|    \@Override\n    public void onStartWithNative\(\) \{|    private void clearVolatileRendererCaches() {\n        PostTask.postTask(\n                TaskTraits.BEST_EFFORT_MAY_BLOCK,\n                () -> {\n                    try {\n                        String dataDir = org.chromium.base.PathUtils.getDataDirectory();\n                        String[] paths = {\n                            "Default/GPUCache",\n                            "Default/GrShaderCache",\n                            "Default/ShaderCache",\n                            "Default/Code Cache/js",\n                            "Default/Code Cache/wasm"\n                        };\n                        for (String path : paths) {\n                            org.chromium.base.FileUtils.recursivelyDeleteFile(\n                                    new java.io.File(dataDir, path),\n                                    org.chromium.base.FileUtils.DELETE_ALL);\n                        }\n                    } catch (Throwable t) {\n                        Log.w(TAG, "Failed to clear volatile renderer caches", t);\n                    }\n                });\n    }\n\n    \@Override\n    public void onStartWithNative() {|' chrome/android/java/src/org/chromium/chrome/browser/ChromeTabbedActivity.java
# Keep the cache cleanup helper available for emergency debugging, but do not
# run it automatically on every startup. Deleting renderer caches while native
# startup is still settling can destabilize the first launch after install.

# crbug.com/431004500: incognito uaf
sed -i '/for (int i = 0; i < tab_list->GetTabCount(); ++i) {/i if (!tab_list) { continue; }' chrome/browser/extensions/api/tabs/tabs_api.cc

# crbug.com/40274462: incognito uaf
sed -i '/CONTENT_EXPORT static WebContents\* FromRenderFrameHost(RenderFrameHost\* rfh);/a\CONTENT_EXPORT static bool HasLiveWebContentsForBrowserContext(BrowserContext* browser_context);' content/public/browser/web_contents.h
sed -i '/^WebContentsImpl::WebContentsImpl(BrowserContext\* browser_context)/i\ bool WebContents::HasLiveWebContentsForBrowserContext(BrowserContext* browser_context) { for (WebContentsImpl* web_contents : WebContentsImpl::GetAllWebContents()) { if (web_contents->GetBrowserContext() == browser_context) { return true; } } return false; }' content/browser/web_contents/web_contents_impl.cc
sed -i '/#include "content\/public\/browser\/render_process_host.h"/a#include "content/public/browser/web_contents.h"' chrome/browser/profiles/profile_destroyer.cc
sed -i '/^void ProfileDestroyer::DestroyOTRProfileWhenAppropriateWithTimeout($/,/MaybeSendDestroyedNotification/{/  profile->MaybeSendDestroyedNotification();/i\
if (content::WebContents::HasLiveWebContentsForBrowserContext(profile)) { return; }
}' chrome/browser/profiles/profile_destroyer.cc

# crbug.com/444024982: api 31
sed -i 's/|| mSupportedProfileType == SupportedProfileType.REGULAR) {/|| mSupportedProfileType == SupportedProfileType.REGULAR || mSupportedProfileType == SupportedProfileType.MIXED) {/' chrome/android/java/src/org/chromium/chrome/browser/ChromeTabbedActivity.java
sed -i 's/|| mSupportedProfileType == SupportedProfileType.OFF_THE_RECORD) {/|| mSupportedProfileType == SupportedProfileType.OFF_THE_RECORD || mSupportedProfileType == SupportedProfileType.MIXED) {/' chrome/android/java/src/org/chromium/chrome/browser/ChromeTabbedActivity.java

export PATCHED=1

# crbug.com/helium: Android incognito tab events must reach spanning extension
# backgrounds so action icons/titles (SwitchyOmega status) update for OTR tabs.
if [ -f "$TABS_EVENT_ROUTER_CC" ]; then
    grep -q 'build/build_config.h' "$TABS_EVENT_ROUTER_CC" || \
        sed -i '/#include "chrome\/browser\/extensions\/api\/tabs\/tabs_event_router.h"/a\#include "build/build_config.h"' "$TABS_EVENT_ROUTER_CC"
    python3 - "$TABS_EVENT_ROUTER_CC" <<'PYCODE'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
marker = "HeliumAndroidIncognitoTabEvents"
if marker not in text:
    text = text.replace(
        """  Profile* profile = Profile::FromBrowserContext(contents->GetBrowserContext());

  auto event = std::make_unique<Event>(
""",
        """  Profile* profile = Profile::FromBrowserContext(contents->GetBrowserContext());
#if BUILDFLAG(IS_ANDROID)
  // HeliumAndroidIncognitoTabEvents: spanning extension backgrounds live on the
  // original profile, so route OTR tab events through the original profile.
  if (profile->IsOffTheRecord()) {
    profile = profile->GetOriginalProfile();
  }
#endif

  auto event = std::make_unique<Event>(
""",
        1,
    )
    text = text.replace(
        """  Profile* const profile =
      Profile::FromBrowserContext(contents->GetBrowserContext());
  auto event = std::make_unique<Event>(events::TABS_ON_CREATED,
""",
        """  Profile* profile =
      Profile::FromBrowserContext(contents->GetBrowserContext());
#if BUILDFLAG(IS_ANDROID)
  if (profile->IsOffTheRecord()) {
    profile = profile->GetOriginalProfile();
  }
#endif
  auto event = std::make_unique<Event>(events::TABS_ON_CREATED,
""",
        1,
    )
    text = text.replace(
        """  EventRouter* event_router = EventRouter::Get(profile);
  if (!profile_->IsSameOrParent(profile) || !event_router) {
""",
        """#if BUILDFLAG(IS_ANDROID)
  if (profile->IsOffTheRecord()) {
    profile = profile->GetOriginalProfile();
  }
#endif
  EventRouter* event_router = EventRouter::Get(profile);
  if (!profile_->IsSameOrParent(profile) || !event_router) {
""",
        1,
    )
    if marker not in text:
        raise SystemExit(f"tabs event router patterns not found in {path}")
path.write_text(text)
PYCODE
fi

# crbug.com/helium: Android extension popup should see active incognito tab.
if [ -f "$TABS_API_CC" ]; then
    grep -q 'build/build_config.h' "$TABS_API_CC" || \
        sed -i '/#include "chrome\/browser\/extensions\/api\/tabs\/tabs_api.h"/a\#include "build/build_config.h"' "$TABS_API_CC"
    grep -q 'chrome/browser/android/tab_android.h' "$TABS_API_CC" || \
        sed -i '/#include "build\/build_config.h"/a\
#if BUILDFLAG(IS_ANDROID)\
#include "chrome/browser/android/tab_android.h"\
#endif' "$TABS_API_CC"
    grep -q 'content/public/browser/visibility.h' "$TABS_API_CC" || \
        sed -i '/#include "content\/public\/browser\/navigation_handle.h"/a\#include "content/public/browser/visibility.h"' "$TABS_API_CC"
    python3 - "$TABS_API_CC" <<'PYCODE'
from pathlib import Path
import sys
import re

path = Path(sys.argv[1])
text = path.read_text()
text = text.replace(
    '#if BUILDFLAG(IS_ANDROID)\n'
    '#include "chrome/browser/ui/android/extensions/extensions_menu_delegate_android.h"\n'
    '#endif\n',
    '')
forward_decl = """#if BUILDFLAG(IS_ANDROID)
int GetLastAndroidExtensionActionTabId();
content::WebContents* GetLastAndroidExtensionActionWebContents();
#endif

"""
namespace_anchor = "namespace extensions {\n\n"
if "int GetLastAndroidExtensionActionTabId();" not in text:
    if namespace_anchor not in text:
        raise SystemExit(f"namespace pattern not found in {path}")
    text = text.replace(namespace_anchor, namespace_anchor + forward_decl, 1)
elif "content::WebContents* GetLastAndroidExtensionActionWebContents();" not in text:
    text = text.replace(
        "int GetLastAndroidExtensionActionTabId();\n",
        "int GetLastAndroidExtensionActionTabId();\n"
        "content::WebContents* GetLastAndroidExtensionActionWebContents();\n",
        1)
old = """#if BUILDFLAG(IS_ANDROID)
  const bool helium_android_incognito_direct_query =
      query_info_.active && *query_info_.active &&
      ((query_info_.last_focused_window && *query_info_.last_focused_window) ||
       (query_info_.current_window && *query_info_.current_window) ||
       window_id == extension_misc::kCurrentWindowId) &&
      !query_info_.url && index < 0 && window_type.empty();
  if (helium_android_incognito_direct_query) {
    for (BrowserWindowInterface* browser : GetAllBrowserWindowInterfaces()) {
      Profile* candidate_profile = browser->GetProfile();
      if (!candidate_profile || !candidate_profile->IsOffTheRecord()) {
        continue;
      }
      TabListInterface* tab_list = TabListInterface::From(browser);
      if (!tab_list) {
        continue;
      }
      ::tabs::TabInterface* tab = tab_list->GetActiveTab();
      if (!tab || !tab->GetContents()) {
        continue;
      }
      base::ListValue direct_result;
      ExtensionTabUtil::ScrubTabBehavior dont_scrub = {
          ExtensionTabUtil::kDontScrubTab, ExtensionTabUtil::kDontScrubTab};
      direct_result.Append(ExtensionTabUtil::CreateTabObject(
                               tab->GetContents(), dont_scrub, extension(),
                               tab_list, tab_list->GetActiveIndex())
                               .ToValue());
      return RespondNow(WithArguments(std::move(direct_result)));
    }
  }
#endif

  Profile* profile = Profile::FromBrowserContext(browser_context());
"""
new = """#if BUILDFLAG(IS_ANDROID)
  const bool helium_android_current_tab_query =
      query_info_.active && *query_info_.active &&
      ((query_info_.last_focused_window && *query_info_.last_focused_window) ||
       (query_info_.current_window && *query_info_.current_window) ||
       window_id == extension_misc::kCurrentWindowId) &&
      !query_info_.url && index < 0 && window_type.empty();
  if (helium_android_current_tab_query) {
    int action_tab_id = GetLastAndroidExtensionActionTabId();
    if (action_tab_id >= 0) {
      WindowController* action_window = nullptr;
      content::WebContents* action_contents = nullptr;
      int action_index = -1;
      std::string action_error;
      if (tabs_internal::GetTabById(
              action_tab_id, browser_context(),
              /*include_incognito=*/true, &action_window, &action_contents,
              &action_index, &action_error) &&
          action_contents) {
        BrowserWindowInterface* action_browser =
            action_window ? action_window->GetBrowserWindowInterface()
                          : nullptr;
        TabListInterface* action_tab_list =
            action_browser ? TabListInterface::From(action_browser) : nullptr;
        base::ListValue direct_result;
        ExtensionTabUtil::ScrubTabBehavior dont_scrub = {
            ExtensionTabUtil::kDontScrubTab, ExtensionTabUtil::kDontScrubTab};
        direct_result.Append(ExtensionTabUtil::CreateTabObject(
                                 action_contents, dont_scrub, extension(),
                                 action_tab_list, action_index)
                                 .ToValue());
        return RespondNow(WithArguments(std::move(direct_result)));
      }
    }

    for (BrowserWindowInterface* browser : GetAllBrowserWindowInterfaces()) {
      TabListInterface* tab_list = TabListInterface::From(browser);
      if (!tab_list) {
        continue;
      }
      ::tabs::TabInterface* tab = tab_list->GetActiveTab();
      content::WebContents* contents = tab ? tab->GetContents() : nullptr;
      if (!contents || !contents->GetBrowserContext()->IsOffTheRecord()) {
        continue;
      }
      base::ListValue direct_result;
      ExtensionTabUtil::ScrubTabBehavior dont_scrub = {
          ExtensionTabUtil::kDontScrubTab, ExtensionTabUtil::kDontScrubTab};
      direct_result.Append(ExtensionTabUtil::CreateTabObject(
                               contents, dont_scrub, extension(), tab_list,
                               tab_list->GetActiveIndex())
                               .ToValue());
      return RespondNow(WithArguments(std::move(direct_result)));
    }
  }
#endif

  Profile* profile = Profile::FromBrowserContext(browser_context());
"""
if old in text:
    text = text.replace(old, new, 1)
elif "helium_android_current_tab_query" not in text:
    anchor = """  Profile* profile = Profile::FromBrowserContext(browser_context());
"""
    if anchor not in text:
        raise SystemExit(f"pattern not found in {path}")
    text = text.replace(anchor, new, 1)
action_first = """    int action_tab_id = GetLastAndroidExtensionActionTabId();
    if (action_tab_id >= 0) {
      WindowController* action_window = nullptr;
      content::WebContents* action_contents = nullptr;
      int action_index = -1;
      std::string action_error;
      if (tabs_internal::GetTabById(
              action_tab_id, browser_context(),
              /*include_incognito=*/true, &action_window, &action_contents,
              &action_index, &action_error) &&
          action_contents) {
        BrowserWindowInterface* action_browser =
            action_window ? action_window->GetBrowserWindowInterface()
                          : nullptr;
        TabListInterface* action_tab_list =
            action_browser ? TabListInterface::From(action_browser) : nullptr;
        base::ListValue direct_result;
        ExtensionTabUtil::ScrubTabBehavior dont_scrub = {
            ExtensionTabUtil::kDontScrubTab, ExtensionTabUtil::kDontScrubTab};
        direct_result.Append(ExtensionTabUtil::CreateTabObject(
                                 action_contents, dont_scrub, extension(),
                                 action_tab_list, action_index)
                                 .ToValue());
        return RespondNow(WithArguments(std::move(direct_result)));
      }
    }

    for (BrowserWindowInterface* browser : GetAllBrowserWindowInterfaces()) {
      TabListInterface* tab_list = TabListInterface::From(browser);
      if (!tab_list) {
        continue;
      }
      ::tabs::TabInterface* tab = tab_list->GetActiveTab();
      content::WebContents* contents = tab ? tab->GetContents() : nullptr;
      if (!contents || !contents->GetBrowserContext()->IsOffTheRecord()) {
        continue;
      }
      base::ListValue direct_result;
      ExtensionTabUtil::ScrubTabBehavior dont_scrub = {
          ExtensionTabUtil::kDontScrubTab, ExtensionTabUtil::kDontScrubTab};
      direct_result.Append(ExtensionTabUtil::CreateTabObject(
                               contents, dont_scrub, extension(), tab_list,
                               tab_list->GetActiveIndex())
                               .ToValue());
      return RespondNow(WithArguments(std::move(direct_result)));
    }
"""
otr_first = """    for (BrowserWindowInterface* browser : GetAllBrowserWindowInterfaces()) {
      TabListInterface* tab_list = TabListInterface::From(browser);
      if (!tab_list) {
        continue;
      }
      ::tabs::TabInterface* tab = tab_list->GetActiveTab();
      content::WebContents* contents = tab ? tab->GetContents() : nullptr;
      if (!contents || !contents->GetBrowserContext()->IsOffTheRecord()) {
        continue;
      }
      base::ListValue direct_result;
      ExtensionTabUtil::ScrubTabBehavior dont_scrub = {
          ExtensionTabUtil::kDontScrubTab, ExtensionTabUtil::kDontScrubTab};
      direct_result.Append(ExtensionTabUtil::CreateTabObject(
                               contents, dont_scrub, extension(), tab_list,
                               tab_list->GetActiveIndex())
                               .ToValue());
      return RespondNow(WithArguments(std::move(direct_result)));
    }

    int action_tab_id = GetLastAndroidExtensionActionTabId();
    if (action_tab_id >= 0) {
      WindowController* action_window = nullptr;
      content::WebContents* action_contents = nullptr;
      int action_index = -1;
      std::string action_error;
      if (tabs_internal::GetTabById(
              action_tab_id, browser_context(),
              /*include_incognito=*/true, &action_window, &action_contents,
              &action_index, &action_error) &&
          action_contents) {
        BrowserWindowInterface* action_browser =
            action_window ? action_window->GetBrowserWindowInterface()
                          : nullptr;
        TabListInterface* action_tab_list =
            action_browser ? TabListInterface::From(action_browser) : nullptr;
        base::ListValue direct_result;
        ExtensionTabUtil::ScrubTabBehavior dont_scrub = {
            ExtensionTabUtil::kDontScrubTab, ExtensionTabUtil::kDontScrubTab};
        direct_result.Append(ExtensionTabUtil::CreateTabObject(
                                 action_contents, dont_scrub, extension(),
                                 action_tab_list, action_index)
                                 .ToValue());
        return RespondNow(WithArguments(std::move(direct_result)));
      }
    }
"""
text = text.replace(action_first, otr_first, 1)
text = text.replace(
    "if (!contents || !contents->GetBrowserContext()->IsOffTheRecord()) {",
    "if (!contents || !contents->GetBrowserContext()->IsOffTheRecord() ||\\n"
    "          contents->GetVisibility() != content::Visibility::VISIBLE) {")
robust_if = """  if (helium_android_current_tab_query) {
    content::WebContents* last_action_contents =
        GetLastAndroidExtensionActionWebContents();
    Profile* calling_profile =
        Profile::FromBrowserContext(browser_context());
    Profile* action_profile =
        last_action_contents
            ? Profile::FromBrowserContext(
                  last_action_contents->GetBrowserContext())
            : nullptr;
    if (last_action_contents && action_profile &&
        calling_profile->IsSameOrParent(action_profile)) {
      TabAndroid* android_tab =
          TabAndroid::FromWebContents(last_action_contents);
      bool is_current_tab =
          android_tab &&
          (android_tab->IsUserInteractable() || android_tab->IsActivated());
      base::ListValue direct_result;
      ExtensionTabUtil::ScrubTabBehavior dont_scrub = {
          ExtensionTabUtil::kDontScrubTab, ExtensionTabUtil::kDontScrubTab};
      base::DictValue tab_value =
          ExtensionTabUtil::CreateTabObject(last_action_contents, dont_scrub,
                                            extension())
              .ToValue();
      if (is_current_tab || action_profile->IsOffTheRecord()) {
        tab_value.Set(tabs_constants::kActiveKey, true);
        tab_value.Set(tabs_constants::kSelectedKey, true);
      }
      direct_result.Append(std::move(tab_value));
      return RespondNow(WithArguments(std::move(direct_result)));
    }

    for (int pass = 0; pass < 2; ++pass) {
      for (BrowserWindowInterface* browser : GetAllBrowserWindowInterfaces()) {
        TabListInterface* tab_list = TabListInterface::From(browser);
        if (!tab_list) {
          continue;
        }
        for (int i = 0; i < tab_list->GetTabCount(); ++i) {
          ::tabs::TabInterface* tab = tab_list->GetTab(i);
          if (!tab) {
            continue;
          }
          content::WebContents* contents = tab->GetContents();
          if (!contents || !contents->GetBrowserContext()->IsOffTheRecord()) {
            continue;
          }
          TabAndroid* android_tab = TabAndroid::FromWebContents(contents);
          bool is_current_tab =
              android_tab ? (android_tab->IsUserInteractable() ||
                             android_tab->IsActivated())
                          : tab->IsActivated();
          if (pass == 0 && !is_current_tab) {
            continue;
          }
          if (pass == 1 && !is_current_tab &&
              contents->GetVisibility() != content::Visibility::VISIBLE) {
            continue;
          }
          base::ListValue direct_result;
          ExtensionTabUtil::ScrubTabBehavior dont_scrub = {
              ExtensionTabUtil::kDontScrubTab, ExtensionTabUtil::kDontScrubTab};
          base::DictValue tab_value =
              ExtensionTabUtil::CreateTabObject(
                  contents, dont_scrub, extension(), tab_list, i)
                  .ToValue();
          if (is_current_tab) {
            tab_value.Set(tabs_constants::kActiveKey, true);
            tab_value.Set(tabs_constants::kSelectedKey, true);
          }
          direct_result.Append(std::move(tab_value));
          return RespondNow(WithArguments(std::move(direct_result)));
        }
      }
    }

    int action_tab_id = GetLastAndroidExtensionActionTabId();
    if (action_tab_id >= 0) {
      WindowController* action_window = nullptr;
      content::WebContents* action_contents = nullptr;
      int action_index = -1;
      std::string action_error;
      if (tabs_internal::GetTabById(
              action_tab_id, browser_context(),
              /*include_incognito=*/true, &action_window, &action_contents,
              &action_index, &action_error) &&
          action_contents) {
        BrowserWindowInterface* action_browser =
            action_window ? action_window->GetBrowserWindowInterface()
                          : nullptr;
        TabListInterface* action_tab_list =
            action_browser ? TabListInterface::From(action_browser) : nullptr;
        base::ListValue direct_result;
        ExtensionTabUtil::ScrubTabBehavior dont_scrub = {
            ExtensionTabUtil::kDontScrubTab, ExtensionTabUtil::kDontScrubTab};
        direct_result.Append(ExtensionTabUtil::CreateTabObject(
                                 action_contents, dont_scrub, extension(),
                                 action_tab_list, action_index)
                                 .ToValue());
        return RespondNow(WithArguments(std::move(direct_result)));
      }
    }
  }

  const bool helium_android_unfiltered_tab_query =
      !query_info_.active && !query_info_.current_window &&
      !query_info_.last_focused_window && !query_info_.highlighted &&
      !query_info_.pinned && !query_info_.audible && !query_info_.muted &&
      !query_info_.discarded && !query_info_.auto_discardable &&
      !query_info_.frozen && !query_info_.url && !query_info_.title &&
      !query_info_.group_id.has_value() &&
      !query_info_.split_view_id.has_value() && index < 0 &&
      window_type.empty() && window_id == extension_misc::kUnknownWindowId;
  if (helium_android_unfiltered_tab_query) {
    base::ListValue direct_result;
    std::vector<int> appended_tab_ids;
    auto append_tab =
        [&](content::WebContents* contents, TabListInterface* tab_list,
            int tab_index) {
          if (!contents) {
            return;
          }
          Profile* profile = Profile::FromBrowserContext(browser_context());
          Profile* candidate_profile =
              Profile::FromBrowserContext(contents->GetBrowserContext());
          if (!profile->IsSameOrParent(candidate_profile)) {
            return;
          }
          if (!include_incognito_information() &&
              profile != candidate_profile) {
            return;
          }
          int tab_id = ExtensionTabUtil::GetTabId(contents);
          for (int appended_tab_id : appended_tab_ids) {
            if (appended_tab_id == tab_id) {
              return;
            }
          }
          appended_tab_ids.push_back(tab_id);
          ExtensionTabUtil::ScrubTabBehavior dont_scrub = {
              ExtensionTabUtil::kDontScrubTab, ExtensionTabUtil::kDontScrubTab};
          base::DictValue tab_value =
              ExtensionTabUtil::CreateTabObject(contents, dont_scrub,
                                                extension(), tab_list,
                                                tab_index)
                  .ToValue();
          TabAndroid* android_tab = TabAndroid::FromWebContents(contents);
          if (android_tab &&
              (android_tab->IsUserInteractable() ||
               android_tab->IsActivated())) {
            tab_value.Set(tabs_constants::kActiveKey, true);
            tab_value.Set(tabs_constants::kSelectedKey, true);
          }
          direct_result.Append(std::move(tab_value));
        };
    for (BrowserWindowInterface* browser : GetAllBrowserWindowInterfaces()) {
      TabListInterface* tab_list = TabListInterface::From(browser);
      if (!tab_list) {
        continue;
      }
      for (int i = 0; i < tab_list->GetTabCount(); ++i) {
        ::tabs::TabInterface* tab = tab_list->GetTab(i);
        append_tab(tab ? tab->GetContents() : nullptr, tab_list, i);
      }
    }
    append_tab(GetLastAndroidExtensionActionWebContents(), nullptr, -1);
    int action_tab_id = GetLastAndroidExtensionActionTabId();
    if (action_tab_id >= 0) {
      WindowController* action_window = nullptr;
      content::WebContents* action_contents = nullptr;
      int action_index = -1;
      std::string action_error;
      if (tabs_internal::GetTabById(
              action_tab_id, browser_context(),
              /*include_incognito=*/true, &action_window, &action_contents,
              &action_index, &action_error) &&
          action_contents) {
        BrowserWindowInterface* action_browser =
            action_window ? action_window->GetBrowserWindowInterface()
                          : nullptr;
        append_tab(action_contents,
                   action_browser ? TabListInterface::From(action_browser)
                                  : nullptr,
                   action_index);
      }
    }
    return RespondNow(WithArguments(std::move(direct_result)));
  }
"""
while True:
    unfiltered_match = re.search(
        r"(?m)^[ \t]*const bool helium_android_unfiltered_tab_query =\n", text)
    if not unfiltered_match:
        break
    unfiltered_start = unfiltered_match.start()
    unfiltered_if_match = re.search(
        r"(?m)^[ \t]*if \(helium_android_unfiltered_tab_query\) \{",
        text[unfiltered_start:])
    if not unfiltered_if_match:
        raise SystemExit(f"unfiltered query if block not found in {path}")
    unfiltered_if = unfiltered_start + unfiltered_if_match.start()
    brace = text.find("{", unfiltered_if)
    depth = 0
    unfiltered_end = None
    for idx in range(brace, len(text)):
        if text[idx] == "{":
            depth += 1
        elif text[idx] == "}":
            depth -= 1
            if depth == 0:
                unfiltered_end = idx + 1
                while unfiltered_end < len(text) and text[unfiltered_end] in " \t\r\n":
                    unfiltered_end += 1
                break
    if unfiltered_end is None:
        raise SystemExit(f"unfiltered query block end not found in {path}")
    text = text[:unfiltered_start] + text[unfiltered_end:]

if_marker = "  if (helium_android_current_tab_query) {\n"
start = text.find(if_marker)
if start >= 0:
    brace = text.find("{", start)
    depth = 0
    end = None
    for idx in range(brace, len(text)):
        if text[idx] == "{":
            depth += 1
        elif text[idx] == "}":
            depth -= 1
            if depth == 0:
                end = idx + 1
                break
    if end is None:
        raise SystemExit(f"query block end not found in {path}")
    text = text[:start] + robust_if + text[end:]

# Keep reruns safe for Chromium trees patched by an older script revision.
# Rename only the outer cached WebContents variable and leave the later
# tab-id lookup local named action_contents.
outer_pattern = re.compile(
    r"(?m)^[ \t]*content::WebContents\*[ \t]+action_contents[ \t]*=\n"
    r"[ \t]*GetLastAndroidExtensionActionWebContents\(\);\n")
outer_match = outer_pattern.search(text)
if outer_match:
    inner_match = re.search(
        r"(?m)^[ \t]*content::WebContents\*[ \t]+action_contents"
        r"[ \t]*=[ \t]*nullptr;",
        text[outer_match.end():])
    if not inner_match:
        raise SystemExit(f"inner action contents declaration not found in {path}")
    inner_start = outer_match.end() + inner_match.start()
    outer_block = text[outer_match.start():inner_start]
    outer_block = re.sub(
        r"\baction_contents\b", "last_action_contents", outer_block)
    text = text[:outer_match.start()] + outer_block + text[inner_start:]
if outer_pattern.search(text):
    raise SystemExit(f"action contents shadow migration failed in {path}")
path.write_text(text)
PYCODE
    if ! grep -qE 'content::WebContents\*[[:space:]]+last_action_contents' "$TABS_API_CC"; then
        echo "Expected last_action_contents migration was not applied to $TABS_API_CC" >&2
        exit 1
    fi
fi
