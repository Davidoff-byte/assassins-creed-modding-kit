#!/usr/bin/env python3
"""Correlate captured mass-create world keys with data record names (hash check)."""
import sys, os, zlib

sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
from forge import Forge
from anvil import read_container, walk_files

KEYS = r"D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag\plugins\AC.BlackFlag.PatchFix.keys.txt"
G = r"D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag"
W = r"D:\ac4work\work"

kmap = {}
for line in open(KEYS, encoding="latin-1"):
    p = line.split()
    if len(p) >= 2:
        try:
            h = int(p[0], 16); b = int(p[1], 16)
        except ValueError:
            continue
        kmap.setdefault(h, set()).add(b)
print("unique key hashes:", len(kmap), "total key lines:", sum(len(v) for v in kmap.values()))


def names_from_container(path):
    c = read_container(path)
    for (o, tid, name, header, payload) in walk_files(c["files"]):
        yield name, tid


def names_from_forge(path):
    f = Forge(path)
    for e in f.entries:
        yield e["name"], e["type"]


names = []
for cn in ["cell01364.bin", "edward_pirate_body.bin", "edw_default.bin"]:
    p = os.path.join(W, cn)
    if os.path.exists(p):
        names.extend(names_from_container(p))

for fn in ["DataPC_Havana.forge", "DataPC_CaribbeanSea.forge", "DataPC.forge", "DataPC_extra.forge"]:
    p = os.path.join(G, fn)
    if os.path.exists(p):
        names.extend(names_from_forge(p))

print("candidate names:", len(names))


def h32(s):
    return zlib.crc32(s.encode("latin-1")) & 0xFFFFFFFF


matched = 0
shown = 0
seen = set()
for name, tid in names:
    if name in seen:
        continue
    seen.add(name)
    cands = [name, name.lower(), name.upper(), f"{name}.{tid:08X}", f"{name}.{tid}"]
    for v in cands:
        h = h32(v)
        if h in kmap:
            matched += 1
            if shown < 60:
                shown += 1
                print(f"MATCH {name!r} -> {v!r} hash=0x{h:08X} blocks={sorted(kmap[h])}")
            break
print("matched unique names:", matched)
