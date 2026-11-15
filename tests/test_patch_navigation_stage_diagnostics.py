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

SOURCE = """#include "base/containers/span.h"
#include "base/files/file_path.h"
#include "base/strings/stringprintf.h"

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


class TestPatchNavigationStageDiagnostics(unittest.TestCase):
    def _patch(self, tmp):
        path = Path(tmp) / NAV
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(SOURCE, encoding="utf-8")
        result = PATCH.patch_source_tree(tmp)
        return path, result

    def test_installs_file_backed_helper_and_stages(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, changed = self._patch(tmp)
            self.assertTrue(changed)
            out = path.read_text(encoding="utf-8")
            self.assertIn("void HeliumNavTrace(const char* stage", out)
            self.assertIn('path.AppendASCII("helium-nav.log")', out)
            self.assertIn("base::AppendToFile(path, line)", out)
            for header in (
                "base/files/file_util.h",
                "base/path_service.h",
                "base/base_paths_android.h",
            ):
                self.assertIn(f'#include "{header}"', out)
            for stage in ("begin", "checks-complete", "response", "commit", "failed"):
                self.assertIn(f'HeliumNavTrace("{stage}"', out)

    def test_patch_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, _ = self._patch(tmp)
            first = path.read_text(encoding="utf-8")
            self.assertFalse(PATCH.patch_source_tree(tmp))
            self.assertEqual(first, path.read_text(encoding="utf-8"))

    def test_missing_file_is_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(PATCH.patch_source_tree(tmp))


if __name__ == "__main__":
    unittest.main()
