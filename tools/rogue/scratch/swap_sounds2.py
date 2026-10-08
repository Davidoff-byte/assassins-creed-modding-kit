import struct, zlib, sys, os, shutil
from pathlib import Path
sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue\re_scratch")
import anvil, container_rw as crw
from forge import Forge

FORGE = Path(r"D:\SteamLibrary\steamapps\common\Assassin's Creed Rogue\DataPC.forge")
SETTINGS = r"C:\Users\Administrator\Documents\Default Project\ac-rogue\blobs\CUR_Game Bootstrap Settings.data"
BACKUP = Path(r"C:\Users\Administrator\Documents\Default Project\ac-rogue\forge_backups\DataPC.forge.presound2")

# target (in weapon container) -> source (in settings container)
MAP = {
    "WeaponSoundSet_Dual_Medium_Sword": "WeaponSoundSet_Medium_Sword",
    "WeaponSoundSet_Dual_Medium_Sword_NPC": "WeaponSoundSet_Medium_Sword_NPC",
}


def meta_parse(meta):
    cnt = struct.unpack_from("<H", meta, 0)[0]
    ent = []
    o = 2
    for _ in range(cnt):
        rid = struct.unpack_from("<Q", meta, o)[0]
        sz = struct.unpack_from("<I", meta, o + 8)[0]
        ent.append((o + 8, rid, sz))
        o += 14
    return cnt, ent


def reblocks(cfd, data):
    bs = cfd["bi"] & 0x7FFFFFFF
    nb = []
    for i in range(0, len(data), bs):
        chunk = data[i:i + bs]
        comp = anvil.lzo().compress(chunk)
        use = comp if len(comp) < len(chunk) else chunk
        nb.append({"un": len(chunk), "cn": len(use), "ad": zlib.adler32(use, 0) & 0xffffffff, "data": use})
    cfd["blocks"] = nb


def patch_container(blob, sources):
    tmp = os.path.join(os.environ["TEMP"], "_ss2.data")
    open(tmp, "wb").write(blob)
    c = crw.load(tmp)
    files = crw.decompress_all(c["files"]["blocks"])
    meta = crw.decompress_all(c["meta"]["blocks"])
    recs = list(anvil.walk_files(files))
    cnt, entries = meta_parse(meta)
    if cnt != len(recs):
        return None, "count mismatch"
    out = bytearray()
    sizes = []
    hits = 0
    for (o, tid, name, h, p) in recs:
        np = p
        if name in sources:
            np = sources[name]
            hits += 1
        nb = name.encode("latin-1")
        out += struct.pack("<Iii", tid, len(np), len(nb))
        out += nb + h + np
        sizes.append(12 + len(nb) + len(h) + len(np))
    if hits == 0:
        return None, "no soundset"
    m = bytearray(meta)
    for i, (size_off, rid, old) in enumerate(entries):
        struct.pack_into("<I", m, size_off, sizes[i])
    reblocks(c["files"], bytes(out))
    reblocks(c["meta"], bytes(m))
    o2 = os.path.join(os.environ["TEMP"], "_ss2_out.data")
    crw.save(c, o2)
    return Path(o2).read_bytes(), f"{hits} sets"


def main():
    if not BACKUP.exists():
        shutil.copy2(FORGE, BACKUP)
        print("backup ->", BACKUP)
    sources = {}
    cs = crw.load(SETTINGS)
    for (o, tid, n, h, p) in anvil.walk_files(crw.decompress_all(cs["files"]["blocks"])):
        for tgt, src in MAP.items():
            if n == src:
                sources[tgt] = p
                print(f"source {src}: {len(p)} bytes")
    assert len(sources) == len(MAP), sources.keys()

    f = Forge(str(FORGE))
    buf = bytearray(f.data)
    inplace = appended = skipped = 0
    for e in f.entries:
        if not e["name"].endswith("_Secondary"):
            continue
        blob = bytes(buf[e["offset"]:e["offset"] + e["size"]])
        new, why = patch_container(blob, sources)
        if new is None:
            skipped += 1
            print(f"  skip {e['name']}: {why}")
            continue
        if len(new) <= e["size"]:
            buf[e["offset"]:e["offset"] + len(new)] = new
            struct.pack_into("<i", buf, e["desc_off"] + 16, len(new))
            struct.pack_into("<i", buf, e["name_rec_off"], len(new))
            inplace += 1
        else:
            off = (len(buf) + 0x7FFF) & ~0x7FFF
            buf += b"\x00" * (off - len(buf))
            buf += new
            struct.pack_into("<q", buf, e["desc_off"], off)
            struct.pack_into("<i", buf, e["desc_off"] + 16, len(new))
            struct.pack_into("<i", buf, e["name_rec_off"], len(new))
            appended += 1
    FORGE.write_bytes(bytes(buf))
    print(f"in-place {inplace}, appended {appended}, skipped {skipped}, forge {len(f.data)} -> {len(buf)}")


if __name__ == "__main__":
    main()
