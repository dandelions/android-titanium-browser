import json
import os
import re
import shutil
import struct
import sys
import time
import urllib.error
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


def parse_crx3(path, crx_label=None):
    crx = crx_label or os.path.basename(path)
    with open(path, "rb") as handle:
        data = handle.read()
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
    return ext_id, version


def download_crx_with_fallback(url, path, crx, attempts=3, timeout=20, retry_delay=1.0):
    tmp_path = f"{path}.tmp"
    last_error = None
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "android-helium-browser-build"},
    )
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                with open(tmp_path, "wb") as output:
                    shutil.copyfileobj(response, output)
            ext_id, version = parse_crx3(tmp_path, crx)
            os.replace(tmp_path, path)
            return ext_id, version
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, zipfile.BadZipFile, KeyError) as exc:
            last_error = exc
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            if attempt < attempts:
                time.sleep(retry_delay)

    if os.path.isfile(path):
        try:
            ext_id, version = parse_crx3(path, crx)
            print(
                f"[bundle] Download failed ({last_error}); reusing cached valid {crx}",
                file=sys.stderr,
            )
            return ext_id, version
        except (OSError, ValueError, zipfile.BadZipFile, KeyError):
            pass

    raise last_error


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    folder, name, url = args
    os.makedirs(folder, exist_ok=True)
    build_path = os.path.join(folder, "BUILD.gn")
    index_path = os.path.join(folder, "bundled.json")
    if not os.path.exists(build_path):
        shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), "BUILD.gn"), build_path)

    crx = f"{name}.crx"
    path = os.path.join(folder, crx)
    ext_id, version = download_crx_with_fallback(url, path, crx)
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


if __name__ == "__main__":
    main()
