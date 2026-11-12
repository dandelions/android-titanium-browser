import shutil
import tempfile
import unittest
from pathlib import Path

from patch_lemur_app_menu import (
    DELEGATE_INTERFACE_REL,
    patch_app_menu_properties_delegate,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "chromium_157" / "AppMenuPropertiesDelegate.java"


class TestPatchAppMenuPropertiesDelegate(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self.temp_dir.name)
        target = self.work_dir / DELEGATE_INTERFACE_REL
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(FIXTURE, target)
        self.target = target

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_patch_chromium_157_delegate(self):
        patch_app_menu_properties_delegate(self.work_dir)
        content = self.target.read_text(encoding="utf-8")
        self.assertIn("default boolean showCustomAppMenu(", content)
        self.assertIn("default boolean isCustomAppMenuShowing()", content)
        self.assertIn("default void hideCustomAppMenu()", content)
        self.assertIn("shouldKeepMenuBelowTopControls();", content)

        # Idempotence
        patch_app_menu_properties_delegate(self.work_dir)
        content_after = self.target.read_text(encoding="utf-8")
        self.assertEqual(content, content_after)

    def test_appearance_theme_switch_is_posted_asynchronously(self):
        for name in ("patch.sh", "hotfix_existing_src.sh"):
            with self.subTest(script=name):
                text = (REPO_ROOT / name).read_text(encoding="utf-8")
                self.assertIn("mHandler.post(() -> {", text)
                self.assertIn("ChromePreferenceKeys.UI_THEME_SETTING, selectedTheme", text)

    def test_recreation_draw_blocker_has_render_request_and_safety_fallback(self):
        for name in ("patch.sh", "hotfix_existing_src.sh"):
            with self.subTest(script=name):
                text = (REPO_ROOT / name).read_text(encoding="utf-8")
                self.assertIn("cvh.requestRender();", text)
                self.assertIn(
                    "mAppLaunchDrawBlocker.onActiveTabAvailableForRecreation();",
                    text,
                )
                # The synchronous writer duplicated the timed line and blocked the
                # main thread during recreation, so it must stay gone.
                self.assertNotIn('"activity-recreated at "', text)
                self.assertIn("recordHeliumThemeStopped();", text)
                self.assertIn("recordHeliumThemeDestroyed();", text)

    def test_theme_switch_timing_is_logged_by_phase(self):
        for name in ("patch.sh", "hotfix_existing_src.sh"):
            with self.subTest(script=name):
                text = (REPO_ROOT / name).read_text(encoding="utf-8")
                self.assertIn("public static synchronized long beginHeliumThemeTiming(int theme)", text)
                self.assertIn("public static synchronized void recordHeliumThemeTiming(", text)
                self.assertIn("sHeliumThemeTimingId", text)
                self.assertIn('phase=click theme=', text)
                self.assertIn('phase=" + phase + " theme="', text)
                self.assertIn('phase=activity-recreated theme=', text)
                self.assertIn('phase=draw-unblocked theme=', text)
                self.assertIn('"activity-stopped"', text)
                self.assertIn('"activity-destroyed"', text)
                self.assertIn("void recordHeliumThemeStopped() {", text)
                self.assertIn("void recordHeliumThemeDestroyed() {", text)
                self.assertIn("public void onStop() {", text)
                self.assertIn("protected final void onDestroy() {", text)
                self.assertIn("recordHeliumThemeStopped();", text)
                self.assertIn("recordHeliumThemeDestroyed();", text)
                self.assertIn("click_to_preference_ms=", text)
                self.assertIn("click_to_stop_ms=", text)
                self.assertIn("click_to_destroy_ms=", text)
                self.assertIn("click_to_recreate_ms=", text)
                self.assertIn("click_to_draw_ms=", text)
                self.assertIn("SystemClock.elapsedRealtime()", text)

    def test_recreation_timing_survives_baseline_restore(self):
        # restore_modern_android_sdk_baseline git-checkouts ChromeTabbedActivity.java,
        # so the recreation hooks must be applied again afterwards.
        for name in ("patch.sh", "hotfix_existing_src.sh"):
            with self.subTest(script=name):
                text = (REPO_ROOT / name).read_text(encoding="utf-8")
                self.assertIn("apply_helium_recreation_timing() {", text)
                self.assertGreaterEqual(text.count("apply_helium_recreation_timing\n"), 2)
                self.assertLess(
                    text.index("restore_modern_android_sdk_baseline"),
                    text.rindex("apply_helium_recreation_timing"),
                )

    def test_android_tab_list_null_contents_and_draw_blocker_guards(self):
        for name in ("patch.sh", "hotfix_existing_src.sh"):
            with self.subTest(script=name):
                text = (REPO_ROOT / name).read_text(encoding="utf-8")
                self.assertIn("HeliumAndroidNullContentsGuard", text)
                self.assertIn("HeliumAndroidHighlightProfileGuard", text)
                self.assertIn("HeliumAndroidDrawBlockerTimeout", text)
                self.assertIn(
                    "content::WebContents* contents = tab ? tab->GetContents() : nullptr;",
                    text,
                )

    def test_highlighted_tab_profile_guard_rewrites_upstream_source(self):
        upstream = """  for (tabs::TabInterface* tab : highlighted_tabs) {
    content::WebContents* web_contents = tab->GetContents();
    CHECK(web_contents);

    if (highlight_info.window_id == -1) {
      profile = Profile::FromBrowserContext(web_contents->GetBrowserContext());
      highlight_info.window_id =
          ExtensionTabUtil::GetWindowIdOfTab(web_contents);
    }

    int tab_id = ExtensionTabUtil::GetTabId(web_contents);
    highlight_info.tab_ids.push_back(tab_id);
  }
  CHECK(profile);

  base::ListValue args = api::tabs::OnHighlighted::Create(highlight_info);
"""
        for name in ("patch.sh", "hotfix_existing_src.sh"):
            with self.subTest(script=name):
                script = (REPO_ROOT / name).read_text(encoding="utf-8")
                start = script.index('if "HeliumAndroidHighlightProfileGuard" not in text:')
                end = script.index(
                    "if path.read_text() != text:", start
                )
                namespace = {"text": upstream}
                exec(script[start:end], namespace)
                patched = namespace["text"]
                self.assertIn("HeliumAndroidHighlightProfileGuard", patched)
                self.assertIn("  if (!profile) {\n    return;\n  }", patched)
                self.assertIn("  CHECK(profile);", patched)

    def test_get_tab_by_id_skips_frozen_tabs_without_contents(self):
        upstream = """    for (int i = 0; i < window->GetTabCount(); ++i) {
      WebContents* target_contents = window->GetWebContentsAt(i);
      int target_tab_id = sessions::SessionTabHelper::IdForTab(target_contents).id();
#if BUILDFLAG(IS_ANDROID)
      if (target_tab_id == -1) {
"""
        for name in ("patch.sh", "hotfix_existing_src.sh"):
            with self.subTest(script=name):
                script = (REPO_ROOT / name).read_text(encoding="utf-8")
                start = script.index('if "HeliumAndroidGetTabByIdNullContentsGuard" not in text:')
                end = script.index(
                    'if "HeliumAndroidGetTabByIdTabModelListFallback" not in text:',
                    start,
                )
                namespace = {"text": upstream}
                exec(script[start:end], namespace)
                patched = namespace["text"]
                self.assertIn("HeliumAndroidGetTabByIdNullContentsGuard", patched)
                self.assertIn("if (!target_contents) {", patched)
                self.assertIn("continue;", patched)
                self.assertIn("SessionTabHelper::IdForTab(target_contents)", patched)

    def test_for_each_tab_skips_tabs_without_contents(self):
        # Frozen restore tabs are added to the model before they own a
        # WebContents, and every ForEachTab caller dereferences what it gets.
        upstream = """void ExtensionTabUtil::ForEachTab(
    base::RepeatingCallback<void(WebContents*)> callback) {
  tabs::ForEachTabInterface([&callback](tabs::TabInterface* tab) {
    callback.Run(tab->GetContents());
    return true;
  });
}
"""
        for name in ("patch.sh", "hotfix_existing_src.sh"):
            with self.subTest(script=name):
                script = (REPO_ROOT / name).read_text(encoding="utf-8")
                start = script.index(
                    'if "HeliumAndroidForEachTabNullContentsGuard" not in text:'
                )
                end = script.index("if path.read_text() != text:", start)
                namespace = {"text": upstream}
                exec(script[start:end], namespace)
                patched = namespace["text"]
                self.assertIn("HeliumAndroidForEachTabNullContentsGuard", patched)
                self.assertIn(
                    "    WebContents* contents = tab ? tab->GetContents() : nullptr;",
                    patched,
                )
                self.assertIn("#if BUILDFLAG(IS_ANDROID)\n    if (!contents) {", patched)
                self.assertIn("    callback.Run(contents);", patched)
                self.assertNotIn("    callback.Run(tab->GetContents());", patched)

    def test_lemur_menu_patch_runs_after_sdk_baseline_restore(self):
        # The baseline restore git-checkouts the app menu delegates, so running the
        # Lemur menu patch first would leave the build without its custom menu.
        for name, restore_call in (
            ("patch.sh", "restore_modern_android_sdk_baseline ."),
            (
                "hotfix_existing_src.sh",
                'restore_modern_android_sdk_baseline "$SRC_DIR"',
            ),
        ):
            with self.subTest(script=name):
                text = (REPO_ROOT / name).read_text(encoding="utf-8")
                self.assertLess(
                    text.rindex(restore_call),
                    text.rindex("patch_lemur_app_menu.py"),
                )


if __name__ == "__main__":
    unittest.main()
