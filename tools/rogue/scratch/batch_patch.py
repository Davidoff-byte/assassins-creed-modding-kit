import struct, zlib, sys, os, shutil
from pathlib import Path
sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue\re_scratch")
import anvil, container_rw as crw
from forge import Forge

FORGE = Path(r"D:\SteamLibrary\steamapps\common\Assassin's Creed Rogue\DataPC.forge")
BACKUP = Path(r"C:\Users\Administrator\Documents\Default Project\ac-rogue\forge_backups\DataPC.forge.predagger")
PAT = bytes([0, 1, 1, 1, 1, 0, 1, 0])
BS = crw.BS


def patch_container(blob):
    tmp = os.path.join(os.environ["TEMP"], "_bp.data")
    open(tmp, "wb").write(blob)
    c = crw.load(tmp)
    files = bytearray(crw.decompress_all(c["files"]["blocks"]))
    i = files.find(PAT)
    if i == -1 or i > 0x2000:
        return None
    files[i + 1] = 0
    files[i + 5] = 1
    changed = i // BS
    nb = []
    for bi, blk in enumerate(c["files"]["blocks"]):
        chunk = bytes(files[bi * BS:bi * BS + blk["un"]])
        if bi == changed:
            comp = anvil.lzo().compress(chunk)
            use = comp if len(comp) < len(chunk) else chunk
            nb.append({"un": len(chunk), "cn": len(use), "ad": 0, "data": use})
        else:
            nb.append(dict(blk))
    for blk in nb:
        blk["ad"] = zlib.adler32(blk["data"], 0) & 0xffffffff
    c["files"]["blocks"] = nb
    out = os.path.join(os.environ["TEMP"], "_bp_out.data")
    crw.save(c, out)
    return Path(out).read_bytes()


def main():
    if not BACKUP.exists():
        shutil.copy2(FORGE, BACKUP); print("backup ->", BACKUP)
    f = Forge(str(FORGE))
    buf = bytearray(f.data)
    inplace = appended = skipped = 0
    for e in f.entries:
        if not e["name"].endswith("_Secondary"):
            continue
        blob = bytes(buf[e["offset"]:e["offset"] + e["size"]])
        new = patch_container(blob)
        if new is None:
            skipped += 1; continue
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


main()
