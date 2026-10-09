#!/usr/bin/env python3
"""Inspect mission actives: the Edward actor record; search for character refs."""
import sys, os, struct, zlib

sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
from anvil import read_container, walk_files

W = r"D:\ac4work\work"
c = read_container(os.path.join(W, "edward_pirate_body.bin"))
res = list(walk_files(c["files"]))

def crc(s):
    return zlib.crc32(s.encode()) & 0xFFFFFFFF

names = [
    "CHR_P_EdwardKenway_Default",
    "CHR_P_EdwardKenway_Default_VisualMaster",
    "CHR_P_BaseEntity_Male",
    "CHR_U_Adewale",
]
hashes = {n: crc(n) for n in names}
print("crc32 hashes:", {n: hex(h) for n, h in hashes.items()})

# 1) dump the Edward actor record + EdwardBlackFlag record
for target in ["SQ03_M030_SC010_GEN_CIN_EdwardBlackFlag_01A", "EdwardBlackFlag"]:
    for (o, tid, rn, rh, rp) in res:
        if rn == target:
            print(f"== {rn} type=0x{tid:08X} len={len(rp)}")
            print("   head:", rp[:96].hex(" "))
            # strings
            import re
            for m in re.finditer(rb"[ -~]{4,}", rp):
                print("   str:", m.group().decode())
            # crc name refs
            for n, h in hashes.items():
                for fmt in [struct.pack("<I", h), struct.pack("<Q", h)]:
                    if rp.find(fmt) >= 0:
                        print(f"   ref {n} hash={hex(h)} (fmt={'u32' if len(fmt)==4 else 'u64'})")
            break

# 2) search all records for name-hash refs and Kenway strings
import re
print("== Kenway/Edward strings anywhere in records:")
for (o, tid, rn, rh, rp) in res:
    for m in re.finditer(rb"[ -~]{5,}", rp):
        s = m.group().decode()
        if "Kenway" in s or "Edward" in s:
            print(f"   {rn!r}: {s!r}")

print("== name-hash refs anywhere:")
for (o, tid, rn, rh, rp) in res:
    for n, h in hashes.items():
        for fmt, lbl in [(struct.pack("<I", h), "u32"), (struct.pack("<Q", h), "u64")]:
            idx = rp.find(fmt)
            if idx >= 0:
                print(f"   {rn!r} +0x{idx:X} ref {n} ({lbl})")
