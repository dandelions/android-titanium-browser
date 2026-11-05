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
                self.assertIn(
                    "Helium: follow the toolbar preference on the NTP and while editing",
                    text,
                )
                self.assertIn(
                    "AddressBarPreference.isToolbarConfiguredToShowOnTop()",
                    text,
                )


if __name__ == "__main__":
    unittest.main()
