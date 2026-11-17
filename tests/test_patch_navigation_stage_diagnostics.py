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

void NavigationRequest::ReadyToCommitNavigation(bool is_error) {
  CHECK(true);
}

void NavigationRequest::OnCommitTimeout() {
  CHECK(true);
}

void NavigationRequest::OnResponseBodyReady(MojoResult) {
  CHECK(true);
}

void NavigationRequest::RunCommitDeferringConditions(
    base::OnceClosure on_commit_deferring_conditions_complete_callback) {
  CHECK(true);
}

void NavigationRequest::CommitNavigation() {
  CHECK(true);
}
"""

RUNNER = """#include "base/memory/ptr_util.h"

void CommitDeferringConditionRunner::ProcessConditions() {
  while (!conditions_.empty()) {
    auto resume_closure = base::BindOnce(&CommitDeferringConditionRunner);
    CommitDeferringCondition* condition = (*conditions_.begin()).get();
    is_deferred_ = false;
    is_in_will_commit_navigation_ = true;
    was_resumed_synchronously_ = false;

    base::WeakPtr<CommitDeferringConditionRunner> weak_self =
        weak_factory_.GetWeakPtr();
    CommitDeferringCondition::Result result =
        condition->WillCommitNavigation(std::move(resume_closure));
    if (!weak_self) {
      // The runner was deleted, which indicates the navigation was cancelled.
      CHECK_NE(result, CommitDeferringCondition::Result::kProceed);
      return;
    }
    is_in_will_commit_navigation_ = false;
  }
}
"""

RENDER_FRAME = """void RenderFrameImpl::CommitNavigation(
    blink::mojom::CommonNavigationParamsPtr common_params) {
  base::ElapsedTimer timer;
  TRACE_EVENT("navigation", "RenderFrameImpl::CommitNavigation",
              perfetto::Flow::FromPointer(this));
  DCHECK(navigation_client_impl_);
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

    def _apply_commit_stage_files(self, tmp):
        runner = Path(tmp) / PATCH.COMMIT_RUNNER
        runner.parent.mkdir(parents=True, exist_ok=True)
        runner.write_text(RUNNER, encoding="utf-8")
        renderer = Path(tmp) / PATCH.RENDER_FRAME_IMPL
        renderer.parent.mkdir(parents=True, exist_ok=True)
        renderer.write_text(RENDER_FRAME, encoding="utf-8")
        return runner, renderer

    def test_fresh_tree_gets_helper_and_all_stages(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, changed = self._apply(tmp, CLEAN)
            self.assertTrue(changed)
            out = path.read_text(encoding="utf-8")
            self.assertIn("void HeliumNavTrace(const char* stage", out)
            self.assertIn('app_data.AppendASCII("helium-nav.log")', out)
            self.assertIn("base::File file(where,", out)
            for header in (
                "base/files/file.h",
                "base/files/file_path.h",
                "base/path_service.h",
                "base/base_paths_android.h",
            ):
                self.assertIn(f'#include "{header}"', out)
            self.assertIn("base::File::ErrorToString(", out)
            for stage in (
                "begin",
                "checks-complete",
                "response",
                "response-body-ready",
                "ready-to-commit",
                "conditions-start",
                "commit-send",
                "commit-timeout",
                "commit",
                "failed",
            ):
                self.assertIn(f'HeliumNavTrace("{stage}"', out)

    def test_upgrades_a_previously_patched_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, changed = self._apply(tmp, PREVIOUSLY_PATCHED)
            self.assertTrue(changed)
            out = path.read_text(encoding="utf-8")
            self.assertIn("void HeliumNavTrace(const char* stage", out)
            for stage in ("begin", "checks-complete", "commit"):
                self.assertIn(f'HeliumNavTrace("{stage}"', out)
            # 上一版留下的裸 LOG 行必须被清掉，否则每个阶段会打印两次。
            self.assertNotIn('LOG(WARNING) << "Helium nav: begin url=', out)
            self.assertNotIn('LOG(WARNING) << "Helium nav: checks-complete url=', out)
            self.assertNotIn('LOG(WARNING) << "Helium nav: commit url=', out)

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, _ = self._apply(tmp, CLEAN)
            first = path.read_text(encoding="utf-8")
            self.assertFalse(PATCH.patch_source_tree(tmp))
            self.assertEqual(first, path.read_text(encoding="utf-8"))

    def test_commit_stage_traces_cover_conditions_and_renderer_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner, renderer = self._apply_commit_stage_files(tmp)
            self.assertTrue(PATCH.patch_source_tree(tmp))

            runner_out = runner.read_text(encoding="utf-8")
            self.assertIn('#include "base/logging.h"', runner_out)
            self.assertIn('"Helium commit: condition="', runner_out)
            self.assertIn('"Helium commit: condition result="', runner_out)
            self.assertIn("condition->TraceEventName()", runner_out)

            renderer_out = renderer.read_text(encoding="utf-8")
            self.assertIn('"Helium renderer commit: received"', renderer_out)
            self.assertLess(
                renderer_out.index("Helium renderer commit: received"),
                renderer_out.index('TRACE_EVENT("navigation", "RenderFrameImpl'),
            )

            # 第二次运行必须不再改动，避免重复插入日志。
            self.assertFalse(PATCH.patch_source_tree(tmp))
            self.assertEqual(runner_out, runner.read_text(encoding="utf-8"))
            self.assertEqual(renderer_out, renderer.read_text(encoding="utf-8"))

    def test_missing_file_is_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(PATCH.patch_source_tree(tmp))


if __name__ == "__main__":
    unittest.main()
