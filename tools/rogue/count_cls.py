#!/usr/bin/env python3
import struct
from pathlib import Path
EXE = Path(r"D:\SteamLibrary\steamapps\common\Assassin's Creed Rogue\ACC.exe")
IB=0x140000000
def secs(pe):
    e=struct.unpack_from("<I",pe,0x3C)[0];coff=e+4
    n=struct.unpack_from("<H",pe,coff+2)[0]
    o=coff+20+struct.unpack_from("<H",pe,coff+16)[0]
    out=[]
    for i in range(n):
        p=o+i*40;name=pe[p:p+8].rstrip(b"\0").decode("latin-1")
        vs,va,rs,ra=struct.unpack_from("<IIII",pe,p+8);out.append((name,va,vs,ra,rs))
    return out
pe=EXE.read_bytes();S=secs(pe)
def off2va(off):
    for n,v,vs,ra,rs in S:
        if ra<=off<ra+rs: return IB+v+(off-ra),n
    return None,None
base="48 8B 01 48 8D 88 30 02 00 00 48 39 88 70 0B 00 00 75 07 48 8D 88 D0 06 00 00 81 39"
tail="0F 94 C0 C3"
for tgt in (0x1F6,0x1F7,0x1F8,0x1F9):
    pat=bytes(int(b,16) for b in (base+" "+" ".join(f"{b:02X}" for b in struct.pack("<I",tgt))+" "+tail).split())
    hits=[];i=0
    while True:
        j=pe.find(pat,i)
        if j<0:break
        hits.append(j);i=j+1
    print(f"id 0x{tgt:X}: {len(hits)} hit(s)")
    for h in hits:
        va,sec=off2va(h)
        print(f"   off 0x{h:X} VA 0x{va:X} ({sec}) immAt=0x{va+0x1C:X}")
