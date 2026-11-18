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
    (
        "void NavigationRequest::ReadyToCommitNavigation(bool is_error)",
        'HeliumNavTrace("ready-to-commit", GetURL(), is_error);',
        "ready-to-commit",
    ),
    (
        "void NavigationRequest::OnCommitTimeout()",
        'HeliumNavTrace("commit-timeout", GetURL(), 0);',
        "commit-timeout",
    ),
    (
        "void NavigationRequest::OnResponseBodyReady(MojoResult)",
        'HeliumNavTrace("response-body-ready", GetURL(), 0);',
        "response-body-ready",
    ),
    (
        "void NavigationRequest::RunCommitDeferringConditions(\n"
        "    base::OnceClosure on_commit_deferring_conditions_complete_callback)",
        'HeliumNavTrace("conditions-start", GetURL(), 0);',
        "conditions-start",
    ),
)

COMMIT_RUNNER = "content/browser/renderer_host/commit_deferring_condition_runner.cc"
RENDER_FRAME_IMPL = "content/renderer/render_frame_impl.cc"
RENDER_FRAME_HOST_IMPL = "content/browser/renderer_host/render_frame_host_impl.cc"

RUNNER_INCLUDE_ANCHOR = '#include "base/memory/ptr_util.h"\n'
RUNNER_INCLUDE_PATCH = RUNNER_INCLUDE_ANCHOR + '#include "base/logging.h"\n'
RUNNER_EXTRA_INCLUDES = (
    '#include "base/containers/span.h"\n',
    '#include "base/files/file.h"\n',
    '#include "base/files/file_path.h"\n',
    '#include "base/path_service.h"\n',
    '#include "base/base_paths_android.h"\n',
    '#include "base/strings/stringprintf.h"\n',
)

RUNNER_TRACE_HELPER_ANCHOR = "void CommitDeferringConditionRunner::ProcessConditions() {\n"
RUNNER_TRACE_HELPER = '''void HeliumCommitConditionTrace(const char* phase,
                                const char* condition,
                                int result) {
  base::FilePath app_data;
  if (!base::PathService::Get(base::DIR_ANDROID_APP_DATA, &app_data)) {
    return;
  }
  std::string line = base::StringPrintf(
      "Helium commit: condition %s=%s result=%d\\n", phase, condition,
      result);
  base::File file(app_data.AppendASCII("helium-nav.log"),
                  base::File::FLAG_OPEN_ALWAYS | base::File::FLAG_WRITE |
                      base::File::FLAG_APPEND);
  if (file.IsValid()) {
    file.WriteAtCurrentPos(base::as_byte_span(line));
  }
}

'''

RUNNER_CONDITION_ANCHOR = (
    "    CommitDeferringCondition* condition = (*conditions_.begin()).get();\n"
)
RUNNER_CONDITION_PATCH = RUNNER_CONDITION_ANCHOR + (
    '    HeliumCommitConditionTrace("start", condition->TraceEventName(), -1);\n'
    '    LOG(WARNING) << "Helium commit: condition="\n'
    "                 << condition->TraceEventName();\n"
)

RUNNER_RESULT_ANCHOR = (
    "    if (!weak_self) {\n"
    "      // The runner was deleted, which indicates the navigation was cancelled.\n"
    "      CHECK_NE(result, CommitDeferringCondition::Result::kProceed);\n"
    "      return;\n"
    "    }\n"
    "    is_in_will_commit_navigation_ = false;\n"
)
RUNNER_RESULT_PATCH = RUNNER_RESULT_ANCHOR + (
    '    HeliumCommitConditionTrace("result", condition->TraceEventName(),\n'
    '                                static_cast<int>(result));\n'
    '    LOG(WARNING) << "Helium commit: condition result="\n'
    '                 << static_cast<int>(result) << " "\n'
    "                 << condition->TraceEventName();\n"
)

RENDERER_TRACE_INCLUDE_ANCHOR = '#include "base/files/file.h"\n'
RENDERER_TRACE_INCLUDE_PATCH = (
    RENDERER_TRACE_INCLUDE_ANCHOR
    + '#include "base/containers/span.h"\n'
    + '#include "base/files/file_path.h"\n'
)

