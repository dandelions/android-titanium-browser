#!/usr/bin/env python3
"""Log every stage of a browser-initiated navigation on old-android builds.

On the VMOS-based target no web page, local ``file://`` document, or extension
page ever commits, while the native new tab page keeps rendering. The renderer
process is started, initialises Skia, then sits idle until Android reaps it,
and the tab ends up on the sad-tab page. ``logd`` is dead on that device, so the
only observable signal is what we print ourselves.

Emit the four navigation stages (begin, checks complete, commit, failure) with
the URL and the net error, so the stage where the pipeline stalls is visible in
the in-app log capture.
"""
import os
import sys

NAVIGATION_REQUEST = "content/browser/renderer_host/navigation_request.cc"

BEGIN_ORIGINAL = """void NavigationRequest::BeginNavigation() {
  begin_navigation_time_ = base::TimeTicks::Now();
"""

BEGIN_PATCHED = """void NavigationRequest::BeginNavigation() {
  // Helium: report the start of every navigation so a stall is visible.
  LOG(WARNING) << "Helium nav: begin url=" << GetURL().possibly_invalid_spec();
  begin_navigation_time_ = base::TimeTicks::Now();
"""

CHECKS_ORIGINAL = """void NavigationRequest::OnStartChecksComplete(
    NavigationThrottle::ThrottleCheckResult result) {
"""

CHECKS_PATCHED = """void NavigationRequest::OnStartChecksComplete(
    NavigationThrottle::ThrottleCheckResult result) {
  // Helium: throttles are done; the URL loader is about to be created.
  LOG(WARNING) << "Helium nav: checks-complete url="
               << GetURL().possibly_invalid_spec()
               << " action=" << static_cast<int>(result.action());
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
  // Helium: the renderer committed a document, so a frame did reach the screen.
  LOG(WARNING) << "Helium nav: commit url=" << GetURL().possibly_invalid_spec();
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
  // Helium: record why the navigation died and at which net error.
  LOG(WARNING) << "Helium nav: failed url=" << GetURL().possibly_invalid_spec()
               << " net_error=" << status.error_code;
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


def patch_source_tree(src_dir):
    path = os.path.join(src_dir, NAVIGATION_REQUEST)
    changed = False
    for original, patched, label in (
        (BEGIN_ORIGINAL, BEGIN_PATCHED, "navigation begin logging"),
        (CHECKS_ORIGINAL, CHECKS_PATCHED, "navigation checks-complete logging"),
        (COMMIT_ORIGINAL, COMMIT_PATCHED, "navigation commit logging"),
        (FAIL_ORIGINAL, FAIL_PATCHED, "navigation failure logging"),
    ):
        if _replace_once(path, original, patched, label):
            changed = True
    return changed


def main():
    patch_source_tree(sys.argv[1] if len(sys.argv) > 1 else ".")


if __name__ == "__main__":
    main()
