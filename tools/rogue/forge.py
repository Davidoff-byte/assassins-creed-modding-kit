#!/usr/bin/env python3
"""Minimal AnvilNext 'scimitar' forge reader for AC Rogue (version 27).

Format per ATK (ForgeFile.Serialize27 / ForgeEntry) and the scimitar.bms script.
Reads the FileSet / entry tables and can extract raw file blobs (pre-decompression).
"""
import struct
import sys
from pathlib import Path


class Reader:
    def __init__(self, data: bytes):
        self.d = data
        self.p = 0

    def seek(self, p):
        self.p = p

    def u8(self):
        v = self.d[self.p]
        self.p += 1
        return v

    def i16(self):
        v = struct.unpack_from("<h", self.d, self.p)[0]
        self.p += 2
        return v

    def u16(self):
        v = struct.unpack_from("<H", self.d, self.p)[0]
        self.p += 2
        return v

    def i32(self):
        v = struct.unpack_from("<i", self.d, self.p)[0]
        self.p += 4
        return v

    def u32(self):
        v = struct.unpack_from("<I", self.d, self.p)[0]
        self.p += 4
        return v

    def i64(self):
        v = struct.unpack_from("<q", self.d, self.p)[0]
        self.p += 8
        return v

    def u64(self):
        v = struct.unpack_from("<Q", self.d, self.p)[0]
        self.p += 8
        return v

    def cstr(self, n):
        b = self.d[self.p:self.p + n]
        self.p += n
        return b.split(b"\x00", 1)[0].decode("latin1")


class Forge:
    def __init__(self, path):
        self.path = Path(path)
        self.data = self.path.read_bytes()
        self.entries = []
        self._parse()

    def _parse(self):
        r = Reader(self.data)
        magic = r.cstr(9)
        assert magic == "scimitar", f"bad magic {magic!r}"
        self.version = r.u32()
        self.header_size = r.i64()  # 0x41A
        r.seek(self.header_size)
        self.entries_count = r.i32()
        self.const2 = r.i32()
        r.seek(r.p + 12)
        self.h1 = r.i32()
        self.h2 = r.i32()
        self.h3 = r.i32()
        self.fileset_count = r.i32()
        self.first_fileset_offset = r.i64()
        import os
        if os.environ.get("FORGE_DEBUG"):
            print("hdr", hex(self.header_size), "entries", self.entries_count,
                  "const2", self.const2, "hints", self.h1, self.h2, self.h3,
                  "filesets", self.fileset_count, "first", hex(self.first_fileset_offset))
            for o in range(self.header_size, self.header_size + 0x30, 4):
                print(hex(o), hex(struct.unpack_from("<I", self.data, o)[0]))
        # FileSet chain
        off = self.first_fileset_offset
        idx = 0
        while off > 0:
            r.seek(off)
            files = r.i32()
            unk = r.i32()
            start = r.u64()
            nxt = r.i64()
            fmin = r.i32()
            fmax = r.i32()
            name_off = r.u64()
            data_off = r.u64()
            # offset-table records: 20 bytes each (int64 offset, uint64 id, int32 size)
            recs = []
            for _ in range(files):
                desc_off = r.p
                o = r.i64()
                fid = r.u64()
                sz = r.i32()
                recs.append((o, fid, sz, desc_off))
            # name/info records: 192 bytes each
            names = []
            r.seek(name_off)
            for i in range(files):
                rec0 = r.p
                size = r.i32()
                d29 = r.i32()
                d30a = r.i32()
                d30b = r.i32()
                d31 = r.u64()
                d32a = r.i32()
                d32b = r.i32()
                d33 = r.i32()
                d34 = r.i32()
                typ = r.i32()
                name = r.cstr(0x80)
                d37 = r.u64()
                d38 = r.u64()
                d39 = r.i32()
                assert r.p - rec0 == 0xC0, (r.p - rec0)
                names.append((size, typ, name, rec0))
            for i in range(files):
                o, fid, sz, desc_off = recs[i]
                size, typ, name, name_rec_off = names[i]
                self.entries.append({
                    "index": idx,
                    "fid": fid,
                    "offset": o,
                    "size": sz,
                    "rec_size": size,
                    "type": typ,
                    "name": name,
                    "desc_off": desc_off,
                    "name_rec_off": name_rec_off,
                })
                idx += 1
            if nxt <= 0:
                break
            off = nxt


def main():
    f = Forge(sys.argv[1])
    print(f"version={f.version} header=0x{f.header_size:X} entries={f.entries_count} "
          f"filesets={f.fileset_count} first_fs=0x{f.first_fileset_offset:X} parsed={len(f.entries)}")
    needle = sys.argv[2] if len(sys.argv) > 2 else None
    for e in f.entries:
        if needle is None or needle.lower() in e["name"].lower():
            print(f"  idx={e['index']:5d} off=0x{e['offset']:09X} size={e['size']:9d} "
                  f"rec_size={e['rec_size']:9d} type={e['type']} id=0x{e['fid']:016X} name={e['name']!r}")


if __name__ == "__main__":
    main()
