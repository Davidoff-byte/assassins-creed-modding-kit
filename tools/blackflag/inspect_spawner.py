#!/usr/bin/env python3
"""Inspect the mission spawner + membership list header details."""
import sys, os, struct

sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
from anvil import read_container, walk_files

W = r"D:\ac4work\work"

c = read_container(os.path.join(W, "edward_pirate_body.bin"))
res = list(walk_files(c["files"]))

print("== all records (name, type, len) in SQ03M30 Edward body block:")
for (o, tid, rn, rh, rp) in res:
    print(f"   {tid:08X} {len(rp):7d}  {rn}")

print()
print("== DominoSpawner payload:")
for (o, tid, rn, rh, rp) in res:
    if "DominoSpawner" in rn:
        print(f"   {rn} type=0x{tid:08X} len={len(rp)}")
        print("   ", rp[:120].hex(" "))
        break

print()
print("== membership header of cell01364:")
c2 = read_container(os.path.join(W, "cell01364.bin"))
res2 = list(walk_files(c2["files"]))
o, tid, name, header, payload = res2[0]
print("   payload len:", len(payload))
print("   first 0x20:", payload[:0x20].hex(" "))
# find count near start: try u16/u32 values
for off in range(0, 0x20):
    u16 = struct.unpack_from("<H", payload, off)[0]
    u32 = struct.unpack_from("<I", payload, off)[0]
    if u16 == 476 or u32 == 476:
        print(f"   count 476 found at +0x{off:X} as {'u16' if u16==476 else 'u32'}")
# entries actually counted
start = 0x11
n = 0
while start + 10 <= len(payload):
    marker = struct.unpack_from("<H", payload, start)[0]
    block = struct.unpack_from("<I", payload, start + 6)[0]
    if marker != 1 or block > 0x3F:
        break
    n += 1
    start += 10
print("   entries:", n, "list ends at +0x%X, payload=0x%X" % (start, len(payload)))
print("   tail:", payload[start:start + 32].hex(" "))
