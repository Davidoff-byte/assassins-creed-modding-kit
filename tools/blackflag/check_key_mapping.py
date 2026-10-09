#!/usr/bin/env python3
"""Check whether cell datablock keys correspond to record IDs or name hashes."""
import sys, os, struct, zlib

sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
from anvil import read_container, walk_files

W = r"D:\ac4work\work"
KEYS = r"D:\SteamLibrary\steamapps\common\Assassin's Creed IV Black Flag\plugins\AC.BlackFlag.PatchFix.keys.txt"

captured = set()
for line in open(KEYS, encoding="latin-1"):
    p = line.split()
    if p:
        try:
            captured.add(int(p[0], 16))
        except ValueError:
            pass

c = read_container(os.path.join(W, "cell01364.bin"))
res = list(walk_files(c["files"]))

# 1. parse the Cell01364_DataBlock key list
o, tid, name, header, payload = res[0]
cellblk = payload
entries = []
start = 0x11
i = 0
while start + 10 <= len(payload):
    marker = struct.unpack_from("<H", payload, start)[0]
    key = struct.unpack_from("<I", payload, start + 2)[0]
    block = struct.unpack_from("<I", payload, start + 6)[0]
    entries.append((marker, key, block))
    if marker != 1 or block > 0x1F:
        break
    start += 10
    i += 1
print("cell key entries parsed:", len(entries))
print("first 6:", [(hex(k), b) for (_, k, b) in entries[:6]])
print("captured-in-list:", sum(1 for (_, k, b) in entries if k in captured), "/", len(entries))

# 2. record IDs of Entity records in the container
ids = []
for (off, rtid, rname, rheader, rpayload) in res:
    if rtid == 0x0984415E and len(rpayload) >= 13:
        rid = struct.unpack_from("<Q", rpayload, 1)[0]
        ids.append((rname, rid))
print("entity records:", len(ids))
print("sample IDs:", [(n, hex(i)) for (n, i) in ids[:6]])

id_low = {i & 0xFFFFFFFF for (_, i) in ids}
id_high = {(i >> 32) & 0xFFFFFFFF for (_, i) in ids}
print("id low32 in captured:", len(id_low & captured))
print("id high32 in captured:", len(id_high & captured))

# 3. name CRC32 variants vs captured
def h32(s):
    return zlib.crc32(s.encode("latin-1")) & 0xFFFFFFFF

hits = 0
for (n, i) in ids:
    for v in [n, n.lower(), n.upper(), f"{n}.0984415E"]:
        if h32(v) in captured:
            hits += 1
            print("CRC32 hit:", n, "->", v, hex(h32(v)))
print("name crc32 hits:", hits)

# 4. do the cell keys match any record id (low or high)?
key_set = {k for (_, k, b) in entries}
print("cell keys ∩ id low32:", len(key_set & id_low))
print("cell keys ∩ id high32:", len(key_set & id_high))

# 5. block list distribution
from collections import Counter
print("block distribution:", Counter(b for (_, k, b) in entries).most_common())
