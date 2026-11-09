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
                    "mHandler.postDelayed(\n                            mAppLaunchDrawBlocker::onActiveTabAvailableForRecreation, 350);",
                    text,
                )


if __name__ == "__main__":
    unittest.main()
