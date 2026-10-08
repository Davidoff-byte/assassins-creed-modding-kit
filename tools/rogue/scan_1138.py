#!/usr/bin/env python3
"""Find code in .text that references disp32 0x1138 (the fight-manager counter window flag)."""
import struct
from pathlib import Path
EXE=Path(r"D:\SteamLibrary\steamapps\common\Assassin's Creed Rogue\ACC.exe")
IB=0x140000000
pe=EXE.read_bytes()
def secs(pe):
    e=struct.unpack_from("<I",pe,0x3C)[0];coff=e+4
    n=struct.unpack_from("<H",pe,coff+2)[0]
    o=coff+20+struct.unpack_from("<H",pe,coff+16)[0]
    out=[]
    for i in range(n):
        p=o+i*40;name=pe[p:p+8].rstrip(b"\0").decode("latin-1")
        vs,va,rs,ra=struct.unpack_from("<IIII",pe,p+8);out.append((name,va,vs,ra,rs))
    return out
S=secs(pe)
txt=[s for s in S if s[0]==".text"][0]
n,v,vs,ra,rs=txt
disp=struct.pack("<I",0x1138)
i=ra; hits=[]
while True:
    j=pe.find(disp,i,ra+rs)
    if j<0: break
    hits.append(j); i=j+1
print(f"disp32 0x1138 hits in .text: {len(hits)}")
for h in hits:
    va=IB+v+(h-ra)
    # show instruction context: a few bytes before, and following byte
    pre=pe[max(ra,h-4):h]
    post=pe[h+4:h+8]
    print(f"  VA 0x{va:X}  pre={' '.join(f'{b:02X}' for b in pre)}  [38 11 00 00]  post={' '.join(f'{b:02X}' for b in post)}")
