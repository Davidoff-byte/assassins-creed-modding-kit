#!/usr/bin/env python3
import sys
from pathlib import Path
from forge import Forge

CUR = Path(r"D:\SteamLibrary\steamapps\common\Assassin's Creed Rogue\DataPC.forge")
STK = Path(r"D:\SteamLibrary\steamapps\common\Assassin's Creed Rogue\Backups\DataPC.forge")
OUT = Path(r"C:\Users\Administrator\Documents\Default Project\blobs")
OUT.mkdir(exist_ok=True)

needles = ["ShayDefaultSword_Secondary", "ShayDefaultSword_Primary",
           "Game Bootstrap Settings", "LocalizationPackage_English"]

cur = Forge(CUR)
stk = Forge(STK)

for n in needles:
    print("=" * 70)
    for label, f in (("CUR", cur), ("STK", stk)):
        hits = [e for e in f.entries if e["name"] == n or (n in e["name"] and e["name"].endswith(n))]
        for e in hits:
            blob = f.data[e["offset"]:e["offset"] + e["size"]]
            fn = OUT / f"{label}_{e['name']}.data"
            fn.write_bytes(blob)
            print(f"{label:3} idx={e['index']:5d} off=0x{e['offset']:09X} size={e['size']:9d} "
                  f"id=0x{e['fid']:016X} {e['name']!r}")
            print(f"      head: {blob[:16].hex(' ')}")
