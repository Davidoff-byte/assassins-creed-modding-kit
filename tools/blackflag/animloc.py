#!/usr/bin/env python3
"""Determine which object carries the live anim scalars: sample the bytes at
+0x8D0..0x900 on the behavior and its sub-object chain, twice, and report which
region shows small changing scalars (blend/phase/hang-like)."""
import ctypes
import struct
import sys
import time

pid = int(sys.argv[1])
ENT = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x476DFE30

k32 = ctypes.windll.kernel32
h = k32.OpenProcess(0x0410, False, pid)


def rd(a, n):
    b = ctypes.create_string_buffer(n)
    g = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(ctypes.c_void_p(h), ctypes.c_void_p(a), b, n,
                               ctypes.byref(g))
    return b.raw[:g.value] if ok else None


def u32(a):
    b = rd(a, 4)
    return struct.unpack('<I', b)[0] if b and len(b) == 4 else 0


def rgn(a):
    b = rd(a, 0x30)
    if not b:
        return 'unreadable'
    return ' '.join('%02X' % x for x in b)


beh = u32(ENT + 0xE8)
o1 = u32(beh + 0x18) if beh else 0
o2 = u32(o1 + 0xC) if o1 else 0
o3 = u32(o2 + 0xC) if o2 else 0
print('ent=0x%08X beh=0x%08X o1=0x%08X o2=0x%08X o3=0x%08X' % (ENT, beh, o1, o2, o3))

for name, o in (('beh', beh), ('o1', o1), ('o2', o2), ('o3', o3)):
    if not (0x10000 <= o < 0x7FFF0000):
        continue
    print('--- %s 0x%08X +0x8D0:' % (name, o), rgn(o + 0x8D0))
s1 = {n: rgn(o + 0x8D0) for n, o in (('beh', beh), ('o1', o1), ('o2', o2)) if 0x10000 <= o < 0x7FFF0000}
time.sleep(1.2)
print('--- after 1.2s:')
for name, o in (('beh', beh), ('o1', o1), ('o2', o2)):
    if not (0x10000 <= o < 0x7FFF0000):
        continue
    now = rgn(o + 0x8D0)
    changed = '  CHANGED' if now != s1.get(name) else ''
    print('--- %s 0x%08X +0x8D0:' % (name, o), now, changed)
    print('    +0x2F50:', rgn(o + 0x2F50) if name == 'o2' else '')
