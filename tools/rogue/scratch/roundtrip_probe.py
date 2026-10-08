import struct, sys, os
sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue\re_scratch")
import anvil, container_rw as crw
from forge import Forge

FORGE = r"D:\SteamLibrary\steamapps\common\Assassin's Creed Rogue\DataPC.forge"
f = Forge(FORGE)


def load_entry(name):
    e = [x for x in f.entries if x["name"] == name][0]
    blob = f.data[e["offset"]:e["offset"] + e["size"]]
    tmp = os.path.join(os.environ["TEMP"], "_rt.data")
    open(tmp, "wb").write(blob)
    return crw.load(tmp)


def rebuild_files(files):
    out = bytearray()
    for (o, tid, name, header, payload) in anvil.walk_files(files):
        nb = name.encode("latin-1")
        out += struct.pack("<Iii", tid, len(payload), len(nb))
        out += nb + header + payload
    return bytes(out)


def parse_meta(meta):
    cnt = struct.unpack_from("<H", meta, 0)[0]
    ents = []
    o = 2
    for _ in range(cnt):
        rid = struct.unpack_from("<Q", meta, o)[0]
        sz = struct.unpack_from("<I", meta, o + 8)[0]
        fl = struct.unpack_from("<H", meta, o + 12)[0]
        ents.append((rid, sz, fl))
        o += 14
    return ents, o


for nm in ["ACC_W_P_French_Cutlass_Secondary", "WeaponSoundSet_Dual_Medium_Sword"]:
    pass

c = load_entry("ACC_W_P_French_Cutlass_Secondary")
files = crw.decompress_all(c["files"]["blocks"])
meta = crw.decompress_all(c["meta"]["blocks"])
r = rebuild_files(files)
print("files roundtrip identical:", r == files, "len", len(files), len(r))
ents, consumed = parse_meta(meta)
print("meta count", len(ents), "consumed", consumed, "meta len", len(meta))
for rid, sz, fl in ents:
    print(f"  id={rid} (0x{rid:X}) size={sz} flag={fl}")

# settings container single-sword ids
import glob
sp = r"C:\Users\Administrator\Documents\Default Project\ac-rogue\blobs\CUR_Game Bootstrap Settings.data"
cs = crw.load(sp)
ms = crw.decompress_all(cs["meta"]["blocks"])
fss = crw.decompress_all(cs["files"]["blocks"])
ents2, _ = parse_meta(ms)
byname = {}
o = 0
recs = list(anvil.walk_files(fss))
print("\nsettings resources of interest:")
for (o, tid, n, h, p) in recs:
    if n.startswith("WeaponSoundSet_Medium_Sword"):
        # find matching meta id by record size
        rsize = 12 + len(n.encode("latin-1")) + len(h) + len(p)
        match = [e for e in ents2 if e[1] == rsize]
        print(f"  {n}: recsize={rsize} len={len(p)} id_candidates={[hex(m[0]) for m in match]}")
