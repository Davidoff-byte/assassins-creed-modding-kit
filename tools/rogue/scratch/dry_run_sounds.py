import struct, sys, os
sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue\re_scratch")
import anvil, container_rw as crw
from forge import Forge
import swap_sounds2 as S

f = Forge(str(S.FORGE))
sources = {}
cs = crw.load(S.SETTINGS)
for (o, tid, n, h, p) in anvil.walk_files(crw.decompress_all(cs["files"]["blocks"])):
    for tgt, src in S.MAP.items():
        if n == src:
            sources[tgt] = p

e = [x for x in f.entries if x["name"] == "ACC_W_P_French_Cutlass_Secondary"][0]
blob = f.data[e["offset"]:e["offset"] + e["size"]]
new, why = S.patch_container(blob, sources)
print("patched:", why, "old container", len(blob), "new container", len(new))

tmp = os.path.join(os.environ["TEMP"], "_dry.data")
open(tmp, "wb").write(new)
c = crw.load(tmp)
files = crw.decompress_all(c["files"]["blocks"])
meta = crw.decompress_all(c["meta"]["blocks"])
recs = list(anvil.walk_files(files))
cnt, entries = S.meta_parse(meta)
print("meta count", cnt, "records", len(recs), "decompressed files len", len(files))
ok = True
for i, (o, tid, name, h, p) in enumerate(recs):
    rsize = 12 + len(name.encode("latin-1")) + len(h) + len(p)
    msz = entries[i][2]
    mark = "OK" if rsize == msz else "MISMATCH"
    if rsize != msz:
        ok = False
    exp = sources.get(name)
    note = ""
    if exp is not None:
        note = " <-- swapped, len " + str(len(exp))
    print(f"  rec{i} @0x{o:06X} {name!r} payload={len(p)} recsize={rsize} metasize={msz} {mark}{note}")
print("STRUCTURE OK" if ok else "STRUCTURE BAD")
# verify payload equality where swapped
for (o, tid, name, h, p) in recs:
    if name in sources:
        print(f"payload match {name}: {p == sources[name]}")
