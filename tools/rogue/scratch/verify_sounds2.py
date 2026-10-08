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

bad = 0
checked = 0
swapped = 0
for e in f.entries:
    if not e["name"].endswith("_Secondary"):
        continue
    blob = f.data[e["offset"]:e["offset"] + e["size"]]
    tmp = os.path.join(os.environ["TEMP"], "_vs.data")
    open(tmp, "wb").write(blob)
    try:
        c = crw.load(tmp)
        files = crw.decompress_all(c["files"]["blocks"])
        meta = crw.decompress_all(c["meta"]["blocks"])
        recs = list(anvil.walk_files(files))
        cnt, entries = S.meta_parse(meta)
    except Exception as ex:
        print(f"PARSE FAIL {e['name']}: {ex}")
        bad += 1
        continue
    checked += 1
    if cnt != len(recs):
        print(f"COUNT MISMATCH {e['name']}: meta {cnt} recs {len(recs)}")
        bad += 1
        continue
    for i, (o, tid, name, h, p) in enumerate(recs):
        rsize = 12 + len(name.encode("latin-1")) + len(h) + len(p)
        if rsize != entries[i][2]:
            print(f"SIZE MISMATCH {e['name']} {name}")
            bad += 1
        if name in sources:
            swapped += 1
            if p != sources[name]:
                print(f"PAYLOAD MISMATCH {e['name']} {name}")
                bad += 1
print(f"checked {checked} containers, swapped payload slots {swapped}, problems {bad}")
