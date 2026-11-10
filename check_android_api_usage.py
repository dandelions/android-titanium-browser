#!/usr/bin/env python3
"""列出 dex 中引用的、高于指定 API 级别的 Android 框架 API。

old-android 分支把 minSdk 降到 28，而 R8 的 API 建模会把所有高于 minSdk 的框架调用
变成运行时 NoSuchMethodError / NoClassDefFoundError（例如
EventForwarder 里的 MotionEvent.getRawX(I)F）。这个脚本用 SDK 自带的
platforms/<ver>/data/api-versions.xml 反查 dex 里每一个框架方法/字段引用，
把所有 API 级别高于阈值的引用列出来，便于在真机闪退之前提前修掉。

用法:
    python3 check_android_api_usage.py \
        --api-xml third_party/android_sdk/public/platforms/android-37.2/data/api-versions.xml \
        out/old-android/arm64/apks/*.dex
"""
import argparse
import struct
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict


class Dex:
    """最小 dex 解析器，只需要 string/type/proto/field/method id 表。"""

    def __init__(self, path):
        with open(path, "rb") as f:
            self.data = f.read()
        if self.data[:4] != b"dex\n":
            raise ValueError(f"not a dex file: {path}")
        (self.string_ids_size, self.string_ids_off,
         self.type_ids_size, self.type_ids_off,
         self.proto_ids_size, self.proto_ids_off,
         self.field_ids_size, self.field_ids_off,
         self.method_ids_size, self.method_ids_off) = struct.unpack_from(
            "<10I", self.data, 0x38)

    def _uleb128(self, off):
        result = 0
        shift = 0
        while True:
            byte = self.data[off]
            off += 1
            result |= (byte & 0x7F) << shift
            if not byte & 0x80:
                return result, off
            shift += 7

    def string(self, idx):
        off = struct.unpack_from("<I", self.data, self.string_ids_off + idx * 4)[0]
        _, off = self._uleb128(off)
        end = self.data.index(b"\x00", off)
        return self.data[off:end].decode("utf-8", errors="replace")

    def type_desc(self, idx):
        return self.string(struct.unpack_from(
            "<I", self.data, self.type_ids_off + idx * 4)[0])

    def proto_desc(self, idx):
        _shorty, ret_idx, params_off = struct.unpack_from(
            "<3I", self.data, self.proto_ids_off + idx * 12)
        params = ""
        if params_off:
            size = struct.unpack_from("<I", self.data, params_off)[0]
            for i in range(size):
                type_idx = struct.unpack_from(
                    "<H", self.data, params_off + 4 + i * 2)[0]
                params += self.type_desc(type_idx)
        return "(" + params + ")" + self.type_desc(ret_idx)

    @staticmethod
    def class_name(desc):
        """把 dex 描述符 Landroid/view/View; 转成 api-versions.xml 里的 android/view/View。"""
        if desc.startswith("L") and desc.endswith(";"):
            return desc[1:-1]
        return desc

    def methods(self):
        for i in range(self.method_ids_size):
            class_idx, proto_idx, name_idx = struct.unpack_from(
                "<HHI", self.data, self.method_ids_off + i * 8)
            yield (self.class_name(self.type_desc(class_idx)), self.string(name_idx),
                   self.proto_desc(proto_idx))

    def fields(self):
        for i in range(self.field_ids_size):
            class_idx, type_idx, name_idx = struct.unpack_from(
                "<HHI", self.data, self.field_ids_off + i * 8)
            yield (self.class_name(self.type_desc(class_idx)), self.string(name_idx),
                   self.type_desc(type_idx))


class ApiDatabase:
    """api-versions.xml 的查询封装，成员未标注 since 时继承其所属类的级别。"""

    @staticmethod
    def _level(value, default=1):
        # 扩展 SDK 的级别会写成 "37.0" 之类的浮点数。
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            return int(float(value))

    def __init__(self, path):
        self.classes = {}
        root = ET.parse(path).getroot()
        for cls in root.findall("class"):
            since = self._level(cls.get("since"))
            entry = {"since": since, "extends": None, "methods": {}, "fields": {}}
            ext = cls.find("extends")
            if ext is not None:
                entry["extends"] = ext.get("name")
            for method in cls.findall("method"):
                raw = method.get("name")
                if "(" in raw:
                    base, desc = raw.split("(", 1)
                    desc = "(" + desc
                else:
                    base, desc = raw, ""
                entry["methods"][(base, desc)] = self._level(method.get("since"), since)
            for field in cls.findall("field"):
                entry["fields"][(field.get("name"), field.get("type"))] = self._level(
                    field.get("since"), since)
            self.classes[cls.get("name")] = entry

    def _lookup(self, cls, key, table):
        cur = cls
        for _ in range(32):
            info = self.classes.get(cur)
            if info is None:
                return None
            found = info[table].get(key)
            if found is not None:
                return found
            cur = info["extends"]
        return None

    def method_since(self, cls, name, desc):
        return self._lookup(cls, (name, desc), "methods")

    def field_since(self, cls, name, ftype):
        return self._lookup(cls, (name, ftype), "fields")


def scan(api_xml, dex_paths, min_api=28):
    db = ApiDatabase(api_xml)
    methods = defaultdict(set)
    fields = defaultdict(set)
    for path in dex_paths:
        dex = Dex(path)
        for cls, name, desc in dex.methods():
            since = db.method_since(cls, name, desc)
            if since is not None and since > min_api:
                methods[(cls, name, desc)].add(since)
        for cls, name, ftype in dex.fields():
            since = db.field_since(cls, name, ftype)
            if since is not None and since > min_api:
                fields[(cls, name, ftype)].add(since)
    return methods, fields


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-xml", required=True)
    parser.add_argument("--min-api", type=int, default=28)
    parser.add_argument("--summary", action="store_true",
                        help="只输出按 API 级别统计的数量")
    parser.add_argument("dex", nargs="+")
    args = parser.parse_args()

    methods, fields = scan(args.api_xml, args.dex, args.min_api)

    if args.summary:
        by_level = defaultdict(int)
        for sinces in list(methods.values()) + list(fields.values()):
            by_level[min(sinces)] += 1
        print(f"methods above API {args.min_api}: {len(methods)}")
        print(f"fields above API {args.min_api}: {len(fields)}")
        for level in sorted(by_level):
            print(f"  since {level}: {by_level[level]}")
        return 0

    print(f"# methods above API {args.min_api}: {len(methods)}")
    for (cls, name, desc), sinces in sorted(methods.items()):
        print("M\t%d\t%s\t%s\t%s" % (min(sinces), cls, name, desc))
    print(f"# fields above API {args.min_api}: {len(fields)}")
    for (cls, name, ftype), sinces in sorted(fields.items()):
        print("F\t%d\t%s\t%s\t%s" % (min(sinces), cls, name, ftype))
    return 0


if __name__ == "__main__":
    sys.exit(main())
