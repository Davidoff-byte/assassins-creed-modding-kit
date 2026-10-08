import struct, zlib, sys, os, shutil
from pathlib import Path
sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue\re_scratch")
import anvil, container_rw as crw
from forge import Forge

FORGE = Path(r"D:\SteamLibrary\steamapps\common\Assassin's Creed Rogue\DataPC.forge")
SETTINGS = Path(r"C:\Users\Administrator\Documents\Default Project\ac-rogue\blobs\CUR_Game Bootstrap Settings.data")
BACKUP = Path(r"C:\Users\Administrator\Documents\Default Project\ac-rogue\forge_backups\DataPC.forge.presound")
BS = crw.BS

# source (single-sword) by target (dual-wield) resource name
REPLACE = {
    "WeaponSoundSet_Dual_Medium_Sword": "WeaponSoundSet_Medium_Sword",
    "WeaponSoundSet_Dual_Medium_Sword_NPC": "WeaponSoundSet_Medium_Sword_NPC",
}


def get_one(data_path, name):
    c = anvil.read_container(str(data_path))
    for (o, tid, n, h, p) in anvil.walk_files(c["files"]):
        if n == name:
            return p
    return None


def rebuild_files(files, repl):
    out = bytearray()
    n = 0
    for (o, tid, name, header, payload) in anvil.walk_files(files):
        if name in repl:
            payload = repl[name]
            n += 1
        nb = name.encode("latin-1")
        out += struct.pack("<Iii", tid, len(payload), len(nb))
        out += nb + header + payload
    return bytes(out), n


def swap_container(blob, repl):
    tmp = os.path.join(os.environ["TEMP"], "_ss.data")
    open(tmp, "wb").write(blob)
    c = crw.load(tmp)
    files = crw.decompress_all(c["files"]["blocks"])
    files2, hits = rebuild_files(files, repl)
    if hits == 0:
        return None
    # recompress every block (content changed throughout)
    nb = []
    for i in range(0, len(files2), BS):
        chunk = files2[i:i + BS]
        comp = anvil.lzo().compress(chunk)
        use = comp if len(comp) < len(chunk) else chunk
        nb.append({"un": len(chunk), "cn": len(use), "ad": zlib.adler32(use, 0) & 0xffffffff, "data": use})
    c["files"]["blocks"] = nb
    out = os.path.join(os.environ["TEMP"], "_ss_out.data")
    crw.save(c, out)
    return Path(out).read_bytes()


def main():
    if not BACKUP.exists():
        shutil.copy2(FORGE, BACKUP); print("backup ->", BACKUP)
    repl = {}
    for tgt, src in REPLACE.items():
        p = get_one(SETTINGS, src)
        assert p is not None, f"missing source {src}"
        print(f"source {src}: {len(p)} bytes")
        repl[tgt] = p

    f = Forge(str(FORGE))
    buf = bytearray(f.data)
    done = skipped = 0
    for e in f.entries:
        if not e["name"].endswith("_Secondary"):
            continue
        blob = bytes(buf[e["offset"]:e["offset"] + e["size"]])
        new = swap_container(blob, repl)
        if new is None:
            skipped += 1; continue
        if len(new) <= e["size"]:
            buf[e["offset"]:e["offset"] + len(new)] = new
            struct.pack_into("<i", buf, e["desc_off"] + 16, len(new))
            struct.pack_into("<i", buf, e["name_rec_off"], len(new))
        else:
            off = (len(buf) + 0x7FFF) & ~0x7FFF
            buf += b"\x00" * (off - len(buf))
            buf += new
            struct.pack_into("<q", buf, e["desc_off"], off)
            struct.pack_into("<i", buf, e["desc_off"] + 16, len(new))
            struct.pack_into("<i", buf, e["name_rec_off"], len(new))
        done += 1
    FORGE.write_bytes(bytes(buf))
    print(f"swapped sound sets in {done} sets, skipped {skipped}")


main()
