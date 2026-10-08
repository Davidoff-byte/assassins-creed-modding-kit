#!/usr/bin/env python3
"""Find real [reg+0x1138] byte accesses: mov/or/and/cmp, and show the immediate/value."""
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
S=secs(pe); n,v,vs,ra,rs=[s for s in S if s[0]==".text"][0]
disp=struct.pack("<I",0x1138)
i=ra; hits=[]
while True:
    j=pe.find(disp,i,ra+rs)
    if j<0: break
    hits.append(j); i=j+1
def is_modrm(b): return b in (0x80,0x81,0x82,0x83,0x86,0x87,0x88,0x89,0x8E,0x61,0x62,0x63,0xA0,0xB8,0xB9,0xBA,0xBB,0xBC,0xBD,0xBE,0xBF,0x87)
print("real [reg+0x1138] byte ops (modrm 8X):")
for h in hits:
    va=IB+v+(h-ra)
    modrm=pe[h-1]; op=pe[h-2]
    if (modrm & 0xC7)!=0x80:  # need mod=10 (disp32) reg=000 -> modrm 0x80-0x87
        continue
    if op in (0xC6,0xC7):   # mov byte/word [..], imm
        imm=pe[h+4]
        print(f"  0x{va:X}: {op:02X} {modrm:02X} [..+1138], {imm:02X}")
    elif op==0x80:          # group1 eb
        imm=pe[h+4]; sub=(modrm>>3)&7
        print(f"  0x{va:X}: 80 {modrm:02X} [..+1138], {imm:02X}  (grp1 sub={sub})")
    elif op==0xF6:          # test/not/neg/mul
        print(f"  0x{va:X}: F6 {modrm:02X} [..+1138]")
    elif op in (0x8A,0x86,0x88):
        print(f"  0x{va:X}: {op:02X} {modrm:02X} [..+1138] (mov r/m8,r8 / mov r8,r/m8)")
    else:
        print(f"  0x{va:X}: op={op:02X} modrm={modrm:02X} (?)")
