import pathlib
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
VERIFY = ROOT / "verify_old_android_features.py"


class VerifyOldAndroidFeaturesTest(unittest.TestCase):
    def test_accepts_required_feature_markers(self):
        files = {
            "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/extensions/ExtensionsToolbarCoordinatorImpl.java": "return !mIsWebApp && mCanShowMenuIcon;",
            "chrome/android/java/src/org/chromium/chrome/browser/app/appmenu/AppMenuPropertiesDelegateImpl.java": "boolean shouldShowExtensionsItem() {\n        return true;\n    }",
            "chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/ToolbarPositionController.java": "Helium: follow the toolbar preference on the NTP and while editing",
            "chrome/android/java/src/org/chromium/chrome/browser/ntp/NewTabPageCoordinator.java": "AddressBarPreference.isToolbarConfiguredToShowOnTop()",
            "chrome/browser/ui/android/toolbar/java/res/layout/toolbar_phone.xml": '<ViewStub android:id="@+id/extensions_toolbar_container_stub"/>',
            "chrome/android/java/src/org/chromium/chrome/browser/toolbar/ToolbarManager.java": "mToolbarLayout,",
        }
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
