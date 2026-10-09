#!/usr/bin/env python3
"""Read the request-slot region +0x2F40..0x2F80 on the Edward's controller and
the player's controller."""
import ctypes
import struct
import sys

pid = int(sys.argv[1])
CTLS = [0x44742C70, 0x3A3A0640, 0x432F05D0]  # edward1, edward2, player

k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x0410, False, pid)


def rd(a, n):
    b = ctypes.create_string_buffer(n)
    g = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(a), b, n,
                               ctypes.byref(g))
    return b.raw[:g.value] if ok else None


for c in CTLS:
    blob = rd(c + 0x2F40, 0x50)
    if not blob:
        print('0x%08X: unreadable' % c)
        continue
    vals = [struct.unpack_from('<I', blob, i)[0] for i in range(0, 0x50, 4)]
    print('0x%08X +0x2F40..0x2F90: %s' % (c, ' '.join('%08X' % v for v in vals)))
    blob2 = rd(c + 0x8C0, 0x60)
    if blob2:
        vals2 = [struct.unpack_from('<I', blob2, i)[0] for i in range(0, 0x60, 4)]
        print('          +0x8C0..0x920: %s' % ' '.join('%08X' % v for v in vals2))
