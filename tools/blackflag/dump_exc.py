#!/usr/bin/env python3
"""Minimal minidump exception reader: faulting VA, EIP, and stack code pointers."""
import struct
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def u32(d, off):
    if off + 4 > len(d):
        return None
    return struct.unpack_from('<I', d, off)[0]


def u64(d, off):
    if off + 8 > len(d):
        return None
    return struct.unpack_from('<Q', d, off)[0]


def md_string(d, off):
    n = u32(d, off)
    if n is None:
        return ''
    raw = d[off + 4: off + 4 + n]
    try:
        s = raw.decode('utf-16-le', 'replace')
    except Exception:
        s = repr(raw)
    return ''.join(c if 32 <= ord(c) < 127 else '.' for c in s)


def parse(path):
    d = open(path, 'rb').read()
    assert u32(d, 0) == 0x504D444D
    n_streams = u32(d, 8)
    dir_rva = u32(d, 12)
    print('--- %s size=%d' % (path, len(d)))
    streams = {}
    for i in range(n_streams):
        st, sz, rva = struct.unpack_from('<III', d, dir_rva + 12 * i)
        streams.setdefault(st, []).append((sz, rva))
    exe_base = exe_size = None
    if 4 in streams:
        sz, rva = streams[4][0]
        nmod = u32(d, rva)
        off = rva + 4
        for m in range(nmod):
            base = u64(d, off)
            imgsize = u32(d, off + 8)
            namerva = u32(d, off + 24)
            name = md_string(d, namerva)
            if 'AC4BFSP' in name:
                exe_base, exe_size = base, imgsize
                print('  exe base=0x%x size=0x%x' % (base, imgsize))
            off += 108
    if 6 in streams:
        sz, rva = streams[6][0]
        code = u32(d, rva + 8)
        exc_addr = u64(d, rva + 16)
        ctx_size = u32(d, rva + 0xA0)
        ctx_rva = u32(d, rva + 0xA4)
        print('  exception code=0x%08x addr=0x%x' % (code, exc_addr))
        if ctx_rva and ctx_rva + 0xD4 <= len(d):
            eip = u32(d, ctx_rva + 0xC0)
            esp = u32(d, ctx_rva + 0xCC)
            ebp = u32(d, ctx_rva + 0xBC)
            print('  context: eip=0x%x esp=0x%x ebp=0x%x' % (eip, esp, ebp))
            if exe_base:
                print('  => fault VA=0x%x eip VA=0x%x (base 0x400000 naming)'
                      % (exc_addr, eip))
            if exe_base and esp:
                lo, hi = exe_base, exe_base + (exe_size or 0)
                out = []
                top = min(0x1800, len(d) - esp)
                for i in range(0, top, 4):
                    v = u32(d, esp + i)
                    if v is not None and lo <= v < hi:
                        out.append(v)
                print('  stack code addrs: %s' % ' '.join('0x%x' % v for v in out[:20]))


if __name__ == '__main__':
    for p in sys.argv[1:]:
        try:
            parse(p)
        except Exception as e:
            print('ERROR %s: %r' % (p, e))
