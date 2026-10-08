#!/usr/bin/env python3
"""In-place forge blob replacement (equal-or-smaller blobs only; no relocation).

Usage:
  python forge_patch.py <forge> <out> <target_name> <source_forge> <source_name>
"""
import shutil
import struct
import sys
from pathlib import Path
from forge import Forge


def patch_inplace(forge_path, out_path, target_name, src_forge_path, src_name):
    f = Forge(forge_path)
    tgt = [e for e in f.entries if e["name"] == target_name]
    assert len(tgt) == 1, f"target {target_name!r} -> {len(tgt)} entries"
    tgt = tgt[0]
    src = Forge(src_forge_path)
    sl = [e for e in src.entries if e["name"] == src_name]
    assert len(sl) == 1, f"source {src_name!r} -> {len(sl)} entries"
    sl = sl[0]
    new_blob = src.data[sl["offset"]:sl["offset"] + sl["size"]]
    assert len(new_blob) <= tgt["size"], \
        f"new blob {len(new_blob)} > target {tgt['size']} (relocation needed)"
    buf = bytearray(f.data)
    buf[tgt["offset"]:tgt["offset"] + len(new_blob)] = new_blob
    # update declared sizes (descriptor record + name record)
    struct.pack_into("<i", buf, tgt["desc_off"] + 16, len(new_blob))
    struct.pack_into("<i", buf, tgt["name_rec_off"], len(new_blob))
    Path(out_path).write_bytes(bytes(buf))
    # verify
    g = Forge(out_path)
    e = [x for x in g.entries if x["name"] == target_name][0]
    got = g.data[e["offset"]:e["offset"] + e["size"]]
    assert got == new_blob, "round-trip mismatch!"
    print(f"OK: {target_name}: {tgt['size']} -> {len(new_blob)} bytes; "
          f"verified round-trip; wrote {out_path}")


if __name__ == "__main__":
    patch_inplace(*sys.argv[1:6])
