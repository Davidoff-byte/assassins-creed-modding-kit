#!/usr/bin/env python3
from pathlib import Path
from forge import Forge

G = r"D:\SteamLibrary\steamapps\common\Assassin's Creed Rogue"
patch = Forge(Path(G) / "DataPC_patch.forge")
print(f"patch forge entries={len(patch.entries)}")
for e in patch.entries:
    print(f"  {e['name']}")

cur = Forge(Path(G) / "DataPC.forge")
bs = [e for e in cur.entries if e["name"] == "Game Bootstrap Settings"][0]
blob = cur.data[bs["offset"]:bs["offset"] + bs["size"]]
print("\nBootstrap header:", blob[:64].hex(" "))
for needle in (b"FightSettings", b"CounterWindowSettings", b"GameBootstrap",
               b"ACC_W_P", b"FightStrategy"):
    print(f"  search {needle!r}: {blob.find(needle)}")
printable = sum(1 for c in blob[:2_000_000] if 32 <= c < 127)
print(f"  printable ASCII in first 2MB: {printable}")
