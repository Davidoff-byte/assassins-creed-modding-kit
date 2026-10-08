import struct, sys, shutil, os
from pathlib import Path
sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
from forge import Forge

FORGE = Path(r"D:\SteamLibrary\steamapps\common\Assassin's Creed Rogue\DataPC.forge")
BACKUP = Path(r"C:\Users\Administrator\Documents\Default Project\ac-rogue\forge_backups\DataPC.forge.predagger")
NAME = "ACC_W_P_ShayDefaultSword_Secondary"
NEW = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(os.environ["TEMP"]) / "patched_secondary.data"


def main():
    new = NEW.read_bytes()
    if not BACKUP.exists():
        BACKUP.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(FORGE, BACKUP)
        print(f"backup -> {BACKUP}")
    f = Forge(str(FORGE))
    hits = [e for e in f.entries if e["name"] == NAME]
    assert len(hits) == 1, f"{NAME}: {len(hits)} entries"
    e = hits[0]
    assert len(new) <= e["size"], f"new {len(new)} > target {e['size']}"
    buf = bytearray(f.data)
    buf[e["offset"]:e["offset"] + len(new)] = new
    struct.pack_into("<i", buf, e["desc_off"] + 16, len(new))
    struct.pack_into("<i", buf, e["name_rec_off"], len(new))
    FORGE.write_bytes(bytes(buf))
    # verify
    g = Forge(str(FORGE))
    ee = [x for x in g.entries if x["name"] == NAME][0]
    got = g.data[ee["offset"]:ee["offset"] + ee["size"]]
    print("round-trip:", got == new, "size", ee["size"])


main()
