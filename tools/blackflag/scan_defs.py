#!/usr/bin/env python3
"""Name-only scan of AC4 forges for definition-type records (fast: entry tables only)."""
import sys, os

sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
from forge import Forge

G = r"D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag"

needles = ["universe", "datalayer", "buildtable", "entity", "bhv", "spawn",
           "human", "cit_", "edward", "player", "ai_", "agent", "npc"]

files = ["DataPC.forge", "DataPC_extra.forge", "DataPC_extra_chr.forge",
         "DataPC_Havana.forge", "DataPC_CaribbeanSea.forge"]

for fn in files:
    p = os.path.join(G, fn)
    if not os.path.exists(p):
        print("##", fn, "(missing)"); continue
    try:
        f = Forge(p)
    except Exception as e:
        print("##", fn, "!!", e); continue
    print(f"## {fn}  ({len(f.entries)} entries)")
    for n in needles:
        hits = [e for e in f.entries if n in e["name"].lower()]
        if hits:
            print(f"   [{n}] {len(hits)}:")
            for e in hits[:8]:
                print(f"      {e['size']:9d}  {e['name']!r}")
