#!/usr/bin/env python3
"""Report where ContentMain stops in an old-android child process.

On the Android 9 target the sandboxed renderer child logs ``entering child
main`` and then ``child main returned`` within ~30 ms, and Android reaps it with
exit code 0. ``ChildProcessService`` only logs the return of ``runMain()``, so
the process type, the result of ``ContentMainRunner::Initialize`` and the
selected main function are all invisible, and an early bail-out inside
``content::RunContentProcess`` cannot be told apart from a renderer main that
returns on its own.

Log those three points, and the main function that
``RunOtherNamedProcessTypeMain`` selects, so the exit stage is attributable.
"""
import os
import sys

CONTENT_MAIN = "content/app/content_main.cc"
CONTENT_MAIN_RUNNER = "content/app/content_main_runner_impl.cc"

TRACE_MARK = "// Helium content main trace revision: 1"

ENTRY_ORIGINAL = """NO_STACK_PROTECTOR int RunContentProcess(
    ContentMainParams params,
    ContentMainRunner* content_main_runner) {
  base::FeatureList::FailOnFeatureAccessWithoutFeatureList();"""

ENTRY_PATCHED = """NO_STACK_PROTECTOR int RunContentProcess(
    ContentMainParams params,
    ContentMainRunner* content_main_runner) {
  base::FeatureList::FailOnFeatureAccessWithoutFeatureList();

  // Helium content main trace revision: 1
  // A child process that returns from ContentMain within a few milliseconds
  // leaves no trace of the stage that decided to exit.
#if BUILDFLAG(IS_ANDROID)
  const std::string helium_process_type =
      base::CommandLine::ForCurrentProcess()->GetSwitchValueASCII(
          switches::kProcessType);
  LOG(WARNING) << "Helium content main: type="
               << (helium_process_type.empty() ? "<browser>"
                                               : helium_process_type)
               << " subprocess=" << IsSubprocess();
#endif  // BUILDFLAG(IS_ANDROID)"""

INITIALIZE_ORIGINAL = """    exit_code = content_main_runner->Initialize(std::move(params));

    if (exit_code >= 0) {
      return exit_code;
    }"""

INITIALIZE_PATCHED = """    exit_code = content_main_runner->Initialize(std::move(params));

#if BUILDFLAG(IS_ANDROID)
    LOG(WARNING) << "Helium content main: initialize returned " << exit_code;
#endif  // BUILDFLAG(IS_ANDROID)

    if (exit_code >= 0) {
      return exit_code;
    }"""

RUN_ORIGINAL = """  if (IsSubprocess())
    CommonSubprocessInit();
  exit_code = content_main_runner->Run();"""

RUN_PATCHED = """  if (IsSubprocess())
    CommonSubprocessInit();
  exit_code = content_main_runner->Run();

#if BUILDFLAG(IS_ANDROID)
  LOG(WARNING) << "Helium content main: run returned " << exit_code;
#endif  // BUILDFLAG(IS_ANDROID)"""

RUNNER_ENTRY_ORIGINAL = """NO_STACK_PROTECTOR int RunOtherNamedProcessTypeMain(
    const std::string& process_type,
    MainFunctionParams main_function_params,
    ContentMainDelegate* delegate) {"""

RUNNER_ENTRY_PATCHED = """NO_STACK_PROTECTOR int RunOtherNamedProcessTypeMain(
    const std::string& process_type,
    MainFunctionParams main_function_params,
    ContentMainDelegate* delegate) {
  // Helium child main trace revision: 1
  LOG(WARNING) << "Helium child main: type=" << process_type;"""

RUNNER_MATCH_ORIGINAL = """  for (const MainFunction& main_function : kMainFunctions) {
    if (process_type == main_function.name) {
      auto exit_code =
          delegate->RunProcess(process_type, std::move(main_function_params));"""

RUNNER_MATCH_PATCHED = """  for (const MainFunction& main_function : kMainFunctions) {
    if (process_type == main_function.name) {
      // Helium child main trace revision: 1
      LOG(WARNING) << "Helium child main: matched " << main_function.name;
      auto exit_code =
          delegate->RunProcess(process_type, std::move(main_function_params));"""

RUNNER_FALLTHROUGH_ORIGINAL = """  // If it's a process we don't know about, the embedder should know.
  auto exit_code =
      delegate->RunProcess(process_type, std::move(main_function_params));"""

RUNNER_FALLTHROUGH_PATCHED = """  // If it's a process we don't know about, the embedder should know.
  // Helium child main trace revision: 1
  LOG(WARNING) << "Helium child main: no main function for type="
               << process_type;
  auto exit_code =
      delegate->RunProcess(process_type, std::move(main_function_params));"""


def _read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _write(path, content):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def _replace_once(path, original, patched):
    if not os.path.isfile(path):
        return False
    content = _read(path)
    if patched in content:
        return False
    if original not in content:
        print(f"Warning: could not find the anchor in {path}", file=sys.stderr)
        return False
    _write(path, content.replace(original, patched, 1))
    print(f"Patched {path}")
    return True


def patch_source_tree(src_dir):
    content_main = os.path.join(src_dir, CONTENT_MAIN)
    runner = os.path.join(src_dir, CONTENT_MAIN_RUNNER)
    if not os.path.isfile(content_main) or not os.path.isfile(runner):
        return False

    changed = False
    for original, patched in (
        (ENTRY_ORIGINAL, ENTRY_PATCHED),
        (INITIALIZE_ORIGINAL, INITIALIZE_PATCHED),
        (RUN_ORIGINAL, RUN_PATCHED),
    ):
        changed = _replace_once(content_main, original, patched) or changed

    for original, patched in (
        (RUNNER_ENTRY_ORIGINAL, RUNNER_ENTRY_PATCHED),
        (RUNNER_MATCH_ORIGINAL, RUNNER_MATCH_PATCHED),
        (RUNNER_FALLTHROUGH_ORIGINAL, RUNNER_FALLTHROUGH_PATCHED),
    ):
        changed = _replace_once(runner, original, patched) or changed

    return changed


def main():
    patch_source_tree(sys.argv[1] if len(sys.argv) > 1 else ".")


if __name__ == "__main__":
    main()
