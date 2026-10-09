#!/usr/bin/env python3
"""Extract candidate data blobs from AC4 forges for structure analysis."""
import sys, os

sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
from forge import Forge

G = r"D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag"
W = r"D:\ac4work\work"
os.makedirs(W, exist_ok=True)

jobs = [
    ("DataPC_CaribbeanSea.forge", "DataBlock_SQ03M30_Edward_the_Pirate_Body", "edward_pirate_body.bin"),
    ("DataPC_Havana.forge", "Cell01364_DataBlock", "cell01364.bin"),
    ("DataPC_Havana.forge", "Human_NPC_GuardPost", "human_npc_guardpost.bin"),
    ("DataPC_Havana.forge", "HumanMissions_Specific_Behavior", "human_missions_behavior.bin"),
]

for forge_name, entry_name, out_name in jobs:
    p = os.path.join(G, forge_name)
    f = Forge(p)
    hits = [e for e in f.entries if e["name"] == entry_name]
    if not hits:
        print(f"MISS {entry_name} in {forge_name}")
        continue
    e = hits[0]
    blob = f.data[e["offset"]:e["offset"] + e["size"]]
    out = os.path.join(W, out_name)
    with open(out, "wb") as fp:
        fp.write(blob)
    print(f"OK  {out_name:32s} {len(blob):9d} bytes  type={e['type']}  head={blob[:24].hex(' ')}")