RENDERER_TRACE_HELPER_ANCHOR = "const int kExtraCharsBeforeAndAfterSelection = 100;\n"
RENDERER_TRACE_HELPER_PATCH = RENDERER_TRACE_HELPER_ANCHOR + """

void HeliumRendererCommitTrace(const char* stage) {
  std::string line = std::string("Helium renderer commit: ") + stage + "\\n";
  base::File file(
      base::FilePath("/storage/emulated/0/Android/data/io.github.jqssun.helium/files/logs/helium-renderer-commit.log"),
      base::File::FLAG_OPEN_ALWAYS | base::File::FLAG_WRITE |
          base::File::FLAG_APPEND);
  if (file.IsValid()) {
    file.WriteAtCurrentPos(base::as_byte_span(line));
  }
}
"""

RENDER_COMMIT_ANCHOR = (
    "    mojom::NavigationClient::CommitNavigationCallback commit_callback) {\n"
)
RENDER_COMMIT_PATCH = (
    RENDER_COMMIT_ANCHOR + '  HeliumRendererCommitTrace("received");\n'
)
RENDER_PARAMS_ANCHOR = (
    "    std::unique_ptr<DocumentState> document_state,\n"
    "    std::unique_ptr<WebNavigationParams> navigation_params) {\n"
)
RENDER_PARAMS_PATCH = (
    RENDER_PARAMS_ANCHOR + '  HeliumRendererCommitTrace("params");\n'
)
RENDER_BLINK_ANCHOR = "  frame_->CommitNavigation(std::move(navigation_params),\n"
RENDER_BLINK_PATCH = (
    '  HeliumRendererCommitTrace("blink-before");\n' + RENDER_BLINK_ANCHOR
)
RENDER_BLINK_AFTER_ANCHOR = "                           std::move(document_state));\n"
RENDER_BLINK_AFTER_PATCH = (
    RENDER_BLINK_AFTER_ANCHOR + '  HeliumRendererCommitTrace("blink-after");\n'
)

