import pathlib
import subprocess
import sys
import tempfile
import unittest


REPO = pathlib.Path(__file__).resolve().parents[1]
PATCH_SCRIPT = REPO / "extensions" / "patch_external_extensions_path.py"


class ExternalExtensionsPathPatchTest(unittest.TestCase):
    def test_scopes_change_and_is_idempotent(self):
        source = """\
case chrome::DIR_OTHER:
  if (!base::PathService::Get(base::DIR_MODULE, &cur)) {
    return false;
  }
  break;
case chrome::DIR_EXTERNAL_EXTENSIONS:
  if (!base::PathService::Get(base::DIR_MODULE, &cur)) {
    return false;
  }
  cur = cur.Append(FILE_PATH_LITERAL("extensions"));
  break;
case chrome::DIR_AFTER:
  break;
"""
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / "chrome_paths.cc"
            path.write_text(source)

            subprocess.run([sys.executable, str(PATCH_SCRIPT), str(path)], check=True)
            first_result = path.read_text()
            subprocess.run([sys.executable, str(PATCH_SCRIPT), str(path)], check=True)

            self.assertEqual(path.read_text(), first_result)

        self.assertEqual(first_result.count("base::DIR_MODULE"), 1)
        self.assertEqual(first_result.count("chrome::DIR_USER_DATA"), 1)
        self.assertEqual(
            first_result,
            source.replace(
                "case chrome::DIR_EXTERNAL_EXTENSIONS:\n"
                "  if (!base::PathService::Get(base::DIR_MODULE, &cur)) {",
                "case chrome::DIR_EXTERNAL_EXTENSIONS:\n"
                "  if (!base::PathService::Get(chrome::DIR_USER_DATA, &cur)) {",
                1,
            ),
        )


if __name__ == "__main__":
    unittest.main()
