#!/usr/bin/env python3
"""AnvilNext `.data` container codec for AC Rogue (Game.Rogue = Version 1, Algorithm 0, Block 32768).

Layout (from ATK 1.3.6 DataFile/CompressedFileData/DataBlock/CompressionInfo):
  [int32 filterTableSize][filterTable bytes][CFD meta][CFD files]
  CompressedFileData (TOC mode):
    u64 magic 0x1004FA9957FBAA33
    CompressionInfo: i16 Version, u8 Algorithm, u32 (TOC<<31 | BlockSize)
    u16 blockCount                       (Rogue)
    blockCount * (u16 uncompressed, u16 compressed)   (Version==1)
    per block: u32 adler32, then `compressed` bytes (raw if uncomp==comp, else LZO1X)
  Decompressed `files` block = sequence of records:
    u32 typeId | i32 len | i32 nameLen | name[nameLen] | FileHeader | payload[len]
  FileHeader = 1 byte, unless that byte==1 -> 12*count + 8 bytes.
"""
import ctypes
import struct
import zlib
from pathlib import Path

MAGIC = 0x1004FA9957FBAA33

# Rogue: TOC mode, block-compressed with LZO1X (algorithm 0).
VERSION = 1
ALGORITHM = 0
BLOCK_SIZE = 32768


def _find_lzo():
    for c in [
        r"C:\SteamLibrary\steamapps\common\Assassins Creed\Libs\lzo.dll",
        r"D:\SteamLibrary\steamapps\common\Assassin's Creed Rogue\libs\lzo.dll",
        r"D:\SteamLibrary\steamapps\common\Assassin's Creed Rogue\lzo.dll",
    ]:
        if Path(c).is_file():
            return c
    raise FileNotFoundError("lzo.dll not found")


class Lzo:
    LZO1X_1_MEM_COMPRESS = 16384 * 16

    def __init__(self, path=None):
        self._comp = None
        self.dll = ctypes.WinDLL(path or _find_lzo())
        self.dec = self.dll.lzo1x_decompress_safe
        self.dec.restype = ctypes.c_int
        self.dec.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p,
                             ctypes.POINTER(ctypes.c_size_t), ctypes.c_void_p]

    def decompress(self, src: bytes, out_len: int) -> bytes:
        dst = ctypes.create_string_buffer(out_len)
        dst_len = ctypes.c_size_t(out_len)
        rc = self.dec(src, len(src), dst, ctypes.byref(dst_len), None)
        if rc != 0:
            raise RuntimeError(f"lzo decompress rc={rc}")
        return dst.raw[:dst_len.value]

    def compress(self, src: bytes) -> bytes:
        if self._comp is None:
            f = self.dll.lzo1x_1_compress
            f.restype = ctypes.c_int
            f.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p,
                          ctypes.POINTER(ctypes.c_size_t), ctypes.c_void_p]
            self._comp = f
            self._work = ctypes.create_string_buffer(1 << 18)
        dst = ctypes.create_string_buffer(len(src) + len(src) // 8 + 128 + 3)
        dst_len = ctypes.c_size_t(len(dst))
        rc = self._comp(src, len(src), dst, ctypes.byref(dst_len), self._work)
        if rc != 0:
            raise RuntimeError(f"lzo compress rc={rc}")
        return dst.raw[:dst_len.value]


_lzo = None


def lzo():
    global _lzo
    if _lzo is None:
        _lzo = Lzo()
    return _lzo


def read_cfd(b: bytes, off: int):
    """Read one TOC-mode CompressedFileData at off. Returns (data, next_off)."""
    magic = struct.unpack_from("<Q", b, off)[0]
    if magic != MAGIC:
        raise ValueError(f"bad magic 0x{magic:016X} at 0x{off:X}")
    off += 8
    ver = struct.unpack_from("<h", b, off)[0]
    off += 2
    algo = b[off]
    off += 1
    bi = struct.unpack_from("<I", b, off)[0]
    off += 4
    block_size = bi & 0x7FFFFFFF
    toc = (bi >> 31) == 1
    nblocks = struct.unpack_from("<H", b, off)[0]
    off += 2
    infos = []
    for _ in range(nblocks):
        un, cn = struct.unpack_from("<HH", b, off)
        off += 4
        infos.append((un, cn))
    out = bytearray()
    for un, cn in infos:
        adler = struct.unpack_from("<I", b, off)[0]
        off += 4
        blk = b[off:off + cn]
        off += cn
        if un == cn:
            out += blk
        else:
            out += lzo().decompress(blk, un)
    return bytes(out), off, dict(version=ver, algo=algo, toc=toc, blocks=nblocks)


def walk_files(files: bytes):
    """Yield (offset, type_id, name, header, payload)."""
    o = 0
    n = len(files)
    while o + 12 <= n:
        tid, length, slen = struct.unpack_from("<Iii", files, o)
        h = o + 12 + slen
        if slen < 0 or length < 0 or slen > 0x1000 or h >= n:
            break
        name = files[o + 12:h].decode("latin-1", "replace")
        hl = 1
        if files[h] == 1:
            cnt = struct.unpack_from("<i", files, h + 4)[0]
            hl = 12 * cnt + 8
        end = h + hl + length
        if end > n:
            break
        yield (o, tid, name, files[h:h + hl], files[h + hl:end])
        o = end


def read_container(path):
    b = Path(path).read_bytes()
    fts = struct.unpack_from("<i", b, 0)[0]
    off = 4
    ft = b[off:off + fts]
    off += fts
    meta, off, imeta = read_cfd(b, off)
    files, off, ifiles = read_cfd(b, off)
    file_count = struct.unpack_from("<H", meta, 0)[0] if len(meta) >= 2 else 0
    return dict(filter_table_size=fts, filter_table=ft, meta=meta, files=files,
                file_count=file_count, reader_off=off, info_meta=imeta, info_files=ifiles)


if __name__ == "__main__":
    import sys
    c = read_container(sys.argv[1])
    print(f"filterTableSize={c['filter_table_size']} meta={len(c['meta'])}B blocks={c['info_meta']['blocks']} "
          f"files={len(c['files'])}B blocks={c['info_files']['blocks']} fileCount={c['file_count']}")
    res = list(walk_files(c["files"]))
    print(f"parsed resources: {len(res)}")
    for (o, tid, name, header, payload) in res[:60]:
        cid = struct.unpack_from("<Q", payload, 1)[0] if len(payload) >= 9 and payload[0] in (0, 1) else (
            struct.unpack_from("<Q", payload, 0)[0] if len(payload) >= 8 else 0)
        print(f"  @0x{o:06X} type=0x{tid:08X} len={len(payload):7d} hdr={len(header)}B "
              f"name={name!r}")
