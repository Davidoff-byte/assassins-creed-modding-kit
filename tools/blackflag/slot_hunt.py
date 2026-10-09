#!/usr/bin/env python3
"""Slot-object hunter: walk component chains of an entity and look for the
object whose +0x2F50..+0x2F68 holds slot-like values (-1 or small ints)."""
import ctypes
import struct
import sys

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


def slots_ok(vals):
    return all(v == 0xFFFFFFFF or v < 0x100000 for v in vals)


checked = set()
base = u32(ENT + 0x60)
cnt = struct.unpack('<H', rd(ENT + 0x66, 2))[0]
print('entity 0x%08X children=%d' % (ENT, cnt))

def probe_sub(sub, note):
    if not (0x10000 <= sub < 0x7FFF0000) or sub in checked:
        return
    checked.add(sub)
    b = rd(sub + 0x2F50, 0x18)
    if not b:
        return
    vals = struct.unpack('<IIIIII', b)
    mark = '  <<< SLOT-LIKE' if slots_ok(vals) else ''
    print('   %s sub=0x%08X slots=%s%s' % (note, sub, ['%08X' % v for v in vals], mark))

for i in range(min(cnt, 40)):
    c = u32(base + i * 4)
    if not (0x10000 <= c < 0x7FFF0000):
        continue
    for offA in (0x18, 0x14, 0x1C, 0x20, 0x10, 0xC):
        o1 = u32(c + offA)
        if not (0x10000 <= o1 < 0x7FFF0000):
            continue
        print('child[%2d] 0x%08X +0x%X -> 0x%08X (vt=0x%08X)' % (i, c, offA, o1, u32(o1)))
        for offB in (0xC, 0x10, 0x8, 0x14, 0x4):
            sub = u32(o1 + offB)
            probe_sub(sub, 'child[%d]+0x%X+0x%X' % (i, offA, offB))
