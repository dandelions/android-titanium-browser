import pathlib
import re
import sys


def patch(path):
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
    if target not in deps_body:
        indent_match = re.search(r"\n([ \t]*)\S", deps_body)
        indent = indent_match.group(1) if indent_match else "      "
        source = source[:list_start + 1] + "\n" + indent + target + source[list_start + 1:]
        path.write_text(source)
        print(f"Added Titanium Android asset target to {path}")
    else:
        print(f"Titanium Android asset target already present in {path}")

    updated = path.read_text()
    updated_group_start = updated.find('java_group("chrome_public_non_pak_assets")')
    updated_deps_start = updated.find("deps = [", updated_group_start)
    updated_list_start = updated_deps_start + len("deps = [") - 1
    updated_list_end = updated.find("]", updated_list_start + 1)
    if target not in updated[updated_list_start + 1:updated_list_end]:
        raise SystemExit(f"Titanium Android asset target is missing from {path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} BUILD.gn")
    patch(pathlib.Path(sys.argv[1]))
