import json
import os
import re
import shutil
import struct
import sys
import urllib.request
import zipfile


def varint(buf, i):
    value = shift = 0
    while True:
        byte = buf[i]
        i += 1
        value |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            return value, i


def update_crx_entries(build, marker, entries):
    head, rest = build.split(marker, 1)
    body, tail = rest.split("  ]", 1)
    lines = [line for line in body.splitlines() if line.strip()]
    lines = [
        line for line in lines
        if not re.fullmatch(r'\s*"[^"\n]*\.crx",\s*', line)
    ]
    lines.extend(f'    "{entry}",' for entry in entries)
    body = "\n" + "\n".join(lines) + "\n"
    return head + marker + body + "  ]" + tail


folder, name, url = sys.argv[1:]
os.makedirs(folder, exist_ok=True)
build_path = os.path.join(folder, "BUILD.gn")
index_path = os.path.join(folder, "bundled.json")
if not os.path.exists(build_path):
    shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), "BUILD.gn"), build_path)

crx = f"{name}.crx"
path = os.path.join(folder, crx)
urllib.request.urlretrieve(url, path)
data = open(path, "rb").read()
if data[:8] != b"Cr24\x03\x00\x00\x00" or len(data) < 12:
    raise ValueError(f"{crx} is not a CRX3 file")
header_size = struct.unpack("<I", data[8:12])[0]
header = data[12:12 + header_size]
if len(header) != header_size:
    raise ValueError(f"{crx} has a truncated CRX3 header")
i = 0
while i < len(header):
    key, i = varint(header, i)
    length, i = varint(header, i)
    if key >> 3 == 10000:
        break
    i += length
else:
    raise ValueError(f"{crx} is missing signed CRX3 data")

key_data = header[i + 2:i + 18]
if len(key_data) != 16:
    raise ValueError(f"{crx} has an invalid extension ID key")
ext_id = "".join(chr(97 + n) for b in key_data for n in (b >> 4, b & 15))
with zipfile.ZipFile(path) as archive:
    version = json.loads(archive.read("manifest.json"))["version"]
print(f"{crx}: {ext_id} {version}")

if os.path.exists(index_path):
    with open(index_path, encoding="utf-8") as source:
        index = json.load(source)
else:
    index = {}
if not isinstance(index, dict):
    raise ValueError(f"{index_path} must contain a JSON object")

# One extension ID can have only one bundled CRX; replace aliases and stale versions.
for existing_id, entry in list(index.items()):
    if not isinstance(entry, dict):
        continue
    if existing_id == ext_id or entry.get("external_crx") == crx:
        del index[existing_id]
index[ext_id] = {"external_crx": crx, "external_version": version}
with open(index_path, "w", encoding="utf-8") as output:
    json.dump(index, output, indent=2)
    output.write("\n")

asset_crxs = sorted({
    entry["external_crx"]
    for entry in index.values()
    if isinstance(entry, dict) and isinstance(entry.get("external_crx"), str)
})
with open(build_path, encoding="utf-8") as source:
    build = source.read()
build = update_crx_entries(build, "renaming_sources = [", asset_crxs)
build = update_crx_entries(
    build,
    "renaming_destinations = [",
    [f"extensions/{asset}" for asset in asset_crxs],
)
with open(build_path, "w", encoding="utf-8") as output:
    output.write(build)
