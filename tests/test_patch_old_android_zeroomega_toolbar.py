import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "patch_old_android_zeroomega_toolbar", ROOT / "patch_old_android_zeroomega_toolbar.py"
)
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)
FIXTURE = ROOT / "tests/fixtures/chromium_157/toolbar_actions_model.cc"


class OldAndroidZeroOmegaToolbarPatchTest(unittest.TestCase):
    def test_pins_only_zeroomega_and_migrates_existing_install_once(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "toolbar_actions_model.cc"
            source = FIXTURE.read_text(encoding="utf-8")
            source = source.replace(
                "  const bool is_pinned_by_feature =\n"
                "      pin_mode == extensions::ManagedToolbarPinMode::kNotSet &&\n"
                "      !is_enterprise_extension && !is_installed_from_sync &&\n"
                "      is_feature_enabled && is_toggle_on;\n",
                PATCH.OLD_PIN_DEFAULT,
            )
            source += PATCH.OLD_INITIALIZE
            path.write_text(source, encoding="utf-8")

            self.assertTrue(PATCH.patch_model(path))
            result = path.read_text(encoding="utf-8")
            self.assertIn(
                f'extension->id() == "{PATCH.EXTENSION_ID}" &&', result
            )
            self.assertIn("is_pinned_by_policy", result)
            self.assertIn("Helium: migrate an existing ZeroOmega install", result)
            self.assertIn("WasPinnedByDefault(kZeroOmegaExtensionId) != true", result)
            self.assertIn("if (action_ids_.contains(kZeroOmegaExtensionId))", result)
            self.assertIn("SetWasPinnedByDefault(kZeroOmegaExtensionId, true)", result)
            self.assertIn("std::ranges::contains(stored_pinned_actions", result)

            self.assertFalse(PATCH.patch_model(path))
            self.assertEqual(result, path.read_text(encoding="utf-8"))

    def test_handles_unmodified_upstream_pin_expression(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "toolbar_actions_model.cc"
            source = FIXTURE.read_text(encoding="utf-8")
            source += PATCH.OLD_INITIALIZE
            path.write_text(source, encoding="utf-8")

            self.assertIn(PATCH.VANILLA_PIN_DEFAULT, source)
            self.assertTrue(PATCH.patch_model(path))
            result = path.read_text(encoding="utf-8")
            self.assertIn(f'extension->id() == "{PATCH.EXTENSION_ID}" &&', result)
            self.assertIn("Helium: migrate an existing ZeroOmega install", result)
            self.assertFalse(PATCH.patch_model(path))
            self.assertEqual(result, path.read_text(encoding="utf-8"))

    def test_handles_v158_default_install_condition(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "toolbar_actions_model.cc"
            source = FIXTURE.read_text(encoding="utf-8").replace(
                PATCH.VANILLA_PIN_DEFAULT, PATCH.V158_PIN_DEFAULT
            )
            source += PATCH.OLD_INITIALIZE
            path.write_text(source, encoding="utf-8")

            self.assertTrue(PATCH.patch_model(path))
            result = path.read_text(encoding="utf-8")
            self.assertIn(f'extension->id() == "{PATCH.EXTENSION_ID}" &&', result)
            self.assertIn("Helium: migrate an existing ZeroOmega install", result)
            self.assertFalse(PATCH.patch_model(path))

    def test_fails_when_upstream_anchors_change(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "toolbar_actions_model.cc"
            path.write_text("unrecognized source", encoding="utf-8")
            with self.assertRaises(SystemExit):
                PATCH.patch_model(path)


if __name__ == "__main__":
    unittest.main()
