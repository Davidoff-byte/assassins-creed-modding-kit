#!/usr/bin/env python3
"""Search world data for references to Edward's character resources."""
import sys, os, struct

sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
from anvil import read_container, walk_files

W = r"D:\ac4work\work"

REFS = {
    "CHR_P_EdwardKenway_Default.EntityBuilder": 0x2C0A3FCE0,
    "CHR_P_BaseEntity_Male.Entity": 0x1917A360,
    "CHR_P_EdwardKenway_Default_Body.BuildTable": 0x617CAB64F,
    "CHR_P_EdwardKenway_Default_Head.BuildTable": 0x64AA806FE,
}

targets = {
    "edward_pirate_body.bin": "SQ03 Edward body mission block",
    "cell01364.bin": "Havana cell 1364",
}

for fn, label in targets.items():
    path = os.path.join(W, fn)
    if not os.path.exists(path):
        print("missing", fn); continue
    c = read_container(path)
    res = list(walk_files(c["files"]))
    print(f"## {fn} ({label}) records={len(res)}")
    for (name, rid) in REFS.items():
        blob = struct.pack("<Q", rid)
        hits = []
        for (o, tid, rname, rheader, rpayload) in res:
            idx = rpayload.find(blob)
            if idx >= 0:
                hits.append((rname, idx))
        print(f"   {name} (0x{rid:X}): {len(hits)} hits")
        for (rname, idx) in hits[:6]:
            print(f"      {rname!r} +0x{idx:X}")
    # also try 4-byte low/any: search u32 low value
    for (name, rid) in [("EdwardBuilder low32", 0x2C0A3FCE0 & 0xFFFFFFFF), ("BaseEntity low32", 0x1917A360 & 0xFFFFFFFF)]:
        blob = struct.pack("<I", rid)
        hits = []
        for (o, tid, rname, rheader, rpayload) in res:
            idx = rpayload.find(blob)
            if idx >= 0:
                hits.append((rname, idx))
        print(f"   {name} (0x{rid:X} as u32): {len(hits)} hits")
