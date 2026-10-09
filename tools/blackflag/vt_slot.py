#!/usr/bin/env python3
"""Locate the update function's slot in the player behavior vtable and print the
crowd vtable's value at the same slot index."""
import ctypes
import struct
import sys

pid = int(sys.argv[1])
PLAYER_VT = 0x026FA898
CROWD_VT = 0x026E34D8
UPDATE_FN = 0x01AC1AD0
DISPATCH_FN = 0x01AF9F40

k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x0410, False, pid)


def rd(a, n):
    b = ctypes.create_string_buffer(n)
    g = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(a), b, n,
                               ctypes.byref(g))
    return b.raw[:g.value] if ok else None


def find_slot(vt, fn, size=0x400):
    b = rd(vt, size)
    if not b:
        return None
    for i in range(0, len(b), 4):
        v = struct.unpack_from('<I', b, i)[0]
        if v == fn:
            return i
    return None


for name, fn in (('update(1ac1ad0)', UPDATE_FN), ('dispatcher(1af9f40)', DISPATCH_FN)):
    sp = find_slot(PLAYER_VT, fn)
    print('%s: player slot = %s' % (name, ('+0x%X' % sp) if sp is not None else 'NOT FOUND'))
    if sp is not None:
        cb = rd(CROWD_VT + sp, 4)
        if cb:
            v = struct.unpack('<I', cb)[0]
            print('    crowd slot +0x%X = 0x%08X' % (sp, v))
