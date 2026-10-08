#!/usr/bin/env python3
"""Search ACC.exe for `mov dword ptr [reg+0x230], imm32` where imm is a small id.
Also search for any occurrence of `30 02 00 00 <imm32>` to catch the disp+imm pair."""
import struct, sys
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

pe = EXE.read_bytes(); S = sections(pe)
def off2va(off):
    for n,v,vs,ra,rs in S:
        if ra <= off < ra+rs:
            return IB+v+(off-ra), n
    return None,None

# scan for disp32 0x230 followed by an imm32 in a plausible id range
disp = struct.pack("<I", 0x230)
i = 0
found = 0
while True:
    j = pe.find(disp, i)
    if j < 0: break
    i = j + 1
    imm = struct.unpack_from("<i", pe, j+4)[0] if j+4+4 <= len(pe) else None
    if imm is None: continue
    if 0x1E0 <= imm <= 0x240 or imm in (0x1F4,0x1F5,0x1F6,0x1F7,0x1F8,0x1F9,0x1FA):
        va,sec = off2va(j)
        # show a few bytes before
        pre = pe[max(0,j-4):j+8]
        print(f"off 0x{j:X} VA 0x{va:X} ({sec}) pre={pre.hex(' ')} imm=0x{imm & 0xffffffff:X}")
        found += 1
print("total", found)
