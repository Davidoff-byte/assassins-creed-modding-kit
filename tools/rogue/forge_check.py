#!/usr/bin/env python3
from pathlib import Path
from forge import Forge

G = r"D:\SteamLibrary\steamapps\common\Assassin's Creed Rogue"
f = Forge(Path(G) / "DataPC.forge")
print(f"entries={len(f.entries)} file size={len(f.data):,}")
# monotonic offset check
prev = -1
mono = True
first_blob = None
last_end = 0
for e in f.entries:
    if first_blob is None and e["offset"]:
        first_blob = e["offset"]
    if e["offset"] < prev:
        mono = False
    prev = e["offset"]
    last_end = max(last_end, e["offset"] + e["size"])
print(f"blobs monotonic in entry order: {mono}")
print(f"first blob offset=0x{first_blob:X}  max end=0x{last_end:X} ({last_end:,})")
print("alignment samples:", [(e['index'], hex(e['offset'])) for e in f.entries[:3]],
      [(e['index'], hex(e['offset'])) for e in f.entries[-3:]])
print("\nLocalizationPackage entries:")
for e in f.entries:
    if "LocalizationPackage" in e["name"]:
        print(f"  idx={e['index']:5d} size={e['size']:9d} off=0x{e['offset']:09X} {e['name']}")
