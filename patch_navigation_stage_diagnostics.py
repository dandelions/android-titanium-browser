#!/usr/bin/env python3
"""Write every navigation stage to a file on old-android builds.

On the VMOS-based target no web page, ``file://`` document, or extension page
ever commits, while the native new tab page keeps painting. The renderer is
started, initialises Skia, then idles until Android reaps it, and the tab ends
up on the sad-tab page.

``logd`` on that device dies repeatedly, so an in-app ``logcat`` capture stops
producing output exactly when the failure happens. Log through both LOG and a
direct append to ``<app data>/helium-nav.log`` so the stages survive logd being
dead, and cover the response stage so a stall between "throttles passed" and
"renderer committed" is attributable to a specific step.

The device never produced that file, so the trace now reports the ``base::File``
error for every path it tries instead of failing silently.
"""
import os
import re
import sys

NAVIGATION_REQUEST = "content/browser/renderer_host/navigation_request.cc"

TRACE_MARK = "Helium nav trace revision: 5"
BEGIN_SIG = "void NavigationRequest::BeginNavigation() {"
LEGACY_TRACE_MARK = "Helium nav trace revision: 2"
LEGACY_HELPER_PATTERN = re.compile(
    r"// Helium: navigation stage trace that survives logd being unavailable\.\n"
    r"// Helium nav trace revision: [2-5]\n"
    r"void HeliumNavTrace\(.*?\n}\n\n",
    re.DOTALL,
)

# Stages that an earlier revision logged with a bare LOG statement next to the
# helper call, which doubled every line in logcat.
LEGACY_INLINE_PATTERN = re.compile(
    r"(?:[ \t]*// Helium: [^\n]*\n)?"
    r'[ \t]*LOG\(WARNING\) << "Helium nav: '
    r"(?:begin|checks-complete|commit|failed) url="
    r"[\s\S]*?;[ \t]*\n"
)

HELPER = '''// Helium: navigation stage trace that survives logd being unavailable.
// Helium nav trace revision: 5
void HeliumNavTrace(const char* stage, const GURL& url, int value) {
  std::string line = base::StringPrintf("Helium nav: %s url=%s value=%d\\n",
                                        stage,
                                        url.possibly_invalid_spec().c_str(),
                                        value);
  LOG(WARNING) << line;

  // The app data directory is the only location the browser process is
  // guaranteed to own, so try it first. The shared app-data volume is written
  // second because logd dies on this device and a file outlives it.
  std::vector<base::FilePath> candidates;
  base::FilePath app_data;
  if (base::PathService::Get(base::DIR_ANDROID_APP_DATA, &app_data)) {
    candidates.push_back(app_data.AppendASCII("helium-nav.log"));
  }
  candidates.push_back(base::FilePath(
      "/storage/emulated/0/Android/data/io.github.jqssun.helium/files/logs/"
      "helium-nav.log"));

  const size_t line_size = line.size();
  for (const base::FilePath& where : candidates) {
    base::File file(where, base::File::FLAG_OPEN_ALWAYS |
                               base::File::FLAG_WRITE |
                               base::File::FLAG_APPEND);
    if (!file.IsValid()) {
      LOG(WARNING) << "Helium nav: cannot open " << where.value()
                   << " error=" << base::File::ErrorToString(
                                     file.error_details());
      continue;
    }
    const std::optional<size_t> written =
        file.WriteAtCurrentPos(base::as_byte_span(line));
    if (written.has_value() && *written == line_size) {
      return;
    }
    LOG(WARNING) << "Helium nav: short write to " << where.value();
  }
}

'''

EXTRA_INCLUDES = (
    "base/files/file.h",
    "base/files/file_path.h",
    "base/path_service.h",
    "base/base_paths_android.h",
)

