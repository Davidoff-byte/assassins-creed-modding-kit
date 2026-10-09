#!/usr/bin/env python3
"""Dump raw bytes of the Edward-related records for structure analysis."""
import sys, os, struct

sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
from anvil import read_container, walk_files

W = r"D:\ac4work\work"
c = read_container(os.path.join(W, "edward_pirate_body.bin"))
res = list(walk_files(c["files"]))
print("total records:", len(res))

targets = [
    "EdwardBlackFlag",
    "SQ03_M030_SC010_GEN_CIN_EdwardBlackFlag_01A",
    "SQ03_M30_HornigoldOnJackdaw_DominoSpawner",
]

recs = {}
for (o, tid, rn, rh, rp) in res:
    if rn in targets:
        recs[rn] = (o, tid, rh, rp)


def hexdump(b, base=0, width=16):
    for i in range(0, len(b), width):
        chunk = b[i:i + width]
        hx = " ".join(f"{x:02x}" for x in chunk)
        asc = "".join(chr(x) if 32 <= x < 127 else "." for x in chunk)
        print(f"  {base+i:04X}: {hx:<{width*3}} {asc}")


for t in targets:
    if t not in recs:
        print("MISSING", t); continue
    o, tid, rh, rp = recs[t]
    print(f"\n===== {t} =====")
    print(f"  rec_off=0x{o:X} type=0x{tid:X} headerlen={len(rh)} payloadlen={len(rp)}")
    print("  header:", rh.hex(" "))
    if len(rp) <= 1600:
        hexdump(rp, 0)
    else:
        hexdump(rp[:1600], 0)
        print(f"  ... ({len(rp)-1600} more bytes)")
    # printable strings
    import re
    for m in re.finditer(rb"[ -~]{4,}", rp):
        print(f"  str@0x{m.start():X}: {m.group().decode(errors='replace')!r}")
