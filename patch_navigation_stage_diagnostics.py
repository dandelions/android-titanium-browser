#!/usr/bin/env python3
"""Write every navigation stage to a file on old-android builds.

On the VMOS-based target no web page, ``file://`` document, or extension page
ever commits, while the native new tab page keeps painting. The renderer is
started, initialises Skia, then idles until Android reaps it, and the tab ends
up on the sad-tab page.

``logd`` on that device dies repeatedly, so an in-app ``logcat`` capture stops
producing output exactly when the failure happens. Log through both LOG and a
direct append to ``<app data>/helium-nav.log`` so the stages survive logd being
dead, and cover the URL loader stages so a stall between "throttles passed" and
"renderer committed" is attributable to a specific step.
"""
import os
import sys

NAVIGATION_REQUEST = "content/browser/renderer_host/navigation_request.cc"
NAVIGATION_URL_LOADER = "content/browser/loader/navigation_url_loader_impl.cc"

HELPER = '''// Helium: navigation stage trace that survives logd being unavailable.
// Helium nav trace revision: 2
void HeliumNavTrace(const char* stage, const GURL& url, int value) {
  std::string line = base::StringPrintf("Helium nav: %s url=%s value=%d\\n",
                                        stage, url.possibly_invalid_spec().c_str(),
                                        value);
  LOG(WARNING) << line;
  base::FilePath path;
  if (!base::PathService::Get(base::DIR_ANDROID_APP_DATA, &path)) return;
  path = path.AppendASCII("helium-nav.log");
  base::AppendToFile(path, line);
}

'''

BEGIN_ORIGINAL = """void NavigationRequest::BeginNavigation() {
  begin_navigation_time_ = base::TimeTicks::Now();
"""

BEGIN_PATCHED = """void NavigationRequest::BeginNavigation() {
  HeliumNavTrace("begin", GetURL(), 0);
  begin_navigation_time_ = base::TimeTicks::Now();
"""

CHECKS_ORIGINAL = """void NavigationRequest::OnStartChecksComplete(
    NavigationThrottle::ThrottleCheckResult result) {
"""

CHECKS_PATCHED = """void NavigationRequest::OnStartChecksComplete(
    NavigationThrottle::ThrottleCheckResult result) {
  HeliumNavTrace("checks-complete", GetURL(), static_cast<int>(result.action()));
"""

RESPONSE_ORIGINAL = """void NavigationRequest::OnResponseStarted(
    network::mojom::URLLoaderClientEndpointsPtr url_loader_client_endpoints,
"""

RESPONSE_PATCHED = """void NavigationRequest::OnResponseStarted(
    network::mojom::URLLoaderClientEndpointsPtr url_loader_client_endpoints,
"""
HELPER_RESPONSE_INJECT = """  HeliumNavTrace("response", GetURL(), 0);
"""

COMMIT_ORIGINAL = """void NavigationRequest::DidCommitNavigation(
    const mojom::DidCommitProvisionalLoadParams& params,
    bool navigation_entry_committed,
    bool did_replace_entry,
    const GURL& previous_main_frame_url) {
"""

COMMIT_PATCHED = """void NavigationRequest::DidCommitNavigation(
    const mojom::DidCommitProvisionalLoadParams& params,
    bool navigation_entry_committed,
    bool did_replace_entry,
    const GURL& previous_main_frame_url) {
  HeliumNavTrace("commit", GetURL(), 0);
"""

FAIL_ORIGINAL = """void NavigationRequest::OnRequestFailedInternal(
    const network::URLLoaderCompletionStatus& status,
    bool skip_throttles,
    const std::optional<std::string>& error_page_content,
    bool collapse_frame) {
"""

FAIL_PATCHED = """void NavigationRequest::OnRequestFailedInternal(
    const network::URLLoaderCompletionStatus& status,
    bool skip_throttles,
    const std::optional<std::string>& error_page_content,
    bool collapse_frame) {
  HeliumNavTrace("failed", GetURL(), status.error_code);
"""

LOADER_ORIGINAL = """void NavigationURLLoaderImpl::OnReceiveResponse(
    network::mojom::URLResponseHeadPtr head,
"""

