#!/usr/bin/env python3
"""Parse BlackFlag.gfl and try to resolve cell-datablock world keys."""
import sys, os, struct, lzma

GFL = r"D:\ac4work\tools\AnvilToolkit\Lists\BlackFlag.gfl"

data = open(GFL, "rb").read()
p = 0
magic = struct.unpack_from("<I", data, p)[0]; p += 4
print("magic=0x%08X" % magic)
version = struct.unpack_from("<i", data, p)[0]; p += 4
print("version=", version)
compressed = data[p]; p += 1
algo = data[p]; p += 1
p += 2
num = struct.unpack_from("<i", data, p)[0]; p += 4
unc = struct.unpack_from("<i", data, p)[0]; p += 4
clen = struct.unpack_from("<i", data, p)[0]; p += 4
print("num=", num, "unc=", unc, "clen=", clen, "compressed=", compressed, "algo=", algo)
blob = data[p:p + clen]
if compressed:
    if algo == 1:
        blob = lzma.decompress(blob)
    else:
        print("algo", algo, "not handled")
        sys.exit(1)

# parse
q = 0
entries = {}
forge_files = []
data_files = []
def read_cstr(buf, off):
    end = buf.index(b"\x00", off)
    return buf[off:end].decode("latin-1"), end + 1

for i in range(num):
    name, q = read_cstr(blob, q)
    forge_files.append(name)
    _ = struct.unpack_from("<Q", blob, q)[0]; q += 8
    dlen = struct.unpack_from("<i", blob, q)[0]; q += 4
    dblob = blob[q:q + dlen]; q += dlen
    r = 0
    while r < len(dblob):
        v = struct.unpack_from("<I", dblob, r)[0]
        if v == 1:
            dname, r = read_cstr(dblob, r + 4)
            data_files.append(dname)
        else:
            key = struct.unpack_from("<Q", dblob, r + 4)[0]
            nm, r = read_cstr(dblob, r + 12)
            entries[key] = (v, forge_files[-1], data_files[-1] if data_files else "?", nm)

print("forge files:", len(forge_files), "data files:", len(data_files), "entries:", len(entries))

# cell keys to resolve (key, block)
cell_keys = [
    (0x9816CCA4, 2), (0x34D83D8F, 6), (0x4C5EFA8C, 6), (0x4E12AA74, 6),
    (0x79F376A5, 6), (0xABB0AD39, 6), (0xC84AD184, 6), (0xDF5DADC4, 6),
    (0xEE218210, 6), (0x11F367B2, 7), (0x2CEB569C, 0xC), (0x4DAFBCA8, 0xC),
    (0x54CFD219, 0xC), (0x9816CCA4, 0), (0x187825BC, 0),
]

print("--- resolve attempts ---")
for k, b in cell_keys:
    variants = {
        "u64=key|block<<32": k | (b << 32),
        "u64=block|key<<32": b | (k << 32),
        "u64=key": k,
        "u64=key|0x100000000": k | 0x100000000,
    }
    found = []
    for label, vid in variants.items():
        if vid in entries:
            e = entries[vid]
            found.append(f"{label} -> [{e[1]}]\\[{e[2]}]\\{e[3]}.{e[0]}")
    print(f"key=0x{k:08X} block={b}: " + ("; ".join(found) if found else "no hit"))
