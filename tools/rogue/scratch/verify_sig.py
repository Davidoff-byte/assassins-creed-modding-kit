import struct
from pathlib import Path
EXE=Path(r"D:\SteamLibrary\steamapps\common\Assassin's Creed Rogue\ACC.exe")
pe=EXE.read_bytes()
pat=bytes.fromhex("40 53 48 83 EC 20 48 8B 59 18 48 83 BB F0 00 00 00 00 75 0A 33 D2 48 8B CB E8 82 E4 FE FF 48 8B 9B F0 00 00 00 48 8B 4B 18 E8 92 4B FF FF")
hits=[];i=pe.find(pat)
while i!=-1: hits.append(i); i=pe.find(pat,i+1)
print("AI_PACING matches:", len(hits), [hex(h) for h in hits[:5]])
# also confirm siblings match their own unique tails
for name,tail in [("420","E8 02 E4 FE FF"),("4a0","E8 82 E3 FE FF")]:
    p=bytes.fromhex("40 53 48 83 EC 20 48 8B 59 18 48 83 BB F0 00 00 00 00 75 0A 33 D2 48 8B CB "+tail+" 48 8B 9B F0 00 00 00 48 8B 4B 18")
    c=pe.count(p); print(f"sibling {name} count:", c)