BROWSER_MOJO_SEND_ANCHOR = (
    "    navigation_request->GetCommitNavigationClient()->CommitNavigation(\n"
)
BROWSER_MOJO_SEND_PATCH = (
    '    LOG(WARNING) << "Helium commit: Mojo send url="\n'
    '                 << navigation_request->GetURL().possibly_invalid_spec();\n'
    + BROWSER_MOJO_SEND_ANCHOR
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


def _replace_anchor(path, anchor, patched, marker, label):
    """Insert `patched` in place of `anchor` once, skipping already patched files."""
    if not os.path.isfile(path):
        return False
    content = _read(path)
    if marker in content:
        return False
    if anchor not in content:
        print(f"Warning: could not find {label} in {path}", file=sys.stderr)
        return False
    _write(path, content.replace(anchor, patched, 1))
    print(f"Patched {label}: {path}")
    return True


def patch_commit_stages(src_dir):
    """Report which commit deferring condition, or the commit send, stalls."""
    changed = False

    navigation = os.path.join(src_dir, NAVIGATION_REQUEST)
    if os.path.isfile(navigation):
        navigation_content = _read(navigation)
        legacy_send = '  HeliumNavTrace("commit-send", GetURL(), 0);\n'
        if legacy_send in navigation_content:
            _write(navigation, navigation_content.replace(legacy_send, "", 1))
            changed = True

    runner = os.path.join(src_dir, COMMIT_RUNNER)
    changed = (
        _replace_anchor(
            runner,
            RUNNER_INCLUDE_ANCHOR,
            RUNNER_INCLUDE_PATCH,
            '#include "base/logging.h"',
            "commit condition logging include",
        )
        or changed
    )
    if os.path.isfile(runner):
        runner_content = _read(runner)
        missing_includes = "".join(
            include
            for include in RUNNER_EXTRA_INCLUDES
            if include not in runner_content
        )
        if missing_includes:
            _write(
                runner,
                runner_content.replace(
                    RUNNER_INCLUDE_ANCHOR,
                    RUNNER_INCLUDE_ANCHOR + missing_includes,
                    1,
                ),
            )
            changed = True
    changed = (
        _replace_anchor(
            runner,
            RUNNER_TRACE_HELPER_ANCHOR,
            RUNNER_TRACE_HELPER + RUNNER_TRACE_HELPER_ANCHOR,
            "HeliumCommitConditionTrace",
            "commit condition file trace helper",
        )
        or changed
    )
    changed = (
        _replace_anchor(
            runner,
            RUNNER_CONDITION_ANCHOR,
            RUNNER_CONDITION_PATCH,
            "Helium commit: condition=",
            "commit deferring condition name",
        )
        or changed
    )
    changed = (
        _replace_anchor(
            runner,
            RUNNER_RESULT_ANCHOR,
            RUNNER_RESULT_PATCH,
            "Helium commit: condition result=",
            "commit deferring condition result",
        )
        or changed
    )

    renderer = os.path.join(src_dir, RENDER_FRAME_IMPL)
    if os.path.isfile(renderer):
        renderer_content = _read(renderer)
        new_trace_path = "/storage/emulated/0/Android/data/io.github.jqssun.helium/files/logs/helium-renderer-commit.log"
        old_trace_paths = (
            "/data/local/tmp/helium-renderer-commit.log",
            "/data/data/io.github.jqssun.helium/app_chrome/helium-renderer-commit.log",
        )
        upgraded = renderer_content
        for old_trace_path in old_trace_paths:
            upgraded = upgraded.replace(old_trace_path, new_trace_path)
        if upgraded != renderer_content:
            _write(renderer, upgraded)
            changed = True

    changed = (
        _replace_anchor(
            renderer,
            RENDERER_TRACE_INCLUDE_ANCHOR,
            RENDERER_TRACE_INCLUDE_PATCH,
            '#include "base/containers/span.h"',
            "renderer commit trace includes",
        )
        or changed
    )
    changed = (
        _replace_anchor(
            renderer,
            RENDERER_TRACE_HELPER_ANCHOR,
            RENDERER_TRACE_HELPER_PATCH,
            "HeliumRendererCommitTrace",
            "renderer commit trace helper",
        )
        or changed
    )
    changed = (
        _replace_anchor(
            renderer,
            RENDER_COMMIT_ANCHOR,
            RENDER_COMMIT_PATCH,
            'HeliumRendererCommitTrace("received")',
            "renderer commit receipt",
        )
        or changed
    )
    changed = (
        _replace_anchor(
            renderer,
            RENDER_PARAMS_ANCHOR,
            RENDER_PARAMS_PATCH,
            'HeliumRendererCommitTrace("params")',
            "renderer commit params",
        )
        or changed
    )
    changed = (
        _replace_anchor(
            renderer,
            RENDER_BLINK_ANCHOR,
            RENDER_BLINK_PATCH,
            'HeliumRendererCommitTrace("blink-before")',
            "renderer Blink commit entry",
        )
        or changed
    )
    changed = (
        _replace_anchor(
            renderer,
            RENDER_BLINK_AFTER_ANCHOR,
            RENDER_BLINK_AFTER_PATCH,
            'HeliumRendererCommitTrace("blink-after")',
            "renderer Blink commit return",
        )
        or changed
    )

    browser = os.path.join(src_dir, RENDER_FRAME_HOST_IMPL)
    if os.path.isfile(browser):
        browser_content = _read(browser)
        legacy_send = (
            '    HeliumNavTrace("commit-mojo-send", navigation_request->GetURL(), 0);\n'
        )
        if legacy_send in browser_content:
            _write(browser, browser_content.replace(legacy_send, "", 1))
            browser_content = _read(browser)
            changed = True
        if '#include "base/logging.h"' not in browser_content:
            include_anchor = '#include "base/feature_list.h"\n'
            if include_anchor in browser_content:
                _write(
                    browser,
                    browser_content.replace(
                        include_anchor,
                        include_anchor + '#include "base/logging.h"\n',
                        1,
                    ),
                )
                changed = True

    changed = (
        _replace_anchor(
            browser,
            BROWSER_MOJO_SEND_ANCHOR,
            BROWSER_MOJO_SEND_PATCH,
            'Helium commit: Mojo send url=',
            "browser Mojo commit send trace",
        )
        or changed
    )

    return changed


def patch_source_tree(src_dir):
    changed = patch_commit_stages(src_dir)

    nav_path = os.path.join(src_dir, NAVIGATION_REQUEST)
    if not os.path.isfile(nav_path):
        return changed

    content = _read(nav_path)
    original = content

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
