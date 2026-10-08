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
S=secs(pe)
def va2off(va):
    for n,v,vs,ra,rs in S:
        if v<=va-IB<v+max(vs,rs): return ra+(va-IB-v)
    return None
def reltarget(va_of_disp):  # disp32 is last 4 bytes of a rip-relative insn ending at va_of_disp+4
    d=struct.unpack_from("<i",pe,va2off(va_of_disp))[0]
    return IB + (va_of_disp-IB) + 4 + d  # va_of_disp is VA of disp start
# FUN_140346AA0: 0F B7 05 disp(VA+2) ; ... ; 48 8B 05 disp(VA+? )
for va in (0x140346AA0,0x140352C10):
    off=va2off(va); b=pe[off:off+40]
    print(hex(va), " ".join(f"{x:02X}" for x in b))
# player_by_index at 0x140346AA0
o=va2off(0x140346AA0); b=pe[o:o+0x20]
# movzx eax, word [rip+disp] -> opcode 0F B7 05 at +0
d1=struct.unpack_from("<i",b,3)[0]; count_va=0x140346AA0+7+d1
# find 48 8B 05
k=b.find(bytes([0x48,0x8B,0x05]))
d2=struct.unpack_from("<i",b,k+3)[0]; arr_va=0x140346AA0+k+7+d2
print(f"count global VA = 0x{count_va:X}")
print(f"array global VA = 0x{arr_va:X}")
# get index fn FUN_140352C10
o=va2off(0x140352C10); b=pe[o:o+0x30]
print("indexfn:", " ".join(f"{x:02X}" for x in b))
