import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "patch_accessibility_recommended_timeout.py"
)
SPEC = importlib.util.spec_from_file_location(
    "patch_accessibility_recommended_timeout", MODULE_PATH
)
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)

TARGET_FILE = (
    "ui/accessibility/android/java/src/org/chromium/ui/accessibility/"
    "AccessibilityStateDelegateImpl.java"
)

SOURCE = """// Copyright 2026 The Chromium Authors
package org.chromium.ui.accessibility;

public class AccessibilityStateDelegateImpl {
    @Override
    public int getRecommendedTimeoutMillis(int minimumTimeout, int nonA11yTimeout) {
        if (mState == null) updateAccessibilityServices();

        int recommendedTimeout =
                fetchAccessibilityManager()
                        .getRecommendedTimeoutMillis(
                                nonA11yTimeout,
                                FLAG_CONTENT_ICONS | FLAG_CONTENT_TEXT | FLAG_CONTENT_CONTROLS);

        return Math.max(minimumTimeout, recommendedTimeout);
    }
}
"""


class TestPatchAccessibilityRecommendedTimeout(unittest.TestCase):
    def test_patch_source_tree(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / TARGET_FILE
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(SOURCE, encoding="utf-8")

            changed = PATCH.patch_source_tree(tmp_dir)
            self.assertTrue(changed)

            patched_content = file_path.read_text(encoding="utf-8")
            self.assertIn("Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q", patched_content)
            self.assertIn("int recommendedTimeout = nonA11yTimeout;", patched_content)

            # Idempotent
            changed_again = PATCH.patch_source_tree(tmp_dir)
            self.assertFalse(changed_again)

    def test_patch_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            changed = PATCH.patch_source_tree(tmp_dir)
            self.assertFalse(changed)


if __name__ == "__main__":
    unittest.main()
