#!/usr/bin/env python3
"""Extract individual resources from an AnvilNext container (AC4)."""
import sys, os

sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
from anvil import read_container, walk_files


def extract(container, outdir, needles):
    c = read_container(container)
    res = list(walk_files(c["files"]))
    os.makedirs(outdir, exist_ok=True)
    n = 0
    for (o, tid, name, header, payload) in res:
        if needles and not any(nd.lower() in name.lower() for nd in needles):
            continue
        safe = (name or f"res_{o:06X}").replace("/", "_").replace("\\", "_")
        base = os.path.join(outdir, f"{o:06X}_{tid:08X}_{safe}")
        with open(base + ".pay", "wb") as f:
            f.write(payload)
        with open(base + ".raw", "wb") as f:
            f.write(header + payload)
        n += 1
        print(f"  {os.path.basename(base)}  payload={len(payload)}")
    print(f"extracted {n} resources to {outdir}")


if __name__ == "__main__":
    container = sys.argv[1]
    outdir = sys.argv[2]
    needles = sys.argv[3:] if len(sys.argv) > 3 else []
    extract(container, outdir, needles)
