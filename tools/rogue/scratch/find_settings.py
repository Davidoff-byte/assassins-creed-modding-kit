import sys, os
sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
from forge import Forge

for fn in ["DataPC.forge", "DataPC_patch.forge"]:
    p = r"D:\SteamLibrary\steamapps\common\Assassin's Creed Rogue\\" + fn
    try:
        f = Forge(p)
    except Exception as ex:
        print(fn, "ERR", ex)
        continue
    hits = [e["name"] for e in f.entries if "Settings" in e["name"] or "Bootstrap" in e["name"]]
    print(f"{fn}: {len(f.entries)} entries; matches:")
    for h in hits:
        print("   ", h)
