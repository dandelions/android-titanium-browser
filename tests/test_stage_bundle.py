import importlib.util
import io
import json
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


STAGE = load("stage_bundle", ROOT / "extensions/stage_bundle.py")
VISIBILITY = load("visibility", ROOT / "patch_titanium_visibility.py")
NEW_ID = "a" * 32
OLD_ID = "b" * 32
OTHER_ID = "c" * 32


def gn(names):
    sources = "".join(f'    "{name}",\n' for name in ["bundled.json"] + names)
    destinations = "".join(f'    "extensions/{name}",\n' for name in ["bundled.json"] + names)
    return ('android_assets("extension_assets") {\n  renaming_sources = [\n' + sources
            + '  ]\n  renaming_destinations = [\n' + destinations + '  ]\n}\n')


def make_crx(extension_id, version):
    raw_id = bytes((ord(extension_id[i]) - 97) * 16 + ord(extension_id[i + 1]) - 97
                   for i in range(0, 32, 2))
    header = b"\x82\xf1\x04\x12\x0a\x10" + raw_id
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("manifest.json", json.dumps({"version": version}))
    return b"Cr24" + struct.pack("<II", 3, len(header)) + header + archive.getvalue()


def entry(name, version="1.0"):
    return {"external_crx": name, "external_version": version}


class StageBundleTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundle = self.root / "bundle"
        self.bundle.mkdir()
        self.source = self.root / "src"
        self.source.mkdir()
        self.dest = self.source / "helium/dist"
        self.include = self.root / "stage.inc"
        self.include.write_text("current helper")
        self.make_bundle()

    def make_bundle(self, extra=False):
        index = {NEW_ID: entry("titanium.crx", "2.0")}
        names = ["titanium.crx"]
        if extra:
            index[OTHER_ID] = entry("other.crx")
            names.append("other.crx")
            (self.bundle / "other.crx").write_bytes(b"other")
        (self.bundle / "bundled.json").write_text(json.dumps(index))
        (self.bundle / "BUILD.gn").write_text(gn(names))
        (self.bundle / "titanium.crx").write_bytes(make_crx(NEW_ID, "2.0"))

    def stage(self):
        return STAGE.stage_bundle(self.bundle, self.source, self.include)

    def test_missing_source_stages_bundle_and_is_idempotent(self):
        self.assertTrue(self.stage())
        self.assertEqual(VISIBILITY.bundled_titanium_id(self.source), NEW_ID)
        for name in ("bundled.json", "BUILD.gn", "titanium.crx"):
            self.assertEqual((self.dest / name).read_bytes(), (self.bundle / name).read_bytes())
        self.assertEqual((self.dest / "stage_bundled_extensions.inc").read_text(), "current helper")
        self.assertFalse(self.stage())

    def test_stale_titanium_is_replaced_unrelated_files_are_preserved(self):
        self.dest.mkdir(parents=True)
        (self.dest / "bundled.json").write_text(json.dumps({OLD_ID: entry("titanium.crx")}))
        (self.dest / "BUILD.gn").write_text(gn(["titanium.crx"]))
        (self.dest / "titanium.crx").write_bytes(b"old titanium")
        (self.dest / "user.crx").write_bytes(b"untouched")
        self.assertTrue(self.stage())
        self.assertEqual(VISIBILITY.bundled_titanium_id(self.source), NEW_ID)
        self.assertEqual((self.dest / "titanium.crx").read_bytes(), (self.bundle / "titanium.crx").read_bytes())
        self.assertEqual((self.dest / "user.crx").read_bytes(), b"untouched")
        self.assertFalse(self.stage())

    def test_missing_or_invalid_repo_bundle_fails_without_changing_source(self):
        self.dest.mkdir(parents=True)
        marker = self.dest / "titanium.crx"
        marker.write_bytes(b"old")
        (self.bundle / "bundled.json").write_text("{}")
        with self.assertRaises(RuntimeError):
            self.stage()
        self.assertEqual(marker.read_bytes(), b"old")
        self.make_bundle()
        (self.bundle / "titanium.crx").write_bytes(b"")
        with self.assertRaises(RuntimeError):
            self.stage()
        self.assertEqual(marker.read_bytes(), b"old")

    def test_mismatched_crx_identity_and_version_fail_without_writes(self):
        for crx in (make_crx(OLD_ID, "2.0"), make_crx(NEW_ID, "1.0"), b"bad"):
            with self.subTest(crx=crx[:12]):
                (self.bundle / "titanium.crx").write_bytes(crx)
                with self.assertRaises(RuntimeError):
                    self.stage()
                self.assertFalse(self.dest.exists())

    def test_conflicting_unrelated_index_or_asset_is_not_overwritten(self):
        self.dest.mkdir(parents=True)
        old = {OLD_ID: entry("titanium.crx"), OTHER_ID: entry("other.crx")}
        (self.dest / "bundled.json").write_text(json.dumps(old))
        (self.dest / "BUILD.gn").write_text(gn(["titanium.crx", "other.crx"]))
        (self.dest / "other.crx").write_bytes(b"user data")
        with self.assertRaises(RuntimeError):
            self.stage()
        self.assertEqual(json.loads((self.dest / "bundled.json").read_text()), old)
        self.make_bundle(extra=True)
        with self.assertRaises(RuntimeError):
            self.stage()
        self.assertEqual((self.dest / "other.crx").read_bytes(), b"user data")
        self.assertEqual(json.loads((self.dest / "bundled.json").read_text()), old)

    def test_conflicting_gn_is_not_overwritten(self):
        self.dest.mkdir(parents=True)
        custom = gn(["titanium.crx"]) + "# custom asset configuration\n"
        (self.dest / "BUILD.gn").write_text(custom)
        with self.assertRaises(RuntimeError):
            self.stage()
        self.assertEqual((self.dest / "BUILD.gn").read_text(), custom)
        self.assertFalse((self.dest / "bundled.json").exists())

    def test_hotfix_stages_before_visibility_and_gn_patch(self):
        script = (ROOT / "hotfix_existing_src.sh").read_text()
        staging = script.index('extensions/stage_bundle.py')
        self.assertLess(staging, script.index('patch_titanium_visibility.py'))
        self.assertLess(staging, script.index('patch_android_asset_group.py'))


if __name__ == "__main__":
    unittest.main()