# (signature of the function, statement to insert, stage name)
STAGES = (
    (
        "void NavigationRequest::OnStartChecksComplete(\n"
        "    NavigationThrottle::ThrottleCheckResult result)",
        'HeliumNavTrace("checks-complete", GetURL(),'
        " static_cast<int>(result.action()));",
        "checks-complete",
    ),
    (
        "void NavigationRequest::OnResponseStarted(\n"
        "    network::mojom::URLLoaderClientEndpointsPtr url_loader_client_endpoints,\n"
        "    network::mojom::URLResponseHeadPtr response_head,\n"
        "    mojo::ScopedDataPipeConsumerHandle response_body,\n"
        "    GlobalRequestID request_id,\n"
        "    bool is_download,\n"
        "    net::NetworkAnonymizationKey network_anonymization_key,\n"
        "    SubresourceLoaderParams subresource_loader_params,\n"
        "    EarlyHints early_hints)",
        'HeliumNavTrace("response", GetURL(), 0);',
        "response",
    ),
    (
        "void NavigationRequest::DidCommitNavigation(\n"
        "    const mojom::DidCommitProvisionalLoadParams& params,\n"
        "    bool navigation_entry_committed,\n"
        "    bool did_replace_entry,\n"
        "    const GURL& previous_main_frame_url)",
        'HeliumNavTrace("commit", GetURL(), 0);',
        "commit",
    ),
    (
        "void NavigationRequest::OnRequestFailedInternal(\n"
        "    const network::URLLoaderCompletionStatus& status,\n"
        "    bool skip_throttles,\n"
        "    const std::optional<std::string>& error_page_content,\n"
        "    bool collapse_frame)",
        'HeliumNavTrace("failed", GetURL(), status.error_code);',
        "failed",
    ),
)


def _read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _write(path, content):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def _add_includes(content):
    extra = ""
    for header in EXTRA_INCLUDES:
        include = f'#include "{header}"\n'
        if include not in content:
            extra += include
    if not extra:
        return content
    anchor = '#include "base/containers/span.h"\n'
    if anchor in content:
        return content.replace(anchor, anchor + extra, 1)
    return extra + content


def _ensure_stage(content, signature, statement, stage):
    """Insert the trace statement after the function's opening brace."""
    if f'HeliumNavTrace("{stage}"' in content:
        return content, False
    marker = signature + " {\n"
    if marker not in content:
        print(
            f"Warning: could not find the {stage} signature in "
            f"{NAVIGATION_REQUEST}",
            file=sys.stderr,
        )
        return content, False
    return content.replace(marker, marker + "  " + statement + "\n", 1), True


def patch_source_tree(src_dir):
    nav_path = os.path.join(src_dir, NAVIGATION_REQUEST)
    if not os.path.isfile(nav_path):
        return False

    content = _read(nav_path)
    original = content
    changed = False

    if BEGIN_SIG in content:
        # Remove every previous helper before inserting exactly one revision 5,
        # and drop the bare LOG statements an earlier revision left behind so a
        # stage is reported once.
        cleaned = LEGACY_HELPER_PATTERN.sub("", content)
        cleaned = LEGACY_INLINE_PATTERN.sub("", cleaned)
        if TRACE_MARK not in cleaned:
            cleaned = _add_includes(cleaned)
            cleaned = cleaned.replace(BEGIN_SIG, HELPER + BEGIN_SIG, 1)
        content = cleaned
        changed = content != original

    content, inserted = _ensure_stage(
        content,
        "void NavigationRequest::BeginNavigation()",
        'HeliumNavTrace("begin", GetURL(), 0);',
        "begin",
    )
    changed = changed or inserted

    for signature, statement, stage in STAGES:
        content, inserted = _ensure_stage(content, signature, statement, stage)
        changed = changed or inserted

    if content != original:
        _write(nav_path, content)
        print(f"Patched navigation stage trace: {nav_path}")
        changed = True

    return changed


def main():
    patch_source_tree(sys.argv[1] if len(sys.argv) > 1 else ".")


if __name__ == "__main__":
    main()
