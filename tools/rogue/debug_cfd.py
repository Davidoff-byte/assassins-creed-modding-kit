import struct, sys, zlib
from pathlib import Path
from anvil import lzo, MAGIC

b = Path(sys.argv[1]).read_bytes()
fts = struct.unpack_from("<i", b, 0)[0]
off = 4 + fts
print(f"filterTableSize={fts} -> cfd1 at 0x{off:X}")


def hdr(off, tag):
    magic = struct.unpack_from("<Q", b, off)[0]
    print(f"\n{tag} @0x{off:X} magic=0x{magic:016X} ok={magic==MAGIC}")
    p = off + 8
    ver = struct.unpack_from("<h", b, p)[0]; p += 2
    algo = b[p]; p += 1
    bi = struct.unpack_from("<I", b, p)[0]; p += 4
    print(f"  ver={ver} algo={algo} blocksize={bi & 0x7FFFFFFF} toc={bi>>31}")
    nblocks = struct.unpack_from("<H", b, p)[0]; p += 2
    print(f"  nblocks(u16)={nblocks}")
    return p, nblocks, ver


p, nblocks, ver = hdr(off, "CFD1")
# print a few block infos and probe
for i in range(min(nblocks, 3)):
    un, cn = struct.unpack_from("<HH", b, p); print(f"   info[{i}] un={un} cn={cn}")
    p += 4
# skip all infos
p0 = p
p = p0 + 4 * nblocks
for i in range(min(nblocks, 3)):
    adler = struct.unpack_from("<I", b, p)[0]
    cn = struct.unpack_from("<HH", b, p0 + 4 * i)[1]
    blk = b[p + 4:p + 4 + cn]
    print(f"   blk[{i}] adler=0x{adler:08X} cn={cn} head={blk[:8].hex(' ')}")
    p += 4 + cn
print(f"  CFD1 ends at 0x{p:X}")
hdr(p, "CFD2")
