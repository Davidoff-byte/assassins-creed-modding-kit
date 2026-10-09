#!/usr/bin/env python3
"""Find Tulum content and count cell containers across region forges."""
import sys, os

sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
from forge import Forge

G = r"D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag"

for fn in ["DataPC_CaribbeanSea.forge", "DataPC.forge", "DataPC_extra.forge"]:
    p = os.path.join(G, fn)
    if not os.path.exists(p):
        continue
    f = Forge(p)
    tulum = [e for e in f.entries if "tulum" in e["name"].lower() or e["name"].upper().startswith("TUL")]
    cells = [e for e in f.entries if e["name"].lower().startswith("cell")]
    print(f"## {fn}: entries={len(f.entries)} tulum_hits={len(tulum)} cell_hits={len(cells)}")
    for e in tulum[:15]:
        print(f"   TUL {e['size']:9d} {e['name']!r}")
    for e in cells[:15]:
        print(f"   CELL {e['size']:9d} {e['name']!r}")
