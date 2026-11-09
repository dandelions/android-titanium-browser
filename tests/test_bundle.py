import io
import json
import pathlib
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile


REPO = pathlib.Path(__file__).resolve().parents[1]
BUNDLE_SCRIPT = REPO / "extensions" / "bundle.py"
BUILD_TEMPLATE = REPO / "extensions" / "BUILD.gn"


def encode_varint(value):
    encoded = bytearray()
    while value >= 0x80:
        encoded.append((value & 0x7F) | 0x80)
        value >>= 7
    encoded.append(value)
    return bytes(encoded)


def make_crx(path, key_bytes, version):
    archive_data = io.BytesIO()
    with zipfile.ZipFile(archive_data, "w") as archive:
        archive.writestr("manifest.json", json.dumps({"version": version}))

    signed_data = b"\x0a\x10" + key_bytes
    header = encode_varint((10000 << 3) | 2) + encode_varint(len(signed_data)) + signed_data
    crx = b"Cr24\x03\x00\x00\x00" + struct.pack("<I", len(header)) + header
    path.write_bytes(crx + archive_data.getvalue())


def extension_id(key_bytes):
    return "".join(chr(97 + nibble) for byte in key_bytes for nibble in (byte >> 4, byte & 15))


class BundleAliasTest(unittest.TestCase):
    def run_bundle(self, output_dir, name, source_crx):
        subprocess.run(
            [sys.executable, str(BUNDLE_SCRIPT), str(output_dir), name, source_crx.as_uri()],
            check=True,
            capture_output=True,
            text=True,
        )

    def test_aliases_and_repeated_runs_keep_one_asset(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            output_dir = root / "dist"
            source_crx = root / "source.crx"
            key_bytes = bytes(range(16))
            make_crx(source_crx, key_bytes, "0.0.1")

            self.run_bundle(output_dir, "helium", source_crx)
            self.run_bundle(output_dir, "titanium", source_crx)
            self.run_bundle(output_dir, "titanium", source_crx)

            index = json.loads((output_dir / "bundled.json").read_text())
            self.assertEqual(
                index,
                {
                    extension_id(key_bytes): {
                        "external_crx": "titanium.crx",
                        "external_version": "0.0.1",
                    }
                },
            )
            build = (output_dir / "BUILD.gn").read_text()
            self.assertIn('"titanium.crx",', build)
            self.assertNotIn('"helium.crx",', build)
            self.assertIn('"extensions/titanium.crx",', build)
            self.assertNotIn('"extensions/helium.crx",', build)

    def test_new_version_replaces_existing_crx_for_same_name(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            output_dir = root / "dist"
            source_crx = root / "source.crx"
            first_key = bytes(range(16))
            second_key = bytes(range(1, 17))
            make_crx(source_crx, first_key, "0.0.1")
            self.run_bundle(output_dir, "titanium", source_crx)

            make_crx(source_crx, second_key, "0.0.2")
            self.run_bundle(output_dir, "titanium", source_crx)

            index = json.loads((output_dir / "bundled.json").read_text())
            self.assertEqual(
                index,
                {
                    extension_id(second_key): {
                        "external_crx": "titanium.crx",
                        "external_version": "0.0.2",
                    }
                },
            )
            build = (output_dir / "BUILD.gn").read_text()
            self.assertEqual(build.count('"titanium.crx",'), 1)
            self.assertEqual(build.count('"extensions/titanium.crx",'), 1)


if __name__ == "__main__":
    unittest.main()
