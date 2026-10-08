#!/usr/bin/env python3
"""Find RIP-relative code references to a VA in ACC.exe by scanning .text for
disp32 such that va(p)+4+disp == target (disp is last operand). Reports the
instruction start by also decoding a plausible instruction length."""
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
texts = [(n,va,vs,ra,rs) for (n,va,vs,ra,rs) in S if n in (".text",)]

for targhex in sys.argv[1:]:
    targ = int(targhex,16)
    print(f"=== refs to 0x{targ:X} ===")
    hits=0
    for (n,va,vs,ra,rs) in texts:
        for off in range(ra, ra+rs-4):
            d = struct.unpack_from("<i", pe, off)[0]
            p_va = IB + va + (off-ra)
            if p_va + 4 + d == targ:
                # instruction start could be off-2..off-3; show a few bytes of context
                start = max(ra, off-7)
                ctx = " ".join(f"{b:02X}" for b in pe[start:off+4])
                print(f"  hit file 0x{off:X} VA 0x{p_va:X} (disp 0x{d & 0xffffffff:X}) ctx[{start-ra:04X}] {ctx}")
                hits+=1
    print(f"  total {hits}")
