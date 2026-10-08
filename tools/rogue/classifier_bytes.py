#!/usr/bin/env python3
"""Dump hex bytes of the parry classifier functions and locate the cmp immediates."""
import struct
from pathlib import Path
EXE = Path(r"D:\SteamLibrary\steamapps\common\Assassin's Creed Rogue\ACC.exe")
IB = 0x140000000

def sections(pe):
    e = struct.unpack_from("<I", pe, 0x3C)[0]; coff=e+4
    n = struct.unpack_from("<H", pe, coff+2)[0]
    optsz = struct.unpack_from("<H", pe, coff+16)[0]; opt=coff+20
    o=opt+optsz; out=[]
    for i in range(n):
        p=o+i*40
        name=pe[p:p+8].rstrip(b"\0").decode("latin-1")
        vs,va,rs,ra=struct.unpack_from("<IIII",pe,p+8)
        out.append((name,va,vs,ra,rs))
    return out

pe = EXE.read_bytes(); S=sections(pe)
def va2off(va):
    for n,v,vs,ra,rs in S:
        if v <= va-IB < v+max(vs,rs):
            return ra+(va-IB-v)
    return None

funcs = {"FUN_142052de0":0x142052de0,"FUN_142052e10":0x142052e10,
         "FUN_142052e40":0x142052e40,"FUN_142052e70":0x142052e70}
for name,va in funcs.items():
    off = va2off(va)
    buf = pe[off:off+0x60]
    print(f"=== {name} @0x{va:X} ===")
    for row in range(0,len(buf),16):
        chunk=buf[row:row+16]
        print(f"  +0x{row:02X}: " + " ".join(f"{b:02X}" for b in chunk))
    # find imm32 values 0x1F6..0x1F9
    for tgt in (0x1F6,0x1F7,0x1F8,0x1F9):
        pat=struct.pack("<I",tgt)
        k=buf.find(pat)
        if k>=0:
            print(f"    imm 0x{tgt:X} at +0x{k:X}  (VA 0x{va+k:X})")
