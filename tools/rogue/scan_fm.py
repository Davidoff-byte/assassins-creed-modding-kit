#!/usr/bin/env python3
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
def scan(off):
    disp=struct.pack("<I",off); i=ra; hits=[]
    while True:
        j=pe.find(disp,i,ra+rs)
        if j<0: break
        hits.append(j); i=j+1
    print(f"=== disp 0x{off:X} ({len(hits)} raw) ===")
    for h in hits:
        modrm=pe[h-1]; op=pe[h-2]; va=IB+v+(h-ra)
        # qword ops: 48 89 8X / 48 8B 8X / 48 C7 8X (mov qword [r+disp32], imm32 signext) etc.
        if op in (0x89,0x8B) and pe[h-3]==0x48 and (modrm&0xC0)==0x80:
            kind="mov qword" + (" [..], reg" if op==0x89 else " reg, [..]")
            print(f"  0x{va:X}: 48 {op:02X} {modrm:02X} {kind}")
        elif op==0xC7 and pe[h-3]==0x48 and (modrm&0xC0)==0x80:
            imm=struct.unpack_from("<i",pe,h+4)[0]
            print(f"  0x{va:X}: 48 C7 {modrm:02X} [..+{off:X}], {imm} (dword)")
        elif op==0x8D and pe[h-3]==0x48:
            print(f"  0x{va:X}: 48 8D {modrm:02X} lea (addr of +{off:X})")
    print()
scan(0x1128); scan(0x1130); scan(0x1120)
