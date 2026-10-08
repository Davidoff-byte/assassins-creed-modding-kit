import struct, sys, os
sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue\re_scratch")
import anvil, container_rw as crw
from forge import Forge

FORGE = r"D:\SteamLibrary\steamapps\common\Assassin's Creed Rogue\DataPC.forge"
f = Forge(FORGE)
e = [x for x in f.entries if x["name"] == "ACC_W_P_French_Cutlass_Secondary"][0]
blob = f.data[e["offset"]:e["offset"] + e["size"]]
tmp = os.path.join(os.environ["TEMP"], "_meta.data")
open(tmp, "wb").write(blob)
c = crw.load(tmp)
meta = crw.decompress_all(c["meta"]["blocks"])
files = crw.decompress_all(c["files"]["blocks"])
print("meta len", len(meta), "files len", len(files))
print("meta[0:2] =", struct.unpack_from("<H", meta, 0)[0])
print("meta hex head:", meta[:160].hex(" "))
print()
walk = list(anvil.walk_files(files))
for (o, tid, n, h, p) in walk:
    print(f"files off=0x{o:06X} tid=0x{tid:08X} len={len(p):6d} hdr={len(h)} name={n}")
print()
# look for the offsets inside meta
offs = [o for (o, tid, n, h, p) in walk]
for off in offs[:20]:
    idx = meta.find(struct.pack("<I", off))
    idxq = meta.find(struct.pack("<Q", off))
    print(f"off 0x{off:06X} in meta as u32 at {idx} as u64 at {idxq}")
