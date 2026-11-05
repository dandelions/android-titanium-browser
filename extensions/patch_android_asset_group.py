import pathlib
import re
import sys


path = pathlib.Path(sys.argv[1])
source = path.read_text()
target = '"//helium/dist:extension_assets",'
group_start = source.find('java_group("chrome_public_non_pak_assets")')
if group_start < 0:
    raise SystemExit(f"Android non-pak asset group not found in {path}")

deps_start = source.find("deps = [", group_start)
if deps_start < 0:
    raise SystemExit(f"Android non-pak asset deps list not found in {path}")

list_start = deps_start + len("deps = [") - 1
list_end = source.find("]", list_start + 1)
if list_end < 0:
    raise SystemExit(f"Android non-pak asset deps list is incomplete in {path}")
deps_body = source[list_start + 1:list_end]
if target in deps_body:
    raise SystemExit(0)

indent_match = re.search(r"\n([ \t]*)\S", deps_body)
indent = indent_match.group(1) if indent_match else "      "
source = source[:list_start + 1] + "\n" + indent + target + source[list_start + 1:]
path.write_text(source)
