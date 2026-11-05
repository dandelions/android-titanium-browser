import pathlib
import sys


path = pathlib.Path(sys.argv[1])
source = path.read_text()
case_start = source.find("case chrome::DIR_EXTERNAL_EXTENSIONS:")
if case_start < 0:
    raise SystemExit(f"External extensions path case not found in {path}")

case_end = source.find("break;", case_start)
if case_end < 0:
    raise SystemExit(f"External extensions path case is incomplete in {path}")
case_end += len("break;")
case = source[case_start:case_end]
module_path = "base::PathService::Get(base::DIR_MODULE, &cur)"
user_data_path = "base::PathService::Get(chrome::DIR_USER_DATA, &cur)"

if user_data_path in case:
    raise SystemExit(0)
if module_path not in case:
    raise SystemExit(f"External extensions path implementation is unsupported in {path}")

case = case.replace(module_path, user_data_path, 1)
path.write_text(source[:case_start] + case + source[case_end:])
