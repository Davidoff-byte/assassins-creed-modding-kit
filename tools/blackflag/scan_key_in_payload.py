#!/usr/bin/env python3
"""Search for captured world keys inside data container record payloads."""
import sys, os, struct

sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
from anvil import read_container, walk_files
from forge import Forge

KEYS = r"D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag\plugins\AC.BlackFlag.PatchFix.keys.txt"
G = r"D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag"
W = r"D:\ac4work\work"

keys = set()
for line in open(KEYS, encoding="latin-1"):
    p = line.split()
    if len(p) >= 1:
        try:
            keys.add(int(p[0], 16))
        except ValueError:
            pass
print("keys:", len(keys))
print("login keys sample:", [hex(k) for k in list(keys)[:8]])

# also grab one known specific key from the login trace
known = 0x187825BC


def scan_payload(name, payload, hits):
    n = len(payload)
    for off in range(0, n - 3, 1):
        v = struct.unpack_from("<I", payload, off)[0]
        if v in keys:
            hits.append((name, off, v))
            if len(hits) >= 40:
                return


def scan_container(path, label):
    hits = []
    c = read_container(path)
    res = list(walk_files(c["files"]))
    for (o, tid, name, header, payload) in res:
        scan_payload(name, payload, hits)
        if len(hits) >= 40:
            break
    print(f"## {label}: records={len(res)} hits={len(hits)}")
    for (name, off, v) in hits[:25]:
        print(f"   {name!r} +0x{off:X} key=0x{v:08X}")


scan_container(os.path.join(W, "cell01364.bin"), "cell01364 (Havana)")
scan_container(os.path.join(W, "edward_pirate_body.bin"), "edward_pirate_body")
