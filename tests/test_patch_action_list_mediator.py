import re
import shutil
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "chromium_157" / "ExtensionActionListMediator.java"


def apply_mediator_patch(path: Path):
    text = path.read_text(encoding="utf-8")
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
                        || incognitoTab.isUserInteractable())) {
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
    if "import org.chromium.base.Callback;" not in text:
        text = text.replace(
            "import org.chromium.base.lifetime.Destroyable;\n",
            "import org.chromium.base.Callback;\nimport org.chromium.base.lifetime.Destroyable;\n",
            1,
        )
    observer_field = """    private final Callback<@Nullable Tab> mTabSupplierObserver =
            (tab) -> {
                WebContents webContents =
                        tab != null && tab.getWebContents() != null
                                ? tab.getWebContents()
                                : getCurrentWebContents();
                updateActionPropertiesForAll(webContents);
            };
"""
    if "mTabSupplierObserver" not in text:
        text = text.replace(
            "    private final ToolbarObserver mToolbarObserver = new ToolbarObserver();\n",
            "    private final ToolbarObserver mToolbarObserver = new ToolbarObserver();\n"
            + observer_field,
            1,
        )
        text = text.replace(
            "        mExtensionsToolbarBridge.addObserver(mToolbarObserver);\n",
            "        mExtensionsToolbarBridge.addObserver(mToolbarObserver);\n"
            "        mCurrentTabSupplier.addSyncObserver(mTabSupplierObserver);\n",
            1,
        )
        text = text.replace(
            "        mExtensionsToolbarBridge.removeObserver(mToolbarObserver);\n",
            "        mCurrentTabSupplier.removeObserver(mTabSupplierObserver);\n"
            "        mExtensionsToolbarBridge.removeObserver(mToolbarObserver);\n",
            1,
        )
    text = text.replace(
        "                mExtensionsToolbarBridge.setActiveWebContents(webContents);\n"
        "                updateActionPropertiesForAll(webContents);\n",
        "                updateActionPropertiesForAll(webContents);\n",
    )
    anchor = re.search(
        r"(?m)^    (?:private )?void updateActionPropertiesForAll\((?:@Nullable )?WebContents webContents\) \{$",
        text,
    )
    if anchor is None:
        raise SystemExit(f"updateActionPropertiesForAll insertion anchor not found in {path}")
    text = text[:anchor.start()] + helper + text[anchor.start():]
    if "mExtensionsToolbarBridge.setActiveWebContents(webContents);" not in text:
        text = re.sub(
            r"(?m)^(    (?:private )?void updateActionPropertiesForAll\((?:@Nullable )?WebContents webContents\) \{\n)",
            r"\1        mExtensionsToolbarBridge.setActiveWebContents(webContents);\n",
            text,
            count=1,
        )
    if len(signature.findall(text)) != 1:
        raise SystemExit(f"expected exactly one getCurrentWebContents helper in {path}")
    path.write_text(text, encoding="utf-8")


class TestPatchActionListMediator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self.temp_dir.name)
        self.mediator = self.work_dir / "ExtensionActionListMediator.java"
        shutil.copy(FIXTURE, self.mediator)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_patch_chromium_157_mediator(self):
        apply_mediator_patch(self.mediator)
        content = self.mediator.read_text(encoding="utf-8")
        self.assertIn("getCurrentWebContents()", content)
        self.assertIn("mExtensionsToolbarBridge.setActiveWebContents(webContents);", content)
        self.assertIn("mTabSupplierObserver", content)

        # Idempotence
        apply_mediator_patch(self.mediator)
        content_after = self.mediator.read_text(encoding="utf-8")
        self.assertEqual(content, content_after)


if __name__ == "__main__":
    unittest.main()
