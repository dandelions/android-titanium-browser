import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "patch_navigation_stage_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location(
    "patch_navigation_stage_diagnostics", MODULE_PATH
)
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)

NAV = PATCH.NAVIGATION_REQUEST

SOURCE = """void NavigationRequest::BeginNavigation() {
  begin_navigation_time_ = base::TimeTicks::Now();
}

void NavigationRequest::OnStartChecksComplete(
    NavigationThrottle::ThrottleCheckResult result) {
  CHECK(true);
}

void NavigationRequest::DidCommitNavigation(
    const mojom::DidCommitProvisionalLoadParams& params,
    bool navigation_entry_committed,
    bool did_replace_entry,
    const GURL& previous_main_frame_url) {
  CHECK(true);
}

void NavigationRequest::OnRequestFailedInternal(
    const network::URLLoaderCompletionStatus& status,
    bool skip_throttles,
    const std::optional<std::string>& error_page_content,
    bool collapse_frame) {
  CHECK(true);
}
"""


class TestPatchNavigationStageDiagnostics(unittest.TestCase):
    def test_patch_adds_all_four_stages(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / NAV
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(SOURCE, encoding="utf-8")

            self.assertTrue(PATCH.patch_source_tree(tmp))
            out = path.read_text(encoding="utf-8")
            for marker in (
                '"Helium nav: begin url="',
                '"Helium nav: checks-complete url="',
                '"Helium nav: commit url="',
                '"Helium nav: failed url="',
                "net_error=",
            ):
                self.assertIn(marker, out)

    def test_patch_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / NAV
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(SOURCE, encoding="utf-8")
            PATCH.patch_source_tree(tmp)
            first = path.read_text(encoding="utf-8")
            self.assertFalse(PATCH.patch_source_tree(tmp))
            self.assertEqual(first, path.read_text(encoding="utf-8"))

    def test_missing_file_is_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(PATCH.patch_source_tree(tmp))


if __name__ == "__main__":
    unittest.main()
