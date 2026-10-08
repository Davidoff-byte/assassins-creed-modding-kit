#!/usr/bin/env python3
"""Grow a forge by appending a new blob and repointing one entry at it.

Keeps every other blob in place (no relocation); the game reads entries by
offset/size, so appended data is valid as long as the forge has no total-size
field (it doesn't: header = magic/version/headerSize/constants/table offsets).
"""
import struct
import sys
from pathlib import Path
from forge import Forge


def append_swap(forge_path, out_path, target_name, new_blob):
    f = Forge(forge_path)
    hits = [e for e in f.entries if e["name"] == target_name]
    assert len(hits) == 1, f"{target_name}: {len(hits)} entries"
    e = hits[0]
    buf = bytearray(f.data)
    off = (len(buf) + 0x7FFF) & ~0x7FFF
    buf += b"\x00" * (off - len(buf))
    buf += new_blob
    struct.pack_into("<q", buf, e["desc_off"], off)
    struct.pack_into("<i", buf, e["desc_off"] + 16, len(new_blob))
    struct.pack_into("<i", buf, e["name_rec_off"], len(new_blob))
    Path(out_path).write_bytes(bytes(buf))
    # verify
    g = Forge(out_path)
    ee = [x for x in g.entries if x["name"] == target_name][0]
    got = g.data[ee["offset"]:ee["offset"] + ee["size"]]
    assert got == new_blob, "round-trip mismatch"
    print(f"OK {target_name}: {e['size']} -> {len(new_blob)} bytes at 0x{off:X}; "
          f"forge {len(f.data)} -> {len(buf)}")


if __name__ == "__main__":
    forge_path, out_path, target = sys.argv[1], sys.argv[2], sys.argv[3]
    src_forge, src_name = sys.argv[4], sys.argv[5]
    sf = Forge(src_forge)
    se = [x for x in sf.entries if x["name"] == src_name][0]
    blob = sf.data[se["offset"]:se["offset"] + se["size"]]
    append_swap(forge_path, out_path, target, blob)
