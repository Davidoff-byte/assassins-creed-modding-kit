import struct, zlib, sys, os
sys.path.insert(0, r"C:\Users\Administrator\Documents\Default Project\ac-rogue")
import anvil

MAGIC = 0x1004FA9957FBAA33
BS = 32768


def parse_cfd(b, off):
    magic = struct.unpack_from("<Q", b, off)[0]
    assert magic == MAGIC, hex(magic)
    o = off + 8
    ver = struct.unpack_from("<h", b, o)[0]; o += 2
    algo = b[o]; o += 1
    bi = struct.unpack_from("<I", b, o)[0]; o += 4
    n = struct.unpack_from("<H", b, o)[0]; o += 2
    infos = [struct.unpack_from("<HH", b, o + 4 * i) for i in range(n)]
    o += 4 * n
    blocks = []
    for (un, cn) in infos:
        ad = struct.unpack_from("<I", b, o)[0]; o += 4
        data = b[o:o + cn]; o += cn
        blocks.append({"un": un, "cn": cn, "ad": ad, "data": data})
    return o, {"ver": ver, "algo": algo, "bi": bi, "blocks": blocks}


def write_cfd(hdr, blocks):
    out = bytearray()
    out += struct.pack("<Q", MAGIC)
    out += struct.pack("<h", hdr["ver"])
    out += bytes([hdr["algo"]])
    out += struct.pack("<I", hdr["bi"])
    out += struct.pack("<H", len(blocks))
    for blk in blocks:
        out += struct.pack("<HH", blk["un"], blk["cn"])
    for blk in blocks:
        out += struct.pack("<I", blk["ad"])
        out += blk["data"]
    return bytes(out)


def load(path):
    b = open(path, "rb").read()
    fts = struct.unpack_from("<i", b, 0)[0]
    ft = b[4:4 + fts]
    o, meta = parse_cfd(b, 4 + fts)
    o, files = parse_cfd(b, o)
    return {"fts": fts, "ft": ft, "meta": meta, "files": files}


def save(c, path):
    out = bytearray()
    out += struct.pack("<i", c["fts"])
    out += c["ft"]
    out += write_cfd(c["meta"], c["meta"]["blocks"])
    out += write_cfd(c["files"], c["files"]["blocks"])
    open(path, "wb").write(bytes(out))
    return len(out)


def decompress_all(blk_list):
    out = bytearray()
    for blk in blk_list:
        if blk["un"] == blk["cn"]:
            out += blk["data"]
        else:
            out += anvil.lzo().decompress(blk["data"], blk["un"])
    return bytes(out)


if __name__ == "__main__":
    c = load(sys.argv[1])
    n = save(c, sys.argv[2])
    a = open(sys.argv[1], "rb").read()
    b = open(sys.argv[2], "rb").read()
    print("orig", len(a), "rebuilt", n, "identical:", a == b)
