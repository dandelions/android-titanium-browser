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

CLEAN = """#include "base/containers/span.h"
#include "base/files/file_path.h"

void NavigationRequest::BeginNavigation() {
  begin_navigation_time_ = base::TimeTicks::Now();
}

void NavigationRequest::OnStartChecksComplete(
    NavigationThrottle::ThrottleCheckResult result) {
  CHECK(true);
}

void NavigationRequest::OnResponseStarted(
    network::mojom::URLLoaderClientEndpointsPtr url_loader_client_endpoints,
    network::mojom::URLResponseHeadPtr response_head,
    mojo::ScopedDataPipeConsumerHandle response_body,
    GlobalRequestID request_id,
    bool is_download,
    net::NetworkAnonymizationKey network_anonymization_key,
    SubresourceLoaderParams subresource_loader_params,
    EarlyHints early_hints) {
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

# 上一版补丁留下的痕迹：只有 LOG 行，没有 HeliumNavTrace
PREVIOUSLY_PATCHED = """

void NavigationRequest::BeginNavigation() {
  // Helium: report the start of every navigation so a stall is visible.
  LOG(WARNING) << "Helium nav: begin url=" << GetURL().possibly_invalid_spec();
  begin_navigation_time_ = base::TimeTicks::Now();
}

void NavigationRequest::OnStartChecksComplete(
    NavigationThrottle::ThrottleCheckResult result) {
  // Helium: throttles are done; the URL loader is about to be created.
  LOG(WARNING) << "Helium nav: checks-complete url="
               << GetURL().possibly_invalid_spec();
}

void NavigationRequest::DidCommitNavigation(
    const mojom::DidCommitProvisionalLoadParams& params,
    bool navigation_entry_committed,
    bool did_replace_entry,
    const GURL& previous_main_frame_url) {
  LOG(WARNING) << "Helium nav: commit url=";
}
"""


class TestPatchNavigationStageDiagnostics(unittest.TestCase):
    def _apply(self, tmp, source):
        path = Path(tmp) / NAV
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
        return path, PATCH.patch_source_tree(tmp)

    def test_fresh_tree_gets_helper_and_all_stages(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, changed = self._apply(tmp, CLEAN)
            self.assertTrue(changed)
            out = path.read_text(encoding="utf-8")
            self.assertIn("void HeliumNavTrace(const char* stage", out)
            self.assertIn('path.AppendASCII("helium-nav.log")', out)
            self.assertIn("base::AppendToFile(", out)
            for header in (
                "base/files/file_util.h",
                "base/path_service.h",
                "base/base_paths_android.h",
            ):
                self.assertIn(f'#include "{header}"', out)
            for stage in ("begin", "checks-complete", "response", "commit", "failed"):
                self.assertIn(f'HeliumNavTrace("{stage}"', out)

    def test_upgrades_a_previously_patched_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, changed = self._apply(tmp, PREVIOUSLY_PATCHED)
            self.assertTrue(changed)
            out = path.read_text(encoding="utf-8")
            self.assertIn("void HeliumNavTrace(const char* stage", out)
            for stage in ("begin", "checks-complete", "commit"):
                self.assertIn(f'HeliumNavTrace("{stage}"', out)

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, _ = self._apply(tmp, CLEAN)
            first = path.read_text(encoding="utf-8")
            self.assertFalse(PATCH.patch_source_tree(tmp))
            self.assertEqual(first, path.read_text(encoding="utf-8"))

    def test_missing_file_is_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(PATCH.patch_source_tree(tmp))


if __name__ == "__main__":
    unittest.main()
