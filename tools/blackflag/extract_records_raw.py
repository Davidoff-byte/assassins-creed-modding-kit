#!/usr/bin/env python3
"""Extract Edward-related records as .raw (header+payload) so atkbf dump can decode them."""
import sys, os

sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
from anvil import read_container, walk_files

W = r"D:\ac4work\work"
OUT = r"D:\ac4work\work\recs"
os.makedirs(OUT, exist_ok=True)

TARGETS = [
    "EdwardBlackFlag",
    "SQ03_M030_SC010_GEN_CIN_EdwardBlackFlag_01A",
    "SQ03_M30_HornigoldOnJackdaw_DominoSpawner",
]

c = read_container(os.path.join(W, "edward_pirate_body.bin"))
for (o, tid, rn, rh, rp) in walk_files(c["files"]):
    if rn in TARGETS:
        safe = rn.replace("/", "_").replace("\\", "_")
        p = os.path.join(OUT, f"{o:06X}_{tid:08X}_{safe}.raw")
        with open(p, "wb") as f:
            f.write(rh + rp)
        print(f"wrote {p}  header={len(rh)} payload={len(rp)}")
