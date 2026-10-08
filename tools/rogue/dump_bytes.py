#!/usr/bin/env python3
"""Print hex bytes + a wildcard-friendly signature line for a VA range in ACC.exe."""
import struct, sys
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
def va2off(va):
    for n,v,vs,ra,rs in S:
        if v<=va-IB<v+max(vs,rs): return ra+(va-IB-v)
    return None
for a in sys.argv[1:]:
    va=int(a,16); off=va2off(va)
    b=pe[off:off+28]
    print(f"{a}: " + " ".join(f"{x:02X}" for x in b))
