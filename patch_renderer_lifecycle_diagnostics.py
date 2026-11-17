#!/usr/bin/env python3
"""Trace renderer message-loop shutdown on old-android builds."""
import os
import sys

RENDERER_MAIN = "content/renderer/renderer_main.cc"
CHILD_THREAD = "content/child/child_thread_impl.cc"

ANCHORS = {
    RENDERER_MAIN: (
        (
            "int RendererMain(MainFunctionParams parameters) {",
            """int RendererMain(MainFunctionParams parameters) {
#if BUILDFLAG(IS_ANDROID)
  LOG(WARNING) << "Helium renderer lifecycle: main entered";
#endif""",
        ),
        (
            "    new RenderThreadImpl(run_loop.QuitClosure(),\n"
            "                         std::move(main_thread_scheduler));",
            """    new RenderThreadImpl(run_loop.QuitClosure(),
                         std::move(main_thread_scheduler));
#if BUILDFLAG(IS_ANDROID)
    LOG(WARNING) << "Helium renderer lifecycle: RenderThreadImpl ready";
#endif""",
        ),
        (
            "      run_loop.Run();",
            """      LOG(WARNING) << "Helium renderer lifecycle: message loop entered";
      run_loop.Run();
      LOG(WARNING) << "Helium renderer lifecycle: message loop exited";""",
        ),
    ),
    CHILD_THREAD: (
        (
            "void ChildThreadImpl::OnChannelError() {\n"
            "  on_channel_error_called_ = true;",
            """void ChildThreadImpl::OnChannelError() {
#if BUILDFLAG(IS_ANDROID)
  LOG(WARNING) << "Helium renderer lifecycle: child channel error pid="
               << base::Process::Current().Pid();
#endif
  on_channel_error_called_ = true;""",
        ),
    ),
}


def patch_source_tree(src_dir):
    changed = False
    for relative, pairs in ANCHORS.items():
        path = os.path.join(src_dir, relative)
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as handle:
            content = handle.read()
        original = content
        if relative == RENDERER_MAIN and '#include "base/logging.h"' not in content:
            anchor = '#include "base/feature_list.h"\n'
            if anchor in content:
                content = content.replace(
                    anchor, anchor + '#include "base/logging.h"\n', 1
                )
        for before, after in pairs:
            if after in content:
                continue
            if before not in content:
                print(f"Warning: could not find lifecycle anchor in {relative}", file=sys.stderr)
                continue
            content = content.replace(before, after, 1)
        if content != original:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(content)
            print(f"Patched renderer lifecycle diagnostics: {relative}")
            changed = True
    return changed


def main():
    patch_source_tree(sys.argv[1] if len(sys.argv) > 1 else ".")


if __name__ == "__main__":
    main()
