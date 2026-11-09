#!/usr/bin/env python3
"""Stage a validated repository extension bundle into an existing source tree."""

import json
import re
import shutil
import struct
import sys
import zipfile
from pathlib import Path


ID = re.compile(r"[a-p]{32}\Z")
TITANIUM = "titanium.crx"


def read_index(path: Path) -> dict:
    try:
        index = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RuntimeError(f"Cannot read extension bundle index {path}: {error}") from error
    if not isinstance(index, dict):
        raise RuntimeError(f"Invalid extension bundle index: {path}")
    names = set()
    for key, entry in index.items():
        name = entry.get("external_crx") if isinstance(entry, dict) else None
        version = entry.get("external_version") if isinstance(entry, dict) else None
        if (not ID.fullmatch(key) or not isinstance(name, str) or not name.endswith(".crx")
                or Path(name).name != name or "\\" in name or not isinstance(version, str)
                or not version or name in names):
            raise RuntimeError(f"Invalid extension bundle entry {key!r} in {path}")
        names.add(name)
    if sum(entry["external_crx"] == TITANIUM for entry in index.values()) != 1:
        raise RuntimeError(f"Expected exactly one Titanium extension in {path}")
    return index


def read_varint(data: bytes, offset: int):
    value = 0
    for shift in range(0, 70, 7):
        if offset >= len(data):
            break
        byte = data[offset]
        offset += 1
        value |= (byte & 127) << shift
        if byte < 128:
            return value, offset
    raise ValueError("invalid protobuf varint")


def validate_titanium(path: Path, expected_id: str, expected_version: str):
    try:
        with path.open("rb") as crx:
            prefix = crx.read(12)
            if len(prefix) != 12 or prefix[:4] != b"Cr24" or struct.unpack("<I", prefix[4:8])[0] != 3:
                raise ValueError("not a CRX3 file")
            header_size = struct.unpack("<I", prefix[8:12])[0]
            if header_size > 16 * 1024 * 1024:
                raise ValueError("CRX header too large")
            header = crx.read(header_size)
            if len(header) != header_size:
                raise ValueError("truncated CRX header")
        offset = 0
        signed_id = None
        while offset < len(header):
            tag, offset = read_varint(header, offset)
            if tag & 7 != 2:
                raise ValueError("unsupported CRX header field")
            length, offset = read_varint(header, offset)
            end = offset + length
            if end > len(header):
                raise ValueError("truncated CRX header field")
            if tag >> 3 == 10000:
                signed = header[offset:end]
                if len(signed) < 18 or signed[:2] != b"\x0a\x10" or signed_id is not None:
                    raise ValueError("invalid signed CRX ID")
                signed_id = "".join(chr(97 + n) for b in signed[2:18] for n in (b >> 4, b & 15))
            offset = end
        with zipfile.ZipFile(path) as archive:
            version = json.loads(archive.read("manifest.json"))["version"]
        if signed_id != expected_id or version != expected_version:
            raise ValueError("CRX ID or manifest version does not match bundled.json")
    except (OSError, KeyError, TypeError, ValueError, zipfile.BadZipFile) as error:
        raise RuntimeError(f"Invalid Titanium bundle {path}: {error}") from error


def without_titanium_assets(text: str) -> str:
    return re.sub(r'(?m)^[ \t]*"(?:extensions/)?titanium\.crx",[ \t]*\n', "", text)


def stage_bundle(bundle: Path, source_root: Path, include: Path) -> bool:
    index = read_index(bundle / "bundled.json")
    gn_path = bundle / "BUILD.gn"
    try:
        gn = gn_path.read_text(encoding="utf-8")
        include.read_bytes()
    except OSError as error:
        raise RuntimeError(f"Missing bundle build files: {error}") from error
    if 'android_assets("extension_assets")' not in gn:
        raise RuntimeError(f"Missing extension_assets target in {gn_path}")
    for name in ["bundled.json"] + [entry["external_crx"] for entry in index.values()]:
        if f'"{name}",' not in gn or f'"extensions/{name}",' not in gn:
            raise RuntimeError(f"Missing asset mapping for {name} in {gn_path}")
        if not (bundle / name).is_file() or (bundle / name).stat().st_size == 0:
            raise RuntimeError(f"Missing or empty bundle asset: {bundle / name}")

    titanium_id, titanium = next((key, entry) for key, entry in index.items()
                                  if entry["external_crx"] == TITANIUM)
    validate_titanium(bundle / TITANIUM, titanium_id, titanium["external_version"])

    destination = source_root / "helium/dist"
    existing_index = destination / "bundled.json"
    if existing_index.exists():
        old_index = read_index(existing_index)
        for key, entry in old_index.items():
            if entry["external_crx"] != TITANIUM and index.get(key) != entry:
                raise RuntimeError(f"Conflicting unrelated bundle entry {key} in {existing_index}")
    existing_gn = destination / "BUILD.gn"
    if existing_gn.exists():
        old_gn = existing_gn.read_text(encoding="utf-8")
        if without_titanium_assets(old_gn) != without_titanium_assets(gn):
            raise RuntimeError(f"Conflicting unrelated asset configuration in {existing_gn}")
    files = ["bundled.json", "BUILD.gn"] + [entry["external_crx"] for entry in index.values()]
    for name in files:
        target = destination / name
        if name not in ("bundled.json", "BUILD.gn", TITANIUM) and target.exists():
            if target.read_bytes() != (bundle / name).read_bytes():
                raise RuntimeError(f"Conflicting unrelated asset {target}")
    destination.mkdir(parents=True, exist_ok=True)
    changed = False
    for origin, target in [(bundle / name, destination / name) for name in files] + [
            (include, destination / "stage_bundled_extensions.inc")]:
        if not target.is_file() or origin.read_bytes() != target.read_bytes():
            shutil.copy2(origin, target)
            changed = True
    return changed


if __name__ == "__main__":
    try:
        if len(sys.argv) != 4:
            raise RuntimeError("usage: stage_bundle.py BUNDLE_DIR SOURCE_ROOT STAGE_INCLUDE")
        changed = stage_bundle(*(Path(arg) for arg in sys.argv[1:]))
    except (OSError, RuntimeError) as error:
        print(f"[stage_bundle] {error}", file=sys.stderr)
        raise SystemExit(1)
    print("[stage_bundle] " + ("staged" if changed else "already staged"))
