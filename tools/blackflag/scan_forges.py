#!/usr/bin/env python3
"""Scan AC4 Black Flag forges for character/entity-looking records (read-only)."""
import sys, os

sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
from forge import Forge

G = r"D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag"

targets = {
    "DataPC.forge": ["entity", "build", "fight", "weapon", "kenway"],
    "DataPC_extra_chr.forge": ["kenway", "edw", "player", "assassin"],
    "DataPC_Havana.forge": ["kenway", "entity", "spawn", "npc", "crowd", "guard", "char"],
    "DataPC_Kingston.forge": ["entity", "spawn", "npc", "crowd", "guard"],
}

for fn, needles in targets.items():
    p = os.path.join(G, fn)
    print("##", fn)
    if not os.path.exists(p):
        print("   missing"); continue
    try:
        f = Forge(p)
    except Exception as e:
        print("   !! parse failed:", e); continue
    print("   entries:", len(f.entries))
    for n in needles:
        hits = [e for e in f.entries if n in e["name"].lower()]
        print(f"   [{n}] {len(hits)} hits")
        for e in hits[:10]:
            print(f"      {e['size']:9d}  {e['name']!r}")