LOADER_PATCHED = """void NavigationURLLoaderImpl::OnReceiveResponse(
    network::mojom::URLResponseHeadPtr head,
"""
LOADER_BODY_INJECT = """  HeliumNavTrace("loader-response", request_url_, 0);
"""


def _read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _write(path, content):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def _replace_once(path, original, patched, label):
    if not os.path.isfile(path):
        return False
    content = _read(path)
    if patched in content:
        return False
    if original not in content:
        print(f"Warning: could not find {label} in {path}", file=sys.stderr)
        return False
    _write(path, content.replace(original, patched, 1))
    print(f"Patched {label}: {path}")
    return True


def _insert_after_signature(path, signature, body, label):
    """Insert a statement right after a function signature's closing brace."""
    if not os.path.isfile(path):
        return False
    content = _read(path)
    if body in content:
        return False
    marker = signature + " {\n"
    if marker not in content:
        print(f"Warning: could not find signature for {label} in {path}", file=sys.stderr)
        return False
    _write(path, content.replace(marker, marker + body, 1))
    print(f"Patched {label}: {path}")
    return True


def patch_source_tree(src_dir):
    nav_path = os.path.join(src_dir, NAVIGATION_REQUEST)
    loader_path = os.path.join(src_dir, NAVIGATION_URL_LOADER)
    changed = False

    # 1. Install the trace helper above BeginNavigation().
    if os.path.isfile(nav_path):
        content = _read(nav_path)
        if "Helium nav trace revision: 2" not in content and BEGIN_ORIGINAL in content:
            extra_includes = ""
            for header in (
                "base/files/file_util.h",
                "base/path_service.h",
                "base/base_paths_android.h",
            ):
                include = f'#include "{header}"\n'
                if include not in content:
                    extra_includes += include
            if extra_includes:
                content = content.replace(
                    '#include "base/containers/span.h"\n',
                    '#include "base/containers/span.h"\n' + extra_includes,
                    1,
                )
            content = content.replace(BEGIN_ORIGINAL, HELPER + BEGIN_PATCHED, 1)
            _write(nav_path, content)
            print(f"Patched navigation trace helper: {nav_path}")
            changed = True

    # 2. Remaining stages.
    if _insert_after_signature(
        nav_path,
        "void NavigationRequest::OnStartChecksComplete(\n"
        "    NavigationThrottle::ThrottleCheckResult result)",
        '  HeliumNavTrace("checks-complete", GetURL(),'
        " static_cast<int>(result.action()));\n",
        "navigation checks-complete logging",
    ):
        changed = True

    if _insert_after_signature(
        nav_path,
        "void NavigationRequest::DidCommitNavigation(\n"
        "    const mojom::DidCommitProvisionalLoadParams& params,\n"
        "    bool navigation_entry_committed,\n"
        "    bool did_replace_entry,\n"
        "    const GURL& previous_main_frame_url)",
        '  HeliumNavTrace("commit", GetURL(), 0);\n',
        "navigation commit logging",
    ):
        changed = True

    if _insert_after_signature(
        nav_path,
        "void NavigationRequest::OnRequestFailedInternal(\n"
        "    const network::URLLoaderCompletionStatus& status,\n"
        "    bool skip_throttles,\n"
        "    const std::optional<std::string>& error_page_content,\n"
        "    bool collapse_frame)",
        '  HeliumNavTrace("failed", GetURL(), status.error_code);\n',
        "navigation failure logging",
    ):
        changed = True

    if _insert_after_signature(
        nav_path,
        "void NavigationRequest::OnResponseStarted(\n"
        "    network::mojom::URLLoaderClientEndpointsPtr url_loader_client_endpoints,\n"
        "    network::mojom::URLResponseHeadPtr response_head,\n"
        "    mojo::ScopedDataPipeConsumerHandle response_body,\n"
        "    GlobalRequestID request_id,\n"
        "    bool is_download,\n"
        "    net::NetworkAnonymizationKey network_anonymization_key,\n"
        "    SubresourceLoaderParams subresource_loader_params,\n"
        "    EarlyHints early_hints)",
        '  HeliumNavTrace("response", GetURL(), 0);\n',
        "navigation response logging",
    ):
        changed = True

    return changed


def main():
    patch_source_tree(sys.argv[1] if len(sys.argv) > 1 else ".")


if __name__ == "__main__":
    main()
