#!/usr/bin/env python3
"""rd_multi.py - read several process memory ranges and hex-dump them.

Usage: rd_multi.py <pid> <addr:len> [addr:len ...]
Addrs/lens in hex (0x optional). Pointer-looking dwords are annotated.
"""
import ctypes
import struct
import sys

pid = int(sys.argv[1])
specs = sys.argv[2:]

k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x0410, False, pid)


def rd(a, n):
    b = ctypes.create_string_buffer(n)
    g = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(a), b, n,
                               ctypes.byref(g))
    return b.raw[:g.value] if ok and g.value else None


for spec in specs:
    if ':' in spec:
        a_s, l_s = spec.split(':', 1)
    else:
        a_s, l_s = spec, '64'
    a = int(a_s, 16)
    n = int(l_s, 16) if not l_s.startswith('0x') else int(l_s, 16)
    data = rd(a, n)
    print('== 0x%08X len=0x%X ==' % (a, n))
    if not data:
        print('  <unreadable>')
        continue
    for off in range(0, len(data), 16):
        chunk = data[off:off + 16]
        hexs = ' '.join('%02X' % c for c in chunk)
        ann = ''
        if len(chunk) >= 4:
            v = struct.unpack_from('<I', chunk, 0)[0]
            if 0x10000 <= v < 0x7FFF0000:
                ann = ' <0x%08X>' % v
        print('  +0x%03X: %-47s%s' % (off, hexs, ann))
    # extra: all pointer-looking dwords
    ptrs = []
    for off in range(0, len(data) - 3, 4):
        v = struct.unpack_from('<I', data, off)[0]
        if 0x10000 <= v < 0x7FFF0000:
            ptrs.append('+0x%X=0x%08X' % (off, v))
    if ptrs:
        print('  ptrs: ' + ' '.join(ptrs))
