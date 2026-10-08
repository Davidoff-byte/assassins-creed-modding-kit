#!/usr/bin/env python3
import struct, sys
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
def off2va(off):
    for n,v,vs,ra,rs in S:
        if ra<=off<ra+rs: return IB+v+(off-ra)
    return None
sigs={
"resolver_a":"40 53 48 83 EC 20 83 7A 34 03 48 8B D9 75 1F E8 6C DF 8E 00",
"resolver_b":"48 89 5C 24 10 48 89 6C 24 18 56 57 41 55 48 83 EC 20 48 8B 01 48 8B F2 48 8B F9 4C",
"counter_can":"40 53 48 83 EC 20 48 8B D9 E8 A2 A8 8F 00 48 05 20 11 00 00 80 78 18 00 74 40 48 8B",
"combat_resolve":"4C 8B DC 48 81 EC 88 00 00 00 48 8B 01 49 89 5B 10 49 89 6B F8 4C 8B 90 E8 01 00 00",
"fight_strategy":"48 89 5C 24 08 48 89 74 24 10 57 48 83 EC 20 48 8B D9 48 8B 89 18 02 00 00 48 8B FA",
}
for name,s in sigs.items():
    pat=bytes(int(b,16) for b in s.split())
    hits=[];i=0
    while True:
        j=pe.find(pat,i)
        if j<0:break
        hits.append(j);i=j+1
    print(f"{name}: {len(hits)} hit(s): " + ", ".join(f"0x{off2va(h):X}" for h in hits[:5]))
