#!/usr/bin/env python3
"""Extract the 'Game Bootstrap Settings' blob from the DataPC.forge copy -> D:\\ac4work\\work\\bootstrap.bin"""
import sys, os

sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
from forge import Forge
from anvil import read_container, walk_files

SRC = r"D:\ac4work\work\DataPC.forge"
OUT = r"D:\ac4work\work\bootstrap.bin"

f = Forge(SRC)
hits = [e for e in f.entries if e["name"] == "Game Bootstrap Settings"]
print("hits:", len(hits))
if not hits:
    sys.exit("not found")
e = hits[0]
print(f"offset=0x{e['offset']:X} size={e['size']} type={e['type']} id=0x{e['fid']:X}")
blob = f.data[e["offset"]:e["offset"] + e["size"]]
with open(OUT, "wb") as fp:
    fp.write(blob)
print(f"wrote {OUT} {len(blob)} bytes  head={blob[:16].hex(' ')}")

c = read_container(OUT)
res = list(walk_files(c["files"]))
print(f"container: filterTable={c['filter_table_size']} meta={len(c['meta'])}B files={len(c['files'])}B fileCount={c['file_count']} records={len(res)}")
print("first records:")
for (o, tid, rn, rh, rp) in res[:10]:
    print(f"   @0x{o:06X} type=0x{tid:08X} len={len(rp):7d} name={rn!r}")
