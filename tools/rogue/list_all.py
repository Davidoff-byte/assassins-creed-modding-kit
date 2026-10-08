#!/usr/bin/env python3
import sys
from pathlib import Path
from forge import Forge

G = Path(r"D:\SteamLibrary\steamapps\common\Assassin's Creed Rogue")
needle = sys.argv[1] if len(sys.argv) > 1 else "Bootstrap"
for forge in sorted(G.glob("*.forge")):
    try:
        f = Forge(forge)
    except Exception as e:
        print(f"!! {forge.name}: {e}")
        continue
    hits = [e for e in f.entries if needle.lower() in e["name"].lower()]
    if hits:
        print(f"\n== {forge.name} ({len(f.entries)} entries) ==")
        for e in hits:
            print(f"   idx={e['index']:5d} size={e['size']:9d} id=0x{e['fid']:016X} {e['name']!r}")
