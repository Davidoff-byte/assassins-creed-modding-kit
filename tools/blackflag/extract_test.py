#!/usr/bin/env python3
"""Feasibility probe: extract Edward's default character blob from the AC4 forge and inspect it (read-only)."""
import sys, os

sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
from forge import Forge

G = r"D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag"
OUT = r"D:\ac4work\work\edw_default.bin"

f = Forge(os.path.join(G, "DataPC_extra_chr.forge"))
hits = [e for e in f.entries if e["name"] == "CHR_P_EdwardKenway_Default"]
print("hits:", len(hits))
if hits:
    e = hits[0]
    print("offset=0x%X size=%d type=%d" % (e["offset"], e["size"], e["type"]))
    blob = f.data[e["offset"]:e["offset"] + e["size"]]
    with open(OUT, "wb") as fp:
        fp.write(blob)
    print("wrote", OUT, len(blob), "bytes")
    print("first 48 bytes:", blob[:48].hex(" "))
    # known magics
    print("container magic 1004FA9957FBAA33?", blob[:8].hex() == "33aa7b5799fa0410")
    # dump printable strings in the blob head/tail
    head = bytes(b for b in blob[:64] if 32 <= b < 127)
    print("head ascii:", head)
else:
    print("entry not found")
