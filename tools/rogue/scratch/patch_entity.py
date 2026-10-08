import struct, zlib, sys, os
sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue\re_scratch")
import anvil, container_rw as crw


def patch(src, dst, verbose=True):
    c = crw.load(src)
    files = bytearray(crw.decompress_all(c["files"]["blocks"]))
    pat = bytes([0, 1, 1, 1, 1, 0, 1, 0])  # IsSpawned..IsMediumObject
    i = files[:0x700].find(pat)
    if i == -1:
        print("pattern not found")
        return False
    if verbose:
        print(f"found visibility bools at files+0x{i:X} (IsVisible=+{i+1:X}, IsHidden=+{i+5:X})")
    files[i + 1] = 0   # IsVisible = False
    files[i + 5] = 1   # IsHidden  = True

    BS = crw.BS
    changed = i // BS
    new_blocks = []
    for bi, blk in enumerate(c["files"]["blocks"]):
        chunk = bytes(files[bi * BS:bi * BS + blk["un"]])
        if bi == changed:
            comp = anvil.lzo().compress(chunk)
            if len(comp) < len(chunk):
                new_blocks.append({"un": len(chunk), "cn": len(comp), "ad": 0, "data": comp})
            else:
                new_blocks.append({"un": len(chunk), "cn": len(chunk), "ad": 0, "data": chunk})
        else:
            new_blocks.append(dict(blk))
    for blk in new_blocks:
        blk["ad"] = zlib.adler32(blk["data"], 0) & 0xffffffff
    c["files"]["blocks"] = new_blocks
    n = crw.save(c, dst)
    print(f"wrote {dst} ({n} bytes)")
    return n


if __name__ == "__main__":
    patch(sys.argv[1], sys.argv[2])
