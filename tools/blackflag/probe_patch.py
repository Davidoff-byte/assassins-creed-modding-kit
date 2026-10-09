#!/usr/bin/env python3
"""Structural sample: patch forge entries + region forge name patterns."""
import sys, os, re
from collections import Counter

sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
from forge import Forge

G = r"D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag"

print("## DataPC_patch.forge")
f = Forge(os.path.join(G, "DataPC_patch.forge"))
print("entries:", len(f.entries))
for e in f.entries[:40]:
    print(f"   {e['size']:9d}  {e['name']!r}")

print()
print("## DataPC_Havana.forge — structure sample")
f = Forge(os.path.join(G, "DataPC_Havana.forge"))
print("entries:", len(f.entries))
print("first 25 names:")
for e in f.entries[:25]:
    print(f"   {e['size']:9d}  {e['name']!r}")
print("largest 20:")
for e in sorted(f.entries, key=lambda x: -x["size"])[:20]:
    print(f"   {e['size']:9d}  {e['name']!r}")

pref = Counter()
for e in f.entries:
    n = e["name"]
    m = re.match(r"^([A-Za-z0-9_]+?)_", n)
    pref[(m.group(1) if m else n[:18])] += 1
print("top name prefixes:")
for k, v in pref.most_common(30):
    print(f"   {v:5d}  {k}")
