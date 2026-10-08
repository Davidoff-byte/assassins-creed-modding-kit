import struct
from pathlib import Path
EXE=Path(r"D:\SteamLibrary\steamapps\common\Assassin's Creed Rogue\ACC.exe"); IB=0x140000000
def secs(pe):
    e=struct.unpack_from("<I",pe,0x3C)[0];coff=e+4
    n=struct.unpack_from("<H",pe,coff+2)[0];optsz=struct.unpack_from("<H",pe,coff+16)[0];opt=coff+20
    o=opt+optsz;out=[]
    for i in range(n):
        p=o+i*40;name=pe[p:p+8].rstrip(b"\0").decode("latin-1")
        vs,va,rs,ra=struct.unpack_from("<IIII",pe,p+8);out.append((name,va,vs,ra,rs))
    return out
def va2off(S,va):
    for n,v,vs,ra,rs in S:
        if v<=va-IB<v+max(vs,rs): return ra+(va-IB-v),n
    return None,None
pe=EXE.read_bytes();S=secs(pe)
for a in ["142102c50","142102d00"]:
    va=int(a,16);off,sec=va2off(S,va)
    print(a, " ".join(f"{x:02X}" for x in pe[off:off+32]))
